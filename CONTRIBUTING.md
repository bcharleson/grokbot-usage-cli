# Contributing

The CLI name is `grokbot-usage`. The repository is `grokbot-usage-cli`.
Keep those consistent. Stdlib Python 3.10+ only — no third-party packages.

## Setup

```bash
git clone https://github.com/bcharleson/grokbot-usage-cli.git
cd grokbot-usage-cli
python3 -m unittest discover -s tests -v -b
```

`PYTHONPATH` is not required when you run `unittest discover` from the repo
root; the test helper adds `cli/` to `sys.path`.

## Scope

Three meters: `cursor` (monthly plan % + on-demand $), `grokbot` (weekly
included pool), and optional `supergrok` (weekly credits via `grok login`,
not the Cursor cookie). The Cursor session covers Grok Bot only. Do not send
`WorkosCursorSessionToken` to grok.com.

## Tests

- `unittest` and `unittest.mock` only.
- Mock HTTP. Do not hit cursor.com or grok.com from tests.
- Do not commit cookies, JWTs, `latest.json` ledgers, or `snapshots/`.
- After a CLI change, add or update a test in `tests/`.

```bash
python3 -m unittest discover -s tests -v -b
bash tests/sanitize.sh
```

CI runs the same commands on Python 3.10 and 3.12.

## Secrets

Never print, log, or commit session cookies, JWTs, or `~/.grok/auth.json`.
`login` writes `~/.secrets/cursor-session-cookie` at mode `0600`. Example JSON
in docs must be marked EXAMPLE and must not be live data.

## Pull requests

1. One focused change.
2. Tests green, `tests/sanitize.sh` clean.
3. Do not include live usage numbers, emails, or machine paths.
