# Contributing

CLI name `grokbot-usage`. Repo `grokbot-usage-cli`. Python 3.10+ stdlib is the
runtime. Install one-liner is
`curl -fsSL https://raw.githubusercontent.com/bcharleson/grokbot-usage-cli/main/install.sh | bash`.
Clone + `./install.sh` is fallback. Do not change GitHub visibility from this
tree.

```bash
git clone https://github.com/bcharleson/grokbot-usage-cli.git
cd grokbot-usage-cli
python3 -m unittest discover -s tests -v -b
bash tests/sanitize.sh
```

Resets are per account (`resetsAt` / `cycleEnd` from this machine's ledger).
Do not document a global reset weekday or time.

Never commit cookies, JWTs, `auth.json`, or live ledgers. Example JSON must
be marked EXAMPLE.
