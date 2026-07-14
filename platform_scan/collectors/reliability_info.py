import os
import time
from typing import Any, Dict, List, Optional

import requests

from config import (
    DISK_WARNING_PERCENT,
    LOAD_WARNING_RATIO,
    MEMORY_WARNING_PERCENT,
    OLLAMA_BASE_URL,
    SCAN_COMMAND_TIMEOUT,
    TEMP_CRITICAL_C,
    TEMP_WARNING_C,
)
from platform_scan.collectors.common import glob_limited, has_default_route, now_ms, read_text
from platform_scan.command_runner import CommandRunner
from platform_scan.schemas import category_result, check, metric


TITLE = "稳定性与实时响应能力"


def _uptime(text: str) -> str:
    try:
        seconds = float(text.split()[0])
    except (ValueError, IndexError):
        return "未知"
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    return "%s 天 %s 小时" % (days, hours)


def _memory_used_percent(meminfo: str) -> Optional[float]:
    values: Dict[str, int] = {}
    for line in meminfo.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            values[parts[0].rstrip(":")] = int(parts[1])
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None
    return (total - available) * 100.0 / total


def _df_root_percent(output: str) -> Optional[float]:
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[-1] == "/":
            value = parts[-2].rstrip("%")
            try:
                return float(value)
            except ValueError:
                return None
    return None


def _temperatures() -> List[float]:
    values: List[float] = []
    for path in glob_limited("/sys/class/thermal/thermal_zone*/temp", 128):
        text, status = read_text(path, max_chars=128)
        if status != "pass" or not text:
            continue
        try:
            raw = float(text.strip())
            values.append(raw / 1000.0 if raw > 1000 else raw)
        except ValueError:
            continue
    return values


def _ollama_latency() -> Optional[int]:
    started = time.monotonic()
    try:
        requests.get(OLLAMA_BASE_URL + "/api/version", timeout=SCAN_COMMAND_TIMEOUT)
        return int((time.monotonic() - started) * 1000)
    except requests.RequestException:
        return None


def collect(runner: CommandRunner, cache: Dict[str, Any]) -> Dict[str, Any]:
    started = time.monotonic()
    checks: List[Dict[str, str]] = []
    metrics: List[Dict[str, str]] = []
    recommendations: List[str] = [
        "飞控内环应由 PX4/ArduPilot/RTOS 承担，Ubuntu 侧仅适合作为软实时上层计算环境。"
    ]

    uptime_text, uptime_status = read_text("/proc/uptime")
    loadavg_text, load_status = read_text("/proc/loadavg")
    meminfo, mem_status = read_text("/proc/meminfo")
    realtime_text, realtime_status = read_text("/sys/kernel/realtime")
    uname = runner.run(["uname", "-a"], timeout=3)
    df = runner.run(["df", "-h"], timeout=3)
    failed_services = runner.run(["systemctl", "--failed", "--no-legend"], timeout=5)
    system_running = runner.run(["systemctl", "is-system-running"], timeout=5)
    ip_route = runner.run(["ip", "route"], timeout=3)

    cpu_count = os.cpu_count() or 1
    try:
        load_1min = float(loadavg_text.split()[0])
        load_ratio = load_1min / cpu_count
    except (ValueError, IndexError):
        load_1min = 0.0
        load_ratio = 0.0
    mem_used = _memory_used_percent(meminfo)
    disk_used = _df_root_percent(df["stdout"]) if df["ok"] else None
    temps = _temperatures()
    max_temp = max(temps) if temps else None
    watchdog = bool(glob_limited("/dev/watchdog*", 16))
    kernel_text = uname["stdout"]
    if realtime_text.strip() == "1" or "PREEMPT_RT" in kernel_text:
        preempt = "PREEMPT_RT"
    elif "PREEMPT_DYNAMIC" in kernel_text:
        preempt = "PREEMPT_DYNAMIC"
    elif "PREEMPT" in kernel_text:
        preempt = "PREEMPT"
    else:
        preempt = "普通内核"
    ollama_latency = _ollama_latency()
    failed_count = len([line for line in failed_services["stdout"].splitlines() if line.strip()]) if failed_services["ok"] else 0
    default_route = has_default_route() or bool(ip_route["ok"] and "default" in ip_route["stdout"])

    metrics.extend(
        [
            metric("系统运行时间", _uptime(uptime_text)),
            metric("CPU负载", "%.2f / 核心比 %.2f" % (load_1min, load_ratio)),
            metric("内存使用率", "%.1f" % mem_used if mem_used is not None else "未知", "%"),
            metric("磁盘使用率", "%.1f" % disk_used if disk_used is not None else "未知", "%"),
            metric("最高温度", "%.1f" % max_temp if max_temp is not None else "未知", "C"),
            metric("Ollama响应", ollama_latency if ollama_latency is not None else "不可达", "ms"),
        ]
    )
    checks.extend(
        [
            check("系统运行时间", "pass" if uptime_text else uptime_status, _uptime(uptime_text), "/proc/uptime"),
            check("CPU负载", "warning" if load_ratio > LOAD_WARNING_RATIO else "pass", "%.2f / %s cores" % (load_1min, cpu_count), "/proc/loadavg"),
            check("内存使用率", "warning" if mem_used is not None and mem_used >= MEMORY_WARNING_PERCENT else ("unknown" if mem_used is None else "pass"), "%.1f%%" % mem_used if mem_used is not None else "未知", "/proc/meminfo"),
            check("磁盘使用率", "warning" if disk_used is not None and disk_used >= DISK_WARNING_PERCENT else ("unknown" if disk_used is None else "pass"), "%.1f%%" % disk_used if disk_used is not None else "未知", "df -h"),
            check("设备温度", "fail" if max_temp is not None and max_temp >= TEMP_CRITICAL_C else ("warning" if max_temp is not None and max_temp >= TEMP_WARNING_C else ("unknown" if max_temp is None else "pass")), "%.1f C" % max_temp if max_temp is not None else "未知", "/sys/class/thermal/thermal_zone*/temp"),
            check("系统失败服务", "warning" if failed_count else ("unknown" if not failed_services["command_available"] else "pass"), "%s 个" % failed_count if failed_services["command_available"] else "systemctl 不可用", "systemctl --failed --no-legend"),
            check("系统运行状态", "pass" if "running" in system_running["stdout"] or "degraded" not in system_running["stdout"] else "warning", system_running["stdout"].strip() if system_running["command_available"] else "systemctl 不可用", "systemctl is-system-running"),
            check("内核抢占模式", "pass" if preempt in {"PREEMPT_RT", "PREEMPT_DYNAMIC", "PREEMPT"} else "warning", preempt, "/sys/kernel/realtime / uname -a"),
            check("watchdog", "pass" if watchdog else "warning", "存在" if watchdog else "未检测到", "/dev/watchdog*"),
            check("Ollama API响应时间", "pass" if ollama_latency is not None else "warning", ollama_latency if ollama_latency is not None else "不可达", "Ollama /api/version"),
            check("网络接口状态", "pass" if default_route else "warning", "默认路由存在" if default_route else "未检测到默认路由", "ip route / /proc/net/route"),
        ]
    )

    check_statuses = [item["status"] for item in checks]
    if "fail" in check_statuses:
        status = "fail"
        summary = "检测到温度或资源等明确异常，需要优先处理。"
    elif "warning" in check_statuses:
        status = "warning"
        summary = "系统可运行，但存在资源、实时性或服务状态方面的注意项。"
    else:
        status = "pass"
        summary = "系统运行状态、资源占用和响应能力处于正常范围。"
    return category_result("reliability", TITLE, status, summary, metrics, checks, recommendations, now_ms(started))
