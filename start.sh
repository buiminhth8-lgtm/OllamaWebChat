#!/usr/bin/env bash
# 开发/调试用启动脚本。生产部署请使用 ./script/install_services.sh 安装 systemd 服务。
set -e
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
export WEB_HOST="${WEB_HOST:-0.0.0.0}"
export WEB_PORT="${WEB_PORT:-3000}"
exec python3 app.py
