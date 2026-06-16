from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import __version__
from app.api.v1 import router as v1_router
from app.config import Settings, get_settings
from app.core.db import dispose_engine, get_engine
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.keycloak_admin import KeycloakAdminClient
from app.core.middleware import RequestContextMiddleware
from app.core.security import JWKSCache

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    app.state.jwks = JWKSCache(
        issuer=str(settings.keycloak_issuer),
        ttl_seconds=settings.keycloak_jwks_cache_ttl,
    )
    if settings.keycloak_admin_enabled:
        app.state.keycloak_admin: KeycloakAdminClient | None = KeycloakAdminClient(
            issuer=str(settings.keycloak_issuer),
            realm=settings.keycloak_realm,
            client_id=settings.keycloak_admin_client_id,
            client_secret=settings.keycloak_admin_client_secret,
        )
        logger.info("keycloak_admin.enabled", realm=settings.keycloak_realm)
    else:
        app.state.keycloak_admin = None
        logger.info("keycloak_admin.disabled")
    get_engine(settings)
    logger.info("app.started", env=settings.app_env, version=__version__)
    try:
        yield
    finally:
        await app.state.jwks.aclose()
        if app.state.keycloak_admin is not None:
            await app.state.keycloak_admin.aclose()
        await dispose_engine()
        logger.info("app.stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="SaaS Backend",
        version=__version__,
        debug=settings.app_debug,
        lifespan=lifespan,
        openapi_url="/openapi.json" if not settings.is_prod else None,
        docs_url="/docs" if not settings.is_prod else None,
        redoc_url=None,
    )
    app.state.settings = settings

    app.add_middleware(RequestContextMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(o).rstrip("/") for o in settings.cors_origins],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["authorization", "content-type", "x-request-id"],
        )

    register_exception_handlers(app)
    app.include_router(v1_router)

    return app


app = create_app()
