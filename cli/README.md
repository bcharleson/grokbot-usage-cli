# grokbot-usage

Read-only CLI that reports two AI usage meters from local Cursor credentials,
and lets Grok Bot agents check their own consumption before they burn through it.

The install target and binary name is `grokbot-usage`. The repository is
[grokbot-usage-cli](https://github.com/bcharleson/grokbot-usage-cli).

See the [project README](../README.md) for full documentation.

## Quick start

```bash
python3 grokbot_usage.py                 # human-readable table
python3 grokbot_usage.py --json --write default
python3 grokbot_usage.py --quiet         # exit 1 when the Grok Bot pool >= 90%
python3 grokbot_usage.py login           # store ~/.secrets/cursor-session-cookie
```

## The two pools

| Meter | What burns it | Auth (local read) |
|---|---|---|
| `cursor` | Cursor IDE plan + on-demand dollars | Cursor session (env, login file, or IDE) |
| `grokbot` | Grok Bot weekly included pool | Same Cursor session |

## Design rules

- **Read-only meters.** Local credential reads; tokens never printed or logged.
- **Fail-open per meter.** One broken meter never blocks the other.
- **No invented numbers.** Missing API fields stay `null`.
- **Stdlib only.** One file, zero dependencies, Python 3.10+.
