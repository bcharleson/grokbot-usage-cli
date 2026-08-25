#!/usr/bin/env python3
"""grokbot-usage — read-only usage meter for Cursor and Grok Bot.

Meters (independent, fail-open):
  cursor   Cursor IDE plan % + on-demand $     (cursor.com web session)
  grokbot  Grok Bot weekly included pool %     (same Cursor session)

The Cursor session covers Grok Bot. There is no third meter.

Auth ladder (first hit wins):
  1. CURSOR_SESSION_COOKIE
  2. ~/.secrets/cursor-session-cookie   (mode 0600; written by `login`)
  3. Cursor IDE state.vscdb (macOS + Linux) → WorkosCursorSessionToken
     = <sub-after-pipe>%3A%3A<jwt>

Tokens and cookies are never printed, logged, or written to the ledger.
Stdlib only.

Usage:
  grokbot-usage
  grokbot-usage --json --write default
  grokbot-usage --json --write PATH
  grokbot-usage --meter grokbot
  grokbot-usage --quiet --threshold 90
  grokbot-usage login
  grokbot-usage logout

Exit codes: 0 ok, 1 threshold breached or every meter failed, 2 usage error.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CURSOR_HOST = "https://cursor.com"
USER_AGENT = "grokbot-usage/1.1 (local read-only meter)"
DEFAULT_THRESHOLD = 90
WEEKLY_BUDGET_ENV = "GROKBOT_USAGE_WEEKLY_BUDGET"
COOKIE_ENV = "CURSOR_SESSION_COOKIE"
SECRET_COOKIE_NAME = "cursor-session-cookie"
LEDGER_DIRNAME = ".grokbot-usage"
LEDGER_FILENAME = "latest.json"
ITEM_ACCESS_TOKEN = "cursorAuth/accessToken"

_REDACT_COOKIE_PREFIX = re.compile(r"WorkosCursorSessionToken=\S+", re.I)
_REDACT_COOKIE_BODY = re.compile(r"%3A%3A\S+")
_REDACT_JWT = re.compile(
    r"\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\b"
)


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------

def secret_cookie_path() -> Path:
    return Path.home() / ".secrets" / SECRET_COOKIE_NAME


def default_ledger_path() -> Path:
    return Path.home() / LEDGER_DIRNAME / LEDGER_FILENAME


def cursor_state_db_candidates() -> list[Path]:
    home = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    return [
        home / "Library/Application Support/Cursor/User/globalStorage/state.vscdb",
        xdg / "Cursor/User/globalStorage/state.vscdb",
    ]


# --------------------------------------------------------------------------
# secrets (never printed)
# --------------------------------------------------------------------------

def safe_error(exc: BaseException) -> str:
    text = str(exc)
    text = _REDACT_COOKIE_PREFIX.sub("WorkosCursorSessionToken=<redacted>", text)
    text = _REDACT_COOKIE_BODY.sub("%3A%3A<redacted>", text)
    text = _REDACT_JWT.sub("<redacted>", text)
    return text[:160]


def write_secret_file(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, content.encode("utf-8"))
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)


def looks_like_jwt(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 3 and all(parts) and " " not in value


def cursor_cookie_from_jwt(token: str) -> str:
    """WorkosCursorSessionToken value: <sub-after-pipe>%3A%3A<jwt>."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        sub = json.loads(base64.urlsafe_b64decode(payload)).get("sub", "")
    except (IndexError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("session token is not a usable JWT") from exc
    if not isinstance(sub, str) or not sub:
        raise RuntimeError("session token JWT has no sub")
    return f"{sub.split('|')[-1]}%3A%3A{token}"


def normalize_session_cookie(raw: str) -> str:
    value = raw.strip().strip('"').strip("'")
    prefix = "workoscursorsessiontoken="
    if value.lower().startswith(prefix):
        value = value[len(prefix):].strip()
    if not value:
        raise RuntimeError("empty session cookie")
    if "%3A%3A" in value:
        return value
    if "::" in value:
        left, right = value.split("::", 1)
        return f"{left}%3A%3A{right}"
    if looks_like_jwt(value):
        return cursor_cookie_from_jwt(value)
    raise RuntimeError("value is not a session cookie or JWT")


def cursor_session_token_from_ide() -> str:
    """Session JWT from Cursor's state DB. Copy-then-query: the DB can be large."""
    db_path = next((p for p in cursor_state_db_candidates() if p.is_file()), None)
    if db_path is None:
        raise RuntimeError("Cursor state.vscdb not found; launch Cursor and sign in")
    fd, tmp = tempfile.mkstemp(suffix=".vscdb")
    os.close(fd)
    try:
        with open(db_path, "rb") as src, open(tmp, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
        row = sqlite3.connect(tmp).execute(
            "SELECT value FROM ItemTable WHERE key=?",
            (ITEM_ACCESS_TOKEN,),
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


def resolve_cursor_cookie() -> str:
    env = os.environ.get(COOKIE_ENV, "").strip()
    if env:
        return normalize_session_cookie(env)
    secret = secret_cookie_path()
    if secret.is_file():
        value = secret.read_text(encoding="utf-8").strip()
        if value:
            return normalize_session_cookie(value)
    return cursor_cookie_from_jwt(cursor_session_token_from_ide())


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def http_json(method: str, url: str, *, cookie: str | None = None,
              body: dict | None = None, timeout: int = 15):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json")
    if cookie:
        req.add_header("Cookie", f"WorkosCursorSessionToken={cookie}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Origin", CURSOR_HOST)
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        host_path = exc.url.split("?")[0] if exc.url else url.split("?")[0]
        raise RuntimeError(f"HTTP {exc.code} from {host_path}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("network error reaching usage endpoint") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("usage endpoint returned non-JSON") from exc


# --------------------------------------------------------------------------
# meters — each returns a dict; raise on hard failure, caller catches
# --------------------------------------------------------------------------

def meter_cursor(cookie: str) -> dict:
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


def meter_grokbot(cookie: str) -> dict:
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


# --------------------------------------------------------------------------
# presentation + ledger
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
    if isinstance(cursor, dict) and "error" not in cursor:
        limit = cursor.get("onDemandLimitUSD")
        lines.append(
            f"  cursor    plan {fmt_pct(cursor.get('planPercentUsed'))} used"
            f" (auto {fmt_pct(cursor.get('autoPercentUsed'))}"
            f" / api {fmt_pct(cursor.get('apiPercentUsed'))})"
            f" · on-demand ${cursor.get('onDemandUsedUSD', 0)}"
            f" of ${limit if limit is not None else '—'}"
            f" · resets {fmt_reset(cursor.get('cycleEnd'))}")
    elif cursor is not None:
        lines.append(f"  cursor    unavailable ({cursor.get('error')})")
    bot = data.get("grokbot")
    if isinstance(bot, dict) and "error" not in bot:
        lines.append(
            f"  grokbot   weekly {fmt_pct(bot.get('weeklyPercentUsed'))} used"
            f" · resets {fmt_reset(bot.get('resetsAt'))}"
            f" ({bot.get('planLabel') or 'Grok Bot'})")
    elif bot is not None:
        lines.append(f"  grokbot   unavailable ({bot.get('error')})")
    return "\n".join(lines)


def resolve_write_path(write_arg: str) -> Path:
    if write_arg == "default":
        return default_ledger_path()
    return Path(write_arg).expanduser()


def write_ledger(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def default_threshold() -> int:
    raw = os.environ.get(WEEKLY_BUDGET_ENV, str(DEFAULT_THRESHOLD))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_THRESHOLD


def grokbot_threshold_breached(data: dict, threshold: int) -> bool:
    bot = data.get("grokbot")
    if not isinstance(bot, dict) or "error" in bot:
        return True
    pct = bot.get("weeklyPercentUsed")
    if not isinstance(pct, (int, float)):
        return True
    return pct >= threshold


def all_meters_failed(data: dict) -> bool:
    selected = [name for name in ("cursor", "grokbot") if name in data]
    if not selected:
        return True
    return all(
        isinstance(data[name], dict) and "error" in data[name]
        for name in selected
    )


# --------------------------------------------------------------------------
# login / logout
# --------------------------------------------------------------------------

def read_login_input() -> str:
    if sys.stdin.isatty():
        return getpass.getpass(
            "Paste WorkosCursorSessionToken (input hidden): "
        )
    return sys.stdin.read()


def cmd_login(from_ide: bool) -> int:
    try:
        if from_ide:
            cookie = cursor_cookie_from_jwt(cursor_session_token_from_ide())
        else:
            raw = read_login_input()
            if raw is None or not str(raw).strip():
                print("login: no cookie on stdin", file=sys.stderr)
                return 2
            cookie = normalize_session_cookie(raw)
        write_secret_file(secret_cookie_path(), cookie)
    except Exception as exc:  # noqa: BLE001 — never surface the secret
        print(f"login failed: {safe_error(exc)}", file=sys.stderr)
        return 2
    path = secret_cookie_path()
    mode = stat.S_IMODE(path.stat().st_mode)
    print(f"Stored session cookie at {path} (mode {mode:04o})")
    return 0


def cmd_logout() -> int:
    path = secret_cookie_path()
    if path.is_file():
        path.unlink()
        print(f"Removed {path}")
    else:
        print("No stored session cookie")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "command", nargs="?", choices=["login", "logout"],
        help="login stores ~/.secrets/cursor-session-cookie; logout deletes it")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--meter", choices=["cursor", "grokbot"], default=None,
        help="one meter only (default: both)")
    parser.add_argument(
        "--threshold", type=int, default=None,
        help="grokbot weekly %% for --quiet breach "
             f"(default ${WEEKLY_BUDGET_ENV} or {DEFAULT_THRESHOLD})")
    parser.add_argument(
        "--quiet", action="store_true",
        help="no stdout; exit 1 when grokbot weekly >= threshold")
    parser.add_argument(
        "--write", metavar="PATH",
        help="write JSON to PATH; use 'default' for ~/.grokbot-usage/latest.json")
    parser.add_argument(
        "--from-ide", action="store_true",
        help="with login: store a cookie from Cursor IDE state.vscdb")
    return parser


def collect_meters(meter: str | None, quiet: bool) -> dict:
    data: dict = {"asOf": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    names = ["cursor", "grokbot"] if meter is None else [meter]
    if quiet and "grokbot" not in names:
        names.append("grokbot")
    try:
        cookie = resolve_cursor_cookie()
    except Exception as exc:  # noqa: BLE001 — fail-open per meter
        err = {"error": safe_error(exc)}
        for name in names:
            data[name] = dict(err)
        return data
    runners = {"cursor": meter_cursor, "grokbot": meter_grokbot}
    for name in names:
        try:
            data[name] = runners[name](cookie)
        except Exception as exc:  # noqa: BLE001 — fail-open per meter
            data[name] = {"error": safe_error(exc)}
    return data


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.from_ide and args.command != "login":
        parser.error("--from-ide is only valid with login")
    if args.command == "login":
        return cmd_login(from_ide=args.from_ide)
    if args.command == "logout":
        return cmd_logout()

    threshold = default_threshold() if args.threshold is None else args.threshold

    data = collect_meters(args.meter, args.quiet)

    if args.write:
        write_ledger(resolve_write_path(args.write), data)

    if args.quiet:
        if grokbot_threshold_breached(data, threshold):
            bot = data.get("grokbot") if isinstance(data.get("grokbot"), dict) else {}
            pct = bot.get("weeklyPercentUsed") if bot else None
            if isinstance(pct, (int, float)):
                print(
                    f"grokbot weekly pool at {pct:.0f}% (>= {threshold}%)",
                    file=sys.stderr)
            else:
                print("grokbot weekly pool unavailable", file=sys.stderr)
            return 1
        return 0

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(render_human(data))
    return 1 if all_meters_failed(data) else 0


if __name__ == "__main__":
    sys.exit(main())
