#!/usr/bin/env sh
# Inicia o backend no notebook (Linux/macOS). O emulador Android acessa via http://10.0.2.2:8000
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt
else
    . .venv/bin/activate
fi
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
