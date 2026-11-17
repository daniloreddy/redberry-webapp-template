#!/usr/bin/env bash
# Print a random bearer token for API_TOKENS in .env (32 bytes, URL-safe).
set -e
cd "$(dirname "$0")/.."
PY=python3
[ -x ".venv/bin/python" ] && PY=.venv/bin/python
exec "$PY" -c "import secrets; print(secrets.token_urlsafe(32))"
