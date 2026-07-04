const state = {
  data: null,
  region: "All",
  income: "All",
  country: "",
  compare: "",
  metric: "",
  search: "",
};

const el = (id) => document.getElementById(id);

function uniq(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function fmt(value, metricId) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const meta = state.data.metrics[metricId] || {};
  const abs = Math.abs(value);
  if (meta.format === "currency") {
    return new Intl.NumberFormat("en", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
  }
  if (meta.format === "large" || abs >= 1000000) {
    return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value);
  }
  if (meta.format === "percent") {
    return `${new Intl.NumberFormat("en", { maximumFractionDigits: 2 }).format(value)}%`;
  }
  return new Intl.NumberFormat("en", { maximumFractionDigits: 2 }).format(value);
}

function countryMap() {
  return new Map(state.data.countries.map((country) => [country.code, country]));
}

function metricOptions() {
  return Object.entries(state.data.metrics)
    .sort((a, b) => `${a[1].group} ${a[1].label}`.localeCompare(`${b[1].group} ${b[1].label}`));
}

function fillSelect(select, options, selected) {
  select.innerHTML = "";
  for (const option of options) {
    const node = document.createElement("option");
    node.value = option.value;
    node.textContent = option.label;
    select.appendChild(node);
  }
  select.value = selected;
}

function availableCountries() {
  return state.data.countries.filter((country) => {
    const regionOk = state.region === "All" || country.region === state.region;
    const incomeOk = state.income === "All" || country.income === state.income;
    return regionOk && incomeOk;
  });
}

function latestByMetric(metricId) {
  const countries = countryMap();
  return state.data.latest
    .filter((record) => record.metric === metricId)
    .map((record) => ({ ...record, countryInfo: countries.get(record.country) }))
    .filter((record) => record.countryInfo)
    .filter((record) => state.region === "All" || record.countryInfo.region === state.region)
    .filter((record) => state.income === "All" || record.countryInfo.income === state.income);
}

function seriesFor(countryCode, metricId) {
  return state.data.records
    .filter((record) => record.country === countryCode && record.metric === metricId)
    .sort((a, b) => a.year - b.year);
}

function updateSelectors() {
  const regions = [{ value: "All", label: "All regions" }, ...uniq(state.data.countries.map((c) => c.region)).map((x) => ({ value: x, label: x }))];
  const incomes = [{ value: "All", label: "All income groups" }, ...uniq(state.data.countries.map((c) => c.income)).map((x) => ({ value: x, label: x }))];
  fillSelect(el("regionFilter"), regions, state.region);
  fillSelect(el("incomeFilter"), incomes, state.income);

  const countries = availableCountries();
  if (!countries.some((country) => country.code === state.country)) {
    state.country = countries[0]?.code || "";
  }
  if (!countries.some((country) => country.code === state.compare)) {
    state.compare = countries.find((country) => country.code !== state.country)?.code || "";
  }

  fillSelect(
    el("countryFilter"),
    countries.map((country) => ({ value: country.code, label: country.name })),
    state.country,
  );
  fillSelect(
    el("compareFilter"),
    [{ value: "", label: "No comparison" }, ...countries.filter((country) => country.code !== state.country).map((country) => ({ value: country.code, label: country.name }))],
    state.compare,
  );

  const metrics = metricOptions().map(([id, meta]) => ({ value: id, label: `${meta.group}: ${meta.label}` }));
  if (!state.metric) state.metric = "SE.XPD.TOTL.GD.ZS";
  fillSelect(el("metricFilter"), metrics, state.metric);
}

function scale(domainMin, domainMax, rangeMin, rangeMax) {
  const span = domainMax - domainMin || 1;
  return (value) => rangeMin + ((value - domainMin) / span) * (rangeMax - rangeMin);
}

function emptyChart(container, text) {
  container.innerHTML = `<div class="empty-state">${text}</div>`;
}

function drawLineChart() {
  const container = el("lineChart");
  const main = seriesFor(state.country, state.metric);
  const compare = state.compare ? seriesFor(state.compare, state.metric) : [];
  const all = [...main, ...compare];
  if (main.length < 2) {
    emptyChart(container, "Not enough yearly data for this country and metric.");
    return;
  }

  const width = container.clientWidth || 900;
  const height = 330;
  const pad = { left: 62, right: 22, top: 22, bottom: 42 };
  const years = all.map((record) => record.year);
  const values = all.map((record) => record.value);
  const x = scale(Math.min(...years), Math.max(...years), pad.left, width - pad.right);
  const y = scale(Math.min(...values), Math.max(...values), height - pad.bottom, pad.top);
  const path = (rows) => rows.map((record, index) => `${index ? "L" : "M"}${x(record.year)},${y(record.value)}`).join(" ");
  const dots = (rows, cls) => rows.map((record) => `<circle class="dot ${cls}" cx="${x(record.year)}" cy="${y(record.value)}" r="4"><title>${record.year}: ${fmt(record.value, state.metric)}</title></circle>`).join("");
  const ticks = [Math.min(...years), Math.round((Math.min(...years) + Math.max(...years)) / 2), Math.max(...years)];
  const valueTicks = [Math.min(...values), (Math.min(...values) + Math.max(...values)) / 2, Math.max(...values)];
  const comparePath = compare.length > 1 ? `<path class="chart-line compare" d="${path(compare)}"></path>${dots(compare, "compare")}` : "";

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" stroke="#dce3df"></line>
      <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" stroke="#dce3df"></line>
      ${ticks.map((tick) => `<text class="tick" x="${x(tick)}" y="${height - 15}" text-anchor="middle">${tick}</text>`).join("")}
      ${valueTicks.map((tick) => `<text class="tick" x="${pad.left - 10}" y="${y(tick) + 4}" text-anchor="end">${fmt(tick, state.metric)}</text>`).join("")}
      <path class="chart-line" d="${path(main)}"></path>
      ${dots(main, "")}
      ${comparePath}
    </svg>`;
}

function drawBarChart() {
  const container = el("barChart");
  const rows = state.data.regions
    .filter((row) => row.metric === state.metric)
    .sort((a, b) => b.average - a.average)
    .slice(0, 9);
  if (!rows.length) {
    emptyChart(container, "No regional summary is available for this metric.");
    return;
  }
  const width = container.clientWidth || 520;
  const height = 300;
  const pad = { left: 132, right: 24, top: 18, bottom: 24 };
  const maxValue = Math.max(...rows.map((row) => row.average)) || 1;
  const barHeight = (height - pad.top - pad.bottom) / rows.length - 8;
  const x = scale(0, maxValue, pad.left, width - pad.right);
  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      ${rows.map((row, index) => {
        const y = pad.top + index * (barHeight + 8);
        return `
          <text class="tick" x="${pad.left - 10}" y="${y + barHeight * 0.68}" text-anchor="end">${row.region.slice(0, 22)}</text>
          <rect class="bar" x="${pad.left}" y="${y}" width="${Math.max(2, x(row.average) - pad.left)}" height="${barHeight}" rx="4"></rect>
          <text class="tick" x="${Math.min(width - pad.right, x(row.average) + 6)}" y="${y + barHeight * 0.68}">${fmt(row.average, state.metric)}</text>`;
      }).join("")}
    </svg>`;
}

function drawScatterChart() {
  const container = el("scatterChart");
  const selected = latestByMetric(state.metric);
  const gdp = new Map(state.data.latest.filter((record) => record.metric === "NY.GDP.PCAP.CD").map((record) => [record.country, record]));
  const points = selected
    .map((record) => ({ ...record, gdp: gdp.get(record.country)?.value }))
    .filter((record) => record.gdp && record.metric !== "NY.GDP.PCAP.CD");
  if (points.length < 4) {
    emptyChart(container, "Choose an education, health, technology, R&D, or quality metric to compare with GDP.");
    return;
  }
  const width = container.clientWidth || 520;
  const height = 300;
  const pad = { left: 62, right: 22, top: 18, bottom: 42 };
  const x = scale(Math.min(...points.map((p) => p.gdp)), Math.max(...points.map((p) => p.gdp)), pad.left, width - pad.right);
  const y = scale(Math.min(...points.map((p) => p.value)), Math.max(...points.map((p) => p.value)), height - pad.bottom, pad.top);
  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" stroke="#dce3df"></line>
      <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" stroke="#dce3df"></line>
      <text class="axis-label" x="${width / 2}" y="${height - 10}" text-anchor="middle">GDP per capita</text>
      ${points.map((point) => `<circle class="scatter" cx="${x(point.gdp)}" cy="${y(point.value)}" r="${point.country === state.country ? 7 : 4}"><title>${point.countryInfo.name}: ${fmt(point.value, state.metric)} | GDP ${fmt(point.gdp, "NY.GDP.PCAP.CD")}</title></circle>`).join("")}
    </svg>`;
}

function updateKpis() {
  const countries = countryMap();
  const selectedCountry = countries.get(state.country);
  const metric = state.data.metrics[state.metric];
  const rows = seriesFor(state.country, state.metric);
  const latest = rows[rows.length - 1];
  const regionRows = latestByMetric(state.metric).filter((record) => record.countryInfo.region === selectedCountry?.region);
  const avg = regionRows.length ? regionRows.reduce((sum, row) => sum + row.value, 0) / regionRows.length : null;

  el("selectedValue").textContent = latest ? fmt(latest.value, state.metric) : "-";
  el("selectedMeta").textContent = latest ? `${selectedCountry.name}, ${latest.year} | ${metric.unit}` : "No value";
  el("regionalValue").textContent = avg === null ? "-" : fmt(avg, state.metric);
  el("regionalMeta").textContent = selectedCountry ? selectedCountry.region : "-";
  el("countryCount").textContent = String(availableCountries().length);
  el("recordCount").textContent = `${state.data.records.length.toLocaleString()} data points loaded`;
  el("latestYear").textContent = latest ? String(latest.year) : "-";
  el("sourceName").textContent = latest ? latest.source : "-";
  el("trendSubtitle").textContent = `${selectedCountry?.name || "-"} | ${metric.label} (${metric.unit})`;
  el("rankingSubtitle").textContent = `${metric.label}, latest available value`;
}

function updateRanking() {
  const rows = latestByMetric(state.metric)
    .filter((record) => record.countryInfo.name.toLowerCase().includes(state.search.toLowerCase()))
    .sort((a, b) => b.value - a.value)
    .slice(0, 60);
  el("rankingBody").innerHTML = rows.map((record, index) => `
    <tr>
      <td>${index + 1}</td>
      <td>${record.countryInfo.name}</td>
      <td>${record.countryInfo.region}</td>
      <td>${record.countryInfo.income}</td>
      <td>${record.year}</td>
      <td class="numeric">${fmt(record.value, state.metric)}</td>
    </tr>`).join("");
}

function render() {
  updateSelectors();
  updateKpis();
  drawLineChart();
  drawBarChart();
  drawScatterChart();
  updateRanking();
}

function attachEvents() {
  el("regionFilter").addEventListener("change", (event) => {
    state.region = event.target.value;
    render();
  });
  el("incomeFilter").addEventListener("change", (event) => {
    state.income = event.target.value;
    render();
  });
  el("countryFilter").addEventListener("change", (event) => {
    state.country = event.target.value;
    render();
  });
  el("compareFilter").addEventListener("change", (event) => {
    state.compare = event.target.value;
    render();
  });
  el("metricFilter").addEventListener("change", (event) => {
    state.metric = event.target.value;
    render();
  });
  el("searchBox").addEventListener("input", (event) => {
    state.search = event.target.value;
    updateRanking();
  });
  el("resetFilters").addEventListener("click", () => {
    state.region = "All";
    state.income = "All";
    state.metric = "SE.XPD.TOTL.GD.ZS";
    state.search = "";
    el("searchBox").value = "";
    render();
  });
  window.addEventListener("resize", () => {
    drawLineChart();
    drawBarChart();
    drawScatterChart();
  });
}

async function init() {
  const response = await fetch("data/dashboard_data.json");
  state.data = await response.json();
  const countries = availableCountries();
  state.country = countries.find((country) => country.code === "IND")?.code || countries[0]?.code || "";
  state.compare = countries.find((country) => country.code === "USA")?.code || "";
  state.metric = "SE.XPD.TOTL.GD.ZS";
  attachEvents();
  render();
}

init().catch((error) => {
  document.body.innerHTML = `<main class="empty-state">Could not load dashboard data. Run the data build script first.<br>${error.message}</main>`;
});
