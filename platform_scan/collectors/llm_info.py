import glob
import os
import time
from typing import Any, Dict, List, Tuple

import requests

from config import MODEL_SCAN_DIRS, OLLAMA_BASE_URL, SCAN_COMMAND_TIMEOUT, SCAN_MAX_MODEL_FILES
from platform_scan.collectors.common import list_process_names, now_ms, process_exists, scan_model_files
from platform_scan.command_runner import CommandRunner
from platform_scan.schemas import category_result, check, metric


TITLE = "大模型部署与调用能力"


def _ollama_get(path: str) -> Tuple[bool, int, Any, int, str]:
    started = time.monotonic()
    try:
        response = requests.get(OLLAMA_BASE_URL + path, timeout=SCAN_COMMAND_TIMEOUT)
        duration_ms = int((time.monotonic() - started) * 1000)
        if response.status_code == 404:
            return False, 404, None, duration_ms, "接口不支持"
        response.raise_for_status()
        return True, response.status_code, response.json(), duration_ms, ""
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        status_code = getattr(getattr(exc, "response", None), "status_code", 0) or 0
        return False, status_code, None, duration_ms, str(exc)
    except ValueError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return False, 0, None, duration_ms, "响应不是 JSON：%s" % exc


def _rkllm_present(process_names: List[str]) -> Tuple[bool, int]:
    library_paths = [
        "/usr/lib/librkllmrt.so",
        "/usr/local/lib/librkllmrt.so",
        "/usr/lib/aarch64-linux-gnu/librkllmrt.so",
    ]
    library_found = any(os.path.exists(path) for path in library_paths)
    library_found = library_found or bool(glob.glob("/usr/local/lib*/librkllmrt.so"))
    model_files = scan_model_files(MODEL_SCAN_DIRS, [".rkllm"], SCAN_MAX_MODEL_FILES, max_depth=3)
    service_found = process_exists(["rkllm"], process_names)
    return library_found or bool(model_files) or service_found, len(model_files)


def collect(runner: CommandRunner, cache: Dict[str, Any]) -> Dict[str, Any]:
    started = time.monotonic()
    checks: List[Dict[str, str]] = []
    metrics: List[Dict[str, str]] = []
    recommendations: List[str] = []
    process_names = cache.setdefault("process_names", list_process_names())

    version_ok, version_code, version_data, version_ms, version_error = _ollama_get("/api/version")
    tags_ok, tags_code, tags_data, tags_ms, tags_error = _ollama_get("/api/tags")
    ps_ok, ps_code, ps_data, ps_ms, ps_error = _ollama_get("/api/ps")

    models = []
    if tags_ok and isinstance(tags_data, dict):
        models = [item.get("name") or item.get("model") for item in tags_data.get("models", [])]
        models = [item for item in models if item]
    lowered = [item.lower() for item in models]
    has_deepseek = any("deepseek" in item for item in lowered)
    has_qwen = any("qwen" in item or "tongyi" in item for item in lowered)

    loaded = []
    if ps_ok and isinstance(ps_data, dict):
        loaded = [item.get("name") or item.get("model") for item in ps_data.get("models", [])]
        loaded = [item for item in loaded if item]

    rkllm_found, rkllm_model_count = _rkllm_present(process_names)
    version = version_data.get("version", "未知") if isinstance(version_data, dict) else "未知"

    metrics.extend(
        [
            metric("Ollama API", "可达" if version_ok or tags_ok else "不可达"),
            metric("Ollama version", version),
            metric("Installed models", len(models)),
            metric("Loaded models", len(loaded)),
            metric("DeepSeek model", "存在" if has_deepseek else "未检测到"),
            metric("Qwen model", "存在" if has_qwen else "未检测到"),
            metric("API latency", min([value for value in [version_ms, tags_ms] if value >= 0] or [0]), "ms"),
            metric("RKLLM models", rkllm_model_count),
        ]
    )
    checks.extend(
        [
            check("Ollama API 是否可达", "pass" if version_ok or tags_ok else "warning", "可达" if version_ok or tags_ok else "不可达", "Ollama /api/version,/api/tags"),
            check("Ollama 版本", "pass" if version_ok else "warning", version if version_ok else version_error, "Ollama /api/version"),
            check("已安装模型", "pass" if models else "warning", ", ".join(models[:20]) if models else "未检测到", "Ollama /api/tags"),
            check("当前加载模型", "pass" if loaded else ("warning" if ps_code == 404 else "warning"), ", ".join(loaded[:20]) if loaded else ("接口不支持" if ps_code == 404 else "未加载或未检测到"), "Ollama /api/ps"),
            check("DeepSeek 模型", "pass" if has_deepseek else "warning", "存在" if has_deepseek else "未检测到", "Ollama /api/tags"),
            check("Qwen/通义千问模型", "pass" if has_qwen else "warning", "存在" if has_qwen else "未检测到", "Ollama /api/tags"),
            check("RKLLM 组件", "pass" if rkllm_found else "warning", "检测到" if rkllm_found else "未检测到", "librkllmrt.so / MODEL_SCAN_DIRS / process comm"),
        ]
    )

    api_failed = any(code >= 500 for code in [version_code, tags_code] if code)
    if (version_ok or tags_ok) and (has_deepseek or has_qwen):
        status = "pass"
        summary = "Ollama API 可访问，并检测到 DeepSeek 或 Qwen/通义千问模型。"
    elif api_failed:
        status = "fail"
        summary = "Ollama API 返回明确异常，需检查服务状态。"
    elif version_ok or tags_ok:
        status = "warning"
        summary = "Ollama API 可访问，但未检测到 DeepSeek 或 Qwen/通义千问模型。"
        recommendations.append("如需验收大模型能力，请通过 Ollama 拉取或导入 DeepSeek/Qwen 模型。")
    elif rkllm_found:
        status = "warning"
        summary = "未连接到 Ollama，但检测到 RKLLM 相关组件或模型文件。"
        recommendations.append("如使用 RKLLM，请补充服务调用接口或运行态检查。")
    else:
        status = "warning"
        summary = "未检测到可用 Ollama API 或 RKLLM 运行证据。"
        recommendations.append("确认 Ollama 服务地址 OLLAMA_BASE_URL 是否正确。")

    return category_result("llm", TITLE, status, summary, metrics, checks, recommendations, now_ms(started))
