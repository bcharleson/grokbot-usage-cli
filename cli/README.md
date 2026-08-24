# grokbot-usage

Read-only CLI that reports AI usage across three commonly-linked pools from local
credentials, and lets Grok Bot agents check their own consumption before they
burn through it.

See the [project README](../README.md) for full documentation. This file is the
package-level summary (npm packaging lands later).

## Quick start

```bash
python3 grokbot_usage.py            # human-readable table
python3 grokbot_usage.py --json     # stable JSON for scripts and agents
python3 grokbot_usage.py --quiet    # exit 1 when the Grok Bot pool >= 90%
```

## The three pools

| Meter | What burns it | Auth (local read) |
|---|---|---|
| `cursor` | Cursor IDE/Ultra plan + on-demand dollars | Session token in Cursor's `state.vscdb` |
| `grokbot` | Grok Bot weekly pool (agents, routines, computer use) | Same Cursor session |
| `supergrok` | SuperGrok weekly credits | Bearer in `~/.grok/auth.json` |

## Design rules

- **Read-only.** Local credential reads; tokens never printed or stored.
- **Fail-open per meter.** One broken meter never blocks the others.
- **No invented numbers.** Missing API fields stay `null`.
- **Stdlib only.** One file, zero dependencies, Python 3.10+.
