#!/bin/bash
# ════════════════════════════════════════════════════════════
# Tara Astro Vision — Backend Startup Script
# Run this on your production server to start FastAPI.
# Prefer this project's Uvicorn in every environment; fall back to a globally
# installed executable when the project virtualenv is not present.
# ════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Prefer this project's environment in both development and production so
# the server uses the dependencies installed for this checkout.
if [ -x ".venv/bin/uvicorn" ]; then
  UVICORN=".venv/bin/uvicorn"
elif command -v uvicorn >/dev/null 2>&1; then
  UVICORN="$(command -v uvicorn)"
else
  echo "Uvicorn not found. Install requirements.txt or create .venv first." >&2
  exit 127
fi

echo "Starting Tara Astro Vision backend..."
echo "Port:   ${PORT:-8000}"

exec "$UVICORN" main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WORKERS:-1}" \
  --log-level info
