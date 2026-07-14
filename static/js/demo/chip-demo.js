class ChipDemo {
  constructor(context) {
    this.context = context;
  }

  async start() {
    const { data, stage, dataPanel, controller, log } = this.context;
    const chip = data.platform.chip;
    DemoUtils.clear(stage);
    DemoUtils.metricList(dataPanel, chip.table.map((row) => [row[0], `${row[1]} · ${row[2]}`]));

    const svg = DemoUtils.svg("svg", { viewBox: "0 0 900 520", class: "chip-svg", role: "img" });
    const outer = DemoUtils.svg("rect", { x: 145, y: 70, width: 610, height: 350, rx: 22, fill: "rgba(31,41,55,.08)", stroke: "var(--border)", "stroke-width": 3 });
    svg.appendChild(outer);

    const modules = [
      ["CPU", 190, 120], ["GPU", 360, 120], ["NPU", 530, 120],
      ["VPU", 190, 250], ["ISP", 360, 250], ["DDR", 530, 250],
      ["PCIe", 190, 350], ["MIPI CSI", 360, 350], ["Ethernet", 530, 350],
    ];
    const boxes = {};
    for (const [name, x, y] of modules) {
      const rect = DemoUtils.svg("rect", { x, y, width: 130, height: 66, rx: 10, class: "chip-box", fill: "var(--assistant)", stroke: "var(--border)" });
      const text = DemoUtils.svg("text", { x: x + 65, y: y + 40, "text-anchor": "middle", fill: "currentColor", "font-size": 18 });
      text.textContent = name;
      boxes[name] = rect;
      svg.append(rect, text);
    }

    for (let y = 205; y <= 330; y += 42) {
      svg.appendChild(DemoUtils.svg("line", { x1: 195, y1: y, x2: 705, y2: y, stroke: "var(--demo-accent)", "stroke-width": 3, class: "flow-line", opacity: .45 }));
    }

    const note = DemoUtils.el("p", "demo-warning");
    note.textContent = chip.note + " 模拟数据 · 虚拟演示 · Demo Mode";
    stage.append(svg, note);

    log.add("芯片架构虚拟演示开始");
    outer.classList.add("is-lit");
    await DemoUtils.sleep(700, controller);
    for (const name of ["CPU", "GPU", "NPU", "VPU", "ISP", "DDR", "PCIe", "MIPI CSI", "Ethernet"]) {
      boxes[name].classList.add("is-lit");
      if (name === "NPU") boxes[name].classList.add("pulse");
      log.add(`${name} 模块点亮`);
      if (!(await DemoUtils.sleep(controller.lowPower ? 260 : 520, controller))) return;
    }
    log.add("核心平台能力总结完成：国产SoC + ARM授权核心 + 板级系统集成");
  }

  pause() {}
  resume() {}
  reset() {}
  destroy() {}
}

window.ChipDemo = ChipDemo;
