from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import RateLimitError, ServiceUnavailableError
from app.core.keycloak_admin import KeycloakAdminClient
from app.core.oidc import OIDCClient, OIDCError
from app.core.rate_limit import RateLimiterDep
from app.core.security import AuthError, JWKSCache, Principal, verify_token
from app.core.sessions import SessionData, SessionStore
from app.core.tenancy import TenantContext, resolve_tenant, session_for_tenant


# ---------------------------------------------------------------------------
# Settings / JWKS / OIDC / SessionStore providers
# ---------------------------------------------------------------------------

def _settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(_settings_dep)]


def _jwks_dep(request: Request) -> JWKSCache:
    jwks: JWKSCache = request.app.state.jwks
    return jwks


JWKSDep = Annotated[JWKSCache, Depends(_jwks_dep)]


def _oidc_dep(request: Request) -> OIDCClient:
    oidc: OIDCClient = request.app.state.oidc
    return oidc


OIDCDep = Annotated[OIDCClient, Depends(_oidc_dep)]


def _session_store_dep(request: Request) -> SessionStore:
    store: SessionStore = request.app.state.session_store
    return store


SessionStoreDep = Annotated[SessionStore, Depends(_session_store_dep)]


# ---------------------------------------------------------------------------
# Principal — derived from server-side session cookie (BFF model)
#
# Order of operations:
#   1. Read session_id from HttpOnly cookie. Missing → 401.
#   2. Look up SessionData in Redis.       Missing → 401 + clear cookie.
#   3. If access_token within 30s of expiry → refresh at Keycloak,
#      persist new tokens. Refresh failure → 401 + clear session.
#   4. Verify access_token signature against cached JWKS, derive Principal.
#   5. Touch session (slide idle TTL forward).
#
# The browser never sees a JWT. Sessions live entirely server-side in Redis.
# ---------------------------------------------------------------------------

_REFRESH_LEEWAY_SECONDS = 30


async def _maybe_refresh(
    sid: str,
    data: SessionData,
    *,
    oidc: OIDCClient,
    store: SessionStore,
) -> SessionData:
    """Refresh access_token if it expires soon; return possibly-updated data."""
    if data.access_expires_at - _REFRESH_LEEWAY_SECONDS > int(time.time()):
        return data
    if data.refresh_token is None:
        # Nothing to refresh with — caller will fall through to verify (which
        # will fail because the token is expired) and surface AuthError.
        return data
    try:
        tokens = await oidc.refresh(refresh_token=data.refresh_token)
    except OIDCError:
        # Refresh failed — wipe the session so we don't keep retrying.
        await store.delete(sid)
        raise AuthError("Session expired") from None

    updated = SessionData(
        subject=data.subject,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token or data.refresh_token,
        id_token=tokens.id_token or data.id_token,
        access_expires_at=int(time.time()) + tokens.expires_in,
        created_at=data.created_at,
    )
    await store.update(sid, updated)
    return updated


async def _principal(
    request: Request,
    settings: SettingsDep,
    jwks: JWKSDep,
    oidc: OIDCDep,
    store: SessionStoreDep,
) -> Principal:
    sid = request.cookies.get(settings.session_cookie_name)
    if not sid:
        raise AuthError("Not authenticated")

    data = await store.get(sid)
    if data is None:
        raise AuthError("Session expired")

    data = await _maybe_refresh(sid, data, oidc=oidc, store=store)

    try:
        principal = await verify_token(
            data.access_token,
            jwks=jwks,
            audience=settings.keycloak_audience,
            tenant_claim=settings.keycloak_tenant_claim,
            roles_claim=settings.keycloak_roles_claim,
            leeway_seconds=settings.keycloak_leeway_seconds,
        )
    except AuthError:
        # Session-backed token failed verification — kill the session.
        await store.delete(sid)
        raise

    # Slide the idle window — every authenticated request keeps the session warm.
    await store.touch(sid)
    return principal


PrincipalDep = Annotated[Principal, Depends(_principal)]


# ---------------------------------------------------------------------------
# Tenant + DB session
# ---------------------------------------------------------------------------

async def _tenant(principal: PrincipalDep) -> TenantContext:
    return await resolve_tenant(tenant_id=principal.tenant_id)


TenantDep = Annotated[TenantContext, Depends(_tenant)]


async def _session(tenant: TenantDep) -> AsyncIterator[AsyncSession]:
    async for session in session_for_tenant(tenant):
        yield session


SessionDep = Annotated[AsyncSession, Depends(_session)]


# ---------------------------------------------------------------------------
# RBAC helper
# ---------------------------------------------------------------------------

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
