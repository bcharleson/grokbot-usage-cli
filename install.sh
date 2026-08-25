#!/usr/bin/env bash
# grokbot-usage installer — works from a checkout OR curl|bash.
#   CLI   -> ~/.local/bin/grokbot-usage
#   skill -> ~/.grok/skills/fleet-usage/
# Video / one-liner:
#   curl -fsSL https://raw.githubusercontent.com/bcharleson/grokbot-usage-cli/main/install.sh | bash
set -euo pipefail

BIN_DIR="${HOME}/.local/bin"
SKILL_DIR="${HOME}/.grok/skills/fleet-usage"
TARBALL="${GROKBOT_USAGE_TARBALL:-https://github.com/bcharleson/grokbot-usage-cli/archive/refs/heads/main.tar.gz}"
TMP=""

cleanup() {
  if [[ -n "${TMP}" && -d "${TMP}" ]]; then
    rm -rf "${TMP}"
  fi
}
trap cleanup EXIT

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found" >&2; exit 1; }
ver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
case "$ver" in
  3.1[0-9]|3.[2-9][0-9]) ;;
  *) echo "ERROR: Python 3.10+ required, found $ver" >&2; exit 1 ;;
esac

local_root() {
  local self="${BASH_SOURCE[0]:-}"
  [[ -n "$self" && -f "$self" ]] || return 1
  local root
  root="$(cd "$(dirname -- "$self")" && pwd)"
  [[ -f "$root/cli/grokbot_usage.py" ]] || return 1
  [[ -f "$root/cli/skills/fleet-usage/SKILL.md" ]] || return 1
  printf '%s\n' "$root"
}

fetch_tree() {
  command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required for remote install" >&2; exit 1; }
  command -v tar >/dev/null 2>&1 || { echo "ERROR: tar is required for remote install" >&2; exit 1; }
  TMP="$(mktemp -d "${TMPDIR:-/tmp}/grokbot-usage-install.XXXXXX")"
  if ! curl -fsSL "$TARBALL" | tar -xz -C "$TMP"; then
    echo "ERROR: could not download the install tree." >&2
    echo "This one-liner needs the GitHub files readable (public repo or a token)." >&2
    echo "Private/offline fallback:" >&2
    echo "  git clone https://github.com/bcharleson/grokbot-usage-cli.git" >&2
    echo "  cd grokbot-usage-cli && ./install.sh" >&2
    exit 1
  fi
  local py
  py="$(find "$TMP" -type f -name grokbot_usage.py -path '*/cli/grokbot_usage.py' | head -n 1 || true)"
  if [[ -z "$py" || ! -f "$py" ]]; then
    echo "ERROR: downloaded tree is missing cli/grokbot_usage.py" >&2
    exit 1
  fi
  ROOT="$(cd "$(dirname "$py")/.." && pwd)"
  if [[ ! -f "$ROOT/cli/skills/fleet-usage/SKILL.md" ]]; then
    echo "ERROR: downloaded tree is missing the fleet-usage skill" >&2
    exit 1
  fi
}

if ROOT="$(local_root)"; then
  :
else
  fetch_tree
fi

mkdir -p "$BIN_DIR" "$(dirname "$SKILL_DIR")"
install -m 0755 "$ROOT/cli/grokbot_usage.py" "$BIN_DIR/grokbot-usage"
rm -rf "$SKILL_DIR"
mkdir -p "$SKILL_DIR"
cp "$ROOT/cli/skills/fleet-usage/SKILL.md" "$SKILL_DIR/SKILL.md"

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *) echo "Note: add ${BIN_DIR} to PATH" ;;
esac

"$BIN_DIR/grokbot-usage" --help >/dev/null 2>&1 || true

echo "Install succeeded."
echo "  binary: $BIN_DIR/grokbot-usage"
echo "  skill:  $SKILL_DIR/SKILL.md"

if "$BIN_DIR/grokbot-usage" --meter grokbot >/dev/null 2>&1; then
  echo "Next: grokbot-usage"
else
  echo "Next: grokbot-usage login --cookie-file ./cursor-cookie.txt"
  echo "      then: grokbot-usage"
fi
exit 0
