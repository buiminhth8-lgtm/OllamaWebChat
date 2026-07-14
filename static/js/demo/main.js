class DemoController {
  constructor() {
    this.data = null;
    this.currentIndex = 0;
    this.currentDemo = null;
    this.paused = false;
    this.cancelled = false;
    this.lowPower = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.eventLog = new DemoEventLog(document.getElementById("eventLog"));
    this.stage = document.getElementById("stage");
    this.dataPanel = document.getElementById("dataPanel");
    this.stageTitle = document.getElementById("stageTitle");
    this.stepNav = document.getElementById("stepNav");
    this.lowPowerInput = document.getElementById("lowPowerMode");
    this.lowPowerInput.checked = this.lowPower;
    this.demoClasses = [ChipDemo, LlmDemo, ClusterDemo, VisionDemo, DriverDemo, StabilityDemo];
    this.reportBase = null;
  }

  async init() {
    const response = await fetch("/api/demo/config");
    this.data = await response.json();
    const report = await fetch("/api/demo/report");
    this.reportBase = await report.json();
    this.renderPlatformStatus();
    this.renderScoreChart();
    this.renderSteps();
    this.bindControls();
    this.eventLog.add("虚拟演示页面就绪：模拟数据 · Demo Mode");
  }

  bindControls() {
    document.getElementById("startDemo").addEventListener("click", () => this.start());
    document.getElementById("pauseDemo").addEventListener("click", () => this.togglePause());
    document.getElementById("resetDemo").addEventListener("click", () => this.reset());
    document.getElementById("exportReport").addEventListener("click", () => this.exportReport());
    this.lowPowerInput.addEventListener("change", () => {
      this.lowPower = this.lowPowerInput.checked;
      this.eventLog.add(this.lowPower ? "低性能模式已启用" : "低性能模式已关闭");
    });
  }

  renderPlatformStatus() {
    const panel = document.getElementById("platformStatus");
    DemoUtils.clear(panel);
    const rows = [
      ["平台型号", this.data.platform.platform.model],
      ["CPU", this.data.platform.platform.cpu],
      ["NPU", this.data.platform.platform.npu],
      ["GPU", this.data.platform.platform.gpu],
      ["内存", this.data.platform.platform.memory],
      ["系统", this.data.platform.platform.system],
      ["内核", this.data.platform.platform.kernel],
      ["运行模式", `${this.data.platform.platform.mode} · 模拟数据`],
      ["当前状态", this.data.platform.platform.status],
    ];
    rows.forEach(([name, value]) => {
      const item = DemoUtils.el("div");
      item.append(DemoUtils.el("span", "", name), DemoUtils.el("strong", "", value));
      panel.appendChild(item);
    });
  }

  renderScoreChart() {
    const names = Object.keys(this.data.platform.scores);
    const values = Object.values(this.data.platform.scores);
    const chartEl = document.getElementById("scoreChart");
    if (window.echarts) {
      const chart = window.echarts.init(chartEl);
      chart.setOption({
        radar: { indicator: names.map((name) => ({ name, max: 100 })) },
        series: [{ type: "radar", data: [{ value: values, name: "虚拟能力评分" }] }],
      });
      return;
    }
    const canvas = document.getElementById("scoreFallback");
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const r = 92;
    ctx.strokeStyle = "#0f766e";
    ctx.fillStyle = "rgba(15,118,110,.18)";
    ctx.beginPath();
    values.forEach((value, index) => {
      const angle = -Math.PI / 2 + (index * Math.PI * 2) / values.length;
      const radius = r * value / 100;
      const x = cx + Math.cos(angle) * radius;
      const y = cy + Math.sin(angle) * radius;
      if (index) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "currentColor";
    ctx.font = "13px system-ui";
    names.forEach((name, index) => {
      const angle = -Math.PI / 2 + (index * Math.PI * 2) / names.length;
      ctx.fillText(name, cx + Math.cos(angle) * 116 - 26, cy + Math.sin(angle) * 116);
    });
  }

  renderSteps() {
    DemoUtils.clear(this.stepNav);
    this.data.capabilities.forEach((capability, index) => {
      const button = DemoUtils.el("button", "step-button", `${index + 1}. ${capability.title}`);
      button.type = "button";
      button.addEventListener("click", () => this.playSingle(index));
      this.stepNav.appendChild(button);
    });
    this.updateSteps();
  }

  updateSteps(doneIndex = -1) {
    Array.from(this.stepNav.children).forEach((button, index) => {
      button.classList.toggle("active", index === this.currentIndex);
      button.classList.toggle("done", index <= doneIndex);
    });
  }

  async start() {
    this.cancelled = false;
    this.paused = false;
    const mode = document.querySelector("input[name='playMode']:checked").value;
    if (mode === "manual") {
      await this.playSingle(this.currentIndex);
      return;
    }
    for (let i = this.currentIndex; i < this.demoClasses.length; i += 1) {
      if (this.cancelled) return;
      await this.playSingle(i);
      this.updateSteps(i);
      await DemoUtils.sleep(this.lowPower ? 450 : 900, this);
    }
    this.eventLog.add("六项能力自动演示完成");
  }

  async playSingle(index) {
    if (this.currentDemo && this.currentDemo.destroy) this.currentDemo.destroy();
    this.currentIndex = index;
    this.updateSteps(index - 1);
    const capability = this.data.capabilities[index];
    this.stageTitle.textContent = capability.title;
    DemoUtils.clear(this.stage);
    DemoUtils.clear(this.dataPanel);
    const DemoClass = this.demoClasses[index];
    this.currentDemo = new DemoClass({
      data: this.data,
      stage: this.stage,
      dataPanel: this.dataPanel,
      controller: this,
      log: this.eventLog,
    });
    this.eventLog.add(`开始演示：${capability.title}（虚拟演示）`);
    await this.currentDemo.start();
  }

  togglePause() {
    this.paused = !this.paused;
    document.getElementById("pauseDemo").textContent = this.paused ? "继续演示" : "暂停演示";
    if (this.currentDemo) {
      if (this.paused && this.currentDemo.pause) this.currentDemo.pause();
      if (!this.paused && this.currentDemo.resume) this.currentDemo.resume();
    }
    this.eventLog.add(this.paused ? "演示已暂停" : "演示继续播放");
  }

  reset() {
    this.cancelled = true;
    this.paused = false;
    if (this.currentDemo && this.currentDemo.destroy) this.currentDemo.destroy();
    this.currentIndex = 0;
    this.stageTitle.textContent = "等待开始";
    DemoUtils.clear(this.stage);
    DemoUtils.clear(this.dataPanel);
    this.eventLog.reset();
    this.updateSteps();
    document.getElementById("pauseDemo").textContent = "暂停演示";
    this.eventLog.add("演示已重置");
  }

  exportReport() {
    const report = Object.assign({}, this.reportBase, {
      demo: true,
      data_source: "mock",
      not_real_device_data: true,
      exported_at: new Date().toISOString(),
      event_log: this.eventLog.items.slice(),
      disclaimer: "本报告为虚拟演示报告，不是真实设备检测报告。",
    });
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json;charset=utf-8" });
    const link = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    link.href = URL.createObjectURL(blob);
    link.download = `rk3588-platform-demo-report-${stamp}.json`;
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
    this.eventLog.add("已导出虚拟演示报告 JSON");
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const controller = new DemoController();
  controller.init().catch((error) => {
    const log = document.getElementById("eventLog");
    if (log) {
      const li = document.createElement("li");
      li.textContent = `演示配置加载失败：${error.message}`;
      log.appendChild(li);
    }
  });
});
