import json
from typing import Iterator, Union

import requests
from flask import Blueprint, Response, jsonify, render_template, request

from config import (
    MAX_HISTORY_CHARS,
    MAX_HISTORY_MESSAGES,
    MAX_MESSAGE_CHARS,
    OLLAMA_BASE_URL,
    REQUEST_TIMEOUT,
)

bp = Blueprint("main", __name__)

VALID_ROLES = {"system", "user", "assistant"}
TRIM_PREFIX = "[已裁剪前文]\n"


def trim_text(text: str, limit: int = MAX_MESSAGE_CHARS) -> str:
    if len(text) <= limit:
        return text
    if limit <= len(TRIM_PREFIX):
        return text[-limit:] if limit > 0 else ""
    keep = limit - len(TRIM_PREFIX)
    return TRIM_PREFIX + text[-keep:]


def clean_messages(messages: object) -> list[dict[str, str]]:
    if not isinstance(messages, list):
        return []

    cleaned: list[dict[str, str]] = []
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
