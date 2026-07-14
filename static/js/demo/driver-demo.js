class DriverDemo {
  constructor(context) {
    this.context = context;
    this.rows = [];
  }

  async start() {
    const { data, stage, dataPanel, controller, log } = this.context;
    this.rows = data.platform.drivers.map((row) => ({
      category: row[0],
      component: row[1],
      status: row[2],
      version: row[3],
      node: row[4],
      description: row[5],
      advice: row[6],
    }));
    DemoUtils.clear(stage);
    DemoUtils.metricList(dataPanel, [
      ["数据标识", "模拟数据 · 虚拟演示 · Demo Mode"],
      ["组件数量", String(this.rows.length)],
      ["说明", "未读取当前设备实际状态"],
    ]);

    const tools = DemoUtils.el("div", "driver-tools");
    const category = DemoUtils.el("select");
    const status = DemoUtils.el("select");
    const search = DemoUtils.el("input");
    search.placeholder = "关键字搜索";
    for (const value of ["全部分类"].concat(Array.from(new Set(this.rows.map((row) => row.category))))) {
      const option = DemoUtils.el("option", "", value);
      category.appendChild(option);
    }
    for (const value of ["全部状态"].concat(Array.from(new Set(this.rows.map((row) => row.status))))) {
      const option = DemoUtils.el("option", "", value);
      status.appendChild(option);
    }
    tools.append(category, status, search);

    const table = DemoUtils.el("table", "driver-table");
    const detail = DemoUtils.el("div", "driver-detail", "点击表格行查看模拟详情。");
    const exportButton = DemoUtils.el("button", "secondary", "导出CSV");
    exportButton.type = "button";
    stage.append(tools, exportButton, table, detail, DemoUtils.el("p", "demo-warning", "以上驱动、版本和设备节点为演示数据，未读取当前设备实际状态。"));

    const render = () => this.renderTable(table, detail, {
      category: category.value,
      status: status.value,
      keyword: search.value.trim().toLowerCase(),
    });
    category.addEventListener("change", render);
    status.addEventListener("change", render);
    search.addEventListener("input", render);
    exportButton.addEventListener("click", () => this.exportCsv());
    render();

    log.add("底层驱动及算法环境表格虚拟演示开始");
    await DemoUtils.sleep(controller.lowPower ? 2400 : 5200, controller);
    log.add("驱动环境筛选表格演示完成");
  }

  renderTable(table, detail, filters) {
    DemoUtils.clear(table);
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["分类", "组件", "模拟状态", "模拟版本", "虚拟设备节点", "功能说明", "部署建议"].forEach((name) => headRow.appendChild(DemoUtils.el("th", "", name)));
    head.appendChild(headRow);
    const body = document.createElement("tbody");
    const rows = this.rows.filter((row) => {
      const categoryOk = filters.category === "全部分类" || row.category === filters.category;
      const statusOk = filters.status === "全部状态" || row.status === filters.status;
      const text = Object.values(row).join(" ").toLowerCase();
      return categoryOk && statusOk && (!filters.keyword || text.includes(filters.keyword));
    });
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      [row.category, row.component, row.status, row.version, row.node, row.description, row.advice].forEach((value) => tr.appendChild(DemoUtils.el("td", "", value)));
      tr.addEventListener("click", () => {
        detail.textContent = `组件名称：${row.component}；虚拟检测命令：demo inspect ${row.component}；虚拟输出：${row.status} ${row.version}；模拟部署路径：/opt/demo/${row.component.toLowerCase()}；依赖关系：${row.category}能力链；功能描述：${row.description}`;
      });
      body.appendChild(tr);
    });
    table.append(head, body);
  }

  exportCsv() {
    const header = ["分类", "组件", "模拟状态", "模拟版本", "虚拟设备节点", "功能说明", "部署建议"];
    const lines = [header].concat(this.rows.map((row) => [row.category, row.component, row.status, row.version, row.node, row.description, row.advice]));
    const csv = lines.map((line) => line.map((item) => `"${String(item).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "rk3588-demo-drivers.csv";
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  }

  pause() {}
  resume() {}
  reset() {}
  destroy() {}
}

window.DriverDemo = DriverDemo;
