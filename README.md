# grokbot-usage-cli

Read-only CLI (`grokbot-usage`) that reports AI usage meters from local
credentials — and lets [Grok Bot](https://cursor.com/help/grok-bot/plans)
agents be **self-aware of their own consumption** before they burn through it.

**Cursor login covers `cursor` + `grokbot`.** SuperGrok is a separate
grok.com / x.ai login even when SuperGrok Heavy is linked to Cursor.

```text
# EXAMPLE output — not live data
$ grokbot-usage
AI usage meters — Mon 12:00
  cursor    plan 40% used (auto 44% / api 5%) · on-demand $8.0 of $100.0 · resets Fri 17:00
  grokbot   weekly 55% used · resets Tue 11:00 (Grok Bot Plan)
  supergrok weekly 22% used · resets Fri 04:00
```

No official APIs exist for these meters. This tool reads the same endpoints the
vendor dashboards use, authenticated with a session already on your machine.
Nothing is invented: if an API does not return a number, the field is `null`.

## The three pools

| Meter | What burns it | Auth (local read) |
|---|---|---|
| `cursor` | Cursor IDE plan (Agent, Composer, Tab) + on-demand dollars | Cursor session (see Auth) |
| `grokbot` | Grok Bot weekly included pool (agents, routines, computer use) | Same Cursor session |
| `supergrok` | SuperGrok weekly credits (Chat, Imagine, Build) — optional | Grok CLI `~/.grok/auth.json` |

Missing SuperGrok auth is `{"error": "..."}`, never `0%`.

## Requirements

- macOS or Linux
- Python 3.10+ (stdlib only — zero dependencies)
- A Cursor session: environment variable, `login`, or a signed-in Cursor IDE
- Optional: Grok CLI signed in (`grok login` or `grok login --device-auth`) for SuperGrok

## Install

```bash
git clone https://github.com/bcharleson/grokbot-usage-cli.git
cd grokbot-usage-cli
./install.sh
```

`install.sh` copies the CLI to `~/.local/bin/grokbot-usage` and the
`fleet-usage` agent skill to `~/.grok/skills/`. Both steps are plain file
copies — review the script first; it does nothing else.

Or run straight from a checkout with no install:

```bash
python3 cli/grokbot_usage.py
```

## Auth

First match wins. Tokens and cookies are never printed, logged, or committed.

1. `CURSOR_SESSION_COOKIE` — cookie value, `user%3A%3A<jwt>`, or a JWT
2. `~/.secrets/cursor-session-cookie` (mode `0600`) — written by `login`
3. Cursor IDE `state.vscdb` (macOS + Linux) — builds
   `WorkosCursorSessionToken=<sub-after-pipe>%3A%3A<jwt>`

```bash
# paste a cookie (input hidden on a TTY; or pipe stdin)
grokbot-usage login

# snapshot from a signed-in Cursor IDE
grokbot-usage login --from-ide

grokbot-usage logout
```

The Cursor cookie is never sent to grok.com. SuperGrok is a different login.

## SuperGrok (optional)

Cursor login does **not** unlock SuperGrok, even if SuperGrok Heavy is linked
to the Cursor account. Install the Grok CLI and sign in on grok.com / x.ai:

```bash
curl -fsSL https://x.ai/cli/install.sh | bash

# browser
grok login

# headless (proven internally): open the printed accounts.x.ai URL, confirm the code
grok login --device-auth
```

The session lands in `~/.grok/auth.json` (mode `0600`). Never commit it.
`grok logout` clears it. This CLI only reads that file locally and never
prints the bearer.

## Usage

```bash
grokbot-usage                        # human-readable table, all meters
grokbot-usage --json                 # stable JSON for scripts and agents
grokbot-usage --json --write default # also write ~/.grokbot-usage/latest.json
grokbot-usage --json --write PATH    # write JSON to PATH
grokbot-usage --meter grokbot        # one of: cursor | grokbot | supergrok
grokbot-usage --quiet                # exit 1 when grokbot weekly >= 90%
grokbot-usage --quiet --threshold 95 # custom threshold
```

`--quiet` default threshold is `GROKBOT_USAGE_WEEKLY_BUDGET` if set, else `90`.

Exit codes: `0` ok · `1` threshold breached, grokbot unknown, or every meter
failed · `2` usage error. Unknown is a breach — never fail-open on a missing %.

### EXAMPLE JSON — not live data

```json
{
  "asOf": "2026-01-15T16:00:00+00:00",
  "cursor": {
    "planPercentUsed": 40.0,
    "autoPercentUsed": 44.0,
    "apiPercentUsed": 5.0,
    "onDemandUsedUSD": 8.0,
    "onDemandLimitUSD": 100.0,
    "cycleStart": "2026-01-01T00:00:00.000Z",
    "cycleEnd": "2026-02-01T00:00:00.000Z",
    "membership": "pro"
  },
  "grokbot": {
    "weeklyPercentUsed": 55,
    "resetsAt": "2026-01-20T18:00:00.000Z",
    "planLabel": "Grok Bot Plan",
    "onDemandEnabled": true
  },
  "supergrok": {
    "weeklyPercentUsed": 22.0,
    "resetsAt": "2026-01-16T12:00:00.000Z"
  }
}
```

A meter that cannot be read reports `{"error": "..."}` instead of fake numbers.

## Agent integration

The bundled `fleet-usage` skill teaches agents to:

- read `~/.grokbot-usage/latest.json` when `asOf` is under 6 hours old
- shell the CLI only when that ledger is stale or missing
- refresh via weekday OS cron at 08:00 / 12:00 / 18:00 (`--json --write default`)
- optionally do **one** weekday Grok Bot file-read (quiet unless over budget)
- treat weekly % like money: <70 healthy, 70–89 elevated, >=90 flag, 100 exhausted
- flag a daily spike (+20 weekly points vs the last ledger) and Cursor on-demand cap
- honor `GROKBOT_USAGE_WEEKLY_BUDGET` (default 90) and `GROKBOT_USAGE_DAILY_SPIKE` (default 20)
- never invent percentages — `"error"` means **unavailable** (including SuperGrok without `grok login`)

Install it with `./install.sh` (or copy `cli/skills/fleet-usage/` into
`~/.grok/skills/`).

## Design rules

- **Read-only meters.** Local credential reads only; tokens are never printed,
  logged, or stored in the ledger. `login` writes a cookie file at mode `0600`.
- **Fail-open per meter.** One broken meter never blocks the others.
- **No invented numbers.** Missing API fields stay `null`.
- **Stdlib only.** One CLI file, zero dependencies.

## Unofficial endpoints (can change without notice)

| Endpoint | Auth | Notes |
|---|---|---|
| `POST cursor.com/api/dashboard/get-sand-usage-status` | session cookie | Grok Bot weekly pool ("sand" is the internal codename). Empty `{}` body. |
| `GET cursor.com/api/usage-summary` | session cookie | Plan/auto/api %, on-demand cents, billing cycle. |
| `GET cli-chat-proxy.grok.com/v1/billing?format=credits` | Bearer + `x-xai-token-auth: xai-grok-cli` | SuperGrok `creditUsagePercent` and `currentPeriod.end`. Never send the Cursor cookie here. |

Cookie value shape: `WorkosCursorSessionToken=<sub-after-last-pipe>%3A%3A<jwt>`.
POSTs to cursor.com require an `Origin: https://cursor.com` header.

If an endpoint moves, the CLI fails open with an error for that meter — update
the URL in [`cli/grokbot_usage.py`](cli/grokbot_usage.py) and re-run.

## License

MIT — see [LICENSE](LICENSE).

See also [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
