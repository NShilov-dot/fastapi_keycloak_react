from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import RateLimitError, ServiceUnavailableError
from app.core.keycloak_admin import KeycloakAdminClient
from app.core.rate_limit import RateLimiterDep
from app.core.security import AuthError, JWKSCache, Principal, verify_token
from app.core.tenancy import TenantContext, resolve_tenant, session_for_tenant


def _settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(_settings_dep)]


def _jwks_dep(request: Request) -> JWKSCache:
    jwks: JWKSCache = request.app.state.jwks
    return jwks


JWKSDep = Annotated[JWKSCache, Depends(_jwks_dep)]


async def _principal(
    settings: SettingsDep,
    jwks: JWKSDep,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AuthError("Empty bearer token")
    return await verify_token(
        token,
        jwks=jwks,
        audience=settings.keycloak_audience,
        tenant_claim=settings.keycloak_tenant_claim,
        roles_claim=settings.keycloak_roles_claim,
        leeway_seconds=settings.keycloak_leeway_seconds,
    )


PrincipalDep = Annotated[Principal, Depends(_principal)]


async def _tenant(principal: PrincipalDep) -> TenantContext:
    return await resolve_tenant(tenant_id=principal.tenant_id)


TenantDep = Annotated[TenantContext, Depends(_tenant)]


async def _session(tenant: TenantDep) -> AsyncIterator[AsyncSession]:
    async for session in session_for_tenant(tenant):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session)]


def require_roles(*roles: str):
    """Dependency factory that enforces presence of all `roles` on the principal."""
    required = frozenset(roles)

    async def _checker(principal: PrincipalDep) -> Principal:
        missing = required - principal.roles
        if missing:
            raise AuthError(f"Missing required roles: {sorted(missing)}")
        return principal

    return _checker


# ---------------------------------------------------------------------------
# Keycloak Admin
# ---------------------------------------------------------------------------

def _keycloak_admin_optional(request: Request) -> KeycloakAdminClient | None:
    return request.app.state.keycloak_admin  # type: ignore[no-any-return]


KeycloakAdminOptionalDep = Annotated[KeycloakAdminClient | None, Depends(_keycloak_admin_optional)]


def _keycloak_admin_required(kc: KeycloakAdminOptionalDep) -> KeycloakAdminClient:
    if kc is None:
        raise ServiceUnavailableError("Keycloak Admin integration is not configured")
    return kc


KeycloakAdminDep = Annotated[KeycloakAdminClient, Depends(_keycloak_admin_required)]


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_WRITE_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})


async def check_rate_limit(
    request: Request,
    principal: PrincipalDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
) -> None:
    """Enforce per-user rate limits. Raises RateLimitError (429) on breach."""
    user_id = principal.subject

    if not await limiter.allow(
        f"global:{user_id}",
        limit=settings.rate_limit_global_per_minute,
        window_seconds=60,
    ):
        raise RateLimitError("Too many requests. Please slow down.")

    if request.method in _WRITE_METHODS:
        if not await limiter.allow(
            f"writes:{user_id}",
            limit=settings.rate_limit_writes_per_minute,
            window_seconds=60,
        ):
            raise RateLimitError("Too many write requests. Please slow down.")


RateLimitDep = Annotated[None, Depends(check_rate_limit)]
