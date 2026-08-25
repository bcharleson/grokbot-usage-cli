#!/usr/bin/env bash
# Fail the build if the tree contains secrets or personal residue.
# Documented SuperGrok (meter name, grok login, cli-chat-proxy URL) is allowed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0
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

scan '/home/box' "personal /home/box path"
scan '[[:space:]]TOFU[[:space:]]|^TOFU|TOFU$|tofu' "TOFU mention"
scan 'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.' "JWT-like literal"
scan '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "email address"
# Live cookie values, not the documented placeholder shape with <angle-brackets>.
scan 'WorkosCursorSessionToken=[A-Za-z0-9_%.+-]{8,}' "live cookie value"
scan '%3A%3AeyJ[A-Za-z0-9_-]{8,}' "cookie-embedded JWT"
# Committed auth.json payloads (path mentions in docs are fine).
if git ls-files -- 'auth.json' '**/.grok/auth.json' '.grok/auth.json' | grep -q .; then
  echo "SANITIZE FAIL: committed auth.json" >&2
  git ls-files -- 'auth.json' '**/.grok/auth.json' '.grok/auth.json' >&2
  FAIL=1
fi
scan '"access_token"[[:space:]]*:[[:space:]]*"[^"]{16,}"' "auth.json access_token contents"
scan 'xai-oauth-[A-Za-z0-9._-]{10,}' "live xai-oauth bearer"

if [[ "$FAIL" -ne 0 ]]; then
  exit 1
fi
echo "sanitize: clean"
