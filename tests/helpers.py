"""Shared test helpers. Fake JWTs are built at runtime — never committed as literals."""
from __future__ import annotations

import base64
import json
import sqlite3
import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1] / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import grokbot_usage as usage  # noqa: E402


def b64url(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def make_jwt(sub: str = "example-user|user_01EXAMPLE") -> str:
    return f"{b64url({'alg': 'none', 'typ': 'JWT'})}.{b64url({'sub': sub})}.testsig"


def make_cookie(sub_tail: str = "user_01EXAMPLE", token: str | None = None) -> str:
    jwt = token if token is not None else make_jwt(f"example-user|{sub_tail}")
    return f"{sub_tail}%3A%3A{jwt}"


def write_vscdb(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE ItemTable (key TEXT, value BLOB)")
        con.execute(
            "INSERT INTO ItemTable VALUES (?, ?)",
            ("cursorAuth/accessToken", token),
        )
        con.commit()
    finally:
        con.close()


CURSOR_SUMMARY = {
    "individualUsage": {
        "plan": {
            "totalPercentUsed": 40.0,
            "autoPercentUsed": 44.0,
            "apiPercentUsed": 5.0,
        },
        "onDemand": {"used": 800, "limit": 10000},
    },
    "billingCycleStart": "2026-01-01T00:00:00.000Z",
    "billingCycleEnd": "2026-02-01T00:00:00.000Z",
    "membershipType": "pro",
}

GROKBOT_STATUS = {
    "usagePercent": 55,
    "nextResetTimestampUtc": "2026-01-20T18:00:00.000Z",
    "currentPeriodStart": "2026-01-13T18:00:00.000Z",
    "hasAvailableUsage": True,
    "hasNonZeroIncludedLimit": True,
    "grokPlanLabel": "Grok Bot Plan",
    "onDemandSettings": {"enabled": True},
}
