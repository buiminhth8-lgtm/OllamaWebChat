import sys
import time
from typing import Any, Dict, List

from platform_scan.collectors.common import (
    has_default_route,
    list_process_names,
    module_available,
    network_interfaces,
    now_ms,
    parse_ip_addr,
    process_exists,
)
from platform_scan.command_runner import CommandRunner
from platform_scan.schemas import category_result, check, metric


TITLE = "集群任务协同能力"


def _module_value(names: List[str]) -> str:
    installed = [name for name in names if module_available(name)]
    return ", ".join(installed) if installed else "未检测到"


def collect(runner: CommandRunner, cache: Dict[str, Any]) -> Dict[str, Any]:
    started = time.monotonic()
    checks: List[Dict[str, str]] = []
    metrics: List[Dict[str, str]] = []
    recommendations: List[str] = [
        "已安装组件不等同于集群协同已完成，进程运行也不代表多机通信一定正常。"
    ]
    process_names = cache.setdefault("process_names", list_process_names())

    ros_distro = runner.run(["printenv", "ROS_DISTRO"], timeout=3)
    ros2_help = runner.run(["ros2", "--help"], timeout=3)
    docker_version = runner.run(["docker", "--version"], timeout=3)
    mosquitto = runner.run(["systemctl", "is-active", "mosquitto"], timeout=3)
    mavlink_router = runner.run(["systemctl", "is-active", "mavlink-router"], timeout=3)
    mavlink_routerd = runner.run(["systemctl", "is-active", "mavlink-routerd"], timeout=3)
    ip_addr = runner.run(["ip", "-o", "-4", "addr", "show"], timeout=3)
    ss_ports = runner.run(["ss", "-ltnu"], timeout=3)

    mavlink_modules = _module_value(["mavsdk", "pymavlink"])
    ros_modules = _module_value(["rclpy"])
    mqtt_modules = _module_value(["paho.mqtt"])
    grpc_modules = _module_value(["grpc"])
    interfaces = network_interfaces()
    ipv4_items = parse_ip_addr(ip_addr["stdout"]) if ip_addr["ok"] else []
    default_route = has_default_route()
    cluster_proc = process_exists(["mavlink-router", "mavproxy", "ros2", "micro-ros-agent", "mosquitto", "task-agent", "cluster-agent"], process_names)
    listening_count = len([line for line in ss_ports["stdout"].splitlines() if line.strip()]) - 1 if ss_ports["ok"] else 0

    ros_value = ros_distro["stdout"].strip() if ros_distro["ok"] else ("ros2 可用" if ros2_help["ok"] else "未检测到")
    mqtt_status = mosquitto["stdout"].strip() if mosquitto["command_available"] else "未安装或不可用"
    mav_status = "active" if mavlink_router["stdout"].strip() == "active" or mavlink_routerd["stdout"].strip() == "active" else "未运行"

    metrics.extend(
        [
            metric("ROS_DISTRO", ros_value),
            metric("MAVLink组件", mavlink_modules if mavlink_modules != "未检测到" else mav_status),
            metric("MQTT状态", mqtt_status if mqtt_status else mqtt_modules),
            metric("集群Agent状态", "运行中" if cluster_proc else "未检测到"),
            metric("网络接口数量", len(interfaces)),
            metric("监听端口数量", max(0, listening_count)),
        ]
    )
    checks.extend(
        [
            check("ROS 2", "pass" if ros_distro["ok"] or ros2_help["ok"] or ros_modules != "未检测到" else "warning", ros_value, "printenv ROS_DISTRO / ros2 --help / import rclpy"),
            check("MAVLink / MAVSDK / MAVROS", "pass" if mavlink_modules != "未检测到" or mav_status == "active" else "warning", mavlink_modules if mavlink_modules != "未检测到" else mav_status, "Python modules / systemctl is-active mavlink-router"),
            check("MQTT", "pass" if mosquitto["stdout"].strip() == "active" or mqtt_modules != "未检测到" else "warning", mqtt_status or mqtt_modules, "systemctl is-active mosquitto / import paho.mqtt"),
            check("Docker", "pass" if docker_version["ok"] else "warning", docker_version["stdout"].splitlines()[0] if docker_version["ok"] else "未检测到", "docker --version"),
            check("Python协同模块", "pass" if any(module_available(name) for name in ["mavsdk", "pymavlink", "rclpy", "paho.mqtt", "grpc"]) else "warning", "MAVLink:%s ROS:%s MQTT:%s gRPC:%s" % (mavlink_modules, ros_modules, mqtt_modules, grpc_modules), "importlib.util.find_spec"),
            check("网络接口", "pass" if interfaces else "unknown", ", ".join(item["name"] + ":" + item["state"] for item in interfaces[:8]) if interfaces else "未检测到", "/sys/class/net"),
            check("IPv4地址", "pass" if ipv4_items else "warning", ", ".join(item["name"] + "=" + item["ipv4"] for item in ipv4_items[:8]) if ipv4_items else "未检测到", "ip -o -4 addr show"),
            check("默认网关", "pass" if default_route else "warning", "存在" if default_route else "未检测到", "/proc/net/route"),
            check("集群相关进程", "pass" if cluster_proc else "warning", "检测到" if cluster_proc else "未检测到", "/proc/*/comm"),
            check("监听端口", "pass" if listening_count > 0 else "warning", max(0, listening_count), "ss -ltnu"),
        ]
    )

    strong = sum(1 for item in [ros_distro["ok"] or ros2_help["ok"], mavlink_modules != "未检测到", mosquitto["stdout"].strip() == "active" or mqtt_modules != "未检测到", default_route] if item)
    status = "pass" if strong >= 3 and cluster_proc else "warning"
    summary = "检测到部分集群协同组件；需结合业务配置验证多机任务链路。" if status == "warning" else "检测到 ROS/MAVLink/MQTT/网络等多项协同组件和运行证据。"
    return category_result("cluster", TITLE, status, summary, metrics, checks, recommendations, now_ms(started))
