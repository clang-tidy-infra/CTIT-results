// Charts and tables of the daily check timings on timings.html. The runs come
// from timings/days.js, the totals from the page's timings-data element, and
// the times of single checks from timings/checks/<check>.js, loaded when the
// check filter needs them.
(() => {
  const data = JSON.parse(document.getElementById("timings-data").textContent);
  const days = window.TIMINGS_DAYS;
  const loadedChecks = window.TIMINGS_CHECKS;
  const METRICS = data.metrics;
  const SERIES = data.series;
  const ALL_CHECKS = data.checks.names;
  const CHECK_NAMES = new Set(ALL_CHECKS);
  const LLVM_URL = "https://github.com/llvm/llvm-project";
  const DOCS_URL = "https://clang.llvm.org/extra/clang-tidy/checks";
  const LINE_COLOR = "#2a78d6";
  const GRID_COLOR = "#e6e6e6";
  const AXIS_COLOR = "#bbbbbb";
  const MARKER_COLOR = "#999999";
  const DAY_MS = 24 * 60 * 60 * 1000;
  const MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");

  const metricSelect = document.getElementById("metric");
  const rangeSelect = document.getElementById("range");
  const checkFilter = document.getElementById("check-filter");
  const checkCount = document.getElementById("check-count");
  const checkDocs = document.getElementById("check-docs");
  const checkDocsLink = document.getElementById("check-docs-link");
  const boxes = [...document.querySelectorAll('input[name="project"]')];
  const totalTitle = document.getElementById("total-title");
  const totalDiv = document.getElementById("total");
  const projectsTitle = document.getElementById("projects-title");
  const projectsDiv = document.getElementById("projects");
  const checksTable = document.getElementById("checks");
  const table = document.getElementById("table");

  // One slot per calendar day, so a day without a run is a gap in the line
  // instead of a straight segment between its neighbours. slotDays holds the
  // index of the run on each day, or -1.
  const dayTime = (i) => Date.parse(`${days[i].date}T00:00:00Z`);
  const timeline = [];
  for (let t = dayTime(0); t <= dayTime(days.length - 1); t += DAY_MS) timeline.push(t);
  const dayByTime = new Map(days.map((_, i) => [dayTime(i), i]));
  const slotDays = timeline.map((t) => dayByTime.get(t) ?? -1);
  const slotByTime = new Map(timeline.map((t, k) => [t, k]));

  // Stretches of runs on the same runner. The timings jump with the hardware,
  // so the charts draw a line wherever the runner changes and name the runner
  // of every stretch. `start` is halfway between the last run on the previous
  // runner and the first run on this one.
  const runnerStretches = [{ start: -Infinity, runner: days[0].runner }];
  for (let i = 1; i < days.length; i++) {
    if (days[i].runner !== days[i - 1].runner) {
      runnerStretches.push({ start: (dayTime(i - 1) + dayTime(i)) / 2, runner: days[i].runner });
    }
  }

  let graphs = [];
  let checkSort = { key: "now", descending: true };
  let renderCount = 0;

  const esc = (text) =>
    String(text).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

  // Same as slug() in ctit_site/model.py, which names the files of checks.
  const slug = (text) => text.replace(/[^A-Za-z0-9._-]/g, "_");

  const docsUrl = (check) => {
    const dash = check.indexOf("-");
    const module = check.slice(0, dash);
    if (dash < 0 || module === "clang") return null;
    return `${DOCS_URL}/${module}/${check.slice(dash + 1)}.html`;
  };

  const seconds = (value) => {
    const size = Math.abs(value);
    if (size >= 100) return Math.round(value).toLocaleString("en-US");
    return value.toFixed(size >= 10 ? 1 : 2);
  };

  const change = (value, previous) => {
    const delta = value - previous;
    const sign = delta >= 0 ? "+" : "-";
    const percent = previous
      ? ` (${sign}${Math.abs((delta / previous) * 100).toFixed(1)}%)`
      : "";
    return `${sign}${seconds(Math.abs(delta))} s${percent}`;
  };

  const changeClass = (delta) => (delta > 0 ? "up" : delta < 0 ? "down" : "dim");

  // Day-to-day noise moves most checks by a few percent, so the checks table
  // only colors changes of at least NOTABLE_PERCENT and NOTABLE_SECONDS, like
  // the comments on the CTIT check timings issue.
  const NOTABLE_PERCENT = 10;
  const NOTABLE_SECONDS = 1;
  const notableClass = (delta, previous) =>
    Math.abs(delta) >= NOTABLE_SECONDS &&
    (previous === 0 || Math.abs(delta / previous) * 100 >= NOTABLE_PERCENT)
      ? changeClass(delta)
      : "dim";

  const selectedProjects = () => boxes.filter((b) => b.checked).map((b) => b.value);

  // The check filter, read like clang-tidy's -checks: comma-separated terms,
  // "*" matches anything, a leading "-" excludes, and the last matching term
  // decides. A term without "*" matches the checks that contain it, or only
  // the check of that exact name.
  const termMatcher = (pattern) => {
    if (pattern.includes("*")) {
      const parts = pattern.split("*").map((part) => part.replace(/[.+?^${}()|[\]\\]/g, "\\$&"));
      const regex = new RegExp(`^${parts.join(".*")}$`);
      return (name) => regex.test(name);
    }
    if (CHECK_NAMES.has(pattern)) return (name) => name === pattern;
    return (name) => name.includes(pattern);
  };

  // The checks the filter selects, or null when it is empty (all checks).
  const filterChecks = (text) => {
    const terms = text
      .toLowerCase()
      .split(",")
      .map((term) => term.trim())
      .filter(Boolean)
      .map((term) => ({
        exclude: term.startsWith("-"),
        matches: termMatcher(term.replace(/^-/, "")),
      }));
    if (!terms.length) return null;
    // A filter that starts by excluding keeps every other check.
    const initial = terms[0].exclude;
    return ALL_CHECKS.filter((name) =>
      terms.reduce((selected, term) => (term.matches(name) ? !term.exclude : selected), initial),
    );
  };

  const loading = new Map();
  const loadCheck = (name) => {
    if (name in loadedChecks) return Promise.resolve();
    if (!loading.has(name)) {
      loading.set(
        name,
        new Promise((resolve) => {
          const script = document.createElement("script");
          script.src = `timings/checks/${slug(name)}.js`;
          script.onload = script.onerror = () => resolve();
          document.head.append(script);
        }),
      );
    }
    return loading.get(name);
  };

  // The time of a loaded check on a project in run i: 0 if it did not run on
  // the project, null if it was not in the run at all (added or removed).
  const checkTime = (name, project, i) => {
    const check = loadedChecks[name];
    if (!check?.in_run[i]) return null;
    return check.projects[project]?.[i] ?? 0;
  };

  // {project: [seconds for each run]} summed over the checks. A run without
  // per-project check times, without timings for the project, or without any
  // of the checks is null.
  const checksSeries = async (checks) => {
    const chosen = new Set(checks);
    // Loading most checks one by one is slow, so then load the others and
    // subtract them from the project's total instead.
    const subtract = checks.length > ALL_CHECKS.length / 2;
    const loads = subtract ? ALL_CHECKS.filter((name) => !chosen.has(name)) : checks;
    await Promise.all(loads.map(loadCheck));
    const series = {};
    for (const [project, totals] of Object.entries(SERIES.check)) {
      series[project] = days.map((day, i) => {
        if (!day.detailed || totals[i] === null) return null;
        let sum = null;
        for (const name of loads) {
          const value = checkTime(name, project, i);
          if (value !== null) sum = (sum ?? 0) + value;
        }
        if (subtract) return Math.max(0, totals[i] - (sum ?? 0));
        return sum;
      });
    }
    return series;
  };

  const valueOf = (series, project, i) => series[project]?.[i] ?? null;

  const missingIn = (series, projects, i) =>
    projects.filter((project) => valueOf(series, project, i) === null);

  // Sum over the projects that have timings that day, e.g. a project added to
  // CTIT later only counts from then on; null if none of them has timings.
  const sumOf = (series, projects, i) => {
    let sum = null;
    for (const project of projects) {
      const value = valueOf(series, project, i);
      if (value !== null) sum = (sum ?? 0) + value;
    }
    return sum;
  };

  // The index of the closest earlier entry with a value, or -1.
  const previousIndex = (values, i) => {
    for (let j = i - 1; j >= 0; j--) {
      if (values[j] !== null) return j;
    }
    return -1;
  };

  // The LLVM changes since the previous run.
  const llvmUrl = (i) => {
    const current = days[i].llvm;
    const previous = i > 0 ? days[i - 1].llvm : null;
    if (!previous || previous === current) return `${LLVM_URL}/commit/${current}`;
    return `${LLVM_URL}/compare/${previous}...${current}`;
  };

  const dateWindow = () => {
    if (rangeSelect.value === "all") return null;
    const last = timeline[timeline.length - 1];
    return [last - Number(rangeSelect.value) * DAY_MS, last + DAY_MS / 2];
  };

  // values has one entry per slot of the timeline.
  const legendFormatter = (values, label, missingAt) => (d) => {
    if (d.x == null) return "";
    const k = slotByTime.get(d.x);
    const i = slotDays[k];
    if (i < 0) return "no run on this day";
    const value = values[k];
    const lines = [
      value === null ? "<b>no timings</b>" : `<b>${seconds(value)} s</b> ${esc(label)}`,
      `${esc(days[i].date)}, LLVM ${esc(days[i].llvm.slice(0, 10))}`,
    ];
    const j = previousIndex(values, k);
    if (value !== null && j >= 0) {
      lines.push(`${change(value, values[j])} vs ${esc(days[slotDays[j]].date)}`);
    }
    const missing = value === null ? [] : missingAt(i);
    if (missing.length) lines.push(`without ${esc(missing.join(", "))}`);
    lines.push(`runner ${esc(days[i].runner)}`);
    return lines.join("<br />");
  };

  // Dygraphs flips the legend to the left of the point near the right edge of
  // the chart, where it can end up outside the page. Keep it to the right and
  // only shift it back as far as needed to stay inside the window.
  const LEGEND_GAP = 16;
  const placeLegend = (graph, points) => {
    const legend = graph.graphDiv.querySelector(".dygraph-legend");
    if (!legend || !points.length) return;
    const point = points[0];
    const room =
      document.documentElement.clientWidth -
      graph.graphDiv.getBoundingClientRect().left -
      legend.offsetWidth -
      LEGEND_GAP;
    legend.style.left = `${Math.max(0, Math.min(point.canvasx + LEGEND_GAP, room))}px`;
    if (Number.isNaN(point.canvasy)) {
      const area = graph.getArea();
      legend.style.top = `${area.y + area.h / 2 - legend.offsetHeight / 2}px`;
    }
  };

  // The runner label that fits `width` pixels: "runner: <name>", else the name
  // shortened with an ellipsis, else "" when too little of it would be left.
  const runnerLabel = (ctx, runner, width) => {
    const full = `runner: ${runner}`;
    if (ctx.measureText(full).width <= width) return full;
    for (let n = runner.length - 1; n >= 6; n--) {
      const short = `${runner.slice(0, n)}…`;
      if (ctx.measureText(short).width <= width) return short;
    }
    return "";
  };

  const drawRunners = (labelled) => (ctx, area, graph) => {
    ctx.save();
    ctx.strokeStyle = MARKER_COLOR;
    ctx.fillStyle = MARKER_COLOR;
    ctx.lineWidth = 1;
    ctx.font = "11px monospace";
    const right = area.x + area.w;
    runnerStretches.forEach(({ start, runner }, k) => {
      const next = runnerStretches[k + 1];
      const x = start === -Infinity ? area.x : Math.round(graph.toDomXCoord(start)) + 0.5;
      const end = next ? Math.round(graph.toDomXCoord(next.start)) + 0.5 : right;
      if (x > area.x && x < right) {
        ctx.beginPath();
        ctx.moveTo(x, area.y);
        ctx.lineTo(x, area.y + area.h);
        ctx.stroke();
      }
      if (!labelled) return;
      // The visible part of the stretch, which may begin left of the chart.
      const from = Math.max(x, area.x);
      const to = Math.min(end, right);
      const text = runnerLabel(ctx, runner, to - from - 8);
      if (text) ctx.fillText(text, from + 4, area.y + 12);
    });
    ctx.restore();
  };

  // values has one entry per slot of the timeline.
  const draw = (div, label, values, labelled, missingAt = () => []) =>
    new Dygraph(
      div,
      timeline.map((time, k) => [new Date(time), values[k]]),
      {
        labels: ["Date", label],
        labelsUTC: true,
        colors: [LINE_COLOR],
        strokeWidth: 2,
        drawGapEdgePoints: true,
        pointSize: 3,
        highlightCircleSize: 5,
        gridLineColor: GRID_COLOR,
        axisLineColor: AXIS_COLOR,
        legend: "follow",
        legendFormatter: legendFormatter(values, label, missingAt),
        underlayCallback: drawRunners(labelled),
        highlightCallback(event, x, points) {
          placeLegend(this, points);
        },
        dateWindow: dateWindow(),
        axes: {
          x: {
            pixelsPerLabel: 50,
            axisLabelFormatter: (d) => `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`,
          },
          y: {
            axisLabelWidth: 64,
            axisLabelFormatter: (v) => seconds(v),
          },
        },
        clickCallback: (event, x) => {
          const i = slotDays[slotByTime.get(x)];
          if (i >= 0) window.open(llvmUrl(i), "_blank", "noopener");
        },
      },
    );

  const describeProjects = (projects) => {
    if (projects.length === boxes.length) {
      return boxes.length === 1 ? projects[0] : `all ${boxes.length} projects`;
    }
    if (projects.length <= 3) return projects.join(", ");
    return `${projects.length} of ${boxes.length} projects`;
  };

  const describeChecks = (checks) => {
    if (checks === null) return "";
    if (checks.length <= 3) return ` of ${checks.join(", ")}`;
    return ` of ${checks.length} checks`;
  };

  const cell = (row, text, className) => {
    const td = row.insertCell();
    if (className) td.className = className;
    td.textContent = text;
    return td;
  };

  const linkCell = (row, text, href, title, className) => {
    const td = row.insertCell();
    if (className) td.className = className;
    const a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    if (title) a.title = title;
    td.append(a);
    return a;
  };

  const header = (tableElement, columns) => {
    const row = tableElement.createTHead().insertRow();
    for (const [text, className] of columns) {
      const th = document.createElement("th");
      th.textContent = text;
      if (className) th.className = className;
      row.append(th);
    }
    return row;
  };

  // One row per run, newest first.
  const renderTable = (series, projects) => {
    table.replaceChildren();
    header(table, [
      ["Date", "l"],
      ["Total (s)"],
      ["", "d"],
      ...projects.map((project) => [project, "p"]),
      ["LLVM", "l"],
      ["Runner", "l"],
    ]);
    const totals = days.map((_, i) => sumOf(series, projects, i));
    const body = table.createTBody();
    for (let i = days.length - 1; i >= 0; i--) {
      const row = body.insertRow();
      linkCell(row, days[i].date, days[i].run, "workflow run", "l");
      const total = cell(row, totals[i] === null ? "-" : seconds(totals[i]));
      const missing = missingIn(series, projects, i);
      if (missing.length && totals[i] !== null) total.title = `without ${missing.join(", ")}`;
      const j = previousIndex(totals, i);
      if (totals[i] !== null && j >= 0) {
        const td = cell(row, change(totals[i], totals[j]), `d ${changeClass(totals[i] - totals[j])}`);
        td.title = `vs ${days[j].date}`;
      } else {
        cell(row, "", "d");
      }
      for (const project of projects) {
        const value = valueOf(series, project, i);
        cell(row, value === null ? "-" : seconds(value), value === null ? "dim" : "");
      }
      linkCell(row, days[i].llvm.slice(0, 10), llvmUrl(i), "LLVM changes since the previous run", "l");
      cell(row, days[i].runner, "l");
    }
  };

  // The page URL with the filter set to one check.
  const checkHref = (name) => {
    const params = new URLSearchParams(location.search);
    params.set("checks", name);
    params.delete("metric");
    return `?${params}`;
  };

  // One row per selected check: its time in the latest run, summed over the
  // projects, and the change since the previous run and the run a week
  // earlier. A change is left out when the runs differ in runner.
  const renderChecks = (projects, checks) => {
    const { days: compared, values } = data.checks;
    const [latest] = compared;
    const sumAt = (k, j) => {
      let sum = null;
      for (const project of projects) {
        const value = values[project]?.[k]?.[j] ?? null;
        if (value !== null) sum = (sum ?? 0) + value;
      }
      return sum;
    };
    const comparable = (j) =>
      compared[j] !== null && days[compared[j]].runner === days[latest].runner;
    const selected = checks === null ? null : new Set(checks);
    const rows = ALL_CHECKS.map((name, k) => ({ name, k }))
      .filter(({ name }) => selected === null || selected.has(name))
      .map(({ name, k }) => {
        const now = sumAt(k, 0);
        const then = [null, sumAt(k, 1), sumAt(k, 2)];
        const delta = then.map((value, j) =>
          j > 0 && now !== null && value !== null && comparable(j) ? now - value : null,
        );
        return { name, now, then, delta };
      });

    const sortValue = (row) =>
      ({ name: row.name, now: row.now, previous: row.delta[1], week: row.delta[2] })[checkSort.key];
    rows.sort((a, b) => {
      const x = sortValue(a);
      const y = sortValue(b);
      if (x === null || y === null) return (x === null) - (y === null); // Empty cells last.
      const order = typeof x === "string" ? x.localeCompare(y) : x - y;
      return checkSort.descending ? -order : order;
    });

    checksTable.replaceChildren();
    const since = (j, text) => (compared[j] === null ? text : `${text} (${days[compared[j]].date})`);
    const columns = [
      ["name", "Check", "l"],
      ["now", since(0, "Time (s)")],
      ["previous", since(1, "vs previous run"), "d"],
      ["week", since(2, "vs a week earlier"), "d"],
    ];
    const headerRow = header(
      checksTable,
      columns.map(([key, text, className]) => [
        key === checkSort.key ? `${text} ${checkSort.descending ? "▼" : "▲"}` : text,
        className,
      ]),
    );
    [...headerRow.cells].forEach((th, c) => {
      const key = columns[c][0];
      th.classList.add("sortable");
      th.title = "Sort by this column";
      th.addEventListener("click", () => {
        checkSort = {
          key,
          descending: checkSort.key === key ? !checkSort.descending : key !== "name",
        };
        renderChecks(selectedProjects(), filterChecks(checkFilter.value));
      });
    });

    const body = checksTable.createTBody();
    for (const row of rows) {
      const tr = body.insertRow();
      const a = linkCell(tr, row.name, checkHref(row.name), "Show only this check", "l");
      a.addEventListener("click", (event) => {
        event.preventDefault();
        checkFilter.value = row.name;
        render();
        document.getElementById("controls").scrollIntoView();
      });
      cell(tr, row.now === null ? "-" : seconds(row.now), row.now === null ? "dim" : "");
      for (const j of [1, 2]) {
        if (row.delta[j] !== null) {
          cell(tr, change(row.now, row.then[j]), `d ${notableClass(row.delta[j], row.then[j])}`);
        } else {
          const td = cell(tr, "-", "d dim");
          if (row.now !== null && row.then[j] !== null) td.title = "different runner";
        }
      }
    }
  };

  const saveState = (metric, projects, filter) => {
    const params = new URLSearchParams();
    if (metric !== metricSelect.options[0].value) params.set("metric", metric);
    if (rangeSelect.value !== "all") params.set("range", rangeSelect.value);
    if (boxes.some((box) => box.checked !== box.defaultChecked)) {
      params.set("projects", projects.join(","));
    }
    if (filter) params.set("checks", filter);
    const query = params.toString();
    try {
      history.replaceState(null, "", query ? `?${query}` : location.pathname);
    } catch {
      // Some embedding frames refuse history changes; the page works without.
    }
  };

  const loadState = () => {
    const params = new URLSearchParams(location.search);
    if (params.get("metric") in METRICS) metricSelect.value = params.get("metric");
    if ([...rangeSelect.options].some((o) => o.value === params.get("range"))) {
      rangeSelect.value = params.get("range");
    }
    if (params.has("projects")) {
      const wanted = new Set(params.get("projects").split(","));
      for (const box of boxes) box.checked = wanted.has(box.value);
    }
    checkFilter.value = params.get("checks") ?? "";
  };

  const showChecks = (checks) => {
    checkCount.textContent =
      checks === null ? "" : `${checks.length} of ${ALL_CHECKS.length} checks`;
    const url = checks?.length === 1 ? docsUrl(checks[0]) : null;
    checkDocs.hidden = !url;
    if (url) checkDocsLink.href = url;
    // Analysis time is not split by check.
    metricSelect.disabled = checks !== null;
    metricSelect.title = checks === null ? "" : "Analysis time is not split by check";
  };

  const clearCharts = () => {
    for (const graph of graphs) graph.destroy();
    graphs = [];
    totalDiv.replaceChildren();
    projectsDiv.replaceChildren();
  };

  const drawCharts = (series, label, projects, checks) => {
    clearCharts();
    const totals = slotDays.map((i) => (i < 0 ? null : sumOf(series, projects, i)));
    const missingAt = (i) => missingIn(series, projects, i);
    graphs.push(draw(totalDiv, label, totals, true, missingAt));

    // With one project the total chart already shows it. Projects on which
    // none of the chosen checks ran are left out.
    const shown =
      checks === null
        ? projects
        : projects.filter((project) => (series[project] ?? []).some((value) => value));
    projectsTitle.hidden = projects.length < 2;
    for (const project of projects.length < 2 ? [] : shown) {
      const figure = document.createElement("div");
      const title = document.createElement("div");
      title.textContent = project;
      const graphDiv = document.createElement("div");
      graphDiv.className = "graph small";
      figure.append(title, graphDiv);
      projectsDiv.append(figure);
      const values = slotDays.map((i) => (i < 0 ? null : valueOf(series, project, i)));
      graphs.push(draw(graphDiv, label, values, false));
    }
  };

  const render = async () => {
    const count = ++renderCount;
    const projects = selectedProjects();
    const filter = checkFilter.value.trim();
    const checks = filterChecks(filter);
    if (checks !== null) metricSelect.value = "check";
    const metric = metricSelect.value;
    saveState(metric, projects, filter);
    showChecks(checks);
    renderChecks(projects, checks);

    if (projects.length === 0 || checks?.length === 0) {
      totalTitle.textContent =
        projects.length === 0 ? "Select at least one project." : "No check matches the filter.";
      clearCharts();
      projectsTitle.hidden = true;
      table.replaceChildren();
      return;
    }

    let series = metric === "analysis" ? SERIES.analysis : SERIES.check;
    if (checks !== null) {
      // Keep the previous charts, dimmed, while the check times load.
      totalDiv.classList.add("loading");
      projectsDiv.classList.add("loading");
      series = await checksSeries(checks);
      if (count !== renderCount) return; // A newer render took over.
      totalDiv.classList.remove("loading");
      projectsDiv.classList.remove("loading");
    }
    const label = `${METRICS[metric].label}${describeChecks(checks)}`;
    totalTitle.textContent =
      `${METRICS[metric].title}${describeChecks(checks)} (s), ` +
      `summed over ${describeProjects(projects)}:`;
    drawCharts(series, label, projects, checks);
    renderTable(series, projects);
  };

  loadState();
  metricSelect.addEventListener("change", render);
  rangeSelect.addEventListener("change", render);
  for (const box of boxes) box.addEventListener("change", render);
  let filterTimer;
  checkFilter.addEventListener("input", () => {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(render, 200);
  });
  document.getElementById("select-all").addEventListener("click", () => {
    for (const box of boxes) box.checked = true;
    render();
  });
  document.getElementById("select-none").addEventListener("click", () => {
    for (const box of boxes) box.checked = false;
    render();
  });
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => graphs.forEach((graph) => graph.resize()), 100);
  });
  render();
})();
