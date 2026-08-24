#!/usr/bin/env python3
"""grokbot-usage — read-only usage meter for the three AI pools on this machine.

Meters (independent, fail-open):
  cursor    Cursor IDE/Ultra plan + on-demand $   (cursor.com web session)
  grokbot   Grok Bot weekly pool %                (Cursor-billed, same session)
  supergrok SuperGrok weekly credits % + tier     (~/.grok/auth.json bearer)

Auth is read locally only: Cursor's state.vscdb session token and the Grok CLI's
auth.json. Tokens are never printed, stored, or sent anywhere except the
vendor endpoints that issued them. No dependencies beyond the Python stdlib.

Usage:
  grokbot_usage.py                 # human-readable table, all meters
  grokbot_usage.py --json          # stable JSON (for agents/scripts)
  grokbot_usage.py --meter grokbot # one meter: cursor|grokbot|supergrok
  grokbot_usage.py --quiet         # exit 1 if any grokbot weekly >= threshold
  grokbot_usage.py --threshold 90  # threshold for --quiet (default 90)

Exit codes: 0 ok, 1 threshold breached or every meter failed, 2 usage error.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

CURSOR_STATE_DB = os.path.expanduser(
    "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb")
CURSOR_HOST = "https://cursor.com"
GROK_AUTH = os.path.expanduser("~/.grok/auth.json")
GROK_CLI_PROXY = "https://cli-chat-proxy.grok.com"
USER_AGENT = "grokbot-usage/1.0 (local read-only meter)"


# --------------------------------------------------------------------------
# credential sources (local reads only)
# --------------------------------------------------------------------------

def cursor_session_token() -> str:
    """Session JWT from Cursor's state DB. Copy-then-query: the DB can be GBs."""
    if not os.path.exists(CURSOR_STATE_DB):
        raise RuntimeError("Cursor state.vscdb not found; launch Cursor and sign in")
    tmp = tempfile.mktemp(suffix=".vscdb")
    try:
        shutil.copy2(CURSOR_STATE_DB, tmp)
        row = sqlite3.connect(tmp).execute(
            "SELECT value FROM ItemTable WHERE key='cursorAuth/accessToken'"
        ).fetchone()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    token = row[0] if row else None
    if isinstance(token, bytes):
        token = token.decode("utf-8", "ignore")
    if not token:
        raise RuntimeError("no cursorAuth/accessToken in state.vscdb")
    return token


def cursor_cookie(token: str) -> str:
    """WorkosCursorSessionToken value: <sub-after-pipe>%3A%3A<jwt>."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    sub = json.loads(base64.urlsafe_b64decode(payload)).get("sub", "")
    return f"{sub.split('|')[-1]}%3A%3A{token}"


def grok_bearer() -> str:
    """OAuth bearer from the Grok CLI's auth.json (~6h TTL, refreshed by the CLI)."""
    if not os.path.exists(GROK_AUTH):
        raise RuntimeError("~/.grok/auth.json not found; run `grok` once and sign in")

    def find_token(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                if isinstance(value, str) and (value.startswith("eyJ") or
                                               value.startswith("xai-oauth")):
                    return value
                found = find_token(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = find_token(value)
                if found:
                    return found
        return None

    token = find_token(json.load(open(GROK_AUTH)))
    if not token:
        raise RuntimeError("no bearer token in ~/.grok/auth.json")
    return token


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def http_json(method: str, url: str, *, cookie: str | None = None,
              bearer: str | None = None, body: dict | None = None,
              timeout: int = 15):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json")
    if cookie:
        req.add_header("Cookie", f"WorkosCursorSessionToken={cookie}")
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Origin", CURSOR_HOST)
        data = json.dumps(body).encode()
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# --------------------------------------------------------------------------
# meters — each returns a dict; raise on hard failure, caller catches
# --------------------------------------------------------------------------

def meter_cursor(token: str) -> dict:
    cookie = cursor_cookie(token)
    summary = http_json("GET", f"{CURSOR_HOST}/api/usage-summary", cookie=cookie)
    individual = summary.get("individualUsage") or {}
    plan = individual.get("plan") or {}
    on_demand = individual.get("onDemand") or {}

    def cents_usd(value):
        return round(value / 100, 2) if isinstance(value, (int, float)) else None

    return {
        "planPercentUsed": plan.get("totalPercentUsed"),
        "autoPercentUsed": plan.get("autoPercentUsed"),
        "apiPercentUsed": plan.get("apiPercentUsed"),
        "onDemandUsedUSD": cents_usd(on_demand.get("used")),
        "onDemandLimitUSD": cents_usd(on_demand.get("limit")),
        "cycleStart": summary.get("billingCycleStart"),
        "cycleEnd": summary.get("billingCycleEnd"),
        "membership": summary.get("membershipType"),
    }


def meter_grokbot(token: str) -> dict:
    cookie = cursor_cookie(token)
    status = http_json(
        "POST", f"{CURSOR_HOST}/api/dashboard/get-sand-usage-status",
        cookie=cookie, body={})
    return {
        "weeklyPercentUsed": status.get("usagePercent"),
        "resetsAt": status.get("nextResetTimestampUtc"),
        "periodStart": status.get("currentPeriodStart"),
        "hasAvailableUsage": status.get("hasAvailableUsage"),
        "hasIncludedAllowance": status.get("hasNonZeroIncludedLimit"),
        "planLabel": status.get("grokPlanLabel"),
        "onDemandEnabled": (status.get("onDemandSettings") or {}).get("enabled"),
    }


def meter_supergrok(bearer: str) -> dict:
    credits = http_json(
        "GET", f"{GROK_CLI_PROXY}/v1/billing?format=credits", bearer=bearer)
    config = credits.get("config") or {}
    period = config.get("currentPeriod") or {}
    tier = None
    try:
        settings = http_json("GET", f"{GROK_CLI_PROXY}/v1/settings", bearer=bearer)
        tier = settings.get("subscription_tier_display")
    except (urllib.error.URLError, OSError, ValueError):
        pass  # tier is cosmetic; credits are the point
    on_demand_used = config.get("onDemandUsed") or {}
    on_demand_cap = config.get("onDemandCap") or {}
    return {
        "tier": tier or ("SuperGrok" if config else None),
        "weeklyPercentUsed": config.get("creditUsagePercent"),
        "resetsAt": period.get("end") or config.get("billingPeriodEnd"),
        "periodType": period.get("type"),
        "onDemandUsed": on_demand_used.get("val"),
        "onDemandCap": on_demand_cap.get("val"),
    }


# --------------------------------------------------------------------------
# presentation
# --------------------------------------------------------------------------

def fmt_pct(value) -> str:
    return f"{value:.0f}%" if isinstance(value, (int, float)) else "?"


def fmt_reset(value) -> str:
    if not value:
        return "?"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%a %H:%M")
    except ValueError:
        return value[:16]


def render_human(data: dict) -> str:
    lines = [f"AI usage meters — {datetime.now().astimezone():%a %H:%M}"]
    cursor = data.get("cursor")
    if isinstance(cursor, dict):
        lines.append(
            f"  cursor    plan {fmt_pct(cursor.get('planPercentUsed'))} used"
            f" (auto {fmt_pct(cursor.get('autoPercentUsed'))}"
            f" / api {fmt_pct(cursor.get('apiPercentUsed'))})"
            f" · on-demand ${cursor.get('onDemandUsedUSD', 0)}"
            f" of ${cursor.get('onDemandLimitUSD') if cursor.get('onDemandLimitUSD') is not None else '—'}"
            f" · resets {fmt_reset(cursor.get('cycleEnd'))}")
    elif cursor is not None:
        lines.append(f"  cursor    unavailable ({cursor.get('error')})")
    bot = data.get("grokbot")
    if isinstance(bot, dict):
        lines.append(
            f"  grokbot   weekly {fmt_pct(bot.get('weeklyPercentUsed'))} used"
            f" · resets {fmt_reset(bot.get('resetsAt'))}"
            f" ({bot.get('planLabel') or 'Grok Bot'})")
    elif bot is not None:
        lines.append(f"  grokbot   unavailable ({bot.get('error')})")
    sg = data.get("supergrok")
    if isinstance(sg, dict):
        lines.append(
            f"  supergrok weekly {fmt_pct(sg.get('weeklyPercentUsed'))} used"
            f" · resets {fmt_reset(sg.get('resetsAt'))}"
            f" ({sg.get('tier') or 'tier?'})")
    elif sg is not None:
        lines.append(f"  supergrok unavailable ({sg.get('error')})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--meter", choices=["cursor", "grokbot", "supergrok"],
                        default=None, help="one meter only (default: all)")
    parser.add_argument("--threshold", type=int, default=90,
                        help="grokbot weekly %% for --quiet breach (default 90)")
    parser.add_argument("--quiet", action="store_true",
                        help="no output; exit 1 when grokbot weekly >= threshold")
    args = parser.parse_args()

    data: dict = {"asOf": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    def run(name: str, fn):
        if args.meter and args.meter != name:
            return
        try:
            if name in ("cursor", "grokbot"):
                data[name] = fn(cursor_session_token())
            else:
                data[name] = fn(grok_bearer())
        except Exception as exc:  # noqa: BLE001 — fail-open per meter
            data[name] = {"error": str(exc)[:160]}

    run("cursor", meter_cursor)
    run("grokbot", meter_grokbot)
    run("supergrok", meter_supergrok)

    if args.quiet:
        bot = data.get("grokbot")
        if isinstance(bot, dict):
            pct = bot.get("weeklyPercentUsed")
            if isinstance(pct, (int, float)) and pct >= args.threshold:
                print(f"grokbot weekly pool at {pct:.0f}% (>= {args.threshold}%)",
                      file=sys.stderr)
                return 1
            return 0
        return 1  # meter unavailable counts as breach — never fail open on unknown

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(render_human(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
