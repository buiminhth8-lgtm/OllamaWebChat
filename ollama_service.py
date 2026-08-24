import json
import subprocess
import threading
import time
from typing import Dict, Iterator, Optional, Set

import requests

from config import (
    OLLAMA_API_TIMEOUT,
    OLLAMA_BASE_URL,
    OLLAMA_PULL_CONNECT_TIMEOUT,
    OLLAMA_PULL_READ_TIMEOUT,
    OLLAMA_START_POLL_INTERVAL,
    OLLAMA_START_WAIT_TIMEOUT,
    OLLAMA_SYSTEMCTL_TIMEOUT,
)
from runtime_settings import RuntimeSettingsStore


OLLAMA_SERVICE_NAME = "ollama-webchat-ollama.service"


def _error(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def _ndjson_error(code: str, message: str) -> bytes:
    payload = json.dumps({"error": {"code": code, "message": message}}, ensure_ascii=False)
    return payload.encode("utf-8") + b"\n"


class OllamaServiceManager:
    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        base_url: str = OLLAMA_BASE_URL,
        api_timeout: float = OLLAMA_API_TIMEOUT,
        systemctl_timeout: float = OLLAMA_SYSTEMCTL_TIMEOUT,
        ready_timeout: float = OLLAMA_START_WAIT_TIMEOUT,
        poll_interval: float = OLLAMA_START_POLL_INTERVAL,
        pull_connect_timeout: float = OLLAMA_PULL_CONNECT_TIMEOUT,
        pull_read_timeout: float = OLLAMA_PULL_READ_TIMEOUT,
    ):
        self.settings_store = settings_store
        self.base_url = base_url.rstrip("/")
        self.api_timeout = api_timeout
        self.systemctl_timeout = systemctl_timeout
        self.ready_timeout = ready_timeout
        self.poll_interval = poll_interval
        self.pull_connect_timeout = pull_connect_timeout
        self.pull_read_timeout = pull_read_timeout
        self._start_lock = threading.Lock()
        self._pull_locks_guard = threading.Lock()
        self._active_pulls: Set[str] = set()

    def get_binary_path(self) -> Optional[str]:
        config = self.settings_store.get_ollama_config()
        binary = config.get("binary")
        return str(binary) if config.get("valid") and binary else None

    def check_api(self) -> Dict[str, object]:
        try:
            response = requests.get(
                f"{self.base_url}/api/version",
                timeout=self.api_timeout,
            )
            response.raise_for_status()
            try:
                payload = response.json()
            except (ValueError, requests.exceptions.JSONDecodeError) as exc:
                return {
                    "ready": False,
                    "version": None,
                    "error": _error("invalid_json", f"Ollama API 返回的 JSON 无效：{exc}"),
                }
        except requests.Timeout as exc:
            return {
                "ready": False,
                "version": None,
                "error": _error("timeout", f"连接 Ollama API 超时：{exc}"),
            }
        except requests.ConnectionError as exc:
            return {
                "ready": False,
                "version": None,
                "error": _error("connection_error", f"无法连接 Ollama API：{exc}"),
            }
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            message = "Ollama API 返回 HTTP 错误"
            if status_code is not None:
                message += f" {status_code}"
            return {
                "ready": False,
                "version": None,
                "error": _error("http_error", message),
            }
        except requests.RequestException as exc:
            return {
                "ready": False,
                "version": None,
                "error": _error("request_error", f"Ollama API 请求失败：{exc}"),
            }

        if not isinstance(payload, dict):
            return {
                "ready": False,
                "version": None,
                "error": _error("invalid_response", "Ollama API 返回格式无效"),
            }

        version = payload.get("version")
        return {"ready": True, "version": str(version) if version is not None else None}

    def get_status(self) -> Dict[str, object]:
        config = self.settings_store.get_ollama_config()
        api_status = self.check_api()
        service_status = self._get_service_state()

        status: Dict[str, object] = {
            "configured": bool(config.get("valid")),
            "binary": config.get("binary") if config.get("valid") else None,
            "running": service_status["state"] == "active",
            "ready": bool(api_status.get("ready")),
            "version": api_status.get("version"),
            "service_state": service_status["state"],
        }
        if config.get("error"):
            status["config_error"] = config["error"]
        if api_status.get("error"):
            status["api_error"] = api_status["error"]
        if service_status.get("error"):
            status["service_error"] = service_status["error"]
        return status

    def start(self) -> Dict[str, object]:
        with self._start_lock:
            api_status = self.check_api()
            if api_status.get("ready"):
                return {
                    "success": True,
                    "started": False,
                    "ready": True,
                    "version": api_status.get("version"),
                }

            config = self.settings_store.get_ollama_config()
            if not config.get("valid"):
                return {
                    "success": False,
                    "started": False,
                    "ready": False,
                    "error": _error(
                        "invalid_config",
                        str(config.get("error") or "Ollama 安装目录配置无效"),
                    ),
                }

            systemctl_result = self._start_systemd_service()
            if not systemctl_result["ok"]:
                return {
                    "success": False,
                    "started": False,
                    "ready": False,
                    "error": systemctl_result["error"],
                }

            ready_status = self.wait_until_ready()
            return {
                "success": bool(ready_status.get("ready")),
                "started": True,
                **ready_status,
            }

    def wait_until_ready(
        self,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
    ) -> Dict[str, object]:
        total_timeout = self.ready_timeout if timeout is None else max(0.0, timeout)
        interval = self.poll_interval if poll_interval is None else max(0.0, poll_interval)
        deadline = time.monotonic() + total_timeout
        last_status: Dict[str, object] = {
            "ready": False,
            "version": None,
            "error": _error("not_checked", "尚未检查 Ollama API"),
        }

        while True:
            last_status = self.check_api()
            if last_status.get("ready"):
                return last_status

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {
                    "ready": False,
                    "version": None,
                    "error": _error(
                        "ready_timeout",
                        f"等待 Ollama API 就绪超时（{total_timeout:g} 秒）",
                    ),
                    "last_error": last_status.get("error"),
                }

            time.sleep(min(interval, remaining))

    def _get_service_state(self) -> Dict[str, object]:
        command = ["systemctl", "is-active", OLLAMA_SERVICE_NAME]
        try:
            result = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.systemctl_timeout,
                check=False,
            )
        except FileNotFoundError:
            return {
                "state": "unavailable",
                "error": _error("command_not_found", "未找到 systemctl 命令"),
            }
        except PermissionError:
            return {
                "state": "unavailable",
                "error": _error("permission_denied", "无权限执行 systemctl"),
            }
        except subprocess.TimeoutExpired:
            return {
                "state": "unknown",
                "error": _error("systemctl_timeout", "查询 Ollama systemd 服务状态超时"),
            }
        except OSError as exc:
            return {
                "state": "unavailable",
                "error": _error("systemctl_error", f"无法执行 systemctl：{exc}"),
            }

        state = result.stdout.strip() or "unknown"
        if result.returncode == 0:
            return {"state": state}
        if state in {"inactive", "failed", "activating", "deactivating"}:
            return {"state": state}
        message = result.stderr.strip() or f"systemctl is-active 退出码 {result.returncode}"
        return {
            "state": "unavailable",
            "error": _error("systemctl_failed", message),
        }

    def _start_systemd_service(self) -> Dict[str, object]:
        # 固定命令：仅允许通过最小 sudoers 权限启动指定 service，
        # 任何用户输入都不会进入该命令。
        command = ["sudo", "-n", "systemctl", "start", OLLAMA_SERVICE_NAME]
        try:
            result = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.systemctl_timeout,
                check=False,
            )
        except FileNotFoundError:
            return {"ok": False, "error": _error("command_not_found", "未找到 systemctl 命令")}
        except PermissionError:
            return {"ok": False, "error": _error("permission_denied", "无权限启动 Ollama systemd 服务")}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": _error("systemctl_timeout", "启动 Ollama systemd 服务超时")}
        except OSError as exc:
            return {"ok": False, "error": _error("systemctl_error", f"无法执行 systemctl：{exc}")}

        if result.returncode != 0:
            message = result.stderr.strip() or f"systemctl start 退出码 {result.returncode}"
            return {
                "ok": False,
                "error": _error("systemctl_failed", message),
            }
        return {"ok": True}

    def try_begin_pull(self, model_name: str) -> bool:
        with self._pull_locks_guard:
            if model_name in self._active_pulls:
                return False
            self._active_pulls.add(model_name)
            return True

    def end_pull(self, model_name: str) -> None:
        with self._pull_locks_guard:
            self._active_pulls.discard(model_name)

    def stream_pull(self, model_name: str) -> Iterator[bytes]:
        try:
            try:
                response = requests.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": True},
                    stream=True,
                    timeout=(self.pull_connect_timeout, self.pull_read_timeout),
                )
            except requests.Timeout:
                yield _ndjson_error("timeout", "连接 Ollama API 超时")
                return
            except requests.ConnectionError:
                yield _ndjson_error("connection_error", "无法连接 Ollama API")
                return
            except requests.RequestException:
                yield _ndjson_error("request_error", "Ollama API 请求失败")
                return

            with response:
                if not 200 <= response.status_code < 300:
                    yield _ndjson_error(
                        "http_error",
                        f"Ollama API 返回 HTTP {response.status_code}",
                    )
                    return
                try:
                    for raw_line in response.iter_lines():
                        if not raw_line:
                            continue
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        try:
                            json.loads(line)
                        except ValueError:
                            yield _ndjson_error("invalid_json", "Ollama API 返回的 JSON 无效")
                            return
                        yield line.encode("utf-8") + b"\n"
                except requests.RequestException:
                    yield _ndjson_error("stream_interrupted", "与 Ollama API 的连接中断")
        finally:
            self.end_pull(model_name)
