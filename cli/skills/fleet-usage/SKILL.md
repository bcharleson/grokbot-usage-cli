---
name: fleet-usage
description: Check AI pool headroom (Grok Bot weekly pool, Cursor plan, SuperGrok credits) via the local grokbot-usage CLI before large or multi-agent work. Use when planning routines, launching multi-task waves, or when the user asks about remaining usage/quota/budget. Read-only, local, no secrets.
user_invocable: true
---

# Fleet Usage / Pool Headroom

Agents sharing a Grok Bot account burn one weekly pool, metered on the linked
Cursor account. When it hits 100%, work stalls mid-wave. Check before you burn.

## The command

```bash
grokbot-usage --json
```

Read-only. Local credentials only. Never prints tokens. ~1-2s.
(If `grokbot-usage` is not on PATH, run
`python3 <repo>/cli/grokbot_usage.py --json` from a checkout instead.)

Fast gate (exit 1 = grokbot weekly pool >= 90%):

```bash
grokbot-usage --quiet
```

## When to check

- BEFORE launching a multi-agent wave, a long routine batch, or computer-use loops
- When the user asks about usage, quota, budget, or "can we afford this"
- When tasks fail in ways that could be quota-related (429s, stalls)
- NOT needed for single quick tasks

## How to act on the numbers

| Reading | Meaning | Action |
|---|---|---|
| grokbot weekly < 70% | healthy | proceed |
| 70-89% | elevated | batch aggressively; avoid redundant agent fan-out; tell the user the number |
| >= 90% | critical | pause non-essential waves; ask the user before burning more; note reset time |
| 100% | exhausted | included pool gone; on-demand may be billing the Cursor account per task — surface `onDemandEnabled` + cursor on-demand dollars and ask before proceeding |
| meter shows "error" | auth expired or endpoint moved | say "usage meter unavailable" — NEVER guess or invent percentages |

## Rules

- Report real numbers only, from the CLI. Never estimate or round optimistically.
- The three pools are SEPARATE: the Cursor IDE plan, the Grok Bot weekly pool,
  and SuperGrok credits refill on their own clocks. A SuperGrok subscription
  does NOT refill the Grok Bot pool.
- Resets: grokbot weekly per `resetsAt` in the JSON (typically weekly);
  supergrok on its own `resetsAt`.
- To automate around the cap: schedule heavy work just after reset, and use
  `--quiet` exit codes as the gate in routines.
