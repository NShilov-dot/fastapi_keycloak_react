"""Unit tests for TenantProvisioningService (Keycloak + DB + migrator mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import (
    ConflictError,
    PermissionDeniedError,
    ServiceUnavailableError,
    TenantResolutionError,
)
from app.core.keycloak_admin import KeycloakAdminClient, KeycloakAdminError
from app.modules.tenants.application.services import (
    InvalidSlugError,
    TenantProvisioningService,
)


class _FakeKC:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.group_id = "grp-1"
        self.user_id = "usr-1"
        self.fail_assign_role = False
        self.fail_email = False
        self.create_conflict = False
        self.deleted: list[str] = []
        self.deleted_groups: list[str] = []

    async def create_group(self, name: str, *, attributes: Any = None) -> str:
        self.calls.append(("create_group", name, attributes))
        return self.group_id

    async def delete_group(self, group_id: str) -> None:
        self.deleted_groups.append(group_id)

    async def create_user(self, **kw: Any) -> str:
        self.calls.append(("create_user", kw))
        if self.create_conflict:
            raise KeycloakAdminError(409, "User exists with same email")
        return self.user_id

    async def add_user_to_group(self, user_id: str, group_id: str) -> None:
        self.calls.append(("add_user_to_group", user_id, group_id))

    async def assign_realm_role(self, user_id: str, role: str) -> None:
        self.calls.append(("assign_realm_role", user_id, role))
        if self.fail_assign_role:
            raise KeycloakAdminError(500, "boom")

    async def send_execute_actions_email(self, user_id: str, actions: Any, **kw: Any) -> None:
        self.calls.append(("email", user_id, actions))
        if self.fail_email:
            # Simulate a transport error (httpx.HTTPError-like), NOT a KeycloakAdminError,
            # to exercise the broadened best-effort except.
            raise RuntimeError("connection reset")

    async def delete_user(self, user_id: str) -> None:
        self.deleted.append(user_id)


class _FakeSession:
    def __init__(self, *, row: Any = None, raise_first: Exception | None = None) -> None:
        self.row = row
        self.raise_first = raise_first
        self.committed = 0
        self.rolled_back = 0
        self.executed: list[str] = []

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False

    async def execute(self, _stmt: Any, _params: Any = None) -> Any:
        self.executed.append(str(_stmt))
        if self.raise_first is not None:
            exc, self.raise_first = self.raise_first, None
            raise exc
        return SimpleNamespace(first=lambda: self.row)

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1


def _service(kc: _FakeKC, session: _FakeSession) -> tuple[TenantProvisioningService, list[str]]:
    migrated: list[str] = []

    async def _migrate(slug: str) -> None:
        migrated.append(slug)

    svc = TenantProvisioningService(
        sessionmaker=cast(async_sessionmaker[AsyncSession], lambda: session),
        kc=cast(KeycloakAdminClient, kc),
        migrate_schema=_migrate,
        invite_client_id="saas-backend",
    )
    return svc, migrated


# ---------------------------------------------------------------------------
# onboard_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_onboard_tenant_happy_path() -> None:
    kc, session = _FakeKC(), _FakeSession()
    svc, migrated = _service(kc, session)
    result = await svc.onboard_tenant(slug="Acme", name="ACME Corp", admin_email="a@acme.io")

    assert result.slug == "acme"  # normalized
    assert result.keycloak_group_id == "grp-1"
    assert result.admin_user_id == "usr-1"
    assert migrated == ["acme"]  # schema migrated

    names = [c[0] for c in kc.calls]
    assert names == ["create_group", "create_user", "add_user_to_group", "assign_realm_role", "email"]
    # group carries the tenant_id attribute
    _, gname, attrs = kc.calls[0]
    assert gname == "tenant_acme" and "tenant_id" in attrs
    # admin user gets tenant_id attribute + tenant_admin role
    create_kw = kc.calls[1][1]
    assert create_kw["attributes"]["tenant_id"] == [str(result.tenant_id)]
    assert "UPDATE_PASSWORD" in create_kw["required_actions"]
    assert kc.calls[3] == ("assign_realm_role", "usr-1", "tenant_admin")


@pytest.mark.asyncio
async def test_onboard_rejects_invalid_slug() -> None:
    kc, session = _FakeKC(), _FakeSession()
    svc, _ = _service(kc, session)
    with pytest.raises(InvalidSlugError):
        await svc.onboard_tenant(slug="ACME CORP!", name="x", admin_email="a@b.io")
    assert kc.calls == []  # nothing provisioned


@pytest.mark.asyncio
async def test_onboard_duplicate_slug_raises_conflict() -> None:
    kc = _FakeKC()
    session = _FakeSession(raise_first=IntegrityError("INSERT", {}, Exception("dup")))
    svc, migrated = _service(kc, session)
    with pytest.raises(ConflictError):
        await svc.onboard_tenant(slug="acme", name="ACME", admin_email="a@b.io")
    assert session.rolled_back == 1
    assert kc.calls == [] and migrated == []  # no KC group, no schema


@pytest.mark.asyncio
async def test_onboard_compensates_when_a_later_step_fails() -> None:
    """If schema migration fails after the row is committed, the group and the
    public.tenants row are rolled back so the slug can be re-onboarded."""
    kc = _FakeKC()
    session = _FakeSession()

    async def _failing_migrate(_slug: str) -> None:
        raise RuntimeError("alembic boom")

    svc = TenantProvisioningService(
        sessionmaker=cast(async_sessionmaker[AsyncSession], lambda: session),
        kc=cast(KeycloakAdminClient, kc),
        migrate_schema=_failing_migrate,
        invite_client_id="saas-backend",
    )
    with pytest.raises(RuntimeError):
        await svc.onboard_tenant(slug="acme", name="ACME", admin_email="a@b.io")

    assert kc.group_id in kc.deleted_groups  # KC group compensated
    assert any("DELETE FROM public.tenants" in sql for sql in session.executed)  # row removed


# ---------------------------------------------------------------------------
# invite_member
# ---------------------------------------------------------------------------

_TID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_invite_member_uses_caller_tenant() -> None:
    kc = _FakeKC()
    session = _FakeSession(row=SimpleNamespace(slug="acme", keycloak_group_id="grp-1"))
    svc, _ = _service(kc, session)
    result = await svc.invite_member(tenant_id=_TID, email="bob@acme.io")

    assert result.user_id == "usr-1" and result.tenant_id == _TID
    create_kw = next(c[1] for c in kc.calls if c[0] == "create_user")
    assert create_kw["attributes"]["tenant_id"] == [str(_TID)]  # from caller, not body
    assert ("assign_realm_role", "usr-1", "tenant_user") in kc.calls


@pytest.mark.asyncio
async def test_invite_member_unknown_tenant() -> None:
    kc = _FakeKC()
    session = _FakeSession(row=None)
    svc, _ = _service(kc, session)
    with pytest.raises(TenantResolutionError):
        await svc.invite_member(tenant_id=_TID, email="x@y.io")
    assert kc.calls == []


@pytest.mark.asyncio
async def test_invite_member_no_group_is_unavailable() -> None:
    kc = _FakeKC()
    session = _FakeSession(row=SimpleNamespace(slug="acme", keycloak_group_id=None))
    svc, _ = _service(kc, session)
    with pytest.raises(ServiceUnavailableError):
        await svc.invite_member(tenant_id=_TID, email="x@y.io")


@pytest.mark.asyncio
async def test_member_rolled_back_when_role_assignment_fails() -> None:
    kc = _FakeKC()
    kc.fail_assign_role = True
    session = _FakeSession(row=SimpleNamespace(slug="acme", keycloak_group_id="grp-1"))
    svc, _ = _service(kc, session)
    with pytest.raises(KeycloakAdminError):
        await svc.invite_member(tenant_id=_TID, email="x@y.io")
    assert kc.deleted == ["usr-1"]  # compensated


@pytest.mark.asyncio
async def test_invite_email_failure_is_best_effort() -> None:
    # The email step raises a transport error (RuntimeError, not KeycloakAdminError);
    # the broadened best-effort except must swallow it (no orphan, no failure). [M-2]
    kc = _FakeKC()
    kc.fail_email = True
    session = _FakeSession(row=SimpleNamespace(slug="acme", keycloak_group_id="grp-1"))
    svc, _ = _service(kc, session)
    result = await svc.invite_member(tenant_id=_TID, email="x@y.io")
    assert result.user_id == "usr-1"  # provisioning still succeeds
    assert kc.deleted == []  # NOT rolled back


@pytest.mark.asyncio
async def test_invite_rejects_non_tenant_role() -> None:  # [L-2]
    """A tenant invite cannot grant platform_admin, even bypassing the Pydantic edge."""
    kc = _FakeKC()
    session = _FakeSession(row=SimpleNamespace(slug="acme", keycloak_group_id="grp-1"))
    svc, _ = _service(kc, session)
    with pytest.raises(PermissionDeniedError):
        await svc.invite_member(tenant_id=_TID, email="x@y.io", roles=["platform_admin"])
    assert kc.calls == []  # rejected before any Keycloak call


@pytest.mark.asyncio
async def test_invite_existing_email_is_conflict_not_500() -> None:  # [L-1]
    kc = _FakeKC()
    kc.create_conflict = True  # email already taken realm-wide
    session = _FakeSession(row=SimpleNamespace(slug="acme", keycloak_group_id="grp-1"))
    svc, _ = _service(kc, session)
    with pytest.raises(ConflictError):
        await svc.invite_member(tenant_id=_TID, email="taken@y.io")
    assert kc.deleted == []  # nothing to roll back — user was never created
