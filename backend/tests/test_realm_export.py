"""Guard: Keycloak must never become the authorizer of a browser/SPA (public) client.

The confidential BFF client is the only way into the realm; the SPA never talks to
Keycloak for tokens. These checks stop the shipped realm export from regressing into
an SPA-style setup (public client, implicit/password grants, browser CORS).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REALM_FILE = Path(__file__).resolve().parents[1] / "keycloak" / "realm-export.json"
_CLIENTS: dict[str, dict[str, Any]] = {
    c["clientId"]: c for c in json.loads(_REALM_FILE.read_text(encoding="utf-8"))["clients"]
}


def test_every_enabled_client_is_confidential() -> None:
    public = [cid for cid, c in _CLIENTS.items() if c["enabled"] and c["publicClient"] is not False]
    assert public == []


def test_no_client_allows_password_or_implicit_grant() -> None:
    for cid, c in _CLIENTS.items():
        # Explicit False: an omitted flag falls back to Keycloak's own default.
        assert c["directAccessGrantsEnabled"] is False, cid
        assert not c.get("implicitFlowEnabled", False), cid


def test_auto_created_admin_cli_is_overridden_and_disabled() -> None:
    # Keycloak creates admin-cli as a PUBLIC client with password grant ON unless the
    # realm file declares it, so it must be declared here — disabled.
    assert _CLIENTS["admin-cli"]["enabled"] is False


def test_bff_client_is_confidential_code_flow_with_pkce_and_no_browser_cors() -> None:
    bff = _CLIENTS["saas-backend"]
    assert bff["standardFlowEnabled"] is True
    assert bff["serviceAccountsEnabled"] is False
    assert bff["attributes"]["pkce.code.challenge.method"] == "S256"
    assert bff["webOrigins"] == []  # the SPA never calls Keycloak from JS
    assert all("*" not in uri for uri in bff["redirectUris"])
