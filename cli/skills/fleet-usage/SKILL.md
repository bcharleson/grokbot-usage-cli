---
name: fleet-usage
description: Check Grok Bot weekly pool, Cursor plan/on-demand dollars, and optional SuperGrok credits. Prefer ~/.grokbot-usage/latest.json when asOf is under 6 hours old; only run grokbot-usage when that ledger is stale or missing. Use before large or multi-agent work, or when the user asks about usage, quota, or budget.
user_invocable: true
---

# Fleet Usage

Cursor login covers `cursor` + `grokbot`. SuperGrok is a separate grok.com / x.ai login even when SuperGrok Heavy is linked to Cursor.

| Meter | What it is | Auth |
|---|---|---|
| `grokbot` | Weekly included pool % | Cursor session |
| `cursor` | Monthly plan % + on-demand $ | Same Cursor session |
| `supergrok` | Weekly SuperGrok credits % (optional) | `~/.grok/auth.json` from `grok login` |

## Read the ledger first

1. Read `~/.grokbot-usage/latest.json`.
2. If `asOf` is less than 6 hours old, use those numbers. Do **not** shell the CLI. Do **not** start an LLM turn just to check usage.
3. If the file is missing or stale, run:

```bash
grokbot-usage --json --write default
```

Then read `~/.grokbot-usage/latest.json`.

If `grokbot-usage` is not on PATH, run
`python3 <repo>/cli/grokbot_usage.py --json --write default` from a checkout.

**Never invent percentages.** If a meter object has `"error"`, say **unavailable**. That includes SuperGrok when `~/.grok/auth.json` is missing — it is not 0%. Do not send the human to ask a friend.

## SuperGrok (optional)

The Cursor cookie does not unlock SuperGrok. Headless / proven path:

```bash
curl -fsSL https://x.ai/cli/install.sh | bash
grok login --device-auth
```

Open the printed `accounts.x.ai` URL and confirm the code. Browser alternative: `grok login`. Session lands in `~/.grok/auth.json` (mode 0600). Never commit it. `grok logout` clears it.

If SuperGrok is error/unavailable, report that and continue with `cursor` + `grokbot`.

## Recurrence (lean)

OS cron, weekdays at 08:00 / 12:00 / 18:00, writing the ledger:

```cron
0 8,12,18 * * 1-5 $HOME/.local/bin/grokbot-usage --json --write default
```

Optional: **one** Grok Bot weekday file-read of `latest.json`. Stay quiet unless over budget.

Do **not** schedule hourly Grok Bot watches. Do **not** use browserUse to scrape usage %.

## Budgets (treat like money)

Overrides (numbers are percents of the grokbot weekly pool):

| Env | Default | Meaning |
|---|---|---|
| `GROKBOT_USAGE_WEEKLY_BUDGET` | 90 | Flag the human at or above this weekly % |
| `GROKBOT_USAGE_DAILY_SPIKE` | 20 | Flag when weekly % jumped this many points vs the last ledger you have |

| grokbot weekly | Band | Action |
|---|---|---|
| < 70 | healthy | proceed |
| 70–89 | elevated | batch; avoid redundant fan-out; tell the human the number |
| >= weekly budget (default 90) | flag | pause non-essential waves; ask before burning more; cite `resetsAt` |
| 100 | exhausted | included pool gone — mention Cursor on-demand $ and `onDemandEnabled`; ask before proceeding |

Daily spike: weekly % is `GROKBOT_USAGE_DAILY_SPIKE` or more above the last ledger you recorded (prior `latest.json` `asOf`, or the last check this session) → flag the human.

Cursor cash flag: `onDemandUsedUSD` >= `onDemandLimitUSD` when both are numbers.

Fast gate (exit 1 = grokbot weekly >= threshold, or the meter is unavailable):

```bash
grokbot-usage --quiet --threshold "${GROKBOT_USAGE_WEEKLY_BUDGET:-90}"
```

## Rules

- Real numbers only, from the ledger or CLI. Never estimate or round optimistically.
- Cursor session covers Grok Bot only. SuperGrok refills on its own `resetsAt`.
- Unknown is a breach: an `"error"` meter is unavailable, not 0%.
- Do not paste, log, or quote session cookies, JWTs, or `auth.json` contents.
