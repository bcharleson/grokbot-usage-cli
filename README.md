# grokbot-usage

Read-only CLI that reports AI usage across three commonly-linked pools from local
credentials — and lets [Grok Bot](https://cursor.com/help/grok-bot/plans) agents be
**self-aware of their own consumption** before they burn through it.

```text
$ grokbot-usage
AI usage meters — Sun 12:17
  cursor    plan 34% used (auto 41% / api 3%) · on-demand $12.50 of $200.0 · resets Thu 17:26
  grokbot   weekly 62% used · resets Tue 11:00 (Grok Bot Plan)
  supergrok weekly 18% used · resets Fri 04:53 (SuperGrok Heavy)
```

No official APIs exist for any of these meters. This tool reads the same
endpoints the vendor's own apps and dashboards use, authenticated with session
credentials already on your machine. Nothing is invented: if an API doesn't
return a number, the field is `null`.

## The three pools

| Meter | What burns it | Auth (local read) |
|---|---|---|
| `cursor` | Cursor IDE/Ultra plan (Agent, Composer, Tab) + on-demand dollars | Session token in Cursor's `state.vscdb` |
| `grokbot` | Grok Bot weekly pool (agents, routines, computer use) | Same Cursor session — Grok Bot is billed on the Cursor account |
| `supergrok` | SuperGrok weekly credits (Chat, Imagine, Build) | Bearer token in `~/.grok/auth.json` |

The three pools are independent. A SuperGrok subscription links Grok Bot access
but does not refill the Grok Bot weekly pool.

## Requirements

- macOS or Linux
- Python 3.10+ (stdlib only — zero dependencies)
- Cursor signed in on this machine (for `cursor` + `grokbot` meters)
- Grok CLI signed in at least once (for the `supergrok` meter)

## Install

```bash
git clone https://github.com/bcharleson/grokbot-usage.git
cd grokbot-usage
./install.sh
```

`install.sh` copies the CLI to `~/.local/bin/grokbot-usage` and installs the
`fleet-usage` agent skill to `~/.grok/skills/` (so Grok Bot agents can use it).
Both steps are plain file copies — review the script first; it does nothing else.

Or run straight from a checkout with no install:

```bash
python3 cli/grokbot_usage.py
```

## Usage

```bash
grokbot-usage                        # human-readable table, all meters
grokbot-usage --json                 # stable JSON for scripts and agents
grokbot-usage --meter grokbot        # one of: cursor | grokbot | supergrok
grokbot-usage --quiet                # exit 1 when grokbot weekly >= 90%
grokbot-usage --quiet --threshold 95 # custom threshold
```

Exit codes: `0` ok · `1` threshold breached (or the grokbot meter is unavailable
— unknown is treated as breach, never fail-open) · `2` usage error.

### JSON shape

```json
{
  "asOf": "2026-08-23T19:17:56+00:00",
  "cursor":   {"planPercentUsed": 34.1, "autoPercentUsed": 41.2,
               "apiPercentUsed": 2.9, "onDemandUsedUSD": 12.5,
               "onDemandLimitUSD": 200.0, "cycleEnd": "...", "membership": "ultra"},
  "grokbot":  {"weeklyPercentUsed": 62, "resetsAt": "...",
               "planLabel": "Grok Bot Plan", "onDemandEnabled": true},
  "supergrok":{"tier": "SuperGrok Heavy", "weeklyPercentUsed": 18.0,
               "resetsAt": "...", "periodType": "USAGE_PERIOD_TYPE_WEEKLY"}
}
```

A meter that cannot be read reports `{"error": "..."}` instead of fake numbers.

## Agent integration

The bundled `fleet-usage` skill teaches Grok Bot agents to:

- check pool headroom (`--json`) before launching multi-agent waves, long
  routine batches, or computer-use loops
- gate routines on `--quiet` exit codes, and schedule heavy work just after
  the weekly reset
- act on thresholds: report the number, batch aggressively, pause non-essential
  work, and ask before letting on-demand billing run past the included pool
- never invent percentages — an unreadable meter is reported as unavailable

Install it with `./install.sh` (or copy `cli/skills/fleet-usage/` into
`~/.grok/skills/`).

## Design rules

- **Read-only.** Local credential reads only; tokens are never printed,
  logged, or stored. Requests go exclusively to the vendor endpoints that
  issued the credentials.
- **Fail-open per meter.** One broken meter never blocks the others.
- **No invented numbers.** Missing API fields stay `null`.
- **Stdlib only.** One file, zero dependencies.

## Unofficial endpoints (can change without notice)

| Endpoint | Auth | Notes |
|---|---|---|
| `POST cursor.com/api/dashboard/get-sand-usage-status` | session cookie | The exact payload the Grok Bot desktop app renders in its account menu ("sand" is the internal codename). Empty `{}` body. |
| `GET cursor.com/api/usage-summary` | session cookie | Plan/auto/api %, on-demand cents, billing cycle. |
| `GET cli-chat-proxy.grok.com/v1/billing?format=credits` | Bearer | Weekly credit %, product split, reset. `/v1/settings` adds the tier label. |

Cookie value shape: `WorkosCursorSessionToken=<sub-after-last-pipe>%3A%3A<jwt>`.
POSTs to cursor.com require an `Origin: https://cursor.com` header.
`~/.grok/auth.json` tokens expire (~6h); running the Grok CLI refreshes them.

If an endpoint moves, the CLI fails open with an error for that meter — update
the URL in `cli/grokbot_usage.py` and re-run.

## License

MIT — see [LICENSE](LICENSE).
