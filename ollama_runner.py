#!/usr/bin/env python3
"""Run `ollama serve` using the Ollama binary resolved from runtime settings.

This script is the ExecStart target of ollama-webchat-ollama.service.
It never uses a shell and never concatenates user input into a command
string; the binary path is validated and executed directly via os.execve.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

from runtime_settings import DEFAULT_SETTINGS_PATH, RuntimeSettingsStore

DEFAULT_OLLAMA_HOST = "127.0.0.1:11434"


def resolve_binary(settings_path: Optional[Union[str, os.PathLike]] = None) -> Path:
    store = RuntimeSettingsStore(settings_path or DEFAULT_SETTINGS_PATH)
    config = store.get_ollama_config()

    if not config.get("valid") or not config.get("binary"):
        error = str(config.get("error") or "Ollama 配置无效")
        print(f"ollama_runner: {error}", file=sys.stderr)
        raise SystemExit(1)

    return Path(str(config["binary"]))


def validate_executable(binary: Path) -> None:
    if not binary.is_file():
        print(f"ollama_runner: Ollama 可执行文件不存在：{binary}", file=sys.stderr)
        raise SystemExit(1)
    if not os.access(str(binary), os.X_OK):
        print(f"ollama_runner: Ollama 可执行文件不可执行：{binary}", file=sys.stderr)
        raise SystemExit(1)


def build_exec_args(binary: Path) -> List[str]:
    return [str(binary), "serve"]


def build_exec_env(environ: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = dict(environ if environ is not None else os.environ)
    host = (env.get("OLLAMA_HOST") or "").strip() or DEFAULT_OLLAMA_HOST
    env["OLLAMA_HOST"] = host
    return env


def main(settings_path: Optional[Union[str, os.PathLike]] = None) -> int:
    try:
        binary = resolve_binary(settings_path)
        validate_executable(binary)
    except SystemExit as exc:
        return int(exc.code or 1)

    env = build_exec_env()
    args = build_exec_args(binary)
    print(f"ollama_runner: starting {' '.join(args)} (OLLAMA_HOST={env['OLLAMA_HOST']})")
    os.execve(str(binary), args, env)
    return 0  # pragma: no cover - execve 不返回


if __name__ == "__main__":
    sys.exit(main())
