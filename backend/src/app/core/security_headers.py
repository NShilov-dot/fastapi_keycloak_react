"""Security headers + body-size limiting middleware.

SecurityHeadersMiddleware adds defensive HTTP headers to every response.
LimitBodySizeMiddleware rejects requests whose Content-Length exceeds a
configured threshold before the body is parsed, preventing memory exhaustion.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response."""

    def __init__(self, app: ASGIApp, *, is_prod: bool = False) -> None:
        super().__init__(app)
        self._is_prod = is_prod

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Disable legacy XSS auditor (modern approach: rely on CSP / nosniff instead)
        response.headers["X-XSS-Protection"] = "0"
        if self._is_prod:
            # Only set HSTS when we know TLS is terminated upstream
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


class LimitBodySizeMiddleware:
    """Rejects requests with Content-Length > max_bytes before body is parsed.

    Implemented as a raw ASGI middleware (not BaseHTTPMiddleware) to intercept
    as early as possible and avoid buffering the oversized body.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: dict, receive: object, send: object) -> None:  # type: ignore[override]
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            content_length = headers.get(b"content-length")
            if content_length is not None:
                try:
                    length = int(content_length)
                except ValueError:
                    length = 0
                if length > self._max_bytes:
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": (
                                    f"Request body exceeds the {self._max_bytes // 1024} KB limit"
                                ),
                                "details": [],
                            }
                        },
                    )
                    await response(scope, receive, send)  # type: ignore[arg-type]
                    return
        await self._app(scope, receive, send)  # type: ignore[arg-type]
