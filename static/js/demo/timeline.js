window.DemoUtils = {
  clear(element) {
    while (element.firstChild) element.removeChild(element.firstChild);
  },
  el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  },
  svg(tag, attrs) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      node.setAttribute(key, value);
    }
    return node;
  },
  metricList(container, rows) {
    DemoUtils.clear(container);
    for (const [name, value] of rows) {
      const row = DemoUtils.el("div", "metric-row");
      row.append(DemoUtils.el("span", "", name), DemoUtils.el("strong", "", value));
      container.appendChild(row);
    }
  },
  sleep(ms, controller) {
    return new Promise((resolve) => {
      const started = Date.now();
      const tick = () => {
        if (controller && controller.cancelled) return resolve(false);
        if (controller && controller.paused) return setTimeout(tick, 120);
        if (Date.now() - started >= ms) return resolve(true);
        setTimeout(tick, 80);
      };
      tick();
    });
  },
  random(min, max, digits = 0) {
    const value = Math.random() * (max - min) + min;
    return digits ? Number(value.toFixed(digits)) : Math.round(value);
  },
};

class DemoEventLog {
  constructor(element) {
    this.element = element;
    this.items = [];
  }

  add(message) {
    const time = new Date().toLocaleTimeString();
    const line = `${time} ${message}`;
    this.items.push(line);
    const li = DemoUtils.el("li", "", line);
    this.element.appendChild(li);
    this.element.scrollTop = this.element.scrollHeight;
  }

  reset() {
    this.items = [];
    DemoUtils.clear(this.element);
  }
}

window.DemoEventLog = DemoEventLog;
