const DEFAULT_CONFIG = {
  maxMessageChars: 8000,
  maxHistoryMessages: 40,
  maxHistoryChars: 24000,
};

// ============================================================
// DOM 引用基线（UI-Slice 0）
// 这些 ID 与 templates/index.html 一一对应，是后续 UI 重构的稳定性契约：
// 移动元素时必须保留 ID，避免 selector 失效。所有元素均存在于页面中。
// ============================================================

// 区域：header（#pageHeader）
const modelSelect = document.getElementById("modelSelect");
const refreshModelsButton = document.getElementById("refreshModels");
const clearChatButton = document.getElementById("clearChat");
const statusElement = document.getElementById("status");

// 区域：chat-main / Ollama 管理/配置（#ollamaPanel）
const ollamaConfigForm = document.getElementById("ollamaConfigForm");
const ollamaInstallDirInput = document.getElementById("ollamaInstallDir");
const saveOllamaConfigButton = document.getElementById("saveOllamaConfig");
const startOllamaButton = document.getElementById("startOllama");
const refreshOllamaStatusButton = document.getElementById("refreshOllamaStatus");
const ollamaServiceStatusElement = document.getElementById("ollamaServiceStatus");
const ollamaStatusTextElement = document.getElementById("ollamaStatusText");
const ollamaVersionElement = document.getElementById("ollamaVersion");
const ollamaServiceStateElement = document.getElementById("ollamaServiceState");
const ollamaMessageElement = document.getElementById("ollamaMessage");

// 区域：chat-main / 模型下载（#ollamaPanel 内）
const modelPullForm = document.getElementById("modelPullForm");
const pullModelNameInput = document.getElementById("pullModelName");
const pullModelButton = document.getElementById("pullModelButton");
const modelPullProgressElement = document.getElementById("modelPullProgress");
const pullStatusTextElement = document.getElementById("pullStatusText");
const pullProgressTextElement = document.getElementById("pullProgressText");
const pullProgressBarFill = document.getElementById("pullProgressBarFill");

// 区域：chat-main / 输入区（#composerBar）
const chatForm = document.getElementById("chatForm");
const promptInput = document.getElementById("prompt");
const sendButton = document.getElementById("sendButton");
const stopButton = document.getElementById("stopButton");

// 区域：chat-main / 消息流（#messages）
const messagesContainer = document.getElementById("messages");

let appConfig = { ...DEFAULT_CONFIG };
let messages = loadMessages();
let abortController = null;
let sideChannelThinking = "";
const ollamaUiState = {
  config: null,
  status: null,
  saving: false,
  starting: false,
  refreshing: false,
  requestFailed: false,
};
const pullUiState = {
  phase: "idle", // idle | downloading | success | error
};

function getApiErrorMessage(payload, fallback) {
  if (typeof payload?.message === "string" && payload.message) return payload.message;
  if (typeof payload?.error === "string" && payload.error) return payload.error;
  if (typeof payload?.error?.message === "string" && payload.error.message) return payload.error.message;
  return fallback;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    throw new Error(response.ok ? "服务器返回格式无效" : `请求失败：HTTP ${response.status}`);
  }
  if (!response.ok) {
    throw new Error(getApiErrorMessage(payload, `请求失败：HTTP ${response.status}`));
  }
  return payload;
}

function setOllamaMessage(text, isError = false) {
  ollamaMessageElement.textContent = text;
  ollamaMessageElement.classList.toggle("error", isError);
}

function setOllamaStatusLabel(text, tone) {
  ollamaStatusTextElement.textContent = text;
  ollamaServiceStatusElement.classList.remove("is-neutral", "is-ready", "is-warning", "is-error");
  ollamaServiceStatusElement.classList.add(tone);
}

function renderOllamaManagement() {
  const config = ollamaUiState.config || {};
  const serviceStatus = ollamaUiState.status || {};
  const configured = serviceStatus.configured === true;
  const running = serviceStatus.running === true;
  const ready = serviceStatus.ready === true;

  ollamaVersionElement.textContent = serviceStatus.version || "—";
  ollamaServiceStateElement.textContent = serviceStatus.service_state || "unknown";

  if (ollamaUiState.requestFailed) {
    setOllamaStatusLabel("请求失败", "is-error");
  } else if (ready) {
    setOllamaStatusLabel("Ready", "is-ready");
  } else if (ollamaUiState.starting) {
    setOllamaStatusLabel("正在启动...", "is-warning");
  } else if (!configured && !config.install_dir) {
    setOllamaStatusLabel("未配置", "is-neutral");
  } else if (!configured || config.valid === false) {
    setOllamaStatusLabel("配置无效", "is-error");
  } else if (running) {
    setOllamaStatusLabel("已运行但 API 未 Ready", "is-warning");
  } else {
    setOllamaStatusLabel("未启动", "is-neutral");
  }

  saveOllamaConfigButton.disabled = ollamaUiState.saving || ollamaUiState.starting || ollamaUiState.refreshing;
  saveOllamaConfigButton.textContent = ollamaUiState.saving ? "保存中..." : "保存";
  startOllamaButton.disabled = ollamaUiState.starting || ollamaUiState.refreshing || ready || !configured;
  startOllamaButton.textContent = ollamaUiState.starting ? "正在启动..." : ready ? "已运行" : "启动 Ollama";
  refreshOllamaStatusButton.disabled = ollamaUiState.refreshing || ollamaUiState.starting;
}

async function refreshOllamaManagement(successMessage = "") {
  if (ollamaUiState.refreshing) return;
  ollamaUiState.refreshing = true;
  ollamaUiState.requestFailed = false;
  renderOllamaManagement();

  const [configResult, statusResult] = await Promise.allSettled([
    requestJson("/api/ollama/config"),
    requestJson("/api/ollama/status"),
  ]);

  if (configResult.status === "fulfilled") {
    ollamaUiState.config = configResult.value;
    ollamaInstallDirInput.value = configResult.value.install_dir || "";
  }
  if (statusResult.status === "fulfilled") {
    ollamaUiState.status = statusResult.value;
  }

  const failure = [configResult, statusResult].find((result) => result.status === "rejected");
  ollamaUiState.requestFailed = Boolean(failure);
  ollamaUiState.refreshing = false;
  if (failure) {
    setOllamaMessage(`请求失败：${failure.reason.message}`, true);
  } else if (successMessage) {
    setOllamaMessage(successMessage);
  }
  renderOllamaManagement();
}

async function refreshOllamaStatus({ allowWhileStarting = false, clearMessage = true } = {}) {
  if (ollamaUiState.refreshing || (ollamaUiState.starting && !allowWhileStarting)) return;
  ollamaUiState.refreshing = true;
  ollamaUiState.requestFailed = false;
  if (clearMessage) setOllamaMessage("");
  renderOllamaManagement();
  try {
    ollamaUiState.status = await requestJson("/api/ollama/status");
  } catch (error) {
    ollamaUiState.requestFailed = true;
    setOllamaMessage(`请求失败：${error.message}`, true);
  } finally {
    ollamaUiState.refreshing = false;
    renderOllamaManagement();
  }
}

async function saveOllamaConfig(event) {
  event.preventDefault();
  if (ollamaUiState.saving || ollamaUiState.starting || ollamaUiState.refreshing) return;
  ollamaUiState.saving = true;
  setOllamaMessage("");
  renderOllamaManagement();
  try {
    await requestJson("/api/ollama/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ install_dir: ollamaInstallDirInput.value.trim() }),
    });
    await refreshOllamaManagement("配置已保存");
  } catch (error) {
    setOllamaMessage(error.message, true);
  } finally {
    ollamaUiState.saving = false;
    renderOllamaManagement();
  }
}

async function startOllama() {
  if (
    ollamaUiState.starting ||
    ollamaUiState.refreshing ||
    ollamaUiState.status?.ready === true
  ) return;

  ollamaUiState.starting = true;
  setOllamaMessage("正在启动 Ollama...");
  renderOllamaManagement();
  try {
    const result = await requestJson("/api/ollama/start", { method: "POST" });
    setOllamaMessage(result.message || "Ollama 已启动");
    await refreshOllamaStatus({ allowWhileStarting: true, clearMessage: false });
    await loadModels();
  } catch (error) {
    setOllamaMessage(error.message, true);
  } finally {
    ollamaUiState.starting = false;
    renderOllamaManagement();
  }
}

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
    appConfig = toClientConfig(await requestJson("/api/config"));
    renderMessages();
    saveMessages();
  } catch {
    appConfig = { ...DEFAULT_CONFIG };
  }
}

async function loadModels(preferredModel = "") {
  setStatus("正在连接 Ollama...");
  try {
    const result = await requestJson("/api/models");

    const current =
      preferredModel || modelSelect.value || localStorage.getItem("ollama_web_chat_model") || "";
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
      } else if (preferredModel) {
        // Ollama 实际模型名可能带 tag，精确匹配失败时按基础名匹配
        const baseName = preferredModel.split(":")[0];
        const fuzzy = models.find((model) => (model.name || "").split(":")[0] === baseName);
        if (fuzzy) modelSelect.value = fuzzy.name;
      }
    }

    localStorage.setItem("ollama_web_chat_model", modelSelect.value || "");
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

function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value <= 0) return "";
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${Math.round(value)} B`;
}

function setPullControlsDisabled(disabled) {
  pullModelButton.disabled = disabled;
  pullModelNameInput.disabled = disabled;
  pullModelButton.textContent = disabled ? "下载中..." : "下载";
}

function resetPullProgress() {
  pullStatusTextElement.textContent = "";
  pullStatusTextElement.classList.remove("is-error", "is-success");
  pullProgressTextElement.textContent = "";
  pullProgressBarFill.style.width = "0%";
  pullProgressBarFill.classList.remove("indeterminate");
}

function renderPullEvent(event) {
  const status = typeof event?.status === "string" ? event.status : "";
  pullStatusTextElement.textContent = status || "下载中...";
  pullStatusTextElement.classList.remove("is-error", "is-success");

  const completed = Number(event?.completed);
  const total = Number(event?.total);
  const hasProgress =
    status === "downloading" &&
    Number.isFinite(completed) &&
    completed >= 0 &&
    Number.isFinite(total) &&
    total > 0;

  if (hasProgress) {
    const percent = Math.min(100, Math.round((completed / total) * 100));
    pullProgressBarFill.classList.remove("indeterminate");
    pullProgressBarFill.style.width = `${percent}%`;
    pullProgressTextElement.textContent = `${percent}% · ${formatBytes(completed) || "0 B"} / ${formatBytes(total)}`;
  } else if (status === "success") {
    pullProgressBarFill.classList.remove("indeterminate");
    pullProgressBarFill.style.width = "100%";
    pullProgressTextElement.textContent = "";
  } else {
    // 没有 total 或非 downloading 状态：不确定进度
    pullProgressBarFill.classList.add("indeterminate");
    pullProgressTextElement.textContent = "";
  }
}

async function finishPullSuccess(modelName) {
  pullUiState.phase = "success";
  setPullControlsDisabled(false);
  pullStatusTextElement.textContent = "success";
  pullStatusTextElement.classList.add("is-success");
  try {
    await loadModels(modelName);
  } catch {
    // 刷新模型列表失败不影响页面正常使用
  }
}

function handlePullLine(line) {
  let event;
  try {
    event = JSON.parse(line);
  } catch {
    throw new Error("模型下载数据格式异常");
  }
  if (!event || typeof event !== "object") {
    throw new Error("模型下载数据格式异常");
  }
  if (event.error !== undefined) {
    throw new Error(getApiErrorMessage(event, "模型下载失败"));
  }
  renderPullEvent(event);
  return event.status === "success";
}

async function startModelPull() {
  if (pullUiState.phase === "downloading") return;

  const modelName = pullModelNameInput.value.trim();
  if (!modelName) {
    resetPullProgress();
    modelPullProgressElement.hidden = false;
    pullStatusTextElement.textContent = "请输入模型名，例如 deepseek-r1:1.5b";
    pullStatusTextElement.classList.add("is-error");
    return;
  }

  pullUiState.phase = "downloading";
  setPullControlsDisabled(true);
  modelPullProgressElement.hidden = false;
  resetPullProgress();
  pullStatusTextElement.textContent = "准备下载...";

  let succeeded = false;
  try {
    const response = await fetch("/api/ollama/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelName }),
    });

    if (!response.ok) {
      let payload = {};
      try {
        payload = await response.json();
      } catch {
        // 响应体不是 JSON 时使用默认错误信息
      }
      throw new Error(getApiErrorMessage(payload, `请求失败：HTTP ${response.status}`));
    }
    if (!response.body) throw new Error("浏览器不支持流式响应");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let sawSuccess = false;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        if (handlePullLine(line)) sawSuccess = true;
      }
    }

    if (buffer.trim()) {
      if (handlePullLine(buffer)) sawSuccess = true;
    }

    if (!sawSuccess) throw new Error("连接中断，模型下载未完成");
    succeeded = true;
  } catch (error) {
    const message = error instanceof TypeError ? "网络连接失败，请检查网络后重试" : error.message;
    pullUiState.phase = "error";
    pullStatusTextElement.textContent = message;
    pullStatusTextElement.classList.add("is-error");
    pullProgressBarFill.classList.remove("indeterminate");
  } finally {
    if (!succeeded) {
      pullUiState.phase = pullUiState.phase === "downloading" ? "error" : pullUiState.phase;
      setPullControlsDisabled(false);
    }
  }

  if (succeeded) await finishPullSuccess(modelName);
}

// ============================================================
// 事件绑定基线：脚本以 defer 方式加载并只执行一次，
// 每个元素的事件在此处仅绑定一次，禁止在渲染函数中重复绑定。
// ============================================================

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
ollamaConfigForm.addEventListener("submit", saveOllamaConfig);
startOllamaButton.addEventListener("click", startOllama);
refreshOllamaStatusButton.addEventListener("click", refreshOllamaStatus);
modelPullForm.addEventListener("submit", (event) => {
  event.preventDefault();
  startModelPull();
});

// 初始化入口：仅在脚本加载时执行一次
renderMessages();
loadConfig();
loadModels();
refreshOllamaManagement();
promptInput.focus();
