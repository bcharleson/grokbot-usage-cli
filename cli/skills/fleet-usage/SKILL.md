---
name: fleet-usage
description: Check this machine's Grok Bot weekly pool, Cursor plan/on-demand dollars, and optional SuperGrok credits before multi-agent waves, long batches, or when the user asks about usage/quota/budget, or when failures look quota-shaped (429s, mid-wave stalls). Read ~/.grokbot-usage/latest.json first. Never invent percentages.
user_invocable: true
---

# Fleet Usage

If `grokbot-usage` is missing:
`curl -fsSL https://raw.githubusercontent.com/bcharleson/grokbot-usage-cli/main/install.sh | bash`
(needs raw.githubusercontent access). Private/offline: clone
`https://github.com/bcharleson/grokbot-usage-cli.git` and run `./install.sh`.
That lands the CLI at `~/.local/bin/grokbot-usage` and this skill at
`~/.grok/skills/fleet-usage/`. Or copy this file into the skill dir that agent
already uses.

## After install — Read the ledger first

1. Read `~/.grokbot-usage/latest.json`.
2. If `asOf` is less than 6 hours old, use those numbers. Do **not** shell the CLI. Do **not** start an LLM turn just to check usage.
3. If the file is missing or stale:

```bash
grokbot-usage --json --write default
```

Then Read `~/.grokbot-usage/latest.json` again.

**Never invent percentages.** `"error"` means **unavailable** (not 0%). Do not ask a friend.

## Meters

Cursor login covers `cursor` + `grokbot`. SuperGrok is optional (`grok login` / `grok login --device-auth` → `~/.grok/auth.json`). The Cursor cookie does not unlock SuperGrok.

| Meter | Field | Reset field (this account only) |
|---|---|---|
| `grokbot` | `weeklyPercentUsed` | `resetsAt` (and `periodStart`) |
| `cursor` | `planPercentUsed`, on-demand $ | `cycleEnd` / `cycleStart` |
| `supergrok` | `weeklyPercentUsed` | `resetsAt` when auth exists |

**Your reset is not anyone else's.** Read `resetsAt` / `cycleEnd` from the ledger (or re-run the CLI). Convert that UTC timestamp to the user's local zone when speaking to a human. If the field is missing or the meter is error, say **reset unknown** / **unavailable**. Do not guess a weekday or time.

## Lean routine

OS cron (not a Grok Bot watch), weekdays 8/12/18, writes the ledger:

```cron
0 8,12,18 * * 1-5 $HOME/.local/bin/grokbot-usage --json --write default
```

Optional: **one** weekday Grok Bot file-read. Stay quiet unless over budget. Tell the human **once**. No hourly watches. No browserUse for %.

## Budgets (treat like money)

`GROKBOT_USAGE_WEEKLY_BUDGET` default 90. `GROKBOT_USAGE_DAILY_SPIKE` default 20.

| grokbot weekly | Band | Action |
|---|---|---|
| < 70 | healthy | proceed |
| 70–89 | elevated | batch; tell the human the number once |
| >= weekly budget (default 90) | flag | pause non-essential waves; cite **this account's** `resetsAt` |
| 100 | exhausted | mention Cursor on-demand $; ask before proceeding |

Daily spike vs last ledger → flag once. Cursor `onDemandUsedUSD` >= `onDemandLimitUSD` → cash flag.

```bash
grokbot-usage --quiet --threshold "${GROKBOT_USAGE_WEEKLY_BUDGET:-90}"
```

## Rules

- Real numbers only, from the ledger or CLI.
- SuperGrok optional; error = unavailable; do not invent %.
- Do not paste cookies, JWTs, or `auth.json` contents.
