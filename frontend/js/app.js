/**
 * TraceTwin — app.js
 * Application coordinator, global state store, toast system,
 * tab routing, form orchestration, and bootstrap.
 */

// ── Global Config ──────────────────────────────────────────────
window.USE_MOCKS = true;   // ← Set to false when backend is running

// ── Global State ──────────────────────────────────────────────
const AppState = {
  assessmentId:   null,
  assessmentMeta: null,
  imageId:        null,
  cvCounts:       {},
  commuteInputs:  null,
  baseline:       null,
  scenarioResult: null,
  sampleSize:     0
};

// ── DOM Ready ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initTabs();
  initMockToggle();
  initAssessmentForm();
  initImageUpload();
  initCommuteForm();
  initBaselineToggle();
  initScenarios();
  initMethodologyDrawer();
  initCanvasPopupEvents();
  await checkStatus();
});

// ── Tab Navigation ─────────────────────────────────────────────
function initTabs() {
  const tabBtns   = document.querySelectorAll('.tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const panel = document.getElementById(`tab-panel-${target}`);
      if (panel) panel.classList.add('active');
    });
  });
}

function switchTab(num) {
  const btn = document.querySelector(`[data-tab="${num}"]`);
  if (btn) btn.click();
}

// ── Mock Toggle ────────────────────────────────────────────────
function initMockToggle() {
  const checkbox = document.getElementById('mock-toggle');
  const badge    = document.getElementById('api-status-badge');
  const dot      = document.getElementById('status-dot');

  function update() {
    window.USE_MOCKS = checkbox.checked;
    if (badge) badge.textContent = USE_MOCKS ? 'Mock Mode' : 'Live API';
    updateStatusIndicator(USE_MOCKS ? 'mock' : 'offline');
  }

  if (checkbox) {
    checkbox.checked = window.USE_MOCKS;
    checkbox.addEventListener('change', update);
    update();
  }
}

async function checkStatus() {
  const status = await checkBackendStatus();
  updateStatusIndicator(status);
}

function updateStatusIndicator(status) {
  const dot  = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  if (!dot) return;

  dot.className  = `status-dot ${status}`;
  if (text) {
    const labels = { online: 'Backend Online', offline: 'Backend Offline', mock: 'Mock Mode', error: 'Backend Error' };
    text.textContent = labels[status] || status;
  }
}

// ── F-03: Assessment Setup Form ────────────────────────────────
function initAssessmentForm() {
  const form = document.getElementById('assessment-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Creating…';

    const payload = {
      assessment_name:  form.querySelector('#audit-name').value.trim(),
      campus_area:      form.querySelector('#campus-area').value.trim(),
      reporting_period: form.querySelector('#reporting-period').value,
      annual_days:      parseInt(form.querySelector('#annual-days').value)
    };

    try {
      const result = await API.createAssessment(payload);
      AppState.assessmentId   = result.assessment_id;
      AppState.assessmentMeta = result;
      updateAssessmentBar(payload);
      showToast(`Assessment created: ${result.assessment_id}`, 'success');
      switchTab(2);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = 'Create Assessment & Continue →';
    }
  });
}

function updateAssessmentBar(meta) {
  const bar = document.getElementById('assessment-bar');
  if (bar) bar.style.display = 'flex';

  setEl('active-assessment-name', meta.assessment_name || '—');
  setEl('active-assessment-area', meta.campus_area || '—');
  setEl('active-assessment-days', `${meta.annual_days || 200} academic days`);
}

// ── F-04: Image Upload & Canvas ────────────────────────────────
function initImageUpload() {
  const dropZone   = document.getElementById('drop-zone');
  const fileInput  = document.getElementById('image-file-input');
  const canvasEl   = document.getElementById('parking-canvas');
  const svgEl      = document.getElementById('bbox-svg');

  if (!dropZone || !canvasEl) return;

  CanvasEditor.init(canvasEl, svgEl);

  // Drag & Drop
  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleImageFile(file);
  });

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) handleImageFile(fileInput.files[0]);
    });
  }

  // Canvas toolbar buttons
  document.getElementById('tool-select-btn')?.addEventListener('click', () => {
    CanvasEditor.setMode('select');
    setActiveToolBtn('tool-select-btn');
  });

  document.getElementById('tool-draw-btn')?.addEventListener('click', () => {
    CanvasEditor.setMode('draw');
    setActiveToolBtn('tool-draw-btn');
  });

  document.getElementById('tool-delete-btn')?.addEventListener('click', () => {
    CanvasEditor.deleteSelected();
  });

  // Image toggle
  document.getElementById('view-raw-btn')?.addEventListener('click', () => {
    toggleImageView('raw');
  });
  document.getElementById('view-annotated-btn')?.addEventListener('click', () => {
    toggleImageView('annotated');
  });

  // Confirm verification
  document.getElementById('confirm-verify-btn')?.addEventListener('click', confirmVerification);
}

async function handleImageFile(file) {
  if (!file.type.startsWith('image/')) {
    showToast('Invalid file. Please upload a JPEG or PNG image.', 'error');
    return;
  }

  // Show canvas loading
  const loading = document.getElementById('canvas-loading');
  const dropSection = document.getElementById('drop-section');
  const canvasSection = document.getElementById('canvas-section');

  if (dropSection) dropSection.style.display  = 'none';
  if (canvasSection) canvasSection.style.display = 'block';
  if (loading) loading.style.display = 'flex';

  try {
    const formData = new FormData();
    formData.append('file', file);

    const result = await API.uploadImage(AppState.assessmentId || 'ast_demo', formData);
    AppState.imageId = result.image_id;

    // Load image on canvas with detections
    const imgUrl = window.USE_MOCKS
      ? URL.createObjectURL(file)
      : `${API_BASE}/uploads/${result.image_id}`;

    CanvasEditor.loadImage(imgUrl, result.detections, result.width, result.height);
    setEl('canvas-res', `${result.width}×${result.height}px`);
    setEl('canvas-det-count', `${result.detections.length} detected`);

    showToast(`Detected ${result.detections.length} objects`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
    if (dropSection) dropSection.style.display = 'block';
    if (canvasSection) canvasSection.style.display = 'none';
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

async function confirmVerification() {
  const btn = document.getElementById('confirm-verify-btn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Confirming…';
  }

  try {
    const counts = CanvasEditor.getVerifiedCounts();
    const payload = {
      image_id: AppState.imageId || 'img_demo',
      verified_counts: counts,
      reviewer_notes: ''
    };

    const res = await API.verifyDetections(AppState.assessmentId || 'ast_demo', payload);
    showToast('✅ Verification confirmed — evidence label: [Human-confirmed observation]', 'success');

    // Store counts to pre-fill commute form
    AppState.cvCounts = counts;
    switchTab(3);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '✓ Confirm Verification';
    }
  }
}

function initCanvasPopupEvents() {
  const popupSelect = document.getElementById('popup-class-select');
  const popupDelete = document.getElementById('popup-delete-btn');
  const popupClose  = document.getElementById('popup-close-btn');

  popupSelect?.addEventListener('change', () => {
    CanvasEditor.reclassifySelected(popupSelect.value);
  });

  popupDelete?.addEventListener('click', () => {
    CanvasEditor.deleteSelected();
    document.getElementById('canvas-popup').classList.remove('visible');
  });

  popupClose?.addEventListener('click', () => {
    document.getElementById('canvas-popup').classList.remove('visible');
  });
}

function setActiveToolBtn(activeId) {
  ['tool-select-btn', 'tool-draw-btn'].forEach(id => {
    document.getElementById(id)?.classList.toggle('active', id === activeId);
  });
}

function toggleImageView(view) {
  ['view-raw-btn', 'view-annotated-btn'].forEach(id => {
    document.getElementById(id)?.classList.toggle('active', id === `view-${view}-btn`);
  });
}

// ── F-05: Commute Survey Form ──────────────────────────────────
function initCommuteForm() {
  const presetBtn  = document.getElementById('load-preset-btn');
  const sampleSize = document.getElementById('sample-size-input');
  const calcBtn    = document.getElementById('calc-baseline-btn');

  if (presetBtn) {
    presetBtn.addEventListener('click', loadDSUPreset);
  }

  if (sampleSize) {
    sampleSize.addEventListener('input', checkSampleSizeWarning);
  }

  if (calcBtn) {
    calcBtn.addEventListener('click', calculateBaseline);
  }
}

function loadDSUPreset() {
  DSU_SAMPLE_PRESET.forEach((row, i) => {
    setInput(`vehicles-${i}`,    row.daily_vehicles);
    setInput(`distance-${i}`,    row.avg_one_way_km);
    setInput(`occupancy-${i}`,   row.occupancy);
  });
  setInput('sample-size-input', 18);
  checkSampleSizeWarning();
  showToast('DSU sample survey loaded (n=18)', 'info');
}

function checkSampleSizeWarning() {
  const n    = parseInt(document.getElementById('sample-size-input')?.value) || 0;
  const warn = document.getElementById('sample-size-warning');
  const warnN = document.getElementById('sample-size-n');
  if (warn) warn.style.display = n > 0 && n < 20 ? 'flex' : 'none';
  if (warnN) warnN.textContent = n;
  AppState.sampleSize = n;
}

async function calculateBaseline() {
  const btn = document.getElementById('calc-baseline-btn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Calculating…';
  }

  const rows = ['Cars', 'Motorcycles and scooters', 'Buses and campus shuttles', 'Other fuel-burning vehicles'];
  const mode_data = rows.map((cat, i) => ({
    category:       cat,
    daily_vehicles: parseFloat(document.getElementById(`vehicles-${i}`)?.value) || 0,
    avg_one_way_km: parseFloat(document.getElementById(`distance-${i}`)?.value)  || 0,
    occupancy:      parseFloat(document.getElementById(`occupancy-${i}`)?.value) || 1.0
  }));

  const payload = {
    sample_size:      AppState.sampleSize || 18,
    population_total: parseInt(document.getElementById('population-input')?.value) || 4500,
    mode_data
  };

  try {
    const result = await API.submitCommuteInputs(AppState.assessmentId || 'ast_demo', payload);
    AppState.baseline     = result;
    AppState.commuteInputs = payload;
    renderBaselineDashboard(result);
    showToast(`Baseline: ${result.total_annual_tonnes_co2.toFixed(2)} t CO₂/yr`, 'success');
    switchTab(4);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = 'Calculate Baseline Emissions →';
    }
  }
}

// ── F-06: Baseline Dashboard ───────────────────────────────────
function renderBaselineDashboard(data) {
  setEl('kpi-total-co2',  `${data.total_annual_tonnes_co2.toFixed(2)}`);
  setEl('kpi-total-vkt',  `${(data.total_annual_vkt / 1000).toFixed(1)}k`);
  setEl('kpi-sample-n',   data.sample_size);
  setEl('kpi-annual-days', AppState.assessmentMeta?.annual_days || 200);

  // Sample size warning on baseline tab too
  const baselineWarn = document.getElementById('baseline-sample-warning');
  if (baselineWarn) {
    baselineWarn.style.display = data.sample_size < 20 ? 'flex' : 'none';
  }

  // Render breakdown table
  const tbody = document.getElementById('breakdown-tbody');
  if (tbody && data.category_breakdown) {
    tbody.innerHTML = data.category_breakdown.map(row => `
      <tr>
        <td class="font-bold">${row.category}</td>
        <td class="font-mono">${row.daily_vehicles}</td>
        <td class="font-mono">${row.annual_vkt.toLocaleString()}</td>
        <td class="font-mono">${row.emission_factor_kg_per_vkt}</td>
        <td class="font-mono font-bold text-accent">${row.annual_tonnes_co2.toFixed(2)}</td>
        <td><span class="badge badge-derived">[Derived calculation]</span></td>
      </tr>
    `).join('');
  }

  // Charts
  Charts.initDoughnut('breakdown-doughnut', data);

  // Update scenario bar baseline
  if (AppState.scenarioResult) {
    Charts.updateBarChart(data.total_annual_tonnes_co2, AppState.scenarioResult);
  }
}

function initBaselineToggle() {
  const toggle = document.getElementById('projection-toggle');
  if (toggle) {
    toggle.addEventListener('change', () => {
      const label = document.getElementById('projection-label');
      if (label) label.textContent = toggle.checked ? 'Campus Projection Total' : 'Sample-Based Baseline';

      if (toggle.checked && AppState.baseline) {
        const projBanner = document.getElementById('projection-banner');
        if (projBanner) projBanner.style.display = 'flex';
      } else {
        const projBanner = document.getElementById('projection-banner');
        if (projBanner) projBanner.style.display = 'none';
      }
    });
  }
}

// ── F-07: Scenarios ────────────────────────────────────────────
function initScenarios() {
  Scenarios.init();

  const runBtn = document.getElementById('run-simulation-btn');
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      if (!AppState.baseline) {
        showToast('Please calculate a baseline first (Tab 3)', 'warning');
        return;
      }

      // init bar chart if not yet done
      const barCanvas = document.getElementById('scenario-bar-chart');
      if (barCanvas && !barCanvas.dataset.initialized) {
        Charts.initBarChart('scenario-bar-chart', AppState.baseline.total_annual_tonnes_co2, MOCK_SCENARIO);
        barCanvas.dataset.initialized = 'true';
      }

      await Scenarios.recalc();
    });
  }
}

// ── F-09: Methodology Drawer ───────────────────────────────────
function initMethodologyDrawer() {
  const openBtn  = document.getElementById('open-methodology-btn');
  const overlay  = document.getElementById('methodology-modal');
  const closeBtn = document.getElementById('close-methodology-btn');

  if (openBtn && overlay) {
    openBtn.addEventListener('click', () => {
      overlay.classList.add('open');
      renderFactorTable();
    });
  }

  if (closeBtn && overlay) {
    closeBtn.addEventListener('click', () => overlay.classList.remove('open'));
  }

  overlay?.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.classList.remove('open');
  });
}

function renderFactorTable() {
  const tbody = document.getElementById('factor-table-tbody');
  if (!tbody || !window.EMISSION_FACTORS) return;

  tbody.innerHTML = EMISSION_FACTORS.map(f => `
    <tr>
      <td class="font-mono text-xs">${f.factor_id}</td>
      <td>${f.category}</td>
      <td class="font-mono font-bold text-accent">${f.value}</td>
      <td class="text-xs">${f.unit}</td>
      <td class="text-xs">${f.source}</td>
      <td class="text-xs">${f.year}</td>
      <td class="text-xs">${f.geography}</td>
    </tr>
  `).join('');
}

// ── Toast Notifications ────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const toast  = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ── Utility Helpers ────────────────────────────────────────────
function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function setInput(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

// Expose showToast globally (used in canvas_editor.js)
window.showToast = showToast;
