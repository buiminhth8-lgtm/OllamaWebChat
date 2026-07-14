import glob
import importlib.util
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple


def now_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def read_text(path: str, max_chars: int = 65536) -> Tuple[str, str]:
    try:
        with open(path, "rb") as handle:
            data = handle.read(max_chars)
        return data.decode("utf-8", "replace").replace("\x00", " ").strip(), "pass"
    except FileNotFoundError:
        return "", "warning"
    except PermissionError:
        return "", "unknown"
    except OSError:
        return "", "unknown"


def first_line(text: str) -> str:
    return text.strip().splitlines()[0].strip() if text.strip() else ""


def parse_os_release(text: str) -> str:
    values: Dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values.get("PRETTY_NAME") or values.get("NAME") or ""


def parse_mem_total_kb(text: str) -> Optional[int]:
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    return None


def format_kb(kb: Optional[int]) -> str:
    if not kb:
        return "未知"
    gb = kb / 1024.0 / 1024.0
    return "%.1f GB" % gb


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def python_module_check(name: str) -> Dict[str, str]:
    return {"name": name, "available": module_available(name)}


def glob_limited(pattern: str, limit: int = 200) -> List[str]:
    return sorted(glob.glob(pattern))[:limit]


def safe_basename(path: str) -> str:
    return os.path.basename(path.rstrip(os.sep)) or path


def list_process_names(limit: int = 4096) -> List[str]:
    names: List[str] = []
    for pid in os.listdir("/proc") if os.path.isdir("/proc") else []:
        if not pid.isdigit():
            continue
        name, _status = read_text(os.path.join("/proc", pid, "comm"), max_chars=256)
        if name:
            names.append(first_line(name))
        if len(names) >= limit:
            break
    return names


def process_exists(candidates: Iterable[str], process_names: Optional[List[str]] = None) -> bool:
    names = process_names if process_names is not None else list_process_names()
    lowered = [item.lower() for item in names]
    return any(candidate.lower() in item for candidate in candidates for item in lowered)


def scan_model_files(dirs: Iterable[str], extensions: Iterable[str], max_files: int, max_depth: int = 3) -> List[str]:
    found: List[str] = []
    allowed = tuple(ext.lower() for ext in extensions)
    for root in dirs:
        root = os.path.abspath(os.path.expanduser(root))
        if root in {os.path.abspath(os.sep), ""} or not os.path.isdir(root):
            continue
        root_depth = root.rstrip(os.sep).count(os.sep)
        for current, dirnames, filenames in os.walk(root):
            depth = current.rstrip(os.sep).count(os.sep) - root_depth
            if depth >= max_depth:
                dirnames[:] = []
            for filename in filenames:
                if filename.lower().endswith(allowed):
                    found.append(filename)
                    if len(found) >= max_files:
                        return found
    return found


def parse_ip_addr(output: str) -> List[Dict[str, str]]:
    interfaces: List[Dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[1]
        address = ""
        if "inet" in parts:
            index = parts.index("inet")
            if index + 1 < len(parts):
                address = parts[index + 1]
        if name and address:
            interfaces.append({"name": name, "ipv4": address})
    return interfaces


def network_interfaces() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    base = "/sys/class/net"
    if not os.path.isdir(base):
        return items
    for name in sorted(os.listdir(base)):
        state, _ = read_text(os.path.join(base, name, "operstate"), max_chars=128)
        items.append({"name": name, "state": state or "unknown"})
    return items


def has_default_route() -> bool:
    text, status = read_text("/proc/net/route")
    if status not in {"pass", "warning"}:
        return False
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) > 2 and parts[1] == "00000000":
            return True
    return False
