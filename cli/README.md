# grokbot-usage

Stdlib Python CLI. Binary name `grokbot-usage`. Repo
[grokbot-usage-cli](https://github.com/bcharleson/grokbot-usage-cli).

Install (see the [project README](../README.md)):

```bash
curl -fsSL https://raw.githubusercontent.com/bcharleson/grokbot-usage-cli/main/install.sh | bash
```

Fallback: `git clone https://github.com/bcharleson/grokbot-usage-cli.git && cd grokbot-usage-cli && ./install.sh`

Python 3.10+ is the runtime.

```bash
python3 grokbot_usage.py
python3 grokbot_usage.py --json --write default
python3 grokbot_usage.py login --cookie-file ./cursor-cookie.txt
```
