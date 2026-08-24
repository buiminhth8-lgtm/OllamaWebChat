# Ollama Web Chat

Ollama Web Chat 是面向 Linux / RK3588 设备的 Flask Web 应用，包含：

- Ollama Chat：模型选择、多轮对话、流式输出、停止生成和思考过程展示。
- Ollama 服务管理：持久化安装目录、状态检测和网页按需启动。
- 模型下载：通过 Ollama Pull API 展示 NDJSON 实时进度，完成后自动刷新并选中新模型。
- RK3588 Platform Scan：采集并展示平台能力与运行状态。
- Demo：使用模拟数据展示 RK3588 智能平台能力，不访问真实硬件或 Ollama。

默认 Web 地址为 `http://<device-ip>:3000`，Ollama API 默认为 `http://127.0.0.1:11434`。

## 项目结构

```text
app.py                         Flask 应用入口
routes.py                      Chat、Ollama 管理和模型 API
runtime_settings.py            data/settings.json 持久化配置
ollama_service.py              状态、启动和模型 Pull 服务层
ollama_runner.py               systemd 启动 Ollama 的安全入口
platform_scan/                 RK3588 Platform Scan
demo/                          虚拟演示及模拟数据
templates/                     Chat、Platform Scan、Demo 页面
static/                        页面样式、脚本和本地 ECharts
systemd/                       Web 与 Ollama systemd 模板
script/install_services.sh     正式部署安装脚本
tests/                         unittest 测试
```

## 环境准备

目标系统需要 Python 3、`venv`、systemd 和 sudo。正式部署前，先在仓库根目录创建项目虚拟环境；Python 依赖始终以 `requirements.txt` 为准：

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv

git clone https://github.com/buiminhth8-lgtm/OllamaWebChat.git
cd OllamaWebChat

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

准备适用于设备架构的 Ollama 可执行文件，并确保它具有执行权限。网页配置的安装目录支持以下任一布局：

```text
<install_dir>/ollama
<install_dir>/bin/ollama
```

例如可执行文件是 `/home/lvi/ollama-server/bin/ollama` 时，安装目录可填写 `/home/lvi/ollama-server/bin`，也可填写 `/home/lvi/ollama-server`。

## 开发模式启动

激活虚拟环境后运行：

```bash
source venv/bin/activate
./start.sh
```

也可以直接运行：

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
python3 app.py
```

开发模式不会安装 systemd 单元；如需从网页启动 Ollama，应先完成下方正式部署。可用环境变量包括 `WEB_HOST`、`WEB_PORT`、`OLLAMA_BASE_URL`、`OLLAMA_API_TIMEOUT`、`OLLAMA_START_WAIT_TIMEOUT`、`OLLAMA_PULL_CONNECT_TIMEOUT`、`OLLAMA_PULL_READ_TIMEOUT`、`OLLAMA_REQUEST_TIMEOUT`、`MAX_MESSAGE_CHARS`、`MAX_HISTORY_MESSAGES` 和 `MAX_HISTORY_CHARS`。

页面入口：

```text
Chat：          http://<device-ip>:3000/
Platform Scan：http://<device-ip>:3000/platform
Demo：          http://<device-ip>:3000/demo
```

## 正式部署

安装脚本根据当前仓库路径和执行用户渲染 systemd 单元，因此不要移动已部署的仓库或其中的 `venv`：

```bash
chmod +x script/install_services.sh
./script/install_services.sh
```

安装结果：

```text
ollama-webchat.service
→ enable --now
→ Web 开机自动启动
→ Flask 监听 0.0.0.0:3000

ollama-webchat-ollama.service
→ 明确保持 disabled
→ 不随系统开机自动启动
→ 由网页按需启动
```

Ollama systemd 单元不会写死 Ollama 安装路径。网页保存的配置位于 `data/settings.json`，`ollama_runner.py` 启动时读取该配置、校验可执行文件，然后执行 `ollama serve`。安装脚本还会创建 `/etc/sudoers.d/ollama-webchat`，仅授权部署用户无密码执行固定命令 `systemctl start ollama-webchat-ollama.service`，并在安装前通过 `visudo` 校验。

## Web 使用流程

打开 `http://<device-ip>:3000`：

```text
配置 Ollama 安装目录
→ 保存
→ 检查 Ollama 状态
→ 点击“启动 Ollama”
→ 等待 /api/version Ready
→ 选择已有模型并开始对话
```

也可以直接在“下载模型”中输入：

```text
deepseek-r1:1.5b
→ 下载
→ 查看实时进度
→ 下载成功后模型列表自动刷新并选中新模型
```

配置写入使用同目录临时文件和原子替换；无效路径不会覆盖已有有效配置。`data/settings.json` 是设备私有运行数据，不应提交到 Git。

## 常用维护命令

```bash
systemctl status ollama-webchat.service
systemctl status ollama-webchat-ollama.service

sudo systemctl restart ollama-webchat.service

journalctl -u ollama-webchat.service -f
journalctl -u ollama-webchat-ollama.service -f
```

检查开机自启策略：

```bash
systemctl is-enabled ollama-webchat.service
systemctl is-enabled ollama-webchat-ollama.service
```

预期结果分别为 `enabled` 和 `disabled`（Ollama 单元没有 `[Install]` 段，部分 systemd 版本会显示 `static`）。

## API

主要接口：

```text
GET  /health
GET  /api/config

GET  /api/ollama/config
PUT  /api/ollama/config
GET  /api/ollama/status
POST /api/ollama/start
POST /api/ollama/pull           application/x-ndjson

GET  /api/models
POST /api/chat                  application/x-ndjson

GET  /api/platform/health
GET  /api/platform/latest
POST /api/platform/scan         application/x-ndjson

GET  /api/demo/config
GET  /api/demo/scenario
GET  /api/demo/report
GET  /api/demo/metrics
```

`POST /api/ollama/pull` 请求示例：

```json
{
  "model": "deepseek-r1:1.5b"
}
```

## Platform Scan 与 Demo

Platform Scan 只采集设备能力证据，不安装软件、不修改配置、不启停服务，也不执行压力测试。部分 NPU、温度或系统服务信息因设备能力或权限不足时会显示为 `unknown`。

Demo 的设备状态、性能指标、任务状态和识别结果均来自 `demo/mock_data.py`，仅用于方案展示，不代表真实设备测试结果。Demo API 不读取 `/proc`、`/sys`、`/dev`，不执行系统命令，也不访问 Ollama。

## 测试与静态检查

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall .
node --check static/js/app.js

for script in $(find . -type f -name '*.sh'); do
  bash -n "$script"
done
```

## Troubleshooting

### Ollama 路径无效

确认填写的是目录而不是命令或文件路径，并检查 `<install_dir>/ollama` 或 `<install_dir>/bin/ollama` 存在且可执行：

```bash
ls -l /path/to/install_dir/ollama /path/to/install_dir/bin/ollama
chmod +x /path/to/install_dir/bin/ollama
```

修正后在网页保存配置并刷新状态。

### Ollama 启动失败

查看 Ollama 单元状态和日志：

```bash
systemctl status ollama-webchat-ollama.service
journalctl -u ollama-webchat-ollama.service -n 100 --no-pager
```

同时确认配置文件中的目录有效、二进制与设备架构匹配。

### systemctl 权限问题

网页启动使用非交互 sudo。重新运行安装脚本，并检查最小 sudoers 规则：

```bash
sudo visudo -cf /etc/sudoers.d/ollama-webchat
sudo -n systemctl start ollama-webchat-ollama.service
```

不要将规则扩大为 `NOPASSWD: ALL`。

### 11434 端口占用

```bash
sudo ss -ltnp | grep ':11434'
```

停止冲突进程或服务后，再从网页启动 Ollama。不要同时手工运行多个 `ollama serve`。

### Web service 启动失败

确认仓库未移动、`venv/bin/python` 存在且依赖安装完整：

```bash
systemctl status ollama-webchat.service
journalctl -u ollama-webchat.service -n 100 --no-pager
source venv/bin/activate
pip install -r requirements.txt
```

如仓库路径或部署用户发生变化，重新执行 `./script/install_services.sh` 以重新渲染单元文件。

## 真实设备部署验收

在 Ubuntu / RK3588 设备完成正式部署后，至少执行：

```bash
systemctl is-enabled ollama-webchat.service
systemctl is-enabled ollama-webchat-ollama.service
systemctl status ollama-webchat.service
curl -f http://127.0.0.1:3000/health

sudo reboot
# 重启后再次确认 Web 可访问、Ollama 未自动启动

curl -f http://127.0.0.1:3000/api/ollama/status
# 从网页保存安装目录并启动 Ollama 后：
curl -f http://127.0.0.1:11434/api/version
```

最后在网页下载一个测试模型，确认 NDJSON 进度持续更新、成功后模型列表自动刷新且 Chat 可正常对话；同时回归 `/platform`、`/demo` 和 `/api/models`。
