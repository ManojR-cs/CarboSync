/**
 * TraceTwin — scenarios.js
 * Digital Twin slider listeners & recalculation triggers.
 * Handles Scenario 1 (Remote), Scenario 2 (Carpool), Scenario 3 (Shuttle).
 */

const Scenarios = (() => {

  // ── Local state ────────────────────────────────────────────
  let params = {
    s1_remote_pct:    0.20,   // 20% default
    s2_carpool_pct:   0.30,   // 30% default
    s2_occupancy:     2.5,
    s3_routes:        2,
    s3_trips_per_day: 4,
    s3_route_km:      12.0,
    s3_shifted:       50
  };

  // ── Wire up all sliders & inputs ──────────────────────────
  function init() {
    // Scenario 1
    wire('s1-remote-slider', 's1-remote-val', v => {
      params.s1_remote_pct = v / 100;
      recalc();
    }, v => `${v}%`);

    // Scenario 2
    wire('s2-carpool-slider', 's2-carpool-val', v => {
      params.s2_carpool_pct = v / 100;
      recalc();
    }, v => `${v}%`);

    wire('s2-occupancy-input', null, v => {
      params.s2_occupancy = parseFloat(v) || 2.5;
      recalc();
    });

    // Scenario 3
    wire('s3-routes-input',    null, v => { params.s3_routes        = parseInt(v) || 1; recalc(); });
    wire('s3-trips-input',     null, v => { params.s3_trips_per_day = parseInt(v) || 2; recalc(); });
    wire('s3-km-input',        null, v => { params.s3_route_km      = parseFloat(v) || 10; recalc(); });
    wire('s3-shifted-slider',  's3-shifted-val', v => {
      params.s3_shifted = parseInt(v);
      recalc();
    }, v => `${v} vehicles`);
  }

  function wire(inputId, displayId, onChange, formatter) {
    const el = document.getElementById(inputId);
    if (!el) return;

    const display = displayId ? document.getElementById(displayId) : null;
    const updateDisplay = (v) => { if (display) display.textContent = formatter ? formatter(v) : v; };
    updateDisplay(el.value);

    el.addEventListener('input', () => {
      updateDisplay(el.value);
      onChange(el.value);
    });
  }

  // ── Recalculate all scenarios ──────────────────────────────
  async function recalc() {
    if (!AppState.assessmentId || !AppState.baseline) return;

    // Show loading state on bar chart area
    const runBtn = document.getElementById('run-simulation-btn');
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.innerHTML = '<span class="spinner spinner-sm"></span> Calculating…';
    }

    try {
      const result = await API.runSimulation(AppState.assessmentId, params);
      AppState.scenarioResult = result;
      renderScenarioResults(result);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.innerHTML = '▶ Run Simulation';
      }
    }
  }

  // ── Render scenario result ─────────────────────────────────
  function renderScenarioResults(result) {
    const baseline = result.baseline_tonnes_co2;

    // Update bar chart
    Charts.updateBarChart(baseline, result);

    // KPI results
    setEl('scenario-baseline-val',   `${baseline.toFixed(2)} t`);
    setEl('scenario-s1-val',         `${(result.scenario_1_tonnes_co2 ?? baseline).toFixed(2)} t`);
    setEl('scenario-s2-val',         `${(result.scenario_2_tonnes_co2 ?? baseline).toFixed(2)} t`);
    setEl('scenario-s3-val',         `${(result.scenario_3_tonnes_co2 ?? baseline).toFixed(2)} t`);

    const netSavings = result.net_savings_tonnes_co2 ?? 0;
    const netEl      = document.getElementById('net-savings-val');
    const netBanner  = document.getElementById('negative-savings-banner');

    if (netEl) {
      if (netSavings < 0) {
        netEl.textContent    = `+${Math.abs(netSavings).toFixed(2)} t ADDED`;
        netEl.style.color    = 'var(--danger)';
        if (netBanner) {
          netBanner.style.display = 'flex';
          const addedTxt = document.getElementById('shuttle-added-emissions');
          if (addedTxt) addedTxt.textContent = Math.abs(netSavings).toFixed(1);
        }
      } else {
        netEl.textContent    = `-${netSavings.toFixed(2)} t SAVED`;
        netEl.style.color    = 'var(--success)';
        if (netBanner) netBanner.style.display = 'none';
      }
    }

    // Shuttle disclosure row
    const shuttleSection = document.getElementById('shuttle-emissions-disclosure');
    if (shuttleSection) {
      const avoided = result.avoided_private_tonnes_co2 ?? 0;
      const added   = result.added_shuttle_tonnes_co2   ?? 0;
      setEl('avoided-private-val', `${avoided.toFixed(2)} t`);
      setEl('added-shuttle-val',   `${added.toFixed(2)} t`);
    }

    // AI Recommendations
    if (result.recommendations) {
      renderRecommendations(result.recommendations, result.fallback_activated);
    }
  }

  // ── Render Recommendation Cards ────────────────────────────
  function renderRecommendations(recs, isFallback) {
    const container = document.getElementById('rec-cards-container');
    const fallbackBanner = document.getElementById('fallback-banner');

    if (!container) return;

    if (fallbackBanner) {
      fallbackBanner.style.display = isFallback ? 'flex' : 'none';
    }

    container.innerHTML = recs.map((rec, i) => `
      <div class="rec-card" style="animation-delay:${i * 0.1}s">
        <div class="rec-card-header">
          <div>
            <div class="rec-id">${rec.rec_id}</div>
            <div class="rec-card-title">${rec.title}</div>
          </div>
          <span class="badge badge-${rec.difficulty.toLowerCase()}">${rec.difficulty} Effort</span>
        </div>
        <p class="rec-card-body">${rec.qualitative_rationale}</p>
        <div class="rec-steps">
          ${rec.action_steps.map((step, j) => `
            <div class="rec-step">
              <div class="rec-step-num">${j + 1}</div>
              <span>${step}</span>
            </div>
          `).join('')}
        </div>
        <div class="rec-savings">
          🌿 ${rec.attached_savings_tonnes.toFixed(2)} t CO₂/yr saved
          <span class="badge badge-derived ml-auto" style="margin-left:auto">[Derived calculation]</span>
        </div>
      </div>
    `).join('');

    // Switch to AI tab
    const aiTab = document.querySelector('[data-tab="6"]');
    if (aiTab && !isFallback) showToast('AI recommendations ready', 'success');
  }

  // ── Helpers ────────────────────────────────────────────────
  function setEl(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function getParams() { return { ...params }; }

  // ── Public API ─────────────────────────────────────────────
  return { init, recalc, getParams };
})();
