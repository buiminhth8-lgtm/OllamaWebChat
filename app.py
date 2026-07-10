#!/usr/bin/env python3
import json
import os
from typing import Iterator

import requests
from flask import Flask, Response, jsonify, render_template_string, request

app = Flask(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "600"))

HTML = r'''
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Ollama Web Chat</title>
  <style>
    :root { color-scheme: light dark; --bg:#f4f6f8; --panel:#fff; --text:#1f2937; --muted:#6b7280; --border:#d1d5db; --primary:#2563eb; --user:#dbeafe; --assistant:#f3f4f6; --danger:#dc2626; }
    @media (prefers-color-scheme: dark) { :root { --bg:#111827; --panel:#1f2937; --text:#f9fafb; --muted:#9ca3af; --border:#374151; --primary:#60a5fa; --user:#1e3a8a; --assistant:#374151; --danger:#f87171; } }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif; }
    .app { width:min(980px,100%); height:100vh; margin:0 auto; display:grid; grid-template-rows:auto 1fr auto; background:var(--panel); border-left:1px solid var(--border); border-right:1px solid var(--border); }
    header { display:flex; gap:12px; align-items:center; flex-wrap:wrap; padding:14px 16px; border-bottom:1px solid var(--border); }
    header h1 { margin:0; font-size:18px; white-space:nowrap; }
    .toolbar { display:flex; gap:8px; align-items:center; flex:1; min-width:260px; }
    select,button,textarea { font:inherit; }
    select { min-width:220px; max-width:100%; padding:9px 10px; border:1px solid var(--border); border-radius:8px; background:var(--panel); color:var(--text); }
    button { border:0; border-radius:8px; padding:9px 14px; cursor:pointer; }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .primary { background:var(--primary); color:white; }
    .secondary { background:transparent; color:var(--text); border:1px solid var(--border); }
    #status { margin-left:auto; font-size:13px; color:var(--muted); }
    #messages { overflow-y:auto; padding:20px 16px 36px; }
    .message { max-width:86%; margin:0 0 14px; padding:12px 14px; border-radius:12px; line-height:1.6; white-space:pre-wrap; overflow-wrap:anywhere; }
    .message.user { margin-left:auto; background:var(--user); }
    .message.assistant { margin-right:auto; background:var(--assistant); }
    .role { display:block; margin-bottom:5px; font-size:12px; font-weight:700; color:var(--muted); }
    .error { color:var(--danger); }
    footer { border-top:1px solid var(--border); padding:12px 16px 16px; }
    .input-row { display:grid; grid-template-columns:1fr auto; gap:10px; align-items:end; }
    textarea { width:100%; min-height:54px; max-height:180px; resize:vertical; padding:12px; border:1px solid var(--border); border-radius:10px; background:var(--panel); color:var(--text); }
    .hint { margin-top:7px; font-size:12px; color:var(--muted); }
    @media (max-width:640px) { .app{border:0}.message{max-width:94%}.input-row{grid-template-columns:1fr}.input-row button{width:100%}#status{width:100%;margin-left:0} }
  </style>
</head>
<body>
<div class="app">
  <header>
    <h1>Ollama Web Chat</h1>
    <div class="toolbar">
      <select id="modelSelect"><option value="">正在加载模型...</option></select>
      <button id="refreshModels" class="secondary" type="button">刷新模型</button>
      <button id="clearChat" class="secondary" type="button">清空对话</button>
    </div>
    <span id="status">未连接</span>
  </header>
  <main id="messages"></main>
  <footer>
    <form id="chatForm">
      <div class="input-row">
        <textarea id="prompt" placeholder="输入消息。Enter 发送，Shift+Enter 换行。" required></textarea>
        <button id="sendButton" class="primary" type="submit">发送</button>
      </div>
      <div class="hint">对话记录保存在当前浏览器中，并随请求发送给 Ollama。</div>
    </form>
  </footer>
</div>
<script>
const modelSelect=document.getElementById('modelSelect');
const refreshModelsButton=document.getElementById('refreshModels');
const clearChatButton=document.getElementById('clearChat');
const chatForm=document.getElementById('chatForm');
const promptInput=document.getElementById('prompt');
const sendButton=document.getElementById('sendButton');
const messagesContainer=document.getElementById('messages');
const statusElement=document.getElementById('status');
let messages=loadMessages();
let abortController=null;
function loadMessages(){try{return JSON.parse(localStorage.getItem('ollama_web_chat_messages')||'[]')}catch{return[]}}
function saveMessages(){localStorage.setItem('ollama_web_chat_messages',JSON.stringify(messages))}
function scrollToBottom(){messagesContainer.scrollTop=messagesContainer.scrollHeight}
function appendMessageElement(role,content=''){const wrapper=document.createElement('div');wrapper.className=`message ${role}`;const roleEl=document.createElement('span');roleEl.className='role';roleEl.textContent=role==='user'?'你':'Ollama';const contentEl=document.createElement('div');contentEl.textContent=content;wrapper.append(roleEl,contentEl);messagesContainer.appendChild(wrapper);scrollToBottom();return contentEl}
function renderMessages(){messagesContainer.innerHTML='';for(const m of messages)appendMessageElement(m.role,m.content);scrollToBottom()}
function setBusy(busy){sendButton.disabled=busy;modelSelect.disabled=busy;refreshModelsButton.disabled=busy;clearChatButton.disabled=busy;sendButton.textContent=busy?'生成中...':'发送'}
async function loadModels(){statusElement.classList.remove('error');statusElement.textContent='正在连接 Ollama...';try{const response=await fetch('/api/models');const result=await response.json();if(!response.ok)throw new Error(result.error||'读取模型列表失败');const current=modelSelect.value||localStorage.getItem('ollama_web_chat_model')||'';modelSelect.innerHTML='';const models=result.models||[];if(models.length===0){const option=document.createElement('option');option.value='';option.textContent='未发现本地模型';modelSelect.appendChild(option)}else{for(const model of models){const option=document.createElement('option');option.value=model.name;option.textContent=model.name;modelSelect.appendChild(option)}if(models.some(x=>x.name===current))modelSelect.value=current}statusElement.textContent=`已连接，共 ${models.length} 个模型`}catch(error){modelSelect.innerHTML='<option value="">连接失败</option>';statusElement.textContent=error.message;statusElement.classList.add('error')}}
async function sendMessage(text){const model=modelSelect.value;if(!model){alert('请先安装并选择一个 Ollama 模型。');return}statusElement.classList.remove('error');messages.push({role:'user',content:text});appendMessageElement('user',text);const assistantMessage={role:'assistant',content:''};messages.push(assistantMessage);const assistantEl=appendMessageElement('assistant','');saveMessages();setBusy(true);statusElement.textContent=`正在使用 ${model} 生成...`;abortController=new AbortController();try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},signal:abortController.signal,body:JSON.stringify({model,messages:messages.slice(0,-1)})});if(!response.ok){const result=await response.json().catch(()=>({}));throw new Error(result.error||`请求失败：HTTP ${response.status}`)}if(!response.body)throw new Error('浏览器不支持流式响应');const reader=response.body.getReader();const decoder=new TextDecoder('utf-8');let buffer='';while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const lines=buffer.split('\n');buffer=lines.pop()||'';for(const line of lines){if(!line.trim())continue;const chunk=JSON.parse(line);if(chunk.error)throw new Error(chunk.error);const content=chunk.message?.content||'';if(content){assistantMessage.content+=content;assistantEl.textContent=assistantMessage.content;scrollToBottom()}}}if(buffer.trim()){const chunk=JSON.parse(buffer);assistantMessage.content+=chunk.message?.content||'';assistantEl.textContent=assistantMessage.content}saveMessages();statusElement.textContent=`完成 · ${model}`}catch(error){if(error.name==='AbortError'){statusElement.textContent='已取消'}else{const msg=`请求失败：${error.message}`;assistantMessage.content=msg;assistantEl.textContent=msg;assistantEl.classList.add('error');statusElement.textContent=msg;statusElement.classList.add('error');saveMessages()}}finally{abortController=null;setBusy(false);promptInput.focus()}}
chatForm.addEventListener('submit',async e=>{e.preventDefault();const text=promptInput.value.trim();if(!text||sendButton.disabled)return;promptInput.value='';await sendMessage(text)});
promptInput.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();chatForm.requestSubmit()}});
modelSelect.addEventListener('change',()=>localStorage.setItem('ollama_web_chat_model',modelSelect.value));
refreshModelsButton.addEventListener('click',loadModels);
clearChatButton.addEventListener('click',()=>{if(abortController)abortController.abort();messages=[];saveMessages();renderMessages();statusElement.textContent='对话已清空'});
renderMessages();loadModels();promptInput.focus();
</script>
</body>
</html>
'''

@app.get("/")
def index():
    return render_template_string(HTML)

@app.get("/health")
def health():
    return jsonify({"ok": True, "ollama_base_url": OLLAMA_BASE_URL})

@app.get("/api/models")
def models():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=20)
        response.raise_for_status()
        data = response.json()
        return jsonify({"models": [{"name": x.get("name") or x.get("model"), "size": x.get("size"), "modified_at": x.get("modified_at")} for x in data.get("models", []) if x.get("name") or x.get("model")]})
    except requests.RequestException as exc:
        return jsonify({"error": f"无法连接 Ollama：{exc}", "ollama_base_url": OLLAMA_BASE_URL}), 502

def stream_ollama_chat(payload: dict) -> Iterator[str]:
    try:
        with requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": payload["model"], "messages": payload["messages"], "stream": True},
            stream=True,
            timeout=(15, REQUEST_TIMEOUT),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    yield line + b"\n"
    except requests.RequestException as exc:
        yield json.dumps({"error": f"Ollama 请求失败：{exc}"}, ensure_ascii=False) + "\n"

@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    model = str(payload.get("model", "")).strip()
    messages = payload.get("messages")
    if not model:
        return jsonify({"error": "缺少 model 参数"}), 400
    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "messages 必须是非空数组"}), 400
    cleaned = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role in {"system", "user", "assistant"} and isinstance(content, str):
            cleaned.append({"role": role, "content": content})
    if not cleaned:
        return jsonify({"error": "没有有效的对话消息"}), 400
    return Response(
        stream_ollama_chat({"model": model, "messages": cleaned}),
        content_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

if __name__ == "__main__":
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "3000"))
    app.run(host=host, port=port, threaded=True)
