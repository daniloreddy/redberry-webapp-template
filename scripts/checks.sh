#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if [ ! -f ".venv/bin/activate" ]; then
    echo "Virtual environment not found, creating it..."
    python3 -m venv .venv
fi
source .venv/bin/activate
if ! python -c "import ruff" 2>/dev/null; then
    echo "Dependencies not installed, installing them..."
    pip install -r requirements.dev.txt
fi

echo "=== ruff ==="
ruff check .

echo "=== mypy ==="
mypy app

echo "=== pytest ==="
pytest

echo "All checks passed."
