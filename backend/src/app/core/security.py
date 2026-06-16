from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
import structlog
from jose import jwt
from jose.exceptions import JWTError

from app.core.errors import DomainError

logger = structlog.get_logger(__name__)


class AuthError(DomainError):
    code = "AUTH_FAILED"
    http_status = 401


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    tenant_id: UUID
    roles: frozenset[str]
    raw_claims: dict[str, Any] = field(hash=False, compare=False, default_factory=dict)


class JWKSCache:
    """Fetch JWKS from Keycloak and cache it for `ttl_seconds` (per process)."""

    def __init__(self, *, issuer: str, ttl_seconds: int = 3600) -> None:
        self._issuer = issuer.rstrip("/")
        self._ttl = ttl_seconds
        self._jwks: dict[str, Any] | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=5.0)

    @property
    def issuer(self) -> str:
        return self._issuer

    async def get(self, *, force_refresh: bool = False) -> dict[str, Any]:
        if (
            not force_refresh
            and self._jwks is not None
            and time.monotonic() < self._expires_at
        ):
            return self._jwks
        async with self._lock:
            if (
                not force_refresh
                and self._jwks is not None
                and time.monotonic() < self._expires_at
            ):
                return self._jwks
            url = f"{self._issuer}/protocol/openid-connect/certs"
            response = await self._client.get(url)
            response.raise_for_status()
            self._jwks = response.json()
            self._expires_at = time.monotonic() + self._ttl
            logger.info("jwks.refreshed", issuer=self._issuer, key_count=len(self._jwks["keys"]))
            return self._jwks

    async def aclose(self) -> None:
        await self._client.aclose()


def _find_key(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
    return next((k for k in jwks["keys"] if k.get("kid") == kid), None)


def _get_path(claims: dict[str, Any], path: str) -> Any:
    cursor: Any = claims
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


async def verify_token(
    token: str,
    *,
    jwks: JWKSCache,
    audience: str,
    tenant_claim: str,
    roles_claim: str,
    leeway_seconds: int,
) -> Principal:
    """Verify a Keycloak access token and produce a Principal.

    Refreshes JWKS once on `kid` miss to handle realm key rotation without restart.
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthError("Malformed bearer token") from exc

    kid = unverified_header.get("kid")
    if kid is None:
        raise AuthError("Token header missing kid")

    keys = await jwks.get()
    key = _find_key(keys, kid)
    if key is None:
        keys = await jwks.get(force_refresh=True)
        key = _find_key(keys, kid)
    if key is None:
        raise AuthError("Signing key not found in JWKS")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "RS256")],
            audience=audience,
            issuer=jwks.issuer,
            options={"verify_at_hash": False},
            leeway=leeway_seconds,
        )
    except JWTError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str):
        raise AuthError("Token missing 'sub'")

    tenant_raw = _get_path(claims, tenant_claim)
    if not isinstance(tenant_raw, str):
        raise AuthError(f"Token missing tenant claim '{tenant_claim}'")
    try:
        tenant_id = UUID(tenant_raw)
    except ValueError as exc:
        raise AuthError(f"Tenant claim '{tenant_claim}' is not a UUID") from exc

    roles_raw = _get_path(claims, roles_claim) or []
    roles = frozenset(r for r in roles_raw if isinstance(r, str))

    return Principal(subject=subject, tenant_id=tenant_id, roles=roles, raw_claims=claims)
