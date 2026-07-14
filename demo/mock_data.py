import random
from datetime import datetime, timezone
from typing import Any, Dict, List

from demo.schemas import DEMO_DISCLAIMER, demo_response


DEMO_TAGS = ["模拟数据", "虚拟演示", "Demo Mode"]

CAPABILITIES = [
    {"id": "chip", "title": "核心芯片与架构国产化", "score": 92},
    {"id": "llm", "title": "DeepSeek / 通义千问大模型", "score": 88},
    {"id": "cluster", "title": "集群任务协同执行", "score": 90},
    {"id": "vision", "title": "AI目标识别、跟踪与智能决策", "score": 94},
    {"id": "drivers", "title": "底层驱动及算法部署环境", "score": 91},
    {"id": "stability", "title": "系统稳定可靠与实时响应", "score": 89},
]

DEMO_PLATFORM: Dict[str, Any] = {
    "tags": DEMO_TAGS,
    "disclaimer": DEMO_DISCLAIMER,
    "platform": {
        "model": "RK3588 智能计算平台",
        "cpu": "4×Cortex-A76 + 4×Cortex-A55",
        "npu": "6 TOPS",
        "gpu": "Mali-G610",
        "memory": "16 GB",
        "system": "Ubuntu 22.04",
        "kernel": "Linux 5.10 Demo",
        "mode": "虚拟演示",
        "status": "全部模块正常",
    },
    "scores": {
        "核心平台": 92,
        "大模型能力": 88,
        "集群协同": 90,
        "智能推理": 94,
        "驱动环境": 91,
        "稳定性": 89,
    },
    "chip": {
        "modules": ["CPU", "GPU", "NPU", "VPU", "ISP", "DDR", "PCIe", "MIPI CSI", "Ethernet"],
        "table": [
            ["主控芯片", "RK3588", "国产瑞芯微SoC"],
            ["CPU架构", "ARM64", "ARM授权架构"],
            ["CPU核心", "8核", "4大核+4小核"],
            ["NPU算力", "6TOPS", "INT8能力"],
            ["GPU", "Mali-G610", "图形计算"],
            ["视频能力", "8K解码", "虚拟演示参数"],
        ],
        "note": "国产化主要体现为国产SoC、板级方案、驱动适配和系统集成；CPU核心采用ARM授权架构，不表示完全自主CPU指令集。",
    },
    "llm": {
        "models": [
            {
                "name": "DeepSeek-R1-Distill-Qwen-1.5B",
                "quant": "W8A8",
                "device": "RK3588 NPU",
                "first_token_ms": 680,
                "speed": 11.8,
                "context": 4096,
                "memory": "2.3GB",
            },
            {
                "name": "Qwen2.5-1.5B-Instruct",
                "quant": "W8A8",
                "device": "RK3588 NPU",
                "first_token_ms": 640,
                "speed": 12.2,
                "context": 4096,
                "memory": "2.1GB",
            },
            {
                "name": "Qwen3-0.6B",
                "quant": "INT8",
                "device": "RK3588 NPU",
                "first_token_ms": 430,
                "speed": 18.4,
                "context": 2048,
                "memory": "1.1GB",
            },
        ],
        "flow": ["用户问题", "Tokenizer", "DeepSeek / Qwen", "模型推理", "Token流式输出", "应用调用"],
        "answer": "已完成任务理解、航线规划和目标摘要生成。本段为虚拟Token流式输出。",
    },
    "cluster": {
        "mission": "区域巡检任务",
        "uavs": [
            {"id": "UAV-01", "task": "巡检任务", "battery": 86, "lat": 31.2304, "lng": 121.4737, "alt": 120, "latency": 18, "progress": 0, "action": "待命"},
            {"id": "UAV-02", "task": "目标搜索", "battery": 78, "lat": 31.2312, "lng": 121.4761, "alt": 110, "latency": 24, "progress": 0, "action": "待命"},
            {"id": "UAV-03", "task": "区域监控", "battery": 91, "lat": 31.2297, "lng": 121.4715, "alt": 130, "latency": 16, "progress": 0, "action": "待命"},
            {"id": "UAV-04", "task": "等待任务", "battery": 83, "lat": 31.2289, "lng": 121.4744, "alt": 115, "latency": 20, "progress": 0, "action": "待命"},
        ],
        "events": [
            "10:00:01 任务创建",
            "10:00:02 UAV-01 接收任务",
            "10:00:02 UAV-02 接收任务",
            "10:00:03 UAV-03 接收任务",
            "10:00:03 UAV-04 接收任务",
            "10:00:08 UAV-02 通信暂时中断",
            "10:00:09 触发任务重分配",
            "10:00:12 UAV-02 恢复连接",
            "10:00:20 集群任务完成",
        ],
    },
    "vision": {
        "scene": "无人机俯视园区地图",
        "objects": ["车辆", "人员", "无人机", "建筑物"],
        "metrics": {
            "模型": "YOLOv8n-RKNN",
            "跟踪器": "ByteTrack",
            "输入分辨率": "640×640",
            "推理帧率": "25 FPS",
            "NPU负载": "62%",
            "检测目标": "4",
            "当前跟踪目标": "3",
        },
        "decision": ["目标出现", "连续5帧置信度大于0.75", "创建跟踪任务", "目标偏离画面中心", "生成航向修正建议", "上报任务中心"],
    },
    "drivers": [
        ["NPU", "RKNPU", "演示正常", "0.9.8", "/dev/rknpu", "AI推理", "部署RKNN Runtime并固定模型版本"],
        ["图像", "RGA", "演示正常", "1.10", "/dev/rga", "图像缩放转换", "统一图像格式和颜色空间"],
        ["视频", "MPP", "演示正常", "1.0", "/dev/mpp_service", "视频编解码", "按路数配置缓冲区"],
        ["摄像头", "V4L2", "模拟运行", "Demo", "/dev/video0", "视频采集", "实际部署前做相机标定"],
        ["通信", "UART", "虚拟在线", "Demo", "/dev/ttyS4", "MAVLink通信", "隔离飞控串口权限"],
        ["通信", "CAN", "虚拟在线", "Demo", "can0", "总线通信", "配置终端电阻和波特率"],
        ["算法", "RKNN Runtime", "演示正常", "2.x", "Python/C++", "NPU推理", "保持转换工具链一致"],
        ["算法", "RKLLM Runtime", "演示正常", "1.x", "C++", "大模型推理", "结合内存预算选择量化模型"],
        ["图像", "OpenCV", "演示正常", "4.8", "Python/C++", "图像处理", "使用硬件加速路径"],
        ["视频", "FFmpeg", "演示正常", "6.x", "CLI", "视频处理", "限制并发转码任务"],
        ["容器", "Docker", "演示正常", "26.x", "Service", "容器部署", "为NPU设备节点配置映射"],
        ["框架", "ROS 2", "演示正常", "Humble", "Middleware", "机器人通信", "拆分实时链路和上层任务"],
    ],
    "stability": {
        "timeline": ["系统启动完成", "AI服务启动", "任务服务启动", "通信服务上线", "大模型服务就绪", "模拟温度告警", "自动降低推理频率", "温度恢复正常"],
        "note": "该模块为软实时和稳定性策略演示。无人机姿态内环、电机控制和失控保护应由PX4、ArduPilot或RTOS飞控负责。",
    },
}


def get_config() -> Dict[str, Any]:
    return demo_response({"platform": DEMO_PLATFORM, "capabilities": CAPABILITIES})


def get_scenario() -> Dict[str, Any]:
    return demo_response({"capabilities": CAPABILITIES, "scenario": DEMO_PLATFORM})


def get_report() -> Dict[str, Any]:
    return demo_response(
        {
            "report_type": "rk3588-platform-demo-report",
            "demo_time": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "platform": DEMO_PLATFORM["platform"],
            "capabilities": CAPABILITIES,
            "virtual_metrics": DEMO_PLATFORM["scores"],
            "event_log": DEMO_PLATFORM["cluster"]["events"] + DEMO_PLATFORM["stability"]["timeline"],
        }
    )


def get_metrics() -> Dict[str, Any]:
    values = {
        "cpu": random.randint(20, 65),
        "memory": random.randint(45, 70),
        "npu": random.randint(30, 80),
        "temperature": random.randint(55, 76),
        "api_latency": random.randint(15, 60),
        "network_latency": random.randint(8, 45),
        "queue": random.randint(2, 18),
    }
    return demo_response({"metrics": values, "label": "模拟性能数据"})
