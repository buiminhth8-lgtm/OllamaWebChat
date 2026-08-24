import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple, Union


DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent / "data" / "settings.json"


class SettingsValidationError(ValueError):
    pass


class RuntimeSettingsStore:
    def __init__(self, path: Union[str, os.PathLike] = DEFAULT_SETTINGS_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def get_ollama_config(self) -> Dict[str, object]:
        with self._lock:
            settings = self._read_settings_unlocked()

        ollama = settings.get("ollama")
        install_dir = ollama.get("install_dir", "") if isinstance(ollama, dict) else ""
        if not isinstance(install_dir, str):
            install_dir = ""

        binary, error = self._validate_install_dir(install_dir)
        result: Dict[str, object] = {
            "install_dir": install_dir,
            "binary": str(binary) if binary is not None else None,
            "valid": error is None,
        }
        if error is not None:
            result["error"] = error
        return result

    def set_ollama_install_dir(self, install_dir: object) -> Dict[str, object]:
        binary, error = self._validate_install_dir(install_dir)
        if error is not None or binary is None:
            raise SettingsValidationError(error or "Ollama 安装目录无效")

        normalized_dir = str(Path(install_dir).expanduser().resolve())
        with self._lock:
            settings = self._read_settings_unlocked()
            settings["ollama"] = {"install_dir": normalized_dir}
            self._write_settings_unlocked(settings)

        return {
            "install_dir": normalized_dir,
            "binary": str(binary),
            "valid": True,
        }

    def _read_settings_unlocked(self) -> Dict[str, object]:
        try:
            with self.path.open("r", encoding="utf-8") as settings_file:
                settings = json.load(settings_file)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return {}

        return settings if isinstance(settings, dict) else {}

    def _write_settings_unlocked(self, settings: Dict[str, object]) -> None:
        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.path.parent),
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
                newline="\n",
            ) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(settings, temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
                temp_file.flush()
                os.fsync(temp_file.fileno())

            os.replace(str(temp_path), str(self.path))
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    @staticmethod
    def _validate_install_dir(install_dir: object) -> Tuple[Optional[Path], Optional[str]]:
        if not isinstance(install_dir, str):
            return None, "install_dir 必须是字符串"

        install_dir = install_dir.strip()
        if not install_dir:
            return None, "尚未配置 Ollama 安装目录"

        directory = Path(install_dir).expanduser()
        if not directory.exists():
            return None, f"Ollama 安装目录不存在：{directory}"
        if not directory.is_dir():
            return None, f"Ollama 安装路径不是目录：{directory}"

        candidates = (directory / "ollama", directory / "bin" / "ollama")
        invalid_candidates = []
        for candidate in candidates:
            if not candidate.exists():
                continue
            if not candidate.is_file():
                invalid_candidates.append(f"不是普通文件：{candidate}")
                continue
            if not os.access(str(candidate), os.X_OK):
                invalid_candidates.append(f"不可执行：{candidate}")
                continue
            return candidate.resolve(), None

        if invalid_candidates:
            return None, "Ollama 可执行文件无效（" + "；".join(invalid_candidates) + "）"

        checked = "、".join(str(candidate) for candidate in candidates)
        return None, f"未找到 Ollama 可执行文件，已检查：{checked}"
