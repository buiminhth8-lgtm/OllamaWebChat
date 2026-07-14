import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

from config import PLATFORM_SCAN_RESULT_PATH
from platform_scan.collectors import COLLECTORS
from platform_scan.command_runner import CommandRunner
from platform_scan.schemas import empty_category, summary_counts


Collector = Callable[[CommandRunner, Dict[str, Any]], Dict[str, Any]]


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class PlatformScanner:
    def __init__(
        self,
        result_path: str = PLATFORM_SCAN_RESULT_PATH,
        collectors: Optional[Iterable[Tuple[str, str, Collector]]] = None,
        runner: Optional[CommandRunner] = None,
    ):
        self.result_path = result_path
        self.collectors = list(collectors or COLLECTORS)
        self.runner = runner or CommandRunner()

    def stream(self) -> Iterator[str]:
        scan_id = uuid.uuid4().hex
        started_at = iso_now()
        started = time.monotonic()
        total = len(self.collectors)
        categories: List[Dict[str, Any]] = []

        yield self._line({"event": "start", "scan_id": scan_id, "total": total, "started_at": started_at})

        cache: Dict[str, Any] = {}
        for index, (category_id, title, collector) in enumerate(self.collectors, start=1):
            item_started = time.monotonic()
            try:
                category = collector(self.runner, cache)
            except Exception as exc:
                category = empty_category(category_id, title, "检测异常：%s" % exc, int((time.monotonic() - item_started) * 1000))
                yield self._line({"event": "error", "category_id": category_id, "message": str(exc)})
            categories.append(category)
            yield self._line({"event": "progress", "index": index, "total": total, "category": category})

        finished_at = iso_now()
        duration_ms = int((time.monotonic() - started) * 1000)
        summary = summary_counts(categories)
        result = {
            "scan_id": scan_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "summary": summary,
            "categories": categories,
        }
        self.save_latest(result)
        yield self._line(
            {
                "event": "complete",
                "scan_id": scan_id,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
                "summary": summary,
            }
        )

    def latest(self) -> Dict[str, Any]:
        try:
            with open(self.result_path, "r", encoding="utf-8") as handle:
                return {"available": True, "scan": json.load(handle)}
        except FileNotFoundError:
            return {"available": False}
        except (OSError, ValueError):
            return {"available": False}

    def save_latest(self, result: Dict[str, Any]) -> None:
        directory = os.path.dirname(self.result_path) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix=".platform_scan_", suffix=".json", dir=directory)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp_path, self.result_path)
        except OSError:
            return

    def _line(self, payload: Dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False) + "\n"
