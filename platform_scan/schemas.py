from typing import Any, Dict, Iterable, List


ALLOWED_STATUSES = {"pass", "warning", "fail", "unknown", "scanning"}
STATUS_LABELS = {
    "pass": "正常",
    "warning": "部分满足",
    "fail": "异常",
    "unknown": "未知",
    "scanning": "检测中",
}


def normalize_status(status: str) -> str:
    return status if status in ALLOWED_STATUSES else "unknown"


def metric(name: str, value: Any, unit: str = "") -> Dict[str, str]:
    return {"name": str(name), "value": "" if value is None else str(value), "unit": str(unit or "")}


def check(name: str, status: str, value: Any, evidence: str) -> Dict[str, str]:
    return {
        "name": str(name),
        "status": normalize_status(status),
        "value": "" if value is None else str(value),
        "evidence": str(evidence or ""),
    }


def category_result(
    category_id: str,
    title: str,
    status: str,
    summary: str,
    metrics: Iterable[Dict[str, str]],
    checks: Iterable[Dict[str, str]],
    recommendations: Iterable[str],
    duration_ms: int,
) -> Dict[str, Any]:
    return {
        "id": category_id,
        "title": title,
        "status": normalize_status(status),
        "summary": str(summary or ""),
        "metrics": list(metrics),
        "checks": list(checks),
        "recommendations": [str(item) for item in recommendations],
        "duration_ms": int(duration_ms),
    }


def empty_category(category_id: str, title: str, message: str, duration_ms: int = 0) -> Dict[str, Any]:
    return category_result(
        category_id,
        title,
        "unknown",
        message,
        [],
        [check("检测项异常", "unknown", message, "collector exception")],
        ["请查看服务端日志或单独执行相关检测命令。"],
        duration_ms,
    )


def summary_counts(categories: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"pass": 0, "warning": 0, "fail": 0, "unknown": 0}
    for item in categories:
        status = normalize_status(str(item.get("status", "unknown")))
        if status == "scanning":
            status = "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def worst_status(statuses: Iterable[str]) -> str:
    order = {"fail": 4, "unknown": 3, "warning": 2, "pass": 1, "scanning": 0}
    normalized: List[str] = [normalize_status(status) for status in statuses]
    if not normalized:
        return "unknown"
    return max(normalized, key=lambda status: order.get(status, 0))
