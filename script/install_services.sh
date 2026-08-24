#!/usr/bin/env bash
# One-shot installer for Ollama Web Chat systemd services.
#
# - Installs ollama-webchat.service and enables it at boot (enable --now).
# - Installs ollama-webchat-ollama.service WITHOUT enabling it; the web app
#   starts it on demand via `sudo -n systemctl start`.
# - Grants the deploy user the minimal sudo right to start only that unit.
#
# Safe to re-run (idempotent). Run as: ./script/install_services.sh
set -euo pipefail

fail() {
  echo "install_services: 错误：$*" >&2
  exit 1
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_USER="${SUDO_USER:-$(id -un)}"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
SYSTEMD_DIR="$PROJECT_DIR/systemd"
WEB_UNIT="ollama-webchat.service"
OLLAMA_UNIT="ollama-webchat-ollama.service"

[[ -f "$PROJECT_DIR/app.py" ]] || fail "未找到 $PROJECT_DIR/app.py"
[[ -f "$PROJECT_DIR/ollama_runner.py" ]] || fail "未找到 $PROJECT_DIR/ollama_runner.py"
[[ -x "$VENV_PYTHON" ]] || fail "未找到 venv Python：$VENV_PYTHON（请先执行 python3 -m venv venv && pip install -r requirements.txt）"
for unit in "$WEB_UNIT" "$OLLAMA_UNIT"; do
  [[ -f "$SYSTEMD_DIR/$unit" ]] || fail "缺少 systemd 模板：$SYSTEMD_DIR/$unit"
done

command -v systemctl >/dev/null 2>&1 || fail "未找到 systemctl，本脚本仅支持 systemd 系统"
command -v sudo >/dev/null 2>&1 || fail "未找到 sudo"
command -v visudo >/dev/null 2>&1 || fail "未找到 visudo，无法安全安装 sudoers"
SYSTEMCTL_PATH="$(command -v systemctl)"

render_unit() {
  sed \
    -e "s|@PROJECT_DIR@|$PROJECT_DIR|g" \
    -e "s|@DEPLOY_USER@|$DEPLOY_USER|g" \
    -e "s|@VENV_PYTHON@|$VENV_PYTHON|g" \
    "$1" > "$2"
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

render_unit "$SYSTEMD_DIR/$WEB_UNIT" "$TMP_DIR/$WEB_UNIT"
render_unit "$SYSTEMD_DIR/$OLLAMA_UNIT" "$TMP_DIR/$OLLAMA_UNIT"

if grep -n '@PROJECT_DIR@\|@DEPLOY_USER@\|@VENV_PYTHON@' "$TMP_DIR/$WEB_UNIT" "$TMP_DIR/$OLLAMA_UNIT"; then
  fail "模板占位符未被完全替换，已中止安装"
fi
grep -q "^User=$DEPLOY_USER$" "$TMP_DIR/$WEB_UNIT" || fail "web service 用户替换失败"

echo "==> 安装 systemd unit 文件"
sudo install -m 644 -o root -g root "$TMP_DIR/$WEB_UNIT" "/etc/systemd/system/$WEB_UNIT"
sudo install -m 644 -o root -g root "$TMP_DIR/$OLLAMA_UNIT" "/etc/systemd/system/$OLLAMA_UNIT"

echo "==> 安装最小 sudoers 规则（仅允许启动 $OLLAMA_UNIT）"
SUDOERS_FILE="$TMP_DIR/sudoers-ollama-webchat"
printf '%s ALL=(root) NOPASSWD: %s start %s\n' "$DEPLOY_USER" "$SYSTEMCTL_PATH" "$OLLAMA_UNIT" > "$SUDOERS_FILE"
sudo visudo -cf "$SUDOERS_FILE" >/dev/null || fail "sudoers 语法校验失败，已中止"
sudo install -m 440 -o root -g root "$SUDOERS_FILE" /etc/sudoers.d/ollama-webchat

echo "==> 重载 systemd 配置"
sudo systemctl daemon-reload

echo "==> 启用并启动 Web 服务（开机自启）"
sudo systemctl enable --now "$WEB_UNIT"

cat <<EOF

安装完成：
- Web：$WEB_UNIT 已 enable --now（开机自启动）
- Ollama：$OLLAMA_UNIT 仅安装未 enable（由网页按需通过 sudo -n systemctl start 启动）
- 部署用户：$DEPLOY_USER
- 项目目录：$PROJECT_DIR

验证：
  systemctl status $WEB_UNIT
  systemctl status $OLLAMA_UNIT
  journalctl -u $WEB_UNIT -f
  journalctl -u $OLLAMA_UNIT -f
EOF
