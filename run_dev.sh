#!/usr/bin/env bash
# Quick dev start — installs deps if needed, then runs with auto-reload
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your UKHO_API_KEY"
fi

pip install -q -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
