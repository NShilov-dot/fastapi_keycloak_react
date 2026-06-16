"""Framework-agnostic error classes. Safe to import from domain layers.

HTTP wiring lives in `app.core.error_handlers` and only runs in the interface
layer, so the domain never reaches into FastAPI.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    code = "DOMAIN_ERROR"
    http_status = 400

    def __init__(self, message: str, *, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class PermissionDeniedError(DomainError):
    code = "PERMISSION_DENIED"
    http_status = 403


class TenantResolutionError(DomainError):
    code = "TENANT_RESOLUTION_FAILED"
    http_status = 400


class ServiceUnavailableError(DomainError):
    code = "SERVICE_UNAVAILABLE"
    http_status = 503
