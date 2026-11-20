/* USVI Tourism Data Warehouse - reads the JSON files written by pipeline/step6_export.py */
(async function () {
  const C = { ink: '#0E2A3B', coral: '#C8553D', coralL: '#E8836B', sea: '#2F7F86', seaL: '#8CC2C4', line: '#EFE9DE', muted: '#6B7C89' };
  const ISL = { USVI: 'U.S. Virgin Islands', STT_STJ: 'St. Thomas / St. John', STX: 'St. Croix' };
  const SERIES = { A: 'Air arrivals', CP: 'Cruise passengers', CS: 'Ship calls', RN: 'Room nights occupied' };
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const load = (f) => fetch(`data/${f}.json`).then((r) => r.json());
  const [monthly, annual, revisions, occFlags, islandFlags, files, fileIssues, sources, meta] = await Promise.all(
    ['monthly', 'annual', 'revisions', 'occupancy_flags', 'island_flags', 'files', 'file_issues', 'latest_sources', 'meta'].map(load));

  const nf = (v, d = 0) => v == null ? '–' : Number(v).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
  const short = (v) => v == null ? '–' : v >= 1e6 ? (v / 1e6).toFixed(2) + 'M' : v >= 1e4 ? Math.round(v / 1e3) + 'k' : nf(v);
  const mLabel = (m, long) => { const [y, mo] = m.split('-'); return `${long ? ['January','February','March','April','May','June','July','August','September','October','November','December'][+mo - 1] : MON[+mo - 1]} ${y}`; };
  const pct = (a, b) => (a == null || !b) ? null : 100 * (a / b - 1);
  const delta = (p, unit = '%') => p == null ? '<span>no prior year</span>'
    : `<b class="${p > 0.05 ? 'up' : p < -0.05 ? 'down' : 'flat'}">${p > 0 ? '+' : ''}${p.toFixed(1)}${unit}</b><span>vs same months last year</span>`;
  const src = Object.fromEntries(sources.map((s) => [s.series_code, s]));
  const latestMonth = (code) => src[code].latest_month.slice(0, 7);

  const firstMonth = monthly.filter((r) => r.island === 'USVI' && (r.air != null || r.cruise != null)).map((r) => r.month).sort()[0];
  document.getElementById('range').textContent = `· ${mLabel(firstMonth)} to ${mLabel(latestMonth('A'))}`;
  document.getElementById('built').textContent = `Data through ${mLabel(latestMonth('A'), true)} (arrivals) and ${mLabel(latestMonth('H'), true)} (hotels). Refreshed ${meta.built_at.slice(0, 10)}.`;
  document.getElementById('howTitle').textContent = `${meta.files} PDFs to one tested warehouse`;

  let island = 'USVI';
  let range = '36';
  let heatMeasure = 'air';
  const rows = () => monthly.filter((r) => r.island === island);
  const byMonth = () => Object.fromEntries(rows().map((r) => [r.month, r]));

  /* ---------- KPIs: year to date, compared with the same months a year earlier ---------- */
  function ytd(field, endMonth) {
    const [y, m] = endMonth.split('-').map(Number);
    const bm = byMonth();
    let cur = 0, prev = 0, nCur = 0, nPrev = 0;
    for (let i = 1; i <= m; i++) {
      const a = bm[`${y}-${String(i).padStart(2, '0')}`], b = bm[`${y - 1}-${String(i).padStart(2, '0')}`];
      if (a && a[field] != null) { cur += a[field]; nCur++; }
      if (b && b[field] != null) { prev += b[field]; nPrev++; }
    }
    return { cur: nCur ? cur : null, prev: nPrev === nCur ? prev : null, y, m };
  }
  function occYtd(endMonth) {
    const occ = ytd('rooms_occ', endMonth), av = ytd('rooms_avail', endMonth);
    return { cur: occ.cur && av.cur ? 100 * occ.cur / av.cur : null, prev: occ.prev && av.prev ? 100 * occ.prev / av.prev : null, m: occ.m, y: occ.y };
  }
  function renderKpis() {
    const end = latestMonth('A'), endH = latestMonth('H');
    const air = ytd('air', end), cr = ytd('cruise', end), calls = ytd('calls', end), occ = occYtd(endH);
    const period = `Jan–${MON[air.m - 1]} ${air.y}`;
    const latestRow = byMonth()[endH] || {};
    const flag = occFlags.find((f) => f.island === island && f.month === endH);
    const k = [
      ['Air visitors', short(air.cur), delta(pct(air.cur, air.prev)), period],
      ['Cruise passengers', short(cr.cur), delta(pct(cr.cur, cr.prev)), period],
      ['Total visitors', short(air.cur + cr.cur), delta(pct(air.cur + cr.cur, air.prev + cr.prev)), period],
      ['Cruise ship calls', nf(calls.cur), delta(pct(calls.cur, calls.prev)), period],
      ['Hotel occupancy', occ.cur == null ? '–' : occ.cur.toFixed(1) + '%', delta(occ.cur != null && occ.prev != null ? occ.cur - occ.prev : null, ' pts'),
        `Jan–${MON[occ.m - 1]} ${occ.y}, from room nights` + (flag ? ` · USVIBER prints ${nf(latestRow.occ, 1)}% for ${MON[occ.m - 1]}, room nights give ${nf(flag.computed, 1)}%` : '')],
    ];
    document.getElementById('kpis').innerHTML = k.map(([l, v, d, note], i) =>
      `<div class="kpi${i === 4 && flag ? ' flag' : ''}"><p class="l">${l}</p><p class="v">${v}</p><p class="d">${d}</p><p class="note">${note}</p></div>`).join('');
    document.getElementById('applied').textContent = `Showing ${ISL[island]}`;
  }

  /* ---------- Charts ---------- */
  Chart.defaults.font.family = "'Satoshi', system-ui, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.animation.duration = 350;
  Chart.defaults.color = C.muted;
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = C.ink;
  Chart.defaults.plugins.tooltip.padding = 10;
  const grid = { color: C.line, drawTicks: false };
  const charts = {};
  const make = (id, cfg) => {
    // Update an existing chart in place (no animation) so switching islands is instant.
    if (charts[id]) { charts[id].data = cfg.data; charts[id].options = cfg.options; charts[id].update('none'); return; }
    charts[id] = new Chart(document.getElementById(id), cfg);
  };

  function renderArrivals() {
    let r = rows().filter((x) => x.month >= firstMonth && x.month <= latestMonth('A'));
    if (range !== 'all') r = r.slice(-Number(range));
    make('cArrivals', {
      type: 'line',
      data: {
        labels: r.map((x) => x.month),
        datasets: [
          { label: 'Cruise passengers', data: r.map((x) => x.cruise), borderColor: C.sea, backgroundColor: 'rgba(47,127,134,.10)', fill: true, tension: 0.25, pointRadius: 0, borderWidth: 2, spanGaps: false },
          { label: 'Air visitors', data: r.map((x) => x.air), borderColor: C.coral, backgroundColor: C.coral, tension: 0.25, pointRadius: 0, borderWidth: 2.5, spanGaps: false },
        ],
      },
      options: {
        maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { position: 'top', align: 'end' }, tooltip: { callbacks: { title: (i) => mLabel(i[0].label, true), label: (c) => ` ${c.dataset.label}: ${nf(c.raw)}` } } },
        scales: {
          x: { grid: { display: false }, ticks: { autoSkip: true, maxTicksLimit: 10, maxRotation: 0, callback(v) { const m = this.getLabelForValue(v); return range === 'all' ? m.slice(0, 4) : mLabel(m); } } },
          y: { grid, border: { display: false }, ticks: { callback: (v) => short(v) }, beginAtZero: true },
        },
      },
    });
  }

  function renderAnnual() {
    const a = annual.filter((x) => x.island === island && (x.air != null || x.cruise != null) && x.year >= 2017);
    const partial = a.filter((x) => x.air_months > 0 && x.air_months < 12);
    make('cAnnual', {
      type: 'bar',
      data: {
        labels: a.map((x) => x.air_months > 0 && x.air_months < 12 ? `${x.year}*` : String(x.year)),
        datasets: [
          { label: 'Air', data: a.map((x) => x.air), backgroundColor: C.coral, borderRadius: 3, stack: 's' },
          { label: 'Cruise', data: a.map((x) => x.cruise), backgroundColor: C.sea, borderRadius: 3, stack: 's' },
        ],
      },
      options: {
        maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { position: 'top', align: 'end' }, tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${nf(c.raw)}` } } },
        scales: { x: { grid: { display: false }, stacked: true }, y: { stacked: true, grid, border: { display: false }, ticks: { callback: (v) => short(v) } } },
      },
    });
    document.getElementById('annualNote').textContent = partial.length
      ? `* ${partial.map((p) => `${p.year} covers January to ${MON[p.air_months - 1]}`).join('; ')}. Air arrivals start in 2017; 2017 cruise excludes October (ports closed after Hurricane Maria).`
      : '';
  }

  function renderOcc() {
    const r = rows().filter((x) => x.month >= '2020-01' && (x.occ != null || x.rooms_occ != null));
    const computed = r.map((x) => x.rooms_occ != null && x.rooms_avail ? +(100 * x.rooms_occ / x.rooms_avail).toFixed(1) : null);
    const flags = occFlags.filter((f) => f.island === island);
    make('cOcc', {
      type: 'line',
      data: {
        labels: r.map((x) => x.month),
        datasets: [
          { label: 'Printed rate (table H)', data: r.map((x) => x.occ), borderColor: C.coral, backgroundColor: C.coral, borderWidth: 2, tension: 0.2,
            pointRadius: r.map((x) => flags.some((f) => f.month === x.month) ? 4 : 0), pointBackgroundColor: C.coral },
          { label: 'From room nights', data: computed, borderColor: C.ink, borderDash: [5, 4], borderWidth: 1.8, tension: 0.2, pointRadius: 0 },
        ],
      },
      options: {
        maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { position: 'top', align: 'end' }, tooltip: { callbacks: { title: (i) => mLabel(i[0].label, true), label: (c) => ` ${c.dataset.label}: ${c.raw == null ? '–' : c.raw.toFixed(1) + '%'}` } } },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 7, maxRotation: 0, callback(v) { return this.getLabelForValue(v).slice(0, 4); } } },
          y: { grid, border: { display: false }, min: 0, max: 100, ticks: { callback: (v) => v + '%' } },
        },
      },
    });
    const worst = flags.slice().sort((a, b) => Math.abs(b.gap_pts) - Math.abs(a.gap_pts))[0];
    document.getElementById('occNote').innerHTML = worst
      ? `<b>${flags.length} month${flags.length > 1 ? 's' : ''} since 2024 disagree by more than 3 points.</b> Largest: ${mLabel(worst.month, true)}, printed ${nf(worst.published, 1)}% vs ${nf(worst.computed, 1)}% from room nights. Dots mark the flagged months.`
      : 'The printed rate and the room-night calculation agree within 3 points for every month since 2024.';
  }

  function renderShip() {
    const a = annual.filter((x) => x.island === island && x.calls && x.cruise);
    make('cShip', {
      type: 'bar',
      data: { labels: a.map((x) => x.year + (x.cruise_months < 12 ? '*' : '')), datasets: [{ label: 'Passengers per call', data: a.map((x) => Math.round(x.cruise / x.calls)), backgroundColor: a.map((x) => x.year === 2020 || x.year === 2021 ? C.seaL : C.sea), borderRadius: 4 }] },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${nf(c.raw)} passengers per call` } } },
        scales: { x: { grid: { display: false } }, y: { grid, border: { display: false }, ticks: { callback: (v) => nf(v) } } },
      },
    });
  }

  /* ---------- Seasonality heatmap (pure HTML table) ---------- */
  function renderHeat() {
    const field = heatMeasure;
    const bm = byMonth();
    const vals = rows().map((r) => r[field]).filter((v) => v != null);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const years = [...new Set(rows().filter((r) => r[field] != null).map((r) => r.month.slice(0, 4)))].sort();
    const color = (v) => {
      const t = (v - lo) / Math.max(hi - lo, 1e-9);
      // sand -> sea glass -> harbor ink
      const stops = [[238, 245, 244], [47, 127, 134], [14, 42, 59]];
      const [a, b, u] = t < 0.6 ? [stops[0], stops[1], t / 0.6] : [stops[1], stops[2], (t - 0.6) / 0.4];
      return { bg: `rgb(${a.map((c, i) => Math.round(c + (b[i] - c) * u)).join(',')})`, dark: t > 0.45 };
    };
    const fmt = (v) => field === 'occ' ? Math.round(v) : (v / 1000).toFixed(v >= 100000 ? 0 : 1);
    let html = `<thead><tr><th class="y"></th>${MON.map((m) => `<th>${m}</th>`).join('')}</tr></thead><tbody>`;
    for (const y of years) {
      html += `<tr><th class="y">${y}</th>`;
      for (let i = 1; i <= 12; i++) {
        const key = `${y}-${String(i).padStart(2, '0')}`;
        const v = bm[key]?.[field];
        if (v == null) { html += `<td class="na" title="${mLabel(key, true)}: not published">·</td>`; continue; }
        const c = color(v);
        const label = field === 'occ' ? `${v.toFixed(1)}%` : nf(v);
        html += `<td class="${c.dark ? 'dark' : ''}" style="background:${c.bg}" title="${mLabel(key, true)}: ${label}">${fmt(v)}</td>`;
      }
      html += '</tr>';
    }
    document.getElementById('heat').innerHTML = html + '</tbody>';
    document.getElementById('heatSub').textContent = { air: 'Air visitor arrivals by month, thousands', cruise: 'Cruise passengers by month, thousands', occ: 'Printed hotel occupancy rate by month, %' }[field];
  }

  /* ---------- Data quality ---------- */
  function renderQuality() {
    const shifted = [...new Set(fileIssues.filter((f) => /shifted|inconsistent|used header/.test(f.note || '')).map((f) => f.file_name))];
    const failed = fileIssues.filter((f) => f.status === 'failed');
    document.getElementById('dqStats').innerHTML = [
      [`${meta.files_read} of ${meta.files}`, 'report PDFs read; the other 3 are documented and replaced by corrected uploads'],
      [nf(meta.values), `monthly values in the warehouse; ${nf(meta.values_revised)} were revised after first publication`],
      [`${Math.round(100 * meta.ytd_checks_reconciled / meta.ytd_checks)}%`, `of ${nf(meta.ytd_checks)} year-to-date lines add up exactly; the newest report for each count series always does`],
    ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join('');

    const items = [];
    const occ = occFlags.find((f) => f.island === 'USVI') ;
    if (occ) items.push(['', `Occupancy rate does not match room nights (${mLabel(occ.month, true)})`, `Table H prints ${nf(occ.published, 1)}% for the territory. Room nights occupied ÷ available give ${nf(occ.computed, 1)}%, the same figure as USVIBER's detailed hotel report for that month. <a href="${src.H.url}" target="_blank" rel="noopener">${src.H.file}</a>`]);
    islandFlags.forEach((f) => items.push(['', `Islands don't add up: ${SERIES[f.series_code].toLowerCase()}, ${mLabel(f.month, true)}`, `St. Thomas/St. John ${nf(f.stt_stj)} + St. Croix ${nf(f.stx)} = ${nf(f.islands_sum)}, but the territory total is printed as ${nf(f.published_total)}. <a href="${f.source_url}" target="_blank" rel="noopener">${f.source_file}</a>`]));
    items.push(['fixed', `${shifted.length} reports carried the wrong years`, `Some room-night and cruise reports print last year's labels or a typo in the title. Each one was checked against the same months in other reports and read with the years its numbers actually match.`]);
    failed.forEach((f) => items.push(['fixed', `${f.file_name} skipped`, `${f.note}. <a href="${f.source_url}" target="_blank" rel="noopener">Open file</a>`]));
    document.getElementById('issues').innerHTML = items.map(([cls, b, p]) => `<li class="${cls}"><b>${b}</b><p>${p}</p></li>`).join('');

    document.querySelector('#tRev tbody').innerHTML = revisions.slice(0, 8).map((r) =>
      `<tr><td>${SERIES[r.series_code]}</td><td>${mLabel(r.month)}</td><td class="n">${nf(r.first)}</td><td class="n">${nf(r.latest)}</td><td class="n"><b class="${r.change_pct > 0 ? 'up' : 'down'}">${r.change_pct > 0 ? '+' : ''}${r.change_pct.toFixed(1)}%</b></td></tr>`).join('');
  }

  function renderAll() { renderKpis(); renderArrivals(); renderAnnual(); renderOcc(); renderShip(); renderHeat(); }

  document.querySelectorAll('#islandSeg button').forEach((b) => b.addEventListener('click', () => {
    island = b.dataset.i;
    document.querySelectorAll('#islandSeg button').forEach((x) => x.setAttribute('aria-checked', String(x === b)));
    renderAll();
  }));
  document.querySelectorAll('#rangeToggle button').forEach((b) => b.addEventListener('click', () => {
    range = b.dataset.r;
    document.querySelectorAll('#rangeToggle button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    renderArrivals();
  }));
  document.querySelectorAll('#heatToggle button').forEach((b) => b.addEventListener('click', () => {
    heatMeasure = b.dataset.m;
    document.querySelectorAll('#heatToggle button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    renderHeat();
  }));

  renderAll();
  renderQuality();
})();
