from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn
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
    keycloak_admin_client_secret: str = ""

    cors_origins: list[AnyHttpUrl] = Field(default_factory=list)

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def keycloak_admin_enabled(self) -> bool:
        return bool(self.keycloak_admin_client_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
