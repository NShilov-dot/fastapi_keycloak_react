from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    keycloak_issuer: AnyHttpUrl
    keycloak_audience: str
    keycloak_jwks_cache_ttl: int = 3600
    keycloak_tenant_claim: str = "tenant_id"
    keycloak_roles_claim: str = "realm_access.roles"
    keycloak_leeway_seconds: int = 30

    # Keycloak Admin API — service-account client with realm-management roles.
    # Leave keycloak_admin_client_secret empty to disable Admin integration.
    keycloak_realm: str = "saas"
    keycloak_admin_client_id: str = "saas-backend-admin"
    keycloak_admin_client_secret: SecretStr = SecretStr("")

    # Rate limiting (per authenticated user, fixed-window counters in Redis)
    rate_limit_global_per_minute: int = 120   # all requests
    rate_limit_writes_per_minute: int = 30    # POST / PATCH / DELETE / PUT

    # Maximum allowed request body size in bytes (default 1 MB)
    max_body_size_bytes: int = 1_048_576

    # Restrict Host header to these values in production (empty = disabled)
    trusted_hosts: list[str] = Field(default_factory=list)

    cors_origins: list[AnyHttpUrl] = Field(default_factory=list)

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def keycloak_admin_enabled(self) -> bool:
        return bool(self.keycloak_admin_client_secret.get_secret_value())

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
        if errors:
            raise ValueError("Production configuration errors: " + "; ".join(errors))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
