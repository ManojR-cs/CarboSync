/**
 * TraceTwin — charts.js
 * Chart.js initialization and dynamic update functions.
 * Manages: doughnut breakdown, grouped bar comparison.
 */

const Charts = (() => {

  let doughnutChart = null;
  let barChart      = null;

  // ── Color Palette (matches design tokens) ─────────────────
  const COLORS = {
    car:   '#38bdf8',
    moto:  '#f97316',
    bus:   '#22c55e',
    other: '#a855f7',
    grid:  'rgba(148,163,184,0.1)',
    text:  '#94a3b8',
    baseline: 'rgba(56,189,248,0.6)',
    s1:    'rgba(168,85,247,0.6)',
    s2:    'rgba(34,197,94,0.6)',
    s3:    'rgba(245,158,11,0.6)'
  };

  Chart.defaults.color = COLORS.text;
  Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15,23,42,0.95)';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(148,163,184,0.2)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.padding = 16;

  // ── Doughnut: Mode Breakdown ───────────────────────────────
  function initDoughnut(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (doughnutChart) doughnutChart.destroy();

    const breakdown = data.category_breakdown || [];
    const labels    = breakdown.map(d => d.category);
    const values    = breakdown.map(d => d.annual_tonnes_co2 ?? d.annual_emissions_tonnes_co2_per_year ?? 0);
    const colors    = breakdown.map(d => categoryColor(d.category));

    doughnutChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors.map(c => c + 'cc'),
          borderColor:     colors,
          borderWidth: 2,
          hoverOffset: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        cutout: '68%',
        plugins: {
          legend: { position: 'bottom', labels: { color: COLORS.text } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const val = ctx.parsed;
                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                const pct = ((val / total) * 100).toFixed(1);
                return ` ${val.toFixed(2)} t CO₂/yr  (${pct}%)`;
              }
            }
          }
        }
      }
    });
  }

  function updateDoughnut(data) {
    if (!doughnutChart) return;
    const breakdown = data.category_breakdown || [];
    doughnutChart.data.labels             = breakdown.map(d => d.category);
    doughnutChart.data.datasets[0].data   = breakdown.map(d => d.annual_tonnes_co2);
    const colors = breakdown.map(d => categoryColor(d.category));
    doughnutChart.data.datasets[0].backgroundColor = colors.map(c => c + 'cc');
    doughnutChart.data.datasets[0].borderColor      = colors;
    doughnutChart.update('active');
  }

  // ── Grouped Bar: Scenario Comparison ──────────────────────
  function initBarChart(canvasId, baseline, scenarioData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (barChart) barChart.destroy();

    barChart = new Chart(ctx, {
      type: 'bar',
      data: buildBarData(baseline, scenarioData),
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: {
            grid: { color: COLORS.grid },
            ticks: { color: COLORS.text }
          },
          y: {
            grid: { color: COLORS.grid },
            ticks: { color: COLORS.text },
            title: { display: true, text: 'tonnes CO₂ / year', color: COLORS.text }
          }
        },
        plugins: {
          legend: { position: 'top' },
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} t CO₂/yr`
            }
          }
        }
      }
    });
  }

  function buildBarData(baseline, sd) {
    return {
      labels: ['Baseline', 'Scenario 1\nActive Travel', 'Scenario 2\nCarpool', 'Scenario 3\nShuttle'],
      datasets: [
        {
          label: 'Emissions (t CO₂/yr)',
          data: [
            baseline,
            sd.scenario_1_tonnes_co2 ?? baseline,
            sd.scenario_2_tonnes_co2 ?? baseline,
            sd.scenario_3_tonnes_co2 ?? baseline
          ],
          backgroundColor: [COLORS.baseline, COLORS.s1, COLORS.s2, COLORS.s3],
          borderColor:     [COLORS.baseline, COLORS.s1, COLORS.s2, COLORS.s3].map(c => c.replace('0.6', '1')),
          borderWidth: 2,
          borderRadius: 6,
          borderSkipped: false
        }
      ]
    };
  }

  function updateBarChart(baseline, scenarioData) {
    if (!barChart) return;
    const newData = buildBarData(baseline, scenarioData);
    barChart.data = newData;
    barChart.update('active');
  }

  // ── Mini Sparkline (for KPI cards) ────────────────────────
  function initSparkline(canvasId, values, color) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
      type: 'line',
      data: {
        labels: values.map((_, i) => i),
        datasets: [{
          data: values,
          borderColor: color,
          borderWidth: 2,
          fill: true,
          backgroundColor: color + '1a',
          tension: 0.4,
          pointRadius: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: { display: false },
          y: { display: false }
        }
      }
    });
  }

  // ── Helpers ────────────────────────────────────────────────
  function categoryColor(cat) {
    const map = {
      'Cars':                       COLORS.car,
      'Motorcycles and scooters':   COLORS.moto,
      'Buses and campus shuttles':  COLORS.bus,
      'Other fuel-burning vehicles':COLORS.other
    };
    return map[cat] || '#94a3b8';
  }

  // ── Public API ─────────────────────────────────────────────
  return { initDoughnut, updateDoughnut, initBarChart, updateBarChart, initSparkline };
})();
