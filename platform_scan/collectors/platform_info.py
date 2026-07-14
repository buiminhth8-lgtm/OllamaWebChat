import os
import time
from typing import Any, Dict, List

from platform_scan.collectors.common import (
    first_line,
    format_kb,
    now_ms,
    parse_mem_total_kb,
    parse_os_release,
    read_text,
)
from platform_scan.command_runner import CommandRunner
from platform_scan.schemas import category_result, check, metric


TITLE = "核心平台与国产化信息"


def collect(runner: CommandRunner, cache: Dict[str, Any]) -> Dict[str, Any]:
    started = time.monotonic()
    checks: List[Dict[str, str]] = []
    metrics: List[Dict[str, str]] = []
    recommendations: List[str] = []

    compatible, compatible_status = read_text("/proc/device-tree/compatible")
    model, model_status = read_text("/proc/device-tree/model")
    cpuinfo, cpuinfo_status = read_text("/proc/cpuinfo")
    os_release, os_status = read_text("/etc/os-release")
    meminfo, mem_status = read_text("/proc/meminfo")
    uname_m = runner.run(["uname", "-m"])
    uname_r = runner.run(["uname", "-r"])
    hostname = runner.run(["hostname"])
    lscpu = runner.run(["lscpu"])

    cache["cpuinfo"] = cpuinfo
    cache["meminfo"] = meminfo
    cache["os_release"] = os_release

    combined = " ".join([compatible, model, cpuinfo]).lower()
    rk3588 = any(token in combined for token in ["rockchip,rk3588", "rockchip,rk3588s", "rk3588", "rk3588s"])
    arch = first_line(uname_m["stdout"]) if uname_m["ok"] else os.uname().machine if hasattr(os, "uname") else "未知"
    kernel = first_line(uname_r["stdout"]) if uname_r["ok"] else "未知"
    os_name = parse_os_release(os_release) or "未知"
    mem_total = format_kb(parse_mem_total_kb(meminfo))
    cpu_cores = os.cpu_count() or "未知"

    cpu_model = "未知"
    for line in cpuinfo.splitlines():
        if any(line.lower().startswith(key) for key in ["model name", "hardware", "processor"]):
            if ":" in line:
                cpu_model = line.split(":", 1)[1].strip()
                break

    soc = "Rockchip RK3588/RK3588S" if rk3588 else (first_line(model) or "未检测到 RK3588/RK3588S")
    host_value = first_line(hostname["stdout"]) if hostname["ok"] else "未知"

    metrics.extend(
        [
            metric("SoC", soc),
            metric("Architecture", arch),
            metric("CPU cores", cpu_cores),
            metric("Memory total", mem_total),
            metric("OS", os_name),
            metric("Kernel", kernel),
        ]
    )
    checks.extend(
        [
            check("芯片型号", "pass" if rk3588 else "warning", soc, "/proc/device-tree/model"),
            check("设备树兼容信息", compatible_status, "已读取" if compatible else "未读取到", "/proc/device-tree/compatible"),
            check("CPU架构", "pass" if arch in {"aarch64", "arm64"} else "warning", arch, "uname -m"),
            check("CPU核心数量", "pass" if cpu_cores != "未知" else "unknown", cpu_cores, "os.cpu_count"),
            check("CPU型号", "pass" if cpu_model != "未知" else cpuinfo_status, cpu_model, "/proc/cpuinfo"),
            check("操作系统", "pass" if os_name != "未知" else os_status, os_name, "/etc/os-release"),
            check("Linux内核版本", "pass" if kernel != "未知" else "unknown", kernel, "uname -r"),
            check("主机名", "pass" if host_value != "未知" else "unknown", host_value, "hostname"),
            check("内存容量", "pass" if mem_total != "未知" else mem_status, mem_total, "/proc/meminfo"),
            check("lscpu", "pass" if lscpu["ok"] else "warning", "可用" if lscpu["ok"] else "不可用", "lscpu"),
        ]
    )

    if rk3588:
        status = "pass"
        summary = "检测到 Rockchip RK3588/RK3588S，使用国产瑞芯微 SoC；CPU 核心属于 ARM 架构授权。"
    else:
        status = "warning" if any([cpuinfo, os_release, arch != "未知"]) else "unknown"
        summary = "未检测到 RK3588/RK3588S 标识；当前结果仅反映已读取到的系统信息。"
        recommendations.append("如确认为 RK3588，请检查设备树信息是否可由当前系统读取。")

    return category_result("platform", TITLE, status, summary, metrics, checks, recommendations, now_ms(started))
