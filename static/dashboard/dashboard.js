(function () {
  const charts = window.dashboardCharts || {};
  const config = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };
  const draw = (id, spec) => {
    const target = document.getElementById(id);
    if (!target || !spec || !window.Plotly) return;
    const layout = Object.assign({
      paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff", font: { family: "DM Sans, sans-serif", color: "#52615b", size: 11 },
      margin: { t: 18, r: 15, b: 35, l: 48 }, xaxis: { gridcolor: "#edf1ee", zerolinecolor: "#d7dfda" },
      yaxis: { gridcolor: "#edf1ee", zerolinecolor: "#d7dfda" }
    }, spec.layout || {});
    window.Plotly.newPlot(target, spec.data || [], layout, config);
  };
  draw("category-chart", charts.category);
  draw("issuer-chart", charts.issuer);
  draw("comparison-chart", charts.comparison);
  draw("correlation-chart", charts.correlation);
  draw("detail-chart", charts.detail);

  if (charts.comparison) {
    const normalized = charts.comparison.data || [];
    const drawdown = normalized.map((trace) => {
      const values = trace.y || [];
      let peak = -Infinity;
      const series = values.map((value) => {
        if (value !== null && value > peak) peak = value;
        return value === null || !Number.isFinite(peak) ? null : value / peak - 1;
      });
      return Object.assign({}, trace, { y: series, fill: "tozeroy" });
    });
    const layout = Object.assign({}, charts.comparison.layout || {}, { yaxis: { title: "Drawdown", tickformat: ".0%" } });
    draw("drawdown-chart", { data: drawdown, layout });
  }

  const range = document.getElementById("min-aum");
  if (range) range.addEventListener("input", () => {
    const output = document.querySelector(".field-label strong");
    if (output) output.textContent = `$${Number(range.value).toFixed(1)}B`;
  });

  document.querySelectorAll("[data-tab-link]").forEach((link) => link.addEventListener("click", (event) => {
    event.preventDefault();
    const params = new URLSearchParams(window.location.search);
    params.set("tab", link.dataset.tabLink);
    window.location.assign(`?${params.toString()}`);
  }));
})();