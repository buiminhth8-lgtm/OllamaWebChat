#!/usr/bin/env bash
set -e
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
export WEB_HOST="${WEB_HOST:-0.0.0.0}"
export WEB_PORT="${WEB_PORT:-3000}"
exec python3 app.py
