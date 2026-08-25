# Security

Treat Cursor session cookies and `~/.grok/auth.json` as passwords.

Never commit cookies, JWTs, `cursor-cookie.txt`, or `auth.json`. Never paste
them into chat. `login` writes `~/.secrets/cursor-session-cookie` at mode
`0600`. The ledger `~/.grokbot-usage/latest.json` must not contain tokens.

Report vulnerabilities via a private advisory on
[github.com/bcharleson/grokbot-usage-cli](https://github.com/bcharleson/grokbot-usage-cli/security).
