# Ollama Web Chat

简单的 Flask Ollama 网页客户端，支持模型切换、多轮对话、流式输出、清空对话和局域网访问。

## 安装

```bash
cd ollama_web_chat
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

其他电脑访问：

```text
http://Debian服务器IP:3000
```

防火墙放行：

```bash
sudo ufw allow 3000/tcp
```

后台运行：

```bash
nohup env OLLAMA_BASE_URL=http://127.0.0.1:11434 python3 app.py > ollama-web-chat.log 2>&1 &
```

关闭：

```bash
pkill -f "python3 app.py"
```
