import json
from typing import Dict, Iterator, List, Union

import requests
from flask import Blueprint, Response, current_app, jsonify, render_template, request

from config import (
    MAX_HISTORY_CHARS,
    MAX_HISTORY_MESSAGES,
    MAX_MESSAGE_CHARS,
    MAX_MODEL_NAME_LENGTH,
    OLLAMA_BASE_URL,
    REQUEST_TIMEOUT,
)
from runtime_settings import SettingsValidationError

bp = Blueprint("main", __name__)

VALID_ROLES = {"system", "user", "assistant"}
TRIM_PREFIX = "[已裁剪前文]\n"
OLLAMA_START_ERROR_MESSAGES = {
    "invalid_config": "Ollama 安装路径未配置或无效",
    "command_not_found": "systemctl 不可用",
    "permission_denied": "没有权限启动 Ollama 服务",
    "systemctl_timeout": "启动 Ollama systemd 服务超时",
    "systemctl_failed": "Ollama systemd 服务启动失败",
    "systemctl_error": "无法调用 systemd 服务管理器",
    "ready_timeout": "Ollama 服务启动后未能及时就绪",
}


def trim_text(text: str, limit: int = MAX_MESSAGE_CHARS) -> str:
    if len(text) <= limit:
        return text
    if limit <= len(TRIM_PREFIX):
        return text[-limit:] if limit > 0 else ""
    keep = limit - len(TRIM_PREFIX)
    return TRIM_PREFIX + text[-keep:]


def clean_messages(messages: object) -> List[Dict[str, str]]:
    if not isinstance(messages, list):
        return []

    cleaned: List[Dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role in VALID_ROLES and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": trim_text(content.strip())})

    if len(cleaned) > MAX_HISTORY_MESSAGES:
        cleaned = cleaned[-MAX_HISTORY_MESSAGES:]

    while len(cleaned) > 1 and sum(len(item["content"]) for item in cleaned) > MAX_HISTORY_CHARS:
        cleaned.pop(0)

    return cleaned


def stream_ollama_chat(payload: dict) -> Iterator[Union[bytes, str]]:
    try:
        with requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": payload["model"], "messages": payload["messages"], "stream": True},
            stream=True,
            timeout=(15, REQUEST_TIMEOUT),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    yield line + b"\n"
    except requests.RequestException as exc:
        yield json.dumps({"error": f"Ollama 请求失败：{exc}"}, ensure_ascii=False) + "\n"


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/health")
def health():
    return jsonify({"ok": True, "ollama_base_url": OLLAMA_BASE_URL})


@bp.get("/api/config")
def frontend_config():
    return jsonify(
        {
            "max_message_chars": MAX_MESSAGE_CHARS,
            "max_history_messages": MAX_HISTORY_MESSAGES,
            "max_history_chars": MAX_HISTORY_CHARS,
        }
    )


@bp.get("/api/ollama/status")
def ollama_status():
    try:
        status = current_app.extensions["ollama_service"].get_status()
    except Exception:
        current_app.logger.error("Failed to get Ollama service status")
        return jsonify(
            {
                "error": "service_manager_error",
                "message": "无法获取 Ollama 服务状态",
            }
        ), 500

    return jsonify(status)


@bp.get("/api/ollama/config")
def ollama_config():
    try:
        config = current_app.extensions["runtime_settings"].get_ollama_config()
    except Exception:
        current_app.logger.error("Failed to get Ollama runtime configuration")
        return jsonify(
            {
                "error": "runtime_settings_error",
                "message": "无法读取 Ollama 配置",
            }
        ), 500
    return jsonify(config)


@bp.put("/api/ollama/config")
def update_ollama_config():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "install_dir" not in payload:
        return jsonify(
            {
                "error": "invalid_request",
                "message": "请求体必须包含 install_dir",
            }
        ), 400

    try:
        config = current_app.extensions["runtime_settings"].set_ollama_install_dir(
            payload["install_dir"]
        )
    except SettingsValidationError as exc:
        return jsonify(
            {
                "error": "invalid_config",
                "message": str(exc),
            }
        ), 400
    except OSError:
        current_app.logger.error("Failed to save Ollama runtime configuration")
        return jsonify(
            {
                "error": "runtime_settings_error",
                "message": "无法保存 Ollama 配置",
            }
        ), 500

    return jsonify(config)


@bp.post("/api/ollama/start")
def ollama_start():
    try:
        result = current_app.extensions["ollama_service"].start()
    except Exception:
        current_app.logger.error("Failed to start Ollama service")
        return jsonify(
            {
                "ok": False,
                "started": False,
                "error": "service_manager_error",
                "message": "Ollama 服务启动失败",
            }
        ), 500

    if result.get("success"):
        started = bool(result.get("started"))
        status = {
            "ready": bool(result.get("ready")),
            "version": result.get("version"),
        }
        if started:
            status["running"] = True
        return jsonify(
            {
                "ok": True,
                "started": started,
                "message": "Ollama started" if started else "Ollama already running",
                "status": status,
            }
        )

    error = result.get("error")
    if isinstance(error, dict):
        error_code = str(error.get("code") or "start_failed")
    else:
        error_code = "start_failed"
    message = OLLAMA_START_ERROR_MESSAGES.get(error_code, "Ollama 服务启动失败")

    status_code = 400 if error_code == "invalid_config" else 500
    return jsonify(
        {
            "ok": False,
            "started": bool(result.get("started")),
            "error": error_code,
            "message": message,
            "status": {
                "ready": bool(result.get("ready")),
                "version": result.get("version"),
            },
        }
    ), status_code


@bp.post("/api/ollama/pull")
def ollama_pull():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "model" not in payload:
        return jsonify({"ok": False, "error": "请求体必须包含 model 参数"}), 400

    model = payload["model"]
    if not isinstance(model, str):
        return jsonify({"ok": False, "error": "model 参数必须为字符串"}), 400
    model = model.strip()
    if not model:
        return jsonify({"ok": False, "error": "model 不能为空"}), 400
    if len(model) > MAX_MODEL_NAME_LENGTH:
        return jsonify({"ok": False, "error": "model 名称过长"}), 400
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in model):
        return jsonify({"ok": False, "error": "model 包含非法字符"}), 400

    manager = current_app.extensions["ollama_service"]
    try:
        api_status = manager.check_api()
    except Exception:
        current_app.logger.error("Failed to check Ollama API readiness")
        return jsonify(
            {
                "ok": False,
                "error": "service_manager_error",
                "message": "无法确认 Ollama 服务状态",
            }
        ), 500

    if not api_status.get("ready"):
        return jsonify(
            {
                "ok": False,
                "error": "ollama_not_ready",
                "message": "Ollama 未运行，请先启动 Ollama 服务",
            }
        ), 503

    if not manager.try_begin_pull(model):
        return jsonify({"ok": False, "error": "model pull already in progress"}), 409

    return Response(
        manager.stream_pull(model),
        content_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.get("/api/models")
def models():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=20)
        response.raise_for_status()
        data = response.json()
        models = [
            {
                "name": item.get("name") or item.get("model"),
                "size": item.get("size"),
                "modified_at": item.get("modified_at"),
            }
            for item in data.get("models", [])
            if item.get("name") or item.get("model")
        ]
        return jsonify({"models": models})
    except requests.RequestException as exc:
        return jsonify({"error": f"无法连接 Ollama：{exc}", "ollama_base_url": OLLAMA_BASE_URL}), 502


@bp.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    model = str(payload.get("model", "")).strip()
    messages = clean_messages(payload.get("messages"))

    if not model:
        return jsonify({"error": "缺少 model 参数"}), 400
    if not messages:
        return jsonify({"error": "messages 必须包含至少一条有效消息"}), 400

    return Response(
        stream_ollama_chat({"model": model, "messages": messages}),
        content_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
