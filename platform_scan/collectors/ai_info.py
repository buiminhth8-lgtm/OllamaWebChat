import time
from typing import Any, Dict, List

from config import MODEL_SCAN_DIRS, SCAN_MAX_MODEL_FILES
from platform_scan.collectors.common import glob_limited, module_available, now_ms, read_text, scan_model_files
from platform_scan.command_runner import CommandRunner
from platform_scan.schemas import category_result, check, metric


TITLE = "智能处理与推理能力"


def collect(runner: CommandRunner, cache: Dict[str, Any]) -> Dict[str, Any]:
    started = time.monotonic()
    checks: List[Dict[str, str]] = []
    metrics: List[Dict[str, str]] = []
    recommendations: List[str] = []

    module_names = ["cv2", "numpy", "rknn", "rknnlite", "onnxruntime", "torch"]
    modules = {name: module_available(name) for name in module_names}
    ffmpeg = runner.run(["ffmpeg", "-version"], timeout=3)
    gst = runner.run(["gst-launch-1.0", "--version"], timeout=3)
    v4l2 = runner.run(["v4l2-ctl", "--version"], timeout=3)
    video_devices = glob_limited("/dev/video*", 100)
    media_devices = glob_limited("/dev/media*", 100)
    model_files = scan_model_files(MODEL_SCAN_DIRS, [".rknn", ".onnx", ".tflite", ".pt"], SCAN_MAX_MODEL_FILES, max_depth=3)

    npu_paths = ["/sys/kernel/debug/rknpu/load", "/sys/kernel/debug/rknpu/version", "/proc/rknpu"]
    npu_values = []
    npu_status = "warning"
    for path in npu_paths:
        value, status = read_text(path, max_chars=4096)
        if value:
            npu_values.append("%s:可读" % path)
            npu_status = "pass"
        elif status == "unknown":
            npu_status = "unknown"

    rknn_available = modules["rknn"] or modules["rknnlite"]
    metrics.extend(
        [
            metric("NPU驱动状态", "可读" if npu_values else ("权限不足" if npu_status == "unknown" else "未检测到")),
            metric("RKNN Runtime状态", "已安装" if rknn_available else "未检测到"),
            metric("摄像头数量", len(video_devices)),
            metric("FFmpeg状态", "可用" if ffmpeg["ok"] else "不可用"),
            metric("GStreamer状态", "可用" if gst["ok"] else "不可用"),
            metric("检测模型数量", len(model_files)),
        ]
    )
    checks.extend(
        [
            check("RKNN Runtime", "pass" if rknn_available else "warning", "rknn:%s rknnlite:%s" % (modules["rknn"], modules["rknnlite"]), "importlib.util.find_spec"),
            check("OpenCV", "pass" if modules["cv2"] else "warning", "已安装" if modules["cv2"] else "未安装", "import cv2"),
            check("NumPy", "pass" if modules["numpy"] else "warning", "已安装" if modules["numpy"] else "未安装", "import numpy"),
            check("ONNX Runtime / Torch", "pass" if modules["onnxruntime"] or modules["torch"] else "warning", "onnxruntime:%s torch:%s" % (modules["onnxruntime"], modules["torch"]), "importlib.util.find_spec"),
            check("FFmpeg", "pass" if ffmpeg["ok"] else "warning", ffmpeg["stdout"].splitlines()[0] if ffmpeg["ok"] else "未检测到", "ffmpeg -version"),
            check("GStreamer", "pass" if gst["ok"] else "warning", gst["stdout"].splitlines()[0] if gst["ok"] else "未检测到", "gst-launch-1.0 --version"),
            check("V4L2工具", "pass" if v4l2["ok"] else "warning", v4l2["stdout"].splitlines()[0] if v4l2["ok"] else "未检测到", "v4l2-ctl --version"),
            check("摄像头设备", "pass" if video_devices else "warning", "%s 个 video，%s 个 media" % (len(video_devices), len(media_devices)), "/dev/video* /dev/media*"),
            check("NPU状态", npu_status, ", ".join(npu_values) if npu_values else "未检测到或无权限", "/sys/kernel/debug/rknpu/* /proc/rknpu"),
            check("目标检测模型", "pass" if model_files else "warning", "%s 个模型文件" % len(model_files), "MODEL_SCAN_DIRS"),
        ]
    )

    if npu_status == "pass" and rknn_available:
        status = "pass"
        summary = "检测到 NPU/RKNN 相关运行环境，可支撑 RKNN 类智能推理任务。"
    elif npu_status == "unknown":
        status = "unknown"
        summary = "NPU 信息当前用户无权限读取，其他智能处理组件已按可用性展示。"
        recommendations.append("如需读取 RKNPU debugfs，请确认系统挂载和用户权限。")
    else:
        status = "warning"
        summary = "检测到部分智能处理组件；NPU/RKNN 或模型文件可能尚未部署。"
        recommendations.append("如需 RK3588 NPU 推理，请安装 RKNN Runtime 并在配置目录放置模型文件。")

    return category_result("ai", TITLE, status, summary, metrics, checks, recommendations, now_ms(started))
