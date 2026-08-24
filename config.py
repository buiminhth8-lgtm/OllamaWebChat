import os


def _get_int(name, default, minimum=None, maximum=None):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _get_float(name, default, minimum=None, maximum=None):
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _get_dirs(name, default):
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_API_TIMEOUT = _get_float("OLLAMA_API_TIMEOUT", 3.0, minimum=0.1, maximum=60.0)
OLLAMA_SYSTEMCTL_TIMEOUT = _get_float("OLLAMA_SYSTEMCTL_TIMEOUT", 10.0, minimum=0.1, maximum=60.0)
OLLAMA_START_WAIT_TIMEOUT = _get_float("OLLAMA_START_WAIT_TIMEOUT", 30.0, minimum=0.1, maximum=300.0)
OLLAMA_START_POLL_INTERVAL = _get_float("OLLAMA_START_POLL_INTERVAL", 0.5, minimum=0.05, maximum=10.0)
REQUEST_TIMEOUT = _get_int("OLLAMA_REQUEST_TIMEOUT", 600, minimum=1)
MAX_MESSAGE_CHARS = _get_int("MAX_MESSAGE_CHARS", 8000, minimum=100)
MAX_HISTORY_MESSAGES = _get_int("MAX_HISTORY_MESSAGES", 40, minimum=1)
MAX_HISTORY_CHARS = _get_int("MAX_HISTORY_CHARS", 24000, minimum=1000)

MODEL_SCAN_DIRS = _get_dirs("MODEL_SCAN_DIRS", "/opt/uav/models,/userdata/models,/home/zkjr/models")
PLATFORM_SCAN_RESULT_PATH = os.getenv("PLATFORM_SCAN_RESULT_PATH", "data/platform_scan_latest.json")
SCAN_COMMAND_TIMEOUT = _get_int("SCAN_COMMAND_TIMEOUT", 5, minimum=3, maximum=10)
SCAN_MAX_OUTPUT_CHARS = _get_int("SCAN_MAX_OUTPUT_CHARS", 65536, minimum=1024, maximum=262144)
SCAN_MAX_MODEL_FILES = _get_int("SCAN_MAX_MODEL_FILES", 200, minimum=1, maximum=5000)
TEMP_WARNING_C = _get_float("TEMP_WARNING_C", 75.0, minimum=0.0)
TEMP_CRITICAL_C = _get_float("TEMP_CRITICAL_C", 85.0, minimum=0.0)
DISK_WARNING_PERCENT = _get_float("DISK_WARNING_PERCENT", 85.0, minimum=1.0, maximum=100.0)
MEMORY_WARNING_PERCENT = _get_float("MEMORY_WARNING_PERCENT", 85.0, minimum=1.0, maximum=100.0)
LOAD_WARNING_RATIO = _get_float("LOAD_WARNING_RATIO", 1.5, minimum=0.1)
