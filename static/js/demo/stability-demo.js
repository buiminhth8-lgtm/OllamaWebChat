class StabilityDemo {
  constructor(context) {
    this.context = context;
    this.timer = null;
    this.points = [];
    this.chart = null;
  }

  async start() {
    const { data, stage, dataPanel, controller, log } = this.context;
    DemoUtils.clear(stage);
    DemoUtils.clear(dataPanel);
    const grid = DemoUtils.el("div", "stability-grid");
    const chartEl = DemoUtils.el("div", "trend-chart");
    const timeline = DemoUtils.el("ol");
    stage.append(grid, chartEl, DemoUtils.el("p", "demo-warning", data.platform.stability.note), timeline);
    data.platform.stability.timeline.forEach((item) => timeline.appendChild(DemoUtils.el("li", "", item)));

    log.add("稳定性虚拟趋势演示开始");
    this.points = [];
    let tick = 0;
    const update = async () => {
      if (controller.cancelled) return;
      if (controller.paused) return;
      tick += 1;
      const hot = tick > 6 && tick < 11;
      const metrics = {
        cpu: DemoUtils.random(20, 65),
        memory: DemoUtils.random(45, 70),
        npu: hot ? DemoUtils.random(35, 48) : DemoUtils.random(30, 80),
        temperature: hot ? DemoUtils.random(75, 76) : DemoUtils.random(55, 72),
        api_latency: DemoUtils.random(15, 60),
        network_latency: DemoUtils.random(8, 45),
      };
      if (tick === 7) log.add("模拟温度达到75℃，触发黄色告警");
      if (tick === 9) log.add("执行虚拟降载，NPU负载下降");
      if (tick === 12) log.add("温度恢复正常，状态回到模拟运行");
      this.points.push(metrics);
      if (this.points.length > 60) this.points.shift();
      this.renderGauges(grid, metrics);
      DemoUtils.metricList(dataPanel, [
        ["CPU", `${metrics.cpu}%`],
        ["内存", `${metrics.memory}%`],
        ["NPU", `${metrics.npu}%`],
        ["温度", `${metrics.temperature}℃`],
        ["API延迟", `${metrics.api_latency}ms`],
        ["网络延迟", `${metrics.network_latency}ms`],
        ["数据标识", "模拟数据 · Demo Mode"],
      ]);
      this.renderChart(chartEl);
    };
    await update();
    this.timer = setInterval(update, controller.lowPower ? 2000 : 1000);
    await DemoUtils.sleep(controller.lowPower ? 7000 : 14000, controller);
    clearInterval(this.timer);
    this.timer = null;
    log.add("系统稳定性与实时响应虚拟演示完成");
  }

  renderGauges(grid, metrics) {
    DemoUtils.clear(grid);
    const rows = [["CPU", `${metrics.cpu}%`], ["内存", `${metrics.memory}%`], ["NPU", `${metrics.npu}%`], ["温度", `${metrics.temperature}℃`], ["API延迟", `${metrics.api_latency}ms`], ["网络延迟", `${metrics.network_latency}ms`]];
    rows.forEach(([name, value]) => {
      const item = DemoUtils.el("div", "gauge");
      item.append(DemoUtils.el("span", "", name), DemoUtils.el("strong", "", value));
      grid.appendChild(item);
    });
  }

  renderChart(element) {
    if (window.echarts) {
      this.chart = this.chart || window.echarts.init(element);
      this.chart.setOption({
        animation: false,
        tooltip: { trigger: "axis" },
        legend: { data: ["CPU", "内存", "NPU", "温度", "延迟"] },
        xAxis: { type: "category", data: this.points.map((_, i) => String(i + 1)) },
        yAxis: { type: "value" },
        series: [
          { name: "CPU", type: "line", data: this.points.map((p) => p.cpu) },
          { name: "内存", type: "line", data: this.points.map((p) => p.memory) },
          { name: "NPU", type: "line", data: this.points.map((p) => p.npu) },
          { name: "温度", type: "line", data: this.points.map((p) => p.temperature) },
          { name: "延迟", type: "line", data: this.points.map((p) => p.api_latency) },
        ],
      });
      return;
    }

    let canvas = element.querySelector("canvas");
    if (!canvas) {
      canvas = DemoUtils.el("canvas");
      canvas.width = 800;
      canvas.height = 260;
      element.appendChild(canvas);
    }
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#0f766e";
    ctx.beginPath();
    this.points.forEach((p, i) => {
      const x = 20 + i * 12;
      const y = canvas.height - 20 - p.temperature * 2.2;
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = "currentColor";
    ctx.font = "14px system-ui";
    ctx.fillText("ECharts 未加载，使用 Canvas 降级趋势图（模拟数据）", 20, 24);
  }

  pause() {}
  resume() {}
  reset() {}
  destroy() {
    if (this.timer) clearInterval(this.timer);
    if (this.chart) this.chart.dispose();
  }
}

window.StabilityDemo = StabilityDemo;
