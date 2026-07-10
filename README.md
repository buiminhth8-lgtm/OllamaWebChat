# Ollama Web Chat

简单的 Flask Ollama 网页客户端，支持模型切换、多轮对话、流式输出、停止生成、思考过程显示、历史裁剪、清空对话和局域网访问。

## 项目结构

```text
app.py                 # Flask 应用入口
config.py              # 环境变量配置
routes.py              # 页面和 API 路由
templates/index.html   # 页面模板
static/css/app.css     # 页面样式
static/js/app.js       # 前端交互逻辑
```

## 安装

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

如果 Ollama 使用 1143：

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:1143
python3 app.py
```

也可以使用启动脚本：

```bash
./start.sh
```

其他电脑访问：

```text
http://Debian服务器IP:3000
```

防火墙放行：

```bash
sudo ufw allow 3000/tcp
```

## 可选配置

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

## 后台运行

```bash
nohup env OLLAMA_BASE_URL=http://127.0.0.1:11434 python3 app.py > ollama-web-chat.log 2>&1 &
```

关闭：

```bash
pkill -f "python3 app.py"
```
