class VisionDemo {
  constructor(context) {
    this.context = context;
    this.frame = null;
    this.running = false;
  }

  async start() {
    const { data, stage, dataPanel, controller, log } = this.context;
    const vision = data.platform.vision;
    DemoUtils.clear(stage);
    DemoUtils.clear(dataPanel);
    DemoUtils.metricList(dataPanel, Object.entries(vision.metrics).concat([["数据标识", "模拟数据 · Demo Mode"]]));

    const wrap = DemoUtils.el("div", "vision-wrap");
    const canvas = DemoUtils.el("canvas");
    canvas.id = "visionCanvas";
    canvas.width = 960;
    canvas.height = 520;
    const flow = DemoUtils.el("p", "demo-warning", vision.decision.join(" → "));
    wrap.append(canvas, flow);
    stage.appendChild(wrap);

    const ctx = canvas.getContext("2d");
    const targets = [
      { label: "Vehicle", id: "03", x: 60, y: 290, w: 120, h: 54, color: "#22c55e", trail: [] },
      { label: "Person", id: "07", x: 760, y: 330, w: 42, h: 86, color: "#38bdf8", trail: [] },
      { label: "Drone", id: "11", x: 220, y: 100, w: 72, h: 42, color: "#f59e0b", trail: [] },
      { label: "Building", id: "01", x: 520, y: 170, w: 170, h: 130, color: "#a78bfa", trail: [] },
    ];
    let tick = 0;
    this.running = true;
    log.add("AI目标识别虚拟演示开始，未调用摄像头或真实模型");

    const draw = () => {
      if (!this.running || controller.cancelled) return;
      if (!controller.paused) {
        tick += 1;
        this.drawFrame(ctx, canvas, targets, tick);
      }
      this.frame = requestAnimationFrame(draw);
    };
    draw();

    await DemoUtils.sleep(controller.lowPower ? 4500 : 9000, controller);
    this.running = false;
    if (this.frame) cancelAnimationFrame(this.frame);
    log.add("目标跟踪、遮挡恢复和智能决策虚拟流程完成");
  }

  drawFrame(ctx, canvas, targets, tick) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    gradient.addColorStop(0, "#10212b");
    gradient.addColorStop(1, "#1e3a3a");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(255,255,255,.12)";
    for (let x = 0; x < canvas.width; x += 80) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x + 220, canvas.height);
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(255,255,255,.08)";
    ctx.fillRect(80, 360, 820, 60);
    ctx.fillRect(520, 120, 190, 150);

    targets.forEach((target, index) => {
      if (index !== 3) {
        target.x += Math.sin((tick + index * 20) / 30) * 2 + (index === 0 ? 1.4 : -0.5);
        target.y += Math.cos((tick + index * 14) / 35) * 1.1;
      }
      target.trail.push([target.x + target.w / 2, target.y + target.h / 2]);
      if (target.trail.length > 36) target.trail.shift();
      const occluded = target.label === "Vehicle" && tick > 130 && tick < 170;
      ctx.strokeStyle = target.color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      target.trail.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.stroke();
      if (occluded) {
        ctx.fillStyle = "rgba(0,0,0,.45)";
        ctx.fillRect(target.x, target.y, target.w, target.h);
        return;
      }
      ctx.strokeStyle = target.color;
      ctx.strokeRect(target.x, target.y, target.w, target.h);
      ctx.fillStyle = target.color;
      ctx.font = "16px system-ui";
      ctx.fillText(`${target.label}  Confidence: ${index === 3 ? 88 : 92}%  Track ID: ${target.id}`, target.x, target.y - 8);
    });

    ctx.fillStyle = "#f8fafc";
    ctx.font = "18px system-ui";
    ctx.fillText("持续跟踪 · 发送告警 · 调整航线（虚拟演示）", 28, 38);
  }

  pause() {}
  resume() {}
  reset() {}
  destroy() {
    this.running = false;
    if (this.frame) cancelAnimationFrame(this.frame);
  }
}

window.VisionDemo = VisionDemo;
