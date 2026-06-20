#!/usr/bin/env python3
"""Strip the seeded `demo` user from the Keycloak realm export.

The template ships a `demo` / `demo` user so a fresh clone can smoke-test login
immediately. It must NOT reach any shared/production environment. Run this once,
before deploying, to remove it from `keycloak/realm-export.json`.

    python backend/scripts/remove_demo_user.py [--username demo] [--path <realm-export.json>]

Idempotent: a no-op if the user is already gone.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "keycloak" / "realm-export.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Remove the seeded demo user from the realm export.")
    ap.add_argument("--username", default="demo", help="username to remove (default: demo)")
    ap.add_argument("--path", type=Path, default=_DEFAULT_PATH, help="path to realm-export.json")
    args = ap.parse_args()

    realm = json.loads(args.path.read_text(encoding="utf-8"))
    users = realm.get("users", [])
    kept = [u for u in users if u.get("username") != args.username]
    removed = len(users) - len(kept)

    if removed == 0:
        print(f"No user '{args.username}' found in {args.path} — nothing to do.")
        return 0

    realm["users"] = kept
    # Keycloak exports use 2-space indentation; keep a trailing newline.
    args.path.write_text(json.dumps(realm, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Removed {removed} user(s) named '{args.username}' from {args.path}.")
    print("Re-import the realm (e.g. `make clean && make up`) for it to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
