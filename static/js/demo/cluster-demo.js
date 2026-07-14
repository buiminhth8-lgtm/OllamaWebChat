class ClusterDemo {
  constructor(context) {
    this.context = context;
  }

  async start() {
    const { data, stage, dataPanel, controller, log } = this.context;
    const cluster = data.platform.cluster;
    DemoUtils.clear(stage);
    DemoUtils.clear(dataPanel);

    const svg = DemoUtils.svg("svg", { viewBox: "0 0 900 520", class: "cluster-svg", role: "img" });
    const center = DemoUtils.svg("circle", { cx: 450, cy: 250, r: 62, fill: "rgba(15,118,110,.18)", stroke: "var(--demo-accent)", "stroke-width": 3 });
    const centerText = DemoUtils.svg("text", { x: 450, y: 256, "text-anchor": "middle", fill: "currentColor", "font-size": 18 });
    centerText.textContent = "任务中心";
    svg.append(center, centerText);

    const positions = [[180, 105], [720, 105], [180, 395], [720, 395]];
    const nodes = [];
    cluster.uavs.forEach((uav, index) => {
      const [x, y] = positions[index];
      const line = DemoUtils.svg("line", { x1: 450, y1: 250, x2: x, y2: y, stroke: "var(--border)", "stroke-width": 2, class: "flow-line" });
      const node = DemoUtils.svg("circle", { cx: x, cy: y, r: 44, fill: "var(--assistant)", stroke: "var(--border)", "stroke-width": 2, class: "uav-node" });
      const label = DemoUtils.svg("text", { x, y: y + 6, "text-anchor": "middle", fill: "currentColor", "font-size": 15 });
      label.textContent = uav.id;
      svg.append(line, node, label);
      nodes.push(node);
    });
    stage.appendChild(svg);

    const states = cluster.uavs.map((uav) => Object.assign({}, uav));
    this.renderUavs(dataPanel, states);
    log.add("虚拟无人机集群演示开始，未连接真实飞控、MAVLink或无人机设备");
    await DemoUtils.sleep(600, controller);
    log.add("区域巡检任务创建，划分四个任务区");

    for (let i = 0; i < states.length; i += 1) {
      states[i].action = "执行中";
      nodes[i].classList.add("is-lit");
      log.add(`${states[i].id} 接收任务包`);
      this.renderUavs(dataPanel, states);
      if (!(await DemoUtils.sleep(controller.lowPower ? 260 : 520, controller))) return;
    }

    for (let tick = 0; tick < 9; tick += 1) {
      states.forEach((uav, index) => {
        if (tick === 4 && index === 1) {
          uav.action = "短时掉线";
          uav.latency = 999;
          nodes[index].classList.remove("is-lit");
        } else if (tick === 5 && index === 2) {
          uav.action = "接管UAV-02剩余任务";
          uav.progress = Math.min(100, uav.progress + 24);
        } else {
          uav.progress = Math.min(100, uav.progress + DemoUtils.random(8, 17));
        }
        if (tick === 6 && index === 1) {
          uav.action = "恢复上线";
          uav.latency = 24;
          nodes[index].classList.add("is-lit");
        }
      });
      if (tick === 4) log.add("UAV-02 通信暂时中断");
      if (tick === 5) log.add("触发任务重分配，UAV-03 接管剩余任务");
      if (tick === 6) log.add("UAV-02 恢复连接");
      this.renderUavs(dataPanel, states);
      if (!(await DemoUtils.sleep(controller.lowPower ? 350 : 760, controller))) return;
    }
    states.forEach((uav) => {
      uav.progress = 100;
      uav.action = "场景完成";
    });
    this.renderUavs(dataPanel, states);
    log.add("集群任务协同成功：虚拟演示完成");
  }

  renderUavs(panel, states) {
    DemoUtils.clear(panel);
    const note = DemoUtils.el("p", "demo-warning", "当前为虚拟无人机集群演示，未连接真实飞控、MAVLink或无人机设备。");
    panel.appendChild(note);
    for (const uav of states) {
      const row = DemoUtils.el("div", "uav-row");
      row.append(
        DemoUtils.el("span", "", uav.id),
        DemoUtils.el("strong", "", `${uav.action} · 电量${uav.battery}% · 高度${uav.alt}m · 延迟${uav.latency}ms · 进度${uav.progress}%`)
      );
      panel.appendChild(row);
    }
  }

  pause() {}
  resume() {}
  reset() {}
  destroy() {}
}

window.ClusterDemo = ClusterDemo;
