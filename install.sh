#!/usr/bin/env bash
# grokbot-usage installer — copies files, nothing else.
#   CLI   -> ~/.local/bin/grokbot-usage
#   skill -> ~/.grok/skills/fleet-usage/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
SKILL_DIR="${HOME}/.grok/skills/fleet-usage"

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found" >&2; exit 1; }
ver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
case "$ver" in
  3.1[0-9]|3.[2-9][0-9]) ;;
  *) echo "ERROR: Python 3.10+ required, found $ver" >&2; exit 1 ;;
esac

mkdir -p "$BIN_DIR" "$(dirname "$SKILL_DIR")"
install -m 0755 "$ROOT/cli/grokbot_usage.py" "$BIN_DIR/grokbot-usage"
rm -rf "$SKILL_DIR"
mkdir -p "$SKILL_DIR"
cp "$ROOT/cli/skills/fleet-usage/SKILL.md" "$SKILL_DIR/SKILL.md"

echo "Installed:"
echo "  $BIN_DIR/grokbot-usage"
echo "  $SKILL_DIR/SKILL.md"
case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *) echo "Note: add ${BIN_DIR} to PATH to run grokbot-usage from any directory" ;;
esac
"$BIN_DIR/grokbot-usage" --help >/dev/null
"$BIN_DIR/grokbot-usage" --meter grokbot >/dev/null 2>&1 \
  && echo "Smoke test: OK" \
  || echo "Smoke test: meter unavailable (login or sign in to Cursor, then retry) — install is still fine"
