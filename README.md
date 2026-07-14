# Ollama Web Chat

简单的 Flask Ollama 网页客户端，支持模型切换、多轮对话、流式输出、停止生成、思考过程显示、历史裁剪、清空对话、局域网访问，以及 RK3588 智能计算平台能力检测。

## 项目结构

```text
app.py                         # Flask 应用入口
config.py                      # 环境变量配置
routes.py                      # AI 对话页面和 API 路由
templates/index.html           # AI 对话页面
templates/platform.html        # RK3588 平台能力检测页面
static/css/app.css             # 通用和对话页面样式
static/css/platform.css        # 平台检测页面样式
static/js/app.js               # AI 对话前端交互
static/js/platform.js          # 平台检测前端交互
platform_scan/                 # 平台扫描后端模块
tests/                         # 标准库 unittest 测试
```

## 安装

兼容 Python 3.8+，Ubuntu 20.04 自带的 Python 3.8.2 可直接使用。

```bash
cd OllamaWebChat
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 启动

Ollama 默认端口 11434：

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
python3 app.py
```

也可以使用启动脚本：

```bash
./start.sh
```

页面地址：

```text
AI 对话：http://127.0.0.1:3000/
RK3588 平台能力检测：http://127.0.0.1:3000/platform
```

其他电脑访问：

```text
http://Debian服务器IP:3000
```

## AI 对话配置

```bash
export WEB_HOST=0.0.0.0
export WEB_PORT=3000
export OLLAMA_REQUEST_TIMEOUT=600
export MAX_MESSAGE_CHARS=8000
export MAX_HISTORY_MESSAGES=40
export MAX_HISTORY_CHARS=24000
```

历史清理策略：

- 单条消息超过 `MAX_MESSAGE_CHARS` 会保留尾部内容，并加上裁剪提示。
- 对话超过 `MAX_HISTORY_MESSAGES` 会保留最近的消息。
- 对话总长度超过 `MAX_HISTORY_CHARS` 会继续从最早消息开始清理。
- 模型输出中的 `<think>...</think>` 会在页面里显示为可折叠的“思考过程”，不会作为助手正文继续发送给 Ollama。

## RK3588 平台能力检测

页面地址：

```text
/platform
```

六项检测内容：

```text
1. 核心平台与国产化信息
2. 大模型部署与调用能力
3. 集群任务协同能力
4. 智能处理与推理能力
5. 底层驱动与算法环境
6. 稳定性与实时响应能力
```

新增环境变量：

```bash
export MODEL_SCAN_DIRS=/opt/uav/models,/userdata/models,/home/zkjr/models
export PLATFORM_SCAN_RESULT_PATH=data/platform_scan_latest.json
export SCAN_COMMAND_TIMEOUT=5
export SCAN_MAX_OUTPUT_CHARS=65536
export SCAN_MAX_MODEL_FILES=200
export TEMP_WARNING_C=75
export TEMP_CRITICAL_C=85
export DISK_WARNING_PERCENT=85
export MEMORY_WARNING_PERCENT=85
export LOAD_WARNING_RATIO=1.5
```

检测结果状态：

```text
pass     正常
warning  部分满足
fail     异常
unknown  未知
scanning 检测中
```

扫描权限说明：

- 该页面用于采集和展示设备能力证据，不等同于产品认证或安全认证。
- 未安装、无权限和未配置会被区分展示。
- 系统扫描不会安装软件、修改配置、启动服务或停止服务。
- 默认不会触发大模型推理，不会执行压力测试，不会启动摄像头。
- 某些 NPU、温度或系统服务信息可能需要更高权限；无权限时显示 `unknown`。

## API

```text
GET  /health
GET  /api/platform/health
GET  /api/platform/latest
POST /api/platform/scan
```

`POST /api/platform/scan` 返回 `application/x-ndjson; charset=utf-8`，页面会按检测进度实时更新六项结果。

## 测试

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall app.py config.py routes.py platform_scan
```

手工验证：

```bash
curl http://127.0.0.1:3000/health
curl http://127.0.0.1:3000/api/platform/health
curl http://127.0.0.1:3000/api/platform/latest
curl -N -X POST http://127.0.0.1:3000/api/platform/scan
```

## 后台运行

```bash
nohup env OLLAMA_BASE_URL=http://127.0.0.1:11434 python3 app.py > ollama-web-chat.log 2>&1 &
```

关闭：

```bash
pkill -f "python3 app.py"
```
