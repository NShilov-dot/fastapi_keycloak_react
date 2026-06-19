"""Tenant + member provisioning.

onboard_tenant  — register a new organization (tenant): public.tenants row →
                  Keycloak group (carrying tenant_id) → tenant Postgres schema →
                  first admin user (tenant_admin).
invite_member   — add an employee to an EXISTING tenant. The tenant_id is taken
                  from the caller's principal at the interface layer, never from
                  client input, so a tenant_admin can only add to their own tenant.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import (
    ConflictError,
    DomainError,
    ServiceUnavailableError,
    TenantResolutionError,
)
from app.core.keycloak_admin import KeycloakAdminClient, KeycloakAdminError, TenantGroupSpec

logger = structlog.get_logger(__name__)

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
# Required actions stamped on every new member so they must set a password (and
# verify email) on first login — independent of whether the invite email sends.
_MEMBER_REQUIRED_ACTIONS = ["UPDATE_PASSWORD", "VERIFY_EMAIL"]

SchemaMigrator = Callable[[str], Awaitable[None]]


class InvalidSlugError(DomainError):
    code = "INVALID_SLUG"
    http_status = 400


@dataclass(slots=True)
class TenantOnboarded:
    tenant_id: UUID
    slug: str
    keycloak_group_id: str
    admin_user_id: str


@dataclass(slots=True)
class MemberInvited:
    user_id: str
    tenant_id: UUID
    email: str


class TenantProvisioningService:
    def __init__(
        self,
        *,
        sessionmaker: async_sessionmaker[AsyncSession],
        kc: KeycloakAdminClient,
        migrate_schema: SchemaMigrator,
        invite_client_id: str | None = None,
    ) -> None:
        self._sm = sessionmaker
        self._kc = kc
        self._migrate_schema = migrate_schema
        self._invite_client_id = invite_client_id

    # ------------------------------------------------------------------
    # Organization onboarding
    # ------------------------------------------------------------------

    async def onboard_tenant(
        self, *, slug: str, name: str, admin_email: str
    ) -> TenantOnboarded:
        slug = slug.strip().lower()
        if not _SLUG_RE.fullmatch(slug):
            raise InvalidSlugError(f"slug must match {_SLUG_RE.pattern}")

        tenant_id = uuid4()
        # 1. Registry row in public.tenants (id generated app-side so we can build
        #    the Keycloak group attribute before any further side effects).
        async with self._sm() as session:
            try:
                await session.execute(
                    text(
                        "INSERT INTO public.tenants (id, slug, name) "
                        "VALUES (:id, :slug, :name)"
                    ),
                    {"id": tenant_id, "slug": slug, "name": name},
                )
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ConflictError(f"Tenant slug '{slug}' already exists") from exc

        # Steps 2-4 happen after the row is committed; if any fails we compensate
        # (delete the group + the registry row) so a stuck half-provisioned tenant
        # doesn't block re-onboarding the same slug.
        group_id: str | None = None
        try:
            # 2. Keycloak group carrying the tenant_id attribute.
            spec = TenantGroupSpec(tenant_slug=slug, tenant_id=str(tenant_id))
            group_id = await self._kc.create_group(spec.group_name, attributes=spec.attributes)
            async with self._sm() as session:
                await session.execute(
                    text("UPDATE public.tenants SET keycloak_group_id = :gid WHERE id = :id"),
                    {"gid": group_id, "id": tenant_id},
                )
                await session.commit()

            # 3. Tenant Postgres schema (tasks tables, etc.). Idempotent
            #    (CREATE SCHEMA IF NOT EXISTS + versioned alembic), so it's safe to
            #    re-run on a later re-onboard.
            await self._migrate_schema(slug)

            # 4. First admin user.
            admin_user_id = await self._provision_member(
                tenant_id=tenant_id, group_id=group_id, email=admin_email, roles=["tenant_admin"]
            )
        except Exception:
            await self._compensate_onboard(tenant_id=tenant_id, group_id=group_id, slug=slug)
            raise

        logger.info(
            "tenant.onboarded", tenant_id=str(tenant_id), slug=slug, admin_user_id=admin_user_id
        )
        return TenantOnboarded(
            tenant_id=tenant_id, slug=slug, keycloak_group_id=group_id, admin_user_id=admin_user_id
        )

    async def _compensate_onboard(
        self, *, tenant_id: UUID, group_id: str | None, slug: str
    ) -> None:
        """Best-effort rollback of a partially-provisioned tenant.

        Removes the Keycloak group and the public.tenants row. The tenant schema
        is left as-is — it's idempotent and reused on a successful re-onboard.
        """
        logger.warning("tenant.onboard_compensating", tenant_id=str(tenant_id), slug=slug)
        if group_id is not None:
            try:
                await self._kc.delete_group(group_id)
            except KeycloakAdminError:
                logger.warning("tenant.compensate_group_failed", group_id=group_id)
        try:
            async with self._sm() as session:
                await session.execute(
                    text("DELETE FROM public.tenants WHERE id = :id"), {"id": tenant_id}
                )
                await session.commit()
        except Exception:
            # Compensation is best-effort; it must not mask the original error.
            logger.warning("tenant.compensate_row_failed", tenant_id=str(tenant_id))

    # ------------------------------------------------------------------
    # Member (employee) onboarding
    # ------------------------------------------------------------------

    async def invite_member(
        self, *, tenant_id: UUID, email: str, roles: Sequence[str] = ("tenant_user",)
    ) -> MemberInvited:
        async with self._sm() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT slug, keycloak_group_id FROM public.tenants "
                        "WHERE id = :id AND status = 'active'"
                    ),
                    {"id": tenant_id},
                )
            ).first()
        if row is None:
            raise TenantResolutionError(f"Tenant {tenant_id} not found or inactive")
        if row.keycloak_group_id is None:
            raise ServiceUnavailableError("Tenant has no Keycloak group; re-provision required")

        user_id = await self._provision_member(
            tenant_id=tenant_id,
            group_id=row.keycloak_group_id,
            email=email,
            roles=list(roles),
        )
        return MemberInvited(user_id=user_id, tenant_id=tenant_id, email=email)

    # ------------------------------------------------------------------
    # Shared
    # ------------------------------------------------------------------

    async def _provision_member(
        self, *, tenant_id: UUID, group_id: str, email: str, roles: Sequence[str]
    ) -> str:
        user_id = await self._kc.create_user(
            username=email,
            email=email,
            attributes={"tenant_id": [str(tenant_id)]},
            required_actions=list(_MEMBER_REQUIRED_ACTIONS),
            enabled=True,
            email_verified=False,
        )
        try:
            await self._kc.add_user_to_group(user_id, group_id)
            for role in roles:
                await self._kc.assign_realm_role(user_id, role)
        except Exception:
            # Don't leave a half-configured user behind.
            await self._safe_delete_user(user_id)
            raise

        # The required actions are already on the user; the email is just delivery,
        # so a missing SMTP config (common in local dev) must not fail provisioning.
        try:
            await self._kc.send_execute_actions_email(
                user_id, list(_MEMBER_REQUIRED_ACTIONS), client_id=self._invite_client_id
            )
        except KeycloakAdminError as exc:
            logger.warning(
                "tenant.invite_email_failed", user_id=user_id, status=exc.status_code
            )
        return user_id

    async def _safe_delete_user(self, user_id: str) -> None:
        try:
            await self._kc.delete_user(user_id)
        except KeycloakAdminError:
            logger.warning("tenant.member_cleanup_failed", user_id=user_id)
