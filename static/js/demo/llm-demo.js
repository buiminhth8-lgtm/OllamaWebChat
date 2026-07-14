class LlmDemo {
  constructor(context) {
    this.context = context;
    this.model = null;
  }

  async start() {
    const { data, stage, dataPanel, controller, log } = this.context;
    const llm = data.platform.llm;
    this.model = this.model || llm.models[0];
    DemoUtils.clear(stage);
    DemoUtils.clear(dataPanel);

    const select = DemoUtils.el("select");
    for (const model of llm.models) {
      const option = DemoUtils.el("option", "", model.name);
      option.value = model.name;
      select.appendChild(option);
    }
    select.value = this.model.name;
    select.addEventListener("change", () => {
      this.model = llm.models.find((item) => item.name === select.value) || llm.models[0];
      this.renderMetrics(dataPanel);
    });
    dataPanel.appendChild(select);
    this.renderMetrics(dataPanel);

    const wrap = DemoUtils.el("div", "llm-flow");
    const flow = DemoUtils.el("div", "flow-strip");
    for (const item of llm.flow) flow.appendChild(DemoUtils.el("div", "flow-node", item));
    const track = DemoUtils.el("div", "token-track");
    const output = DemoUtils.el("div", "typewriter");
    wrap.append(flow, track, output);
    stage.appendChild(wrap);

    log.add("大模型虚拟调用开始，未访问真实 Ollama");
    for (let i = 0; i < 12; i += 1) {
      const token = DemoUtils.el("span", "token", `T${i + 1}`);
      token.style.animationDelay = `${i * 0.16}s`;
      track.appendChild(token);
    }
    await DemoUtils.sleep(900, controller);

    let text = "";
    for (const char of llm.answer) {
      if (controller.cancelled) return;
      while (controller.paused) await DemoUtils.sleep(120, controller);
      text += char;
      output.textContent = text;
      this.renderMetrics(dataPanel, true);
      await DemoUtils.sleep(controller.lowPower ? 45 : 28, controller);
    }
    log.add("Token 流式输出演示完成：模拟性能数据");
  }

  renderMetrics(panel, jitter = false) {
    const model = this.model;
    const firstToken = jitter ? DemoUtils.random(620, 760) : model.first_token_ms;
    const speed = jitter ? DemoUtils.random(10.5, 12.5, 1) : model.speed;
    const npu = jitter ? DemoUtils.random(45, 75) : 62;
    const rows = [
      ["当前模型", model.name],
      ["量化方式", model.quant],
      ["推理设备", model.device],
      ["首Token延迟", `${firstToken}ms`],
      ["生成速度", `${speed} tokens/s`],
      ["上下文长度", String(model.context)],
      ["模型内存", model.memory],
      ["NPU负载", `${npu}%`],
      ["数据标识", "模拟性能数据 · Demo Mode"],
    ];
    const oldSelect = panel.querySelector("select");
    const selectValue = oldSelect ? oldSelect.value : "";
    DemoUtils.clear(panel);
    if (oldSelect) {
      panel.appendChild(oldSelect);
      oldSelect.value = selectValue;
    }
    DemoUtils.metricList(panel, rows);
  }

  pause() {}
  resume() {}
  reset() {}
  destroy() {}
}

window.LlmDemo = LlmDemo;
