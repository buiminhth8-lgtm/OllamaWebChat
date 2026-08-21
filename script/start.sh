#!/bin/bash

# 启动 ollama serve
cd ~/ollama-server/bin || exit 1
export OLLAMA_HOST=0.0.0.0:11434
nohup ./ollama serve >> /var/log/ollama.log 2>&1 &

# 等待 ollama 完全启动（可根据需要调整等待时间，或检测端口）
sleep 5

# 启动 Python Web 服务
cd ~/OllamaWebChat || exit 1
export OLLAMA_BASE_URL=http://127.0.0.1:11434
nohup python3 app.py >> /var/log/webchat.log 2>&1 &