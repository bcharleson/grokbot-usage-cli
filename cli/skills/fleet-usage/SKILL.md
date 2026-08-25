---
name: fleet-usage
description: Check this machine's Grok Bot weekly pool, Cursor plan/on-demand dollars, and optional SuperGrok credits before multi-agent waves, long batches, or when the user asks about usage/quota/budget, or when failures look quota-shaped (429s, mid-wave stalls). If grokbot-usage is missing, install with curl -fsSL https://raw.githubusercontent.com/bcharleson/grokbot-usage-cli/main/install.sh | bash. Read ~/.grokbot-usage/latest.json first. Report remaining % and time-to-reset from the ledger. Never invent percentages or reset days.
user_invocable: true
---

# Fleet Usage

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/bcharleson/grokbot-usage-cli/main/install.sh | bash
```

Fallback: `git clone https://github.com/bcharleson/grokbot-usage-cli.git && cd grokbot-usage-cli && ./install.sh`

That lands `~/.local/bin/grokbot-usage` and this skill at `~/.grok/skills/fleet-usage/`. Or copy this file into the skill dir that agent already uses.

## After install — Read the ledger first

1. Read `~/.grokbot-usage/latest.json`.
2. If `asOf` is less than 6 hours old, use those numbers. Do **not** shell the CLI. Do **not** start an LLM turn just to check usage.
3. If the file is missing or stale:

```bash
grokbot-usage --json --write default
```

Then Read `~/.grokbot-usage/latest.json` again.

**Never invent percentages.** `"error"` means **unavailable** (not 0%). Do not ask a friend. Never hardcode reset dates.

## Resets and self-awareness

The three pools reset on **different clocks**. Read them from **this machine's** ledger. Never hardcode a weekday or time. Convert UTC → the user's local zone when speaking.

| Meter | What burns it | Ledger fields | Clock |
|---|---|---|---|
| `grokbot` | Grok Bot routines, long chats, computer-use, multi-agent waves | `weeklyPercentUsed`, `resetsAt`, `periodStart` | weekly included pool |
| `cursor` | Cloud agents and IDE Agent (plan %). On-demand $ is cash, not a weekly reset | `planPercentUsed`, `cycleStart`, `cycleEnd`, `onDemandUsedUSD`, `onDemandLimitUSD` | monthly plan window |
| `supergrok` | SuperGrok Heavy Chat / Imagine / Build on grok.com (optional) | `weeklyPercentUsed`, `resetsAt` | weekly SuperGrok credits |

A SuperGrok subscription does **not** refill Grok Bot. Cursor login does **not** read SuperGrok. Missing SuperGrok auth = **unavailable**, not 0%.

1. **Before starting work:** Read the ledger. Report remaining % **and** time-to-reset for each available meter. One sentence is enough. If `resetsAt` / `cycleEnd` is missing or the meter is error, say **reset unknown**.
2. **Routine planning:** Grok Bot weekly is the routine budget. Do not add hourly Grok Bot watches. Prefer OS cron that only writes the ledger. Schedule heavy fleet work just after `grokbot.resetsAt`, not at the end of the period.
3. **Cursor:** useful even with no SuperGrok. Cloud agents and IDE Agent burn `cursor` plan %. `onDemandUsedUSD` >= `onDemandLimitUSD` is a cash flag independent of the Grok Bot weekly reset.
4. **SuperGrok Heavy:** mention `supergrok.resetsAt` when the work is Imagine / Build / grok.com. Do not mix it into Grok Bot %.
5. **Tell the human when:** grokbot weekly >= `GROKBOT_USAGE_WEEKLY_BUDGET` (default 90), daily spike (`GROKBOT_USAGE_DAILY_SPIKE`, default 20), Cursor on-demand over cap, or any meter is **<24h to reset AND already elevated** (>= 70). Otherwise stay quiet. Tell them **once**.

EXAMPLE speech (not live; the next reader's clocks will differ — read the ledger):

> Grok Bot 40% used, resets Tuesday 11:00 local; Cursor plan 23% used, cycle ends mid-month; SuperGrok 33% used, resets Friday morning.

## Lean routine

OS cron (not a Grok Bot watch), weekdays 8/12/18, writes the ledger:

```cron
0 8,12,18 * * 1-5 $HOME/.local/bin/grokbot-usage --json --write default
```

Optional: **one** weekday Grok Bot file-read. Stay quiet unless a flag above fires. No hourly watches. No browserUse for %.

## Budgets (treat like money)

| grokbot weekly | Band | Action |
|---|---|---|
| < 70 | healthy | proceed |
| 70–89 | elevated | batch; tell the human the number once if a tell-when rule fires |
| >= weekly budget (default 90) | flag | pause non-essential waves; cite **this account's** `resetsAt` |
| 100 | exhausted | mention Cursor on-demand $; ask before proceeding |

```bash
grokbot-usage --quiet --threshold "${GROKBOT_USAGE_WEEKLY_BUDGET:-90}"
```

## Rules

- Real numbers only, from the ledger or CLI.
- SuperGrok optional; error = unavailable; do not invent %.
- Do not paste cookies, JWTs, or `auth.json` contents.
