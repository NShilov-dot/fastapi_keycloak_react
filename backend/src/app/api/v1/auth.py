"""Authentication endpoints — Backend-for-Frontend OIDC bridge.

Flow:
  1. Browser → GET  /v1/auth/login?return_to=/tasks
     Backend generates state + PKCE, stores them in Redis, returns 307 to
     Keycloak's authorize URL.

  2. Browser → Keycloak (user logs in)
     Keycloak → 302 to /v1/auth/callback?code=...&state=...

  3. Backend pops login_state from Redis, exchanges code → tokens, stores
     them in a new session, sets HttpOnly cookie, redirects to return_to.

  4. All future API calls: browser sends the session cookie; the SessionDep
     in deps.py turns it into a Principal.

  5. POST /v1/auth/logout — invalidates server-side session, clears cookie,
     revokes refresh token at Keycloak.

  6. GET /v1/auth/me — returns minimal user info (subject + roles) without
     exposing the JWT to the SPA.
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.config import Settings
from app.core.deps import OIDCDep, PrincipalDep, SessionStoreDep
from app.core.errors import DomainError
from app.core.oidc import OIDCError, generate_pkce_pair, generate_state
from app.core.sessions import LoginState, SessionData

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class _AuthFlowError(DomainError):
    code = "AUTH_FLOW_ERROR"
    http_status = 400


def _callback_url(public_base_url: str) -> str:
    return public_base_url.rstrip("/") + "/v1/auth/callback"


def _is_safe_return_to(return_to: str | None) -> str:
    """Allow only same-origin paths to prevent open-redirect attacks."""
    if not return_to or not return_to.startswith("/") or return_to.startswith("//"):
        return "/"
    return return_to


# ---------------------------------------------------------------------------
# Login — kicks off the OIDC dance
# ---------------------------------------------------------------------------

@router.get("/login", summary="Begin OIDC login flow")
async def login(
    request: Request,
    oidc: OIDCDep,
    sessions: SessionStoreDep,
    return_to: str = "/",
) -> RedirectResponse:
    settings: Settings = request.app.state.settings
    state = generate_state()
    pkce = generate_pkce_pair()
    redirect_uri = _callback_url(str(settings.public_base_url))

    await sessions.save_login_state(
        state,
        LoginState(
            pkce_verifier=pkce.verifier,
            redirect_uri=redirect_uri,
            return_to=_is_safe_return_to(return_to),
        ),
    )

    authorize_url = oidc.build_authorize_url(
        redirect_uri=redirect_uri,
        state=state,
        pkce_challenge=pkce.challenge,
    )
    logger.info("auth.login_redirect", state_prefix=state[:6])
    return RedirectResponse(authorize_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


# ---------------------------------------------------------------------------
# Callback — Keycloak comes back here
# ---------------------------------------------------------------------------

@router.get("/callback", summary="OIDC redirect target")
async def callback(
    request: Request,
    oidc: OIDCDep,
    sessions: SessionStoreDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    settings: Settings = request.app.state.settings
    frontend = str(settings.frontend_base_url).rstrip("/")

    if error:
        logger.warning("auth.callback_idp_error", error=error)
        return RedirectResponse(f"{frontend}/?auth_error={error}", status_code=302)
    if not code or not state:
        raise _AuthFlowError("Missing 'code' or 'state' parameter")

    login_state = await sessions.pop_login_state(state)
    if login_state is None:
        # Unknown state — either replay, CSRF attempt, or browser nav-back.
        logger.warning("auth.callback_unknown_state", state_prefix=state[:6])
        raise _AuthFlowError("Unknown or expired login state")

    try:
        tokens = await oidc.exchange_code(
            code=code,
            redirect_uri=login_state.redirect_uri,
            pkce_verifier=login_state.pkce_verifier,
        )
    except OIDCError as exc:
        logger.warning("auth.code_exchange_failed", cause=exc.cause)
        raise _AuthFlowError("Login failed during token exchange") from exc

    # Verify the access_token locally so we don't trust whatever just came back
    # from Keycloak blindly — local import keeps the module-load cycle short.
    from app.core.security import verify_token
    jwks = request.app.state.jwks
    principal = await verify_token(
        tokens.access_token,
        jwks=jwks,
        audience=settings.keycloak_audience,
        tenant_claim=settings.keycloak_tenant_claim,
        roles_claim=settings.keycloak_roles_claim,
        leeway_seconds=settings.keycloak_leeway_seconds,
    )

    now = int(time.time())
    sid = await sessions.create(
        SessionData(
            subject=principal.subject,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            id_token=tokens.id_token,
            access_expires_at=now + tokens.expires_in,
            created_at=now,
        )
    )

    response = RedirectResponse(f"{frontend}{login_state.return_to}", status_code=302)
    _set_session_cookie(response, sid, settings)
    logger.info("auth.session_created", subject=principal.subject)
    return response


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post("/logout", summary="Terminate the session")
async def logout(request: Request, oidc: OIDCDep, sessions: SessionStoreDep) -> Response:
    settings: Settings = request.app.state.settings
    sid = request.cookies.get(settings.session_cookie_name)

    if sid:
        sess = await sessions.get(sid)
        if sess and sess.refresh_token:
            await oidc.revoke_refresh_token(refresh_token=sess.refresh_token)
        await sessions.delete(sid)

    response = JSONResponse({"status": "ok"})
    _clear_session_cookie(response, settings)
    return response


# ---------------------------------------------------------------------------
# Me — minimal user info for the SPA
# ---------------------------------------------------------------------------

@router.get("/me", summary="Current user info")
async def me(principal: PrincipalDep) -> dict[str, object]:
    return {
        "subject":   principal.subject,
        "tenant_id": str(principal.tenant_id),
        "roles":     sorted(principal.roles),
    }


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

def _set_session_cookie(response: Response, sid: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=sid,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.is_prod,
        # 'lax' is required so the cookie survives the OIDC top-level redirect.
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.is_prod,
        samesite="lax",
    )
