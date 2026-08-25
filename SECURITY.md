# Security

`grokbot-usage` reads a Cursor web session so it can call the same unofficial
usage endpoints the Cursor dashboard uses. Treat that session as a password.

## What is stored

| Location | Mode | Purpose |
|---|---|---|
| `~/.secrets/cursor-session-cookie` | `0600` (`~/.secrets` is `0700`) | Written by `grokbot-usage login` |
| `~/.grok/auth.json` | written by the Grok CLI (`0600`) | SuperGrok bearer — this CLI only reads it |
| `~/.grokbot-usage/latest.json` | default umask | Usage ledger only — no tokens |

`CURSOR_SESSION_COOKIE` and Cursor IDE `state.vscdb` are read in memory and
never copied into the ledger. SuperGrok uses the Grok CLI file only — the
Cursor cookie is never sent to grok.com.

## Rules this project will not break

- Tokens and cookies are never printed, logged, or committed.
- HTTP error paths must not echo request headers or response bodies.
- Example docs are marked EXAMPLE and must not contain live credentials.

## Reporting a vulnerability

Open a private security advisory on
[github.com/bcharleson/grokbot-usage-cli](https://github.com/bcharleson/grokbot-usage-cli/security).
Do not file a public issue that includes a session cookie, JWT, or ledger
from a real machine.
