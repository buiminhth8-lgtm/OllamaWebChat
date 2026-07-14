import platform
import time
from typing import Any, Dict, List

from platform_scan.collectors.common import glob_limited, module_available, now_ms, read_text
from platform_scan.command_runner import CommandRunner
from platform_scan.schemas import category_result, check, metric


TITLE = "底层驱动与算法环境"


def _first_line(result: Dict[str, Any]) -> str:
    return result["stdout"].splitlines()[0] if result["ok"] and result["stdout"].splitlines() else "未检测到"


def collect(runner: CommandRunner, cache: Dict[str, Any]) -> Dict[str, Any]:
    started = time.monotonic()
    checks: List[Dict[str, str]] = []
    metrics: List[Dict[str, str]] = []
    recommendations: List[str] = []

    lsmod = runner.run(["lsmod"], timeout=3)
    modules_text = lsmod["stdout"].lower()
    devices = {
        "DRM/GPU": glob_limited("/dev/dri/*", 100),
        "RGA": glob_limited("/dev/rga", 10),
        "MPP": glob_limited("/dev/mpp_service", 10),
        "V4L2": glob_limited("/dev/video*", 100),
        "串口": glob_limited("/dev/ttyS*", 100),
        "USB串口": glob_limited("/dev/ttyUSB*", 100) + glob_limited("/dev/ttyACM*", 100),
        "CAN": glob_limited("/dev/can*", 100),
        "I2C": glob_limited("/dev/i2c-*", 100),
        "SPI": glob_limited("/dev/spidev*", 100),
    }

    rknpu_sys, rknpu_sys_status = read_text("/sys/kernel/debug/rknpu/version", max_chars=4096)
    python_version = runner.run(["python3", "--version"], timeout=3)
    gcc = runner.run(["gcc", "--version"], timeout=3)
    cmake = runner.run(["cmake", "--version"], timeout=3)
    docker = runner.run(["docker", "--version"], timeout=3)
    ffmpeg = runner.run(["ffmpeg", "-version"], timeout=3)
    gst = runner.run(["gst-launch-1.0", "--version"], timeout=3)

    rknpu_present = "rknpu" in modules_text or bool(rknpu_sys)
    rga_present = "rga" in modules_text or bool(devices["RGA"])
    v4l2_present = "v4l2" in modules_text or "videobuf" in modules_text or bool(devices["V4L2"])
    can_present = "can" in modules_text or bool(devices["CAN"])

    metrics.extend(
        [
            metric("Python版本", _first_line(python_version) if python_version["ok"] else platform.python_version()),
            metric("OpenCV版本", "已安装" if module_available("cv2") else "未检测到"),
            metric("RKNN组件", "已安装" if module_available("rknn") or module_available("rknnlite") else "未检测到"),
            metric("FFmpeg版本", _first_line(ffmpeg)),
            metric("GStreamer版本", _first_line(gst)),
            metric("Docker版本", _first_line(docker)),
        ]
    )
    checks.extend(
        [
            check("RKNPU", "pass" if rknpu_present else ("unknown" if rknpu_sys_status == "unknown" else "warning"), "检测到" if rknpu_present else "未检测到", "lsmod /sys/kernel/debug/rknpu/version"),
            check("DRM/GPU", "pass" if devices["DRM/GPU"] else "warning", "%s 个节点" % len(devices["DRM/GPU"]), "/dev/dri/*"),
            check("RGA", "pass" if rga_present else "warning", "检测到" if rga_present else "未检测到", "lsmod /dev/rga"),
            check("MPP", "pass" if devices["MPP"] else "warning", "%s 个节点" % len(devices["MPP"]), "/dev/mpp_service"),
            check("V4L2", "pass" if v4l2_present else "warning", "%s 个 video 节点" % len(devices["V4L2"]), "lsmod /dev/video*"),
            check("串口", "pass" if devices["串口"] or devices["USB串口"] else "warning", "ttyS:%s USB:%s" % (len(devices["串口"]), len(devices["USB串口"])), "/dev/ttyS* /dev/ttyUSB* /dev/ttyACM*"),
            check("CAN", "pass" if can_present else "warning", "%s 个节点" % len(devices["CAN"]), "lsmod /dev/can*"),
            check("I2C", "pass" if devices["I2C"] else "warning", "%s 个节点" % len(devices["I2C"]), "/dev/i2c-*"),
            check("SPI", "pass" if devices["SPI"] else "warning", "%s 个节点" % len(devices["SPI"]), "/dev/spidev*"),
            check("网卡", "pass", "通过 /sys/class/net 在协同能力项中展示", "/sys/class/net"),
            check("Docker", "pass" if docker["ok"] else "warning", _first_line(docker), "docker --version"),
            check("Python", "pass" if python_version["ok"] else "warning", _first_line(python_version), "python3 --version"),
            check("GCC", "pass" if gcc["ok"] else "warning", _first_line(gcc), "gcc --version"),
            check("CMake", "pass" if cmake["ok"] else "warning", _first_line(cmake), "cmake --version"),
        ]
    )

    driver_hits = sum(1 for value in [rknpu_present, rga_present, v4l2_present, bool(devices["DRM/GPU"]), bool(devices["I2C"])] if value)
    status = "pass" if driver_hits >= 3 else "warning"
    if status == "warning":
        recommendations.append("部分底层设备节点或开发工具未检测到；如为普通 x86 开发环境，可视为不适用。")
    summary = "检测到底层驱动节点和算法部署工具链。" if status == "pass" else "底层驱动或算法工具链仅部分可见。"
    return category_result("driver", TITLE, status, summary, metrics, checks, recommendations, now_ms(started))
