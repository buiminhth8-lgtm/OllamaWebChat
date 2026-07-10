const DEFAULT_CONFIG = {
  maxMessageChars: 8000,
  maxHistoryMessages: 40,
  maxHistoryChars: 24000,
};

const modelSelect = document.getElementById("modelSelect");
const refreshModelsButton = document.getElementById("refreshModels");
const clearChatButton = document.getElementById("clearChat");
const chatForm = document.getElementById("chatForm");
const promptInput = document.getElementById("prompt");
const sendButton = document.getElementById("sendButton");
const stopButton = document.getElementById("stopButton");
const messagesContainer = document.getElementById("messages");
const statusElement = document.getElementById("status");

let appConfig = { ...DEFAULT_CONFIG };
let messages = loadMessages();
let abortController = null;
let sideChannelThinking = "";

function toClientConfig(serverConfig) {
  return {
    maxMessageChars: Number(serverConfig.max_message_chars) || DEFAULT_CONFIG.maxMessageChars,
    maxHistoryMessages: Number(serverConfig.max_history_messages) || DEFAULT_CONFIG.maxHistoryMessages,
    maxHistoryChars: Number(serverConfig.max_history_chars) || DEFAULT_CONFIG.maxHistoryChars,
  };
}

function loadMessages() {
  try {
    const loaded = JSON.parse(localStorage.getItem("ollama_web_chat_messages") || "[]");
    return Array.isArray(loaded) ? loaded : [];
  } catch {
    return [];
  }
}

function saveMessages() {
  messages = compactMessages(messages);
  localStorage.setItem("ollama_web_chat_messages", JSON.stringify(messages));
}

function totalContentLength(items) {
  return items.reduce((total, item) => total + (item.content?.length || 0) + (item.thinking?.length || 0), 0);
}

function trimText(text, limit = appConfig.maxMessageChars) {
  if (text.length <= limit) return text;
  const prefix = "[已裁剪前文]\n";
  const keep = Math.max(0, limit - prefix.length);
  if (!keep) return text.slice(-limit);
  return prefix + text.slice(-keep);
}

function normalizeMessage(message) {
  if (!message || typeof message !== "object") return null;
  if (!["system", "user", "assistant"].includes(message.role)) return null;
  const content = typeof message.content === "string" ? trimText(message.content.trim()) : "";
  const thinking = typeof message.thinking === "string" ? trimText(message.thinking.trim()) : "";
  if (!content && !thinking) return null;
  return { role: message.role, content, thinking };
}

function compactMessages(items) {
  let compacted = items.map(normalizeMessage).filter(Boolean);
  if (compacted.length > appConfig.maxHistoryMessages) {
    compacted = compacted.slice(-appConfig.maxHistoryMessages);
  }
  while (compacted.length > 1 && totalContentLength(compacted) > appConfig.maxHistoryChars) {
    compacted.shift();
  }
  return compacted;
}

function requestMessages() {
  const compacted = compactMessages(messages);
  return compacted
    .filter((message) => message.content)
    .map((message) => ({ role: message.role, content: message.content }));
}

function scrollToBottom() {
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function splitThinking(raw) {
  const thinkBlocks = [];
  let answer = "";
  let cursor = 0;
  const lower = raw.toLowerCase();

  while (cursor < raw.length) {
    const start = lower.indexOf("<think>", cursor);
    if (start === -1) {
      answer += raw.slice(cursor);
      break;
    }

    answer += raw.slice(cursor, start);
    const contentStart = start + "<think>".length;
    const end = lower.indexOf("</think>", contentStart);
    if (end === -1) {
      thinkBlocks.push(raw.slice(contentStart));
      break;
    }

    thinkBlocks.push(raw.slice(contentStart, end));
    cursor = end + "</think>".length;
  }

  return {
    content: answer.trimStart(),
    thinking: thinkBlocks.join("\n\n").trim(),
  };
}

function mergeThinking(...parts) {
  return parts
    .map((part) => part.trim())
    .filter(Boolean)
    .join("\n\n");
}

function applyAssistantText(assistantMessage, rawAssistantText) {
  const parsed = splitThinking(rawAssistantText);
  assistantMessage.content = parsed.content;
  assistantMessage.thinking = mergeThinking(sideChannelThinking, parsed.thinking);
}

function createAssistantParts(wrapper) {
  const thinkingEl = document.createElement("details");
  thinkingEl.className = "thinking";
  thinkingEl.open = true;
  thinkingEl.hidden = true;

  const summaryEl = document.createElement("summary");
  summaryEl.textContent = "思考过程";
  const thinkingContentEl = document.createElement("div");
  thinkingContentEl.className = "thinking-content";
  thinkingEl.append(summaryEl, thinkingContentEl);

  const answerEl = document.createElement("div");
  answerEl.className = "answer";
  wrapper.append(thinkingEl, answerEl);

  return { thinkingEl, thinkingContentEl, answerEl };
}

function updateAssistantElement(parts, message) {
  parts.thinkingContentEl.textContent = message.thinking || "";
  parts.thinkingEl.hidden = !message.thinking;
  parts.answerEl.textContent = message.content || "";
  scrollToBottom();
}

function appendMessageElement(role, content = "", thinking = "") {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;

  const roleEl = document.createElement("span");
  roleEl.className = "role";
  roleEl.textContent = role === "user" ? "你" : "Ollama";
  wrapper.appendChild(roleEl);

  let parts = null;
  if (role === "assistant") {
    parts = createAssistantParts(wrapper);
    updateAssistantElement(parts, { content, thinking });
  } else {
    const contentEl = document.createElement("div");
    contentEl.textContent = content;
    wrapper.appendChild(contentEl);
  }

  messagesContainer.appendChild(wrapper);
  scrollToBottom();
  return { wrapper, parts };
}

function renderMessages() {
  messages = compactMessages(messages);
  messagesContainer.innerHTML = "";
  for (const message of messages) {
    appendMessageElement(message.role, message.content, message.thinking);
  }
  scrollToBottom();
}

function setStatus(text, isError = false) {
  statusElement.textContent = text;
  statusElement.classList.toggle("error", isError);
}

function setBusy(busy) {
  sendButton.disabled = busy;
  stopButton.disabled = !busy;
  modelSelect.disabled = busy;
  refreshModelsButton.disabled = busy;
  clearChatButton.disabled = busy;
  sendButton.textContent = busy ? "生成中..." : "发送";
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) return;
    appConfig = toClientConfig(await response.json());
    renderMessages();
    saveMessages();
  } catch {
    appConfig = { ...DEFAULT_CONFIG };
  }
}

async function loadModels() {
  setStatus("正在连接 Ollama...");
  try {
    const response = await fetch("/api/models");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "读取模型列表失败");

    const current = modelSelect.value || localStorage.getItem("ollama_web_chat_model") || "";
    modelSelect.innerHTML = "";
    const models = result.models || [];

    if (models.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "未发现本地模型";
      modelSelect.appendChild(option);
    } else {
      for (const model of models) {
        const option = document.createElement("option");
        option.value = model.name;
        option.textContent = model.name;
        modelSelect.appendChild(option);
      }
      if (models.some((model) => model.name === current)) {
        modelSelect.value = current;
      }
    }

    setStatus(`已连接，共 ${models.length} 个模型`);
  } catch (error) {
    modelSelect.innerHTML = '<option value="">连接失败</option>';
    setStatus(error.message, true);
  }
}

function stopGeneration() {
  if (abortController) {
    abortController.abort();
  }
}

async function sendMessage(text) {
  const model = modelSelect.value;
  if (!model) {
    alert("请先安装并选择一个 Ollama 模型。");
    return;
  }

  const cleanText = trimText(text.trim());
  if (cleanText !== text.trim()) {
    setStatus(`消息过长，已裁剪到 ${appConfig.maxMessageChars} 字`);
  } else {
    setStatus("");
  }

  messages.push({ role: "user", content: cleanText, thinking: "" });
  messages = compactMessages(messages);
  renderMessages();
  saveMessages();

  const assistantMessage = { role: "assistant", content: "", thinking: "" };
  messages.push(assistantMessage);
  const assistantView = appendMessageElement("assistant", "", "");

  setBusy(true);
  setStatus(`正在使用 ${model} 生成...`);
  abortController = new AbortController();
  sideChannelThinking = "";

  let rawAssistantText = "";
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: abortController.signal,
      body: JSON.stringify({ model, messages: requestMessages() }),
    });

    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || `请求失败：HTTP ${response.status}`);
    }
    if (!response.body) throw new Error("浏览器不支持流式响应");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        const chunk = JSON.parse(line);
        if (chunk.error) throw new Error(chunk.error);
        sideChannelThinking += chunk.message?.thinking || chunk.thinking || "";
        rawAssistantText += chunk.message?.content || "";
        applyAssistantText(assistantMessage, rawAssistantText);
        updateAssistantElement(assistantView.parts, assistantMessage);
      }
    }

    if (buffer.trim()) {
      const chunk = JSON.parse(buffer);
      sideChannelThinking += chunk.message?.thinking || chunk.thinking || "";
      rawAssistantText += chunk.message?.content || "";
      applyAssistantText(assistantMessage, rawAssistantText);
      updateAssistantElement(assistantView.parts, assistantMessage);
    }

    saveMessages();
    setStatus(`完成 · ${model}`);
  } catch (error) {
    if (error.name === "AbortError") {
      saveMessages();
      setStatus("已停止生成");
    } else {
      const msg = `请求失败：${error.message}`;
      assistantMessage.content = msg;
      assistantMessage.thinking = "";
      updateAssistantElement(assistantView.parts, assistantMessage);
      assistantView.wrapper.classList.add("error");
      setStatus(msg, true);
      saveMessages();
    }
  } finally {
    abortController = null;
    setBusy(false);
    promptInput.focus();
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = promptInput.value.trim();
  if (!text || sendButton.disabled) return;
  promptInput.value = "";
  await sendMessage(text);
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

modelSelect.addEventListener("change", () => localStorage.setItem("ollama_web_chat_model", modelSelect.value));
refreshModelsButton.addEventListener("click", loadModels);
stopButton.addEventListener("click", stopGeneration);
clearChatButton.addEventListener("click", () => {
  stopGeneration();
  messages = [];
  saveMessages();
  renderMessages();
  setStatus("对话已清空");
});

renderMessages();
loadConfig();
loadModels();
promptInput.focus();
