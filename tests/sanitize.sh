#!/usr/bin/env bash
# Fail the build if the tree contains secrets, personal residue, or SuperGrok.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Patterns live only in this file so the rest of the tree stays clean.
FAIL=0
# grep -R excludes this script by path.
scan() {
  local pattern="$1"
  local label="$2"
  local hits
  hits="$(grep -RInE --binary-files=without-match \
    --exclude-dir=.git \
    --exclude-dir=__pycache__ \
    --exclude-dir=.venv \
    --exclude='sanitize.sh' \
    --exclude='*.pyc' \
    "$pattern" . || true)"
  if [[ -n "$hits" ]]; then
    echo "SANITIZE FAIL: $label" >&2
    echo "$hits" >&2
    FAIL=1
  fi
}

scan 'supergrok|SuperGrok|meter_supergrok|cli-chat-proxy' "SuperGrok remnants"
scan '/home/box' "personal /home/box path"
scan '[[:space:]]TOFU[[:space:]]|^TOFU|TOFU$|tofu' "TOFU mention"
scan 'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.' "JWT-like literal"
scan '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "email address"

if [[ "$FAIL" -ne 0 ]]; then
  exit 1
fi
echo "sanitize: clean"
