import subprocess
import time
from shutil import which
from typing import Any, Dict, List, Optional

from config import SCAN_COMMAND_TIMEOUT, SCAN_MAX_OUTPUT_CHARS


class CommandRunner:
    def __init__(self, default_timeout: int = SCAN_COMMAND_TIMEOUT, max_output_chars: int = SCAN_MAX_OUTPUT_CHARS):
        self.default_timeout = self._clamp_timeout(default_timeout)
        self.max_output_chars = max_output_chars

    def run(self, command_args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        started = time.monotonic()
        timeout_value = self._clamp_timeout(timeout or self.default_timeout)

        if not command_args or not isinstance(command_args, list):
            return self._result(False, False, None, "", "命令参数无效", False, started)
        if self._is_forbidden(command_args):
            return self._result(False, True, None, "", "命令不在安全白名单范围内", False, started)

        executable = command_args[0]
        if which(executable) is None:
            return self._result(False, False, None, "", "命令不存在", False, started)

        try:
            completed = subprocess.run(
                command_args,
                shell=False,
                timeout=timeout_value,
                capture_output=True,
                text=True,
            )
            return self._result(
                completed.returncode == 0,
                True,
                completed.returncode,
                self._truncate(completed.stdout),
                self._truncate(completed.stderr),
                False,
                started,
            )
        except subprocess.TimeoutExpired as exc:
            return self._result(
                False,
                True,
                None,
                self._truncate(exc.stdout or ""),
                self._truncate(exc.stderr or "命令超时"),
                True,
                started,
            )
        except PermissionError as exc:
            return self._result(False, True, None, "", "权限不足：%s" % exc, False, started)
        except OSError as exc:
            return self._result(False, True, None, "", "命令执行失败：%s" % exc, False, started)

    def _truncate(self, text: Any) -> str:
        if isinstance(text, bytes):
            text = text.decode("utf-8", "replace")
        value = str(text or "")
        if len(value) <= self.max_output_chars:
            return value
        return value[: self.max_output_chars] + "\n[输出已截断]"

    def _result(
        self,
        ok: bool,
        command_available: bool,
        return_code: Optional[int],
        stdout: str,
        stderr: str,
        timed_out: bool,
        started: float,
    ) -> Dict[str, Any]:
        return {
            "ok": ok,
            "command_available": command_available,
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    def _clamp_timeout(self, timeout: int) -> int:
        try:
            value = int(timeout)
        except (TypeError, ValueError):
            value = self.default_timeout if hasattr(self, "default_timeout") else 5
        return max(3, min(10, value))

    def _is_forbidden(self, command_args: List[str]) -> bool:
        executable = command_args[0]
        forbidden = {"sudo", "su", "apt", "apt-get", "yum", "dnf", "systemctl start", "systemctl stop"}
        if executable in forbidden:
            return True
        if executable == "systemctl" and len(command_args) > 1:
            allowed = {"is-active", "is-system-running", "--failed"}
            return command_args[1] not in allowed
        return False
