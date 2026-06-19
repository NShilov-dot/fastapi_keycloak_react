from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.crypto import TokenCipher

# Placeholder/weak secrets we refuse to run with in production.
_WEAK_SECRETS = frozenset({"", "change-me-in-prod", "changeme", "secret", "admin"})


def _split_csv(value: object) -> object:
    """Parse a comma-separated env string into a list.

    pydantic-settings JSON-decodes complex (list) fields from the environment by
    default, so ``CORS_ORIGINS=http://a,http://b`` would raise. Combined with the
    ``NoDecode`` annotation this validator accepts both a comma-separated string
    and a JSON array, which is what the .env.example / docker-compose actually ship.
    """
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        if value.startswith("["):
            import json

            return json.loads(value)
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    app_debug: bool = False
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: PostgresDsn
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_recycle_seconds: int = 1800
    database_statement_timeout_ms: int = 30_000

    redis_url: RedisDsn
    # Optional dedicated Redis for rate-limit counters so pressure on the session
    # store cannot disable limits (and vice-versa). Falls back to redis_url.
    rate_limit_redis_url: RedisDsn | None = None

    # Internal (backchannel) issuer — used by the backend to reach Keycloak for
    # token exchange, userinfo, refresh-token revoke, and JWKS fetch. In docker this
    # is the compose-network name (http://keycloak:8080/realms/saas).
    keycloak_issuer: AnyHttpUrl
    # Public (frontchannel) issuer — the URL the BROWSER uses for the authorize and
    # end_session redirects, and the `iss` value tokens are stamped with (Keycloak's
    # KC_HOSTNAME). Defaults to keycloak_issuer when unset (single-URL deployments).
    keycloak_public_issuer: AnyHttpUrl | None = None
    keycloak_audience: str
    keycloak_jwks_cache_ttl: int = 3600
    keycloak_tenant_claim: str = "tenant_id"
    keycloak_roles_claim: str = "realm_access.roles"
    keycloak_leeway_seconds: int = 30
    # Accepted `typ` PAYLOAD-claim values for access tokens. Keycloak emits "Bearer"
    # (the JOSE header typ is always "JWT" and can't distinguish token types).
    # Empty list disables the check.
    keycloak_expected_token_types: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["Bearer"]
    )

    # Keycloak Admin API — service-account client with realm-management roles.
    # Leave keycloak_admin_client_secret empty to disable Admin integration.
    keycloak_realm: str = "saas"
    keycloak_admin_client_id: str = "saas-backend-admin"
    keycloak_admin_client_secret: SecretStr = SecretStr("")

    # OIDC client (Authorization Code + PKCE) — backend acts as confidential client
    oidc_client_id: str = "saas-backend"
    oidc_client_secret: SecretStr = SecretStr("change-me-in-prod")
    # Public-facing URL of THIS backend (the URL Keycloak redirects users back to).
    # Must be reachable by the user's browser, not just the Docker network.
    public_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    # Public-facing URL of the frontend (used as the post-logout / post-login landing).
    frontend_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5173")

    # Sessions — opaque token in HttpOnly cookie, payload in Redis
    session_cookie_name: str = "saas_session"
    session_ttl_seconds: int = 36_000  # 10h sliding lifetime (matches Keycloak default)
    session_idle_seconds: int = 1_800  # 30m idle timeout
    # AES-256-GCM keys (base64, 32 bytes each) for encrypting tokens at rest in Redis.
    # First key encrypts; all are tried on decrypt (newest-first) to allow rotation.
    # Optional in local/dev (plaintext fallback); MANDATORY in prod.
    session_encryption_keys: Annotated[list[SecretStr], NoDecode] = Field(default_factory=list)

    # Rate limiting (per authenticated user, fixed-window counters in Redis)
    rate_limit_global_per_minute: int = 120   # all requests
    rate_limit_writes_per_minute: int = 30    # POST / PATCH / DELETE / PUT
    # Aggregate ceiling per tenant (0 disables). Backstop against one tenant with
    # many service-accounts (distinct subjects) bypassing per-subject limits.
    rate_limit_tenant_per_minute: int = 6_000
    # Unauthenticated / pre-auth endpoints (login, callback), keyed by client IP.
    rate_limit_auth_per_minute_per_ip: int = 20

    # Maximum allowed request body size in bytes (default 1 MB)
    max_body_size_bytes: int = 1_048_576

    # Restrict Host header to these values in production (empty = disabled)
    trusted_hosts: Annotated[list[str], NoDecode] = Field(default_factory=list)

    cors_origins: Annotated[list[AnyHttpUrl], NoDecode] = Field(default_factory=list)

    _csv_fields = field_validator(
        "trusted_hosts",
        "cors_origins",
        "session_encryption_keys",
        "keycloak_expected_token_types",
        mode="before",
    )(_split_csv)

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def keycloak_admin_enabled(self) -> bool:
        return bool(self.keycloak_admin_client_secret.get_secret_value())

    @property
    def keycloak_public_issuer_effective(self) -> str:
        """Browser-facing issuer; falls back to the internal one when unset."""
        return str(self.keycloak_public_issuer or self.keycloak_issuer)

    @property
    def cookies_secure(self) -> bool:
        """Set the Secure cookie flag whenever the backend is served over HTTPS.

        Derived from public_base_url's scheme (not app_env) so that any HTTPS
        deployment — including dev/staging — gets Secure cookies, closing the
        MITM session-cookie interception gap on non-prod TLS deployments.
        """
        return str(self.public_base_url).lower().startswith("https")

    @property
    def session_cookie_effective_name(self) -> str:
        """`__Host-` prefix over HTTPS for the browser's strongest cookie guarantee.

        `__Host-` requires Secure + Path=/ + no Domain, all of which we satisfy.
        Over plain HTTP (local dev) the prefix is invalid, so we fall back to the
        bare name.
        """
        if self.cookies_secure:
            return f"__Host-{self.session_cookie_name}"
        return self.session_cookie_name

    @property
    def csrf_allowed_origins(self) -> frozenset[str]:
        """Origins accepted on state-changing requests (Origin/Referer allowlist)."""
        origins = {
            str(self.frontend_base_url).rstrip("/"),
            str(self.public_base_url).rstrip("/"),
        }
        origins.update(str(o).rstrip("/") for o in self.cors_origins)
        return frozenset(origins)

    @property
    def rate_limit_redis_url_effective(self) -> str:
        return str(self.rate_limit_redis_url or self.redis_url)

    def build_token_cipher(self) -> TokenCipher | None:
        """Build the at-rest token cipher, or None if no keys are configured."""
        raw = [k.get_secret_value() for k in self.session_encryption_keys]
        raw = [k for k in raw if k]
        if not raw:
            return None
        return TokenCipher.from_raw_keys(raw)

    def validate_for_production(self) -> None:
        """Raise ValueError if any mandatory production-safety constraint is violated."""
        if not self.is_prod:
            return
        errors: list[str] = []
        if self.app_debug:
            errors.append("APP_DEBUG must be False in production")
        if not self.cors_origins:
            errors.append("CORS_ORIGINS must be set in production")
        if str(self.keycloak_issuer).startswith("http://"):
            errors.append("KEYCLOAK_ISSUER must use HTTPS in production")
        if self.keycloak_public_issuer and str(self.keycloak_public_issuer).startswith("http://"):
            errors.append("KEYCLOAK_PUBLIC_ISSUER must use HTTPS in production")
        if str(self.public_base_url).startswith("http://"):
            errors.append("PUBLIC_BASE_URL must use HTTPS in production")
        if str(self.frontend_base_url).startswith("http://"):
            errors.append("FRONTEND_BASE_URL must use HTTPS in production")
        if self.oidc_client_secret.get_secret_value() in _WEAK_SECRETS:
            errors.append("OIDC_CLIENT_SECRET must be set to a real secret in production")
        if not self.trusted_hosts:
            errors.append("TRUSTED_HOSTS must be set in production (Host-header validation)")
        if not self._redis_is_authenticated(self.redis_url):
            errors.append(
                "REDIS_URL must use a password or TLS (rediss://) in production — "
                "Redis holds live access/refresh tokens"
            )
        if self.rate_limit_redis_url is not None and not self._redis_is_authenticated(
            self.rate_limit_redis_url
        ):
            errors.append("RATE_LIMIT_REDIS_URL must use a password or TLS (rediss://) in production")
        if not self.session_encryption_keys:
            errors.append(
                "SESSION_ENCRYPTION_KEYS must be set in production to encrypt tokens at rest"
            )
        else:
            # Surface bad key material at startup rather than on first request.
            try:
                self.build_token_cipher()
            except ValueError as exc:
                errors.append(f"SESSION_ENCRYPTION_KEYS invalid: {exc}")
        if (
            self.keycloak_admin_enabled
            and self.keycloak_admin_client_secret.get_secret_value() in _WEAK_SECRETS
        ):
            errors.append("KEYCLOAK_ADMIN_CLIENT_SECRET must be a real secret when Admin is enabled")
        if errors:
            raise ValueError("Production configuration errors: " + "; ".join(errors))

    @staticmethod
    def _redis_is_authenticated(url: RedisDsn) -> bool:
        return url.scheme == "rediss" or bool(url.password)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
