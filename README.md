# grokbot-usage-cli

Read-only stdlib Python CLI (`grokbot-usage`) that reports this machine's AI
usage so [Grok Bot](https://cursor.com/help/grok-bot/plans) agents can check
their own consumption before they burn it. Two required meters — `cursor`
(monthly plan % + on-demand $) and `grokbot` (weekly included pool) — come
from one Cursor session. SuperGrok is an optional third meter via `grok login`
on grok.com / x.ai; the Cursor cookie does not unlock it.

**Your reset is not anyone else's.** Read `resetsAt` / `cycleEnd` from
`~/.grokbot-usage/latest.json` (or re-run the CLI). Those fields are ISO UTC
from this account. Convert to the user's local zone when speaking to a human.
If a timestamp is missing or the meter is `"error"`, say **reset unknown** /
**unavailable**. Do not guess a weekday or time.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/bcharleson/grokbot-usage-cli/main/install.sh | bash
```

That one-liner needs `raw.githubusercontent.com` to be readable (the GitHub
repo public, or a token). It copies:

- CLI → `~/.local/bin/grokbot-usage`
- skill → `~/.grok/skills/fleet-usage/SKILL.md` (Grok Bot / Grok CLI skill path)

Private or offline fallback (no raw.githubusercontent access):

```bash
git clone https://github.com/bcharleson/grokbot-usage-cli.git
cd grokbot-usage-cli
./install.sh
```

Add `~/.local/bin` to `PATH` if the installer says so. Stdlib Python 3.10+ on
macOS or Linux. A later pipx/PyPI extra is not ready.

This skill also belongs wherever *that* agent reads skills. Copy
[`cli/skills/fleet-usage/SKILL.md`](cli/skills/fleet-usage/SKILL.md) into a
Cursor project skill dir, a Grok Bot workflow, or another fleet's skill folder.

From a checkout with no install:

```bash
python3 cli/grokbot_usage.py
```

## One-time auth (two doors)

Tokens and cookies are never printed, logged, or committed. **Never paste a
cookie into chat.**

### Door 1 — Cursor + Grok Bot (required)

Same session covers both meters. First match wins:

1. Sign in to the Cursor IDE on this machine, or
2. `grokbot-usage login --cookie-file ./cursor-cookie.txt` (file holds the
   `WorkosCursorSessionToken` value copied from cursor.com DevTools →
   Application → Cookies), or
3. `CURSOR_SESSION_COOKIE`, or `grokbot-usage login --from-ide`, or paste via
   `grokbot-usage login` (input hidden on a TTY)

`login` writes `~/.secrets/cursor-session-cookie` at mode `0600`.
`grokbot-usage logout` deletes it.

### Door 2 — SuperGrok (optional)

Cursor login does **not** unlock SuperGrok, even when SuperGrok Heavy is
linked to Cursor.

```bash
curl -fsSL https://x.ai/cli/install.sh | bash
grok login                  # browser
# or, headless:
grok login --device-auth    # open the printed accounts.x.ai URL, confirm the code
```

Session lands in `~/.grok/auth.json` (mode `0600`). Never commit it.
`grok logout` clears it. Missing file → SuperGrok `{"error": "..."}`, never 0%.

## First read

```bash
grokbot-usage
grokbot-usage --json --write default
```

The second command writes `~/.grokbot-usage/latest.json`. That file is the
ledger. Other useful flags:

```bash
grokbot-usage --json --write PATH
grokbot-usage --meter grokbot        # cursor | grokbot | supergrok
grokbot-usage --quiet --threshold 90 # exit 1 if grokbot weekly >= threshold
```

`--quiet` default threshold is `GROKBOT_USAGE_WEEKLY_BUDGET` if set, else `90`.
Exit `0` ok · `1` grokbot threshold / unknown, or every meter failed · `2` usage error.

Human output prints each meter's reset from **this account's** API timestamp
(converted to local). It does not assume a global reset day.

## Lean cron (OS — not a Grok Bot routine)

Weekdays at 08:00 / 12:00 / 18:00, write the ledger. Agents **Read the file**.
Stay quiet unless over budget. Do not poll with LLM turns.

```cron
0 8,12,18 * * 1-5 $HOME/.local/bin/grokbot-usage --json --write default
```

## For Grok Bot fleets

1. Drop [`cli/skills/fleet-usage/SKILL.md`](cli/skills/fleet-usage/SKILL.md) into
   the skill path that fleet uses (`./install.sh` already lands it at
   `~/.grok/skills/fleet-usage/`).
2. Point agents at `~/.grokbot-usage/latest.json`.
3. Do not poll usage with extra LLM turns. Do not use browserUse for %.

If `asOf` is under 6 hours old, Read the ledger only. If missing or stale,
shell `grokbot-usage --json --write default`, then Read.

## Budgets (treat like money)

Never invent numbers. `"error"` means **unavailable**, not 0%.

| Env | Default | Meaning |
|---|---|---|
| `GROKBOT_USAGE_WEEKLY_BUDGET` | 90 | Flag the human at or above this grokbot weekly % |
| `GROKBOT_USAGE_DAILY_SPIKE` | 20 | Flag when weekly % jumped this many points vs the last ledger you have |

| grokbot weekly | Band | Action |
|---|---|---|
| < 70 | healthy | proceed |
| 70–89 | elevated | batch; avoid redundant fan-out; tell the human the number once |
| >= weekly budget (default 90) | flag | pause non-essential waves; ask before burning more; cite **this account's** `resetsAt` |
| 100 | exhausted | included pool gone — mention Cursor on-demand $ and `onDemandEnabled`; ask before proceeding |

Daily spike: weekly % is `GROKBOT_USAGE_DAILY_SPIKE` or more above the last
ledger you recorded → flag the human once.

Cursor cash flag: `onDemandUsedUSD` >= `onDemandLimitUSD` when both are numbers.

When telling a human when the pool refills: read `grokbot.resetsAt`,
`cursor.cycleEnd`, and (if present) `supergrok.resetsAt` from the ledger.
Convert UTC → local. If missing or error: **reset unknown**.

## Troubleshoot

| Symptom | What to do |
|---|---|
| no session / `state.vscdb not found` | Sign in to Cursor on this machine, or `login --cookie-file` |
| HTTP 401 | Session expired. Re-login. Do not paste the cookie into chat |
| SuperGrok unavailable | Run `grok login` or `grok login --device-auth`. Cursor cookie will not fix this |
| unofficial endpoints moved | That meter returns `"error"`. Update the URL in [`cli/grokbot_usage.py`](cli/grokbot_usage.py) |

Auth ladder for cursor + grokbot (first hit wins): `CURSOR_SESSION_COOKIE`,
then `~/.secrets/cursor-session-cookie`, then Cursor IDE `state.vscdb`
(macOS + Linux) → `WorkosCursorSessionToken=<sub-after-pipe>%3A%3A<jwt>`.

Unofficial endpoints (can change without notice):

| Endpoint | Auth | Notes |
|---|---|---|
| `POST cursor.com/api/dashboard/get-sand-usage-status` | Cursor session | `usagePercent`, `nextResetTimestampUtc`, `currentPeriodStart` |
| `GET cursor.com/api/usage-summary` | Cursor session | plan %, on-demand cents, `billingCycleStart` / `billingCycleEnd` |
| `GET cli-chat-proxy.grok.com/v1/billing?format=credits` | Grok bearer + `x-xai-token-auth: xai-grok-cli` | SuperGrok `creditUsagePercent` + `currentPeriod.end`. Never send the Cursor cookie here |

POSTs to cursor.com need `Origin: https://cursor.com`.

## EXAMPLE JSON — not live data

The timestamps below are **EXAMPLE** only. The next reader's `resetsAt` /
`cycleEnd` and local clock will differ. Do not treat them as a product default.

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
    "periodStart": "2026-01-13T18:00:00.000Z",
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

## License

MIT — see [LICENSE](LICENSE).

See also [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
