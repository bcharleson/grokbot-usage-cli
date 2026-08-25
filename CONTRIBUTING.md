# Contributing

CLI name `grokbot-usage`. Repo `grokbot-usage-cli`. Stdlib Python 3.10+ only.
Install is `git clone` + `./install.sh`. Do not `npm publish` and do not
change GitHub visibility from this tree. `package.json` is for the owner's
later publish only.

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
