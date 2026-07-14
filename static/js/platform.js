const CATEGORIES = [
  ["platform", "1. 核心平台与国产化信息"],
  ["llm", "2. 大模型部署与调用能力"],
  ["cluster", "3. 集群任务协同能力"],
  ["ai", "4. 智能处理与推理能力"],
  ["driver", "5. 底层驱动与算法环境"],
  ["reliability", "6. 稳定性与实时响应能力"],
];

const STATUS_LABELS = {
  pass: "正常",
  warning: "部分满足",
  fail: "异常",
  unknown: "未知",
  scanning: "检测中",
};

const cardsEl = document.getElementById("cards");
const scanStatusEl = document.getElementById("scanStatus");
const summaryStatusEl = document.getElementById("summaryStatus");
const lastScanTimeEl = document.getElementById("lastScanTime");
const currentStepEl = document.getElementById("currentStep");
const progressTextEl = document.getElementById("progressText");
const progressFillEl = document.getElementById("progressFill");
const startButton = document.getElementById("startScan");
const rescanButton = document.getElementById("rescan");
const exportButton = document.getElementById("exportJson");
const summaryFields = {
  deviceName: document.getElementById("deviceName"),
  socName: document.getElementById("socName"),
  cpuArch: document.getElementById("cpuArch"),
  osName: document.getElementById("osName"),
  kernelVersion: document.getElementById("kernelVersion"),
  uptimeValue: document.getElementById("uptimeValue"),
};

let scanning = false;
let abortController = null;
let currentReader = null;
let latestScan = null;

function setText(element, value) {
  element.textContent = value == null || value === "" ? "未知" : String(value);
}

function statusLabel(status) {
  return STATUS_LABELS[status] || STATUS_LABELS.unknown;
}

function createCard(id, title) {
  const card = document.createElement("article");
  card.className = "capability-card";
  card.dataset.categoryId = id;

  const head = document.createElement("div");
  head.className = "card-head";
  const h2 = document.createElement("h2");
  h2.textContent = title;
  const badge = document.createElement("span");
  badge.className = "status-badge status-unknown";
  badge.textContent = "未知";
  head.append(h2, badge);

  const summary = section("摘要", "summary", "等待扫描");
  const metrics = listSection("关键指标", "metrics");
  const checks = listSection("检测明细", "checks");
  const evidence = listSection("检测依据", "evidence");
  const recommendations = listSection("建议", "recommendations");

  card.append(head, summary, metrics, checks, evidence, recommendations);
  cardsEl.appendChild(card);
}

function section(title, className, initialText) {
  const wrapper = document.createElement("section");
  wrapper.className = `card-section ${className}`;
  const h3 = document.createElement("h3");
  h3.textContent = title;
  const p = document.createElement("p");
  p.textContent = initialText;
  wrapper.append(h3, p);
  return wrapper;
}

function listSection(title, className) {
  const wrapper = document.createElement("section");
  wrapper.className = `card-section ${className}`;
  const h3 = document.createElement("h3");
  h3.textContent = title;
  const ul = document.createElement("ul");
  ul.className = `${className}-list`;
  const li = document.createElement("li");
  li.className = "muted";
  li.textContent = "暂无";
  ul.appendChild(li);
  wrapper.append(h3, ul);
  return wrapper;
}

function resetCards(status = "unknown") {
  cardsEl.innerHTML = "";
  for (const [id, title] of CATEGORIES) {
    createCard(id, title);
    updateCard({ id, title, status, summary: status === "scanning" ? "等待检测..." : "等待扫描", metrics: [], checks: [], recommendations: [] });
  }
}

function updateCard(category) {
  const card = cardsEl.querySelector(`[data-category-id="${category.id}"]`);
  if (!card) return;
  const status = category.status || "unknown";
  const badge = card.querySelector(".status-badge");
  badge.className = `status-badge status-${status}`;
  badge.textContent = statusLabel(status);
  card.querySelector(".summary p").textContent = category.summary || "暂无摘要";
  fillMetrics(card.querySelector(".metrics-list"), category.metrics || []);
  fillChecks(card.querySelector(".checks-list"), category.checks || []);
  fillEvidence(card.querySelector(".evidence-list"), category.checks || []);
  fillRecommendations(card.querySelector(".recommendations-list"), category.recommendations || []);
  updateSummaryFields(category);
}

function fillMetrics(list, metrics) {
  replaceList(list, metrics, (item) => {
    const value = item.unit ? `${item.value} ${item.unit}` : item.value;
    return `${item.name}：${value}`;
  });
}

function fillChecks(list, checks) {
  replaceList(list, checks, (item) => `${item.name}：${statusLabel(item.status)}，${item.value}`);
}

function fillEvidence(list, checks) {
  const evidence = checks.map((item) => item.evidence).filter(Boolean);
  replaceList(list, Array.from(new Set(evidence)), (item) => item);
}

function fillRecommendations(list, recommendations) {
  replaceList(list, recommendations, (item) => item);
}

function replaceList(list, items, formatter) {
  list.innerHTML = "";
  if (!items.length) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "暂无";
    list.appendChild(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = formatter(item);
    list.appendChild(li);
  }
}

function updateSummaryFields(category) {
  const metrics = {};
  for (const item of category.metrics || []) {
    metrics[item.name] = item.unit ? `${item.value} ${item.unit}` : item.value;
  }
  if (category.id === "platform") {
    setText(summaryFields.socName, metrics.SoC);
    setText(summaryFields.cpuArch, metrics.Architecture);
    setText(summaryFields.osName, metrics.OS);
    setText(summaryFields.kernelVersion, metrics.Kernel);
    const hostCheck = (category.checks || []).find((item) => item.name === "主机名");
    if (hostCheck) setText(summaryFields.deviceName, hostCheck.value);
  }
  if (category.id === "reliability") {
    setText(summaryFields.uptimeValue, metrics["系统运行时间"]);
  }
}

function setBusy(value) {
  scanning = value;
  startButton.disabled = value;
  rescanButton.disabled = value;
}

function setProgress(index, total, text) {
  currentStepEl.textContent = text;
  progressTextEl.textContent = `${index} / ${total}`;
  progressFillEl.style.width = total ? `${Math.round((index / total) * 100)}%` : "0";
}

async function startScan() {
  if (scanning) return;
  abortController = new AbortController();
  latestScan = { categories: [] };
  setBusy(true);
  resetCards("scanning");
  scanStatusEl.textContent = "检测中";
  summaryStatusEl.textContent = "检测中";
  exportButton.disabled = true;
  setProgress(0, CATEGORIES.length, "准备扫描");

  try {
    const response = await fetch("/api/platform/scan", { method: "POST", signal: abortController.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if (!response.body) throw new Error("浏览器不支持流式响应");

    currentReader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await currentReader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.trim()) handleEvent(JSON.parse(line));
      }
    }
    if (buffer.trim()) handleEvent(JSON.parse(buffer));
  } catch (error) {
    if (error.name !== "AbortError") {
      scanStatusEl.textContent = `扫描异常：${error.message}`;
      summaryStatusEl.textContent = "异常";
    }
  } finally {
    currentReader = null;
    abortController = null;
    setBusy(false);
  }
}

function handleEvent(event) {
  if (event.event === "start") {
    latestScan.scan_id = event.scan_id;
    latestScan.started_at = event.started_at;
    latestScan.categories = [];
    lastScanTimeEl.textContent = event.started_at;
    setProgress(0, event.total, "扫描开始");
    return;
  }

  if (event.event === "progress") {
    const category = event.category;
    latestScan.categories = latestScan.categories.filter((item) => item.id !== category.id);
    latestScan.categories.push(category);
    updateCard(category);
    setProgress(event.index, event.total, `正在检测：${category.title}`);
    return;
  }

  if (event.event === "error") {
    scanStatusEl.textContent = `单项异常：${event.category_id}`;
    return;
  }

  if (event.event === "complete") {
    latestScan.finished_at = event.finished_at;
    latestScan.duration_ms = event.duration_ms;
    latestScan.summary = event.summary;
    scanStatusEl.textContent = "扫描完成";
    summaryStatusEl.textContent = formatSummary(event.summary);
    lastScanTimeEl.textContent = event.finished_at;
    exportButton.disabled = false;
    setProgress(CATEGORIES.length, CATEGORIES.length, "扫描完成");
  }
}

function formatSummary(summary) {
  if (!summary) return "未知";
  return `正常 ${summary.pass || 0}，部分满足 ${summary.warning || 0}，异常 ${summary.fail || 0}，未知 ${summary.unknown || 0}`;
}

async function loadLatest() {
  try {
    const response = await fetch("/api/platform/latest");
    const result = await response.json();
    if (!result.available) return;
    latestScan = result.scan;
    resetCards("unknown");
    for (const category of latestScan.categories || []) {
      updateCard(category);
    }
    scanStatusEl.textContent = "已加载最近结果";
    summaryStatusEl.textContent = formatSummary(latestScan.summary);
    lastScanTimeEl.textContent = latestScan.finished_at || "暂无";
    setProgress(CATEGORIES.length, CATEGORIES.length, "最近结果已加载");
    exportButton.disabled = false;
  } catch {
    scanStatusEl.textContent = "最近结果不可用";
  }
}

function exportJson() {
  if (!latestScan) return;
  const blob = new Blob([JSON.stringify(latestScan, null, 2)], { type: "application/json;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `rk3588-platform-scan-${latestScan.scan_id || "latest"}.json`;
  document.body.appendChild(link);
  link.click();
  URL.revokeObjectURL(link.href);
  link.remove();
}

function cancelScan() {
  if (currentReader) currentReader.cancel().catch(() => {});
  if (abortController) abortController.abort();
}

startButton.addEventListener("click", startScan);
rescanButton.addEventListener("click", startScan);
exportButton.addEventListener("click", exportJson);
window.addEventListener("pagehide", cancelScan);

resetCards("unknown");
loadLatest();
