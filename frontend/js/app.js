/**
 * TraceTwin — app.js
 * Application coordinator, global state store, toast system,
 * tab routing, form orchestration, and bootstrap.
 */

// ── Global Config ──────────────────────────────────────────────
window.USE_MOCKS = false;  // Offline errors never enable mock responses automatically.

// ── Global State ──────────────────────────────────────────────
const AppState = {
  assessmentId:   null,
  assessmentMeta: null,
  imageId:        null,
  cvCounts:       {},
  commuteInputs:  null,
  baseline:       null,
  scenarioResult: null,
  sampleSize:     0,
  currentCampaign: null,
  currentAnalysis: null,
  currentAnalysisSaved: false,
  commuteSummary: null,
  report: null,
  latestScenario: null,
  latestRecommendations: null,
  selectedScenario: 'carpool',
  scenarioPending: false,
  scenarioError: null,
  scenarioRequestVersion: 0,
  twinAnimationFrame: null,
  twinAnimationPlaying: false,
  twinAnimationUserPaused: false
};
window.AppState = AppState;

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
  initCarbonSyncDemo();
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
async function initMockToggle() {
  const checkbox = document.getElementById('mock-toggle');
  const badge    = document.getElementById('api-status-badge');

  // Offline is an error state, never permission to substitute sample results.
  // Mock mode remains available only through an explicit user toggle.
  window.USE_MOCKS = false;

  if (checkbox) {
    checkbox.checked = window.USE_MOCKS;
    checkbox.addEventListener('change', async () => {
      window.USE_MOCKS = checkbox.checked;
      const status = await checkBackendStatus();
      updateStatusIndicator(status);
      if (badge) badge.textContent = window.USE_MOCKS ? 'Mock Mode' : backendStatusLabel(status);
      showToast(window.USE_MOCKS ? 'Switched to Mock Mode' : 'Switched to Live API', 'info');
    });
  }

  const initialStatus = await checkBackendStatus();
  updateStatusIndicator(initialStatus);
  if (badge) badge.textContent = window.USE_MOCKS ? 'Mock Mode' : backendStatusLabel(initialStatus);
}

async function checkStatus() {
  const status = await checkBackendStatus();
  updateStatusIndicator(status);
}

function updateStatusIndicator(status) {
  const dot  = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  if (!dot) return;

  dot.className  = `status-dot ${status === 'detector-unavailable' ? 'error' : status}`;
  if (text) {
    const labels = {
      online: 'Backend + detector ready',
      'detector-unavailable': 'Backend online · detector unavailable',
      offline: 'Backend Offline', mock: 'Mock Mode', error: 'Backend Error'
    };
    text.textContent = labels[status] || status;
  }
}

function backendStatusLabel(status) {
  if (status === 'online') return 'Live API · Detector Ready';
  if (status === 'detector-unavailable') return 'Live API · Detector Unavailable';
  return status === 'offline' ? 'Offline' : status;
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
      AppState.assessmentMeta = { ...payload, ...result };
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
    if (file) selectParkingImage(file);
  });

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) selectParkingImage(fileInput.files[0]);
    });
  }
  document.getElementById('analyse-image-btn')?.addEventListener('click', () => {
    if (AppState.pendingImageFile) handleImageFile(AppState.pendingImageFile);
  });
  document.getElementById('change-image-btn')?.addEventListener('click', () => {
    AppState.currentAnalysis = null;
    AppState.currentAnalysisSaved = false;
    AppState.pendingImageFile = null;
    const review = document.getElementById('human-review-confirmed');
    if (review) review.checked = false;
    const emptyWarning = document.getElementById('zero-detection-review');
    if (emptyWarning) emptyWarning.style.display = 'none';
    const mockWarning = document.getElementById('mock-detection-warning');
    if (mockWarning) mockWarning.style.display = 'none';
    const input = document.getElementById('image-file-input');
    if (input) input.value = '';
    const dropSection = document.getElementById('drop-section');
    const canvasSection = document.getElementById('canvas-section');
    if (dropSection) dropSection.style.display = 'block';
    if (canvasSection) canvasSection.style.display = 'none';
    const name = document.getElementById('selected-image-name');
    if (name) name.textContent = 'Choose a parking image to begin.';
    const analyze = document.getElementById('analyse-image-btn');
    if (analyze) analyze.disabled = true;
    updateParkingCampaignControls();
  });

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
  document.getElementById('human-review-confirmed')?.addEventListener('change', updateParkingCampaignControls);
}

function selectParkingImage(file) {
  if (!['image/jpeg','image/png','image/webp'].includes(file.type)) {
    showToast('Choose a JPEG, PNG, or WebP image.', 'error');
    return;
  }
  AppState.pendingImageFile = file;
  const label = document.getElementById('selected-image-name');
  if (label) label.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MiB`;
  const button = document.getElementById('analyse-image-btn');
  if (button) button.disabled = file.size > 10 * 1024 * 1024;
  if (file.size > 10 * 1024 * 1024) showToast('Image exceeds the 10 MiB upload limit.', 'error');
}

async function handleImageFile(file) {
  if (!file.type.startsWith('image/')) {
    showToast('Invalid file. Please upload a JPEG or PNG image.', 'error');
    return;
  }
  AppState.currentImageFile = file;
  AppState.currentAnalysis = null;
  AppState.currentAnalysisSaved = false;

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
    AppState.currentAnalysis = result;
    AppState.currentAnalysisSaved = false;
    AppState.imageId = result.image_id;
    const mockWarning = document.getElementById('mock-detection-warning');
    if (mockWarning) mockWarning.style.display = result.simulated ? 'block' : 'none';
    const emptyWarning = document.getElementById('zero-detection-review');
    if (emptyWarning) emptyWarning.style.display = !result.simulated && result.inference_status === 'completed_no_detections' ? 'block' : 'none';

    // Use local blob URL so image loads instantly without network re-download
    const rawImgUrl = URL.createObjectURL(file);
    AppState.rawImgUrl = rawImgUrl;
    AppState.annotatedImgUrl = result.annotated_image_url || null;

    CanvasEditor.loadImage(rawImgUrl, result.detections, result.width, result.height, AppState.annotatedImgUrl);
    updateParkingCampaignControls();
    setEl('canvas-res', result.simulated ? 'Not measured (mock mode)' : `${result.width}×${result.height}px`);
    setEl('canvas-det-count', result.simulated
      ? 'Not analyzed (mock mode)'
      : result.inference_status === 'completed_no_detections'
        ? '0 vehicles (inference complete)'
        : `${result.detections.length} detected`);
    const thresholdLabel = document.getElementById('cv-conf-val');
    if (thresholdLabel) {
      const metadata = result.model_metadata || {};
      const settings = metadata.inference_settings || {};
      thresholdLabel.textContent = result.simulated
        ? 'Mock; no model used'
        : `${metadata.name || result.model || 'YOLO'} · conf ${Math.round((result.confidence_threshold ?? settings.confidence_threshold ?? 0) * 100)}% · IoU ${settings.iou_threshold ?? '—'} · ${settings.image_size ?? '—'}px · ${settings.nms_mode || 'NMS unknown'}`;
    }

    const engineName = window.USE_MOCKS ? 'Mock Data' : `${result.model || 'Local YOLO'}`;
    if (result.simulated) {
      showToast('Mock mode: this image was not analyzed. Connect the live backend for detections.', 'info');
    } else if (result.inference_status === 'completed_no_detections') {
      showToast('Inference completed successfully: no supported vehicles were detected in this image.', 'info');
    } else {
      showToast(`Detected ${result.detections.length} vehicles via ${engineName}`, 'success');
    }
  } catch (err) {
    AppState.currentAnalysis = null;
    updateParkingCampaignControls();
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
    showToast('Review confirmed in this browser. This GitHub backend branch does not persist verification records.', 'warning');

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

  const popupClose2 = document.getElementById('popup-close-btn2');

  popupSelect?.addEventListener('change', () => {
    CanvasEditor.reclassifySelected(popupSelect.value);
  });

  popupDelete?.addEventListener('click', () => {
    CanvasEditor.deleteSelected();
    document.getElementById('canvas-popup').classList.remove('visible');
  });

  const closeFn = () => document.getElementById('canvas-popup')?.classList.remove('visible');
  popupClose?.addEventListener('click', closeFn);
  popupClose2?.addEventListener('click', closeFn);
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
  if (view === 'annotated') {
    CanvasEditor.setAnnotatedView(true, AppState.annotatedImgUrl);
  } else {
    CanvasEditor.setAnnotatedView(false);
  }
}

// ── CarbonSync demo workflow: persisted observations, students and report ──
function initCarbonSyncDemo() {
  const today = new Date();
  const localDate = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const dateInput = document.getElementById('observation-date');
  if (dateInput) dateInput.value = localDate;
  dateInput?.addEventListener('change', updateParkingCampaignControls);
  renderOverviewPage();
  renderStudentsPage({ college_address: '', students: [] });
  renderInsightsPage();
  renderReportPage(null);
  document.getElementById('start-campaign-btn')?.addEventListener('click', async () => {
    const button = document.getElementById('start-campaign-btn');
    button.disabled = true;
    try {
      const campaign = await API.startCampaign(dateInput?.value || localDate);
      AppState.currentCampaign = campaign;
      await refreshCarbonSync(true);
      showToast('10-day observation period started.', 'success');
    } catch (error) { showToast(error.message, 'error'); }
    finally { button.disabled = false; }
  });
  document.getElementById('save-observation-btn')?.addEventListener('click', saveCurrentObservation);
  updateParkingCampaignControls();
  document.getElementById('refresh-report-btn')?.addEventListener('click', () => refreshCarbonSync(false));
  refreshCarbonSync(false);
}

function safeText(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[char]);
}

function showPageError(id, message) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = `<div class="alert alert-warning" role="status">${safeText(message)}</div>`;
}

async function refreshCarbonSync(generateAfterSave = false) {
  try {
    const [campaignResult, studentsResult, summaryResult, reportResult, scenarioResult, recommendationsResult] = await Promise.all([
      API.getCampaign(), API.getStudents(), API.getCommuteSummary(), API.getFinalReport(), API.latestScenario(), API.latestRecommendations()
    ]);
    AppState.currentCampaign = campaignResult.campaign;
    AppState.commuteSummary = summaryResult;
    AppState.report = reportResult;
    AppState.latestScenario = scenarioResult.scenario;
    AppState.latestRecommendations = recommendationsResult.recommendations;
    updateParkingCampaignControls();
    renderOverviewPage();
    renderStudentsPage(studentsResult);
    renderInsightsPage();
    renderReportPage(reportResult);
      const hasEvidence = (reportResult.observations || []).length || summaryResult.student_count;
      if (hasEvidence && (generateAfterSave || !AppState.latestRecommendations)) {
      await generateRecommendationsForCampaign(true);
      renderReportPage(await API.getFinalReport());
    }
  } catch (error) {
    showPageError('overview-page', `Could not load saved demo data: ${error.message}`);
  }
}

function renderOverviewPage() {
  const root = document.getElementById('overview-page');
  if (!root) return;
  const campaign = AppState.currentCampaign;
  const report = AppState.report || {};
  const days = campaign?.observations || report.observations || [];
  const groups = {};
  days.forEach(item => {
    const key = item.observation_date;
    if (!groups[key]) groups[key] = { count: 0, values: { bicycle:0, car:0, motorcycle:0, bus:0, truck:0 } };
    groups[key].count++;
    Object.keys(groups[key].values).forEach(name => groups[key].values[name] += Number(item.counts?.[name] || 0));
  });
  const dailyMeans = Object.entries(groups).sort(([a],[b]) => a.localeCompare(b)).map(([date, group]) => ({
    date, classes: Object.fromEntries(Object.entries(group.values).map(([name, value]) => [name, value / group.count])),
    total: Object.values(group.values).reduce((sum, value) => sum + value / group.count, 0)
  }));
  const mean = dailyMeans.length ? dailyMeans.reduce((sum, day) => sum + day.total, 0) / dailyMeans.length : null;
  const classMeans = Object.fromEntries(['car','motorcycle','bicycle','bus','truck'].map(name => [name, dailyMeans.length ? dailyMeans.reduce((sum, day) => sum + day.classes[name], 0) / dailyMeans.length : null]));
  const summary = AppState.commuteSummary || {};
  const observed = campaign?.observed_day_count || 0;
  const max = Math.max(1, ...dailyMeans.map(day => day.total));
  const chart = dailyMeans.length ? `<div class="trend-chart" role="img" aria-label="Mean detected vehicles per observed day">${dailyMeans.map(day => `<div class="trend-bar-wrap"><span>${day.total.toFixed(1)}</span><div class="trend-bar" style="height:${Math.max(6, day.total / max * 100)}%"></div><small>${safeText(day.date.slice(5))}</small></div>`).join('')}</div>` : '<div class="empty-state compact"><p>No saved parking observations yet.</p></div>';
  root.innerHTML = `
    <div class="page-heading"><div><span class="eyebrow">CAMPUS MOBILITY INTELLIGENCE</span><h1>Overview</h1><p>Parking snapshots and student commute estimates, with their evidence kept separate.</p></div><button class="btn btn-primary" data-go-tab="2">Analyse a parking image</button></div>
    <div class="overview-grid">
      <article class="card campaign-card"><div class="section-label">10-DAY OBSERVATION PERIOD</div><div class="campaign-number">${campaign ? `${observed} / 10` : '—'}</div><strong>${campaign ? `${observed} observed ${observed === 1 ? 'day' : 'days'}` : 'No active period'}</strong><p class="text-sm text-muted">${campaign ? `${safeText(campaign.start_date)} to ${safeText(campaign.end_date)} · ${campaign.image_count} image${campaign.image_count === 1 ? '' : 's'}` : 'Start a campaign to collect separate daily parking snapshots.'}</p><div class="progress-track"><div class="progress-fill" style="width:${campaign ? Math.min(100, observed * 10) : 0}%"></div></div><button class="btn btn-outline" data-go-tab="2">${campaign ? 'Add today’s observation' : 'Start campaign'}</button></article>
      <article class="card metric-card"><span class="section-label">SAVED IMAGES ANALYSED</span><strong>${campaign?.image_count || 0}</strong><span class="text-sm text-muted">Real model analyses saved to this period</span></article>
      <article class="card metric-card"><span class="section-label">MEAN SNAPSHOT COUNT</span><strong>${mean === null ? '—' : mean.toFixed(1)}</strong><span class="text-sm text-muted">Vehicles per observed date; same-day photos averaged</span><div class="class-count-list">${Object.entries(classMeans).map(([name,value]) => `<span>${safeText(name)} <strong>${value === null ? '—' : value.toFixed(1)}</strong></span>`).join('')}</div></article>
      <article class="card metric-card"><span class="section-label">AVERAGE WEEKDAY COMMUTE</span><strong>${summary.calculated_student_count ? `${Number(summary.average_weekday_kg_co2).toFixed(2)} kg` : '—'}</strong><span class="text-sm text-muted">Student estimate · ${summary.calculated_student_count || 0}/${summary.student_count || 0} records calculable</span></article>
      <article class="card metric-card"><span class="section-label">ESTIMATED PERIOD EMISSIONS</span><strong>${summary.calculated_student_count ? `${Number(summary.observation_period_kg_co2_estimate).toFixed(2)} kg` : '—'}</strong><span class="text-sm text-muted">Student commute inputs only; provisional factors</span></article>
      <article class="card"><div class="flex items-center justify-between"><div><span class="section-label">PARKING OBSERVATION TREND</span><p class="text-sm text-muted">Mean vehicles per saved date</p></div><span class="badge badge-direct">Image snapshots</span></div>${chart}</article>
    </div>
    <div class="card next-action"><div><span class="section-label">RECOMMENDED NEXT ACTION</span><p>${campaign && observed < 10 ? 'Continue the observation period on another date; avoid counting repeat photos as extra unique vehicles.' : !summary.student_count ? 'Add the five demo commute records to calculate an illustrative student estimate.' : 'Review the saved report and scenario assumptions before presenting results.'}</p></div><button class="btn btn-outline" data-go-tab="${!summary.student_count ? 3 : 6}">${!summary.student_count ? 'Add students' : 'Open report'}</button></div>`;
  root.querySelectorAll('[data-go-tab]').forEach(button => button.addEventListener('click', () => switchTab(Number(button.dataset.goTab))));
}

function updateParkingCampaignControls() {
  const campaign = AppState.currentCampaign;
  const progress = document.getElementById('campaign-progress');
  const detail = document.getElementById('campaign-progress-detail');
  const startButton = document.getElementById('start-campaign-btn');
  const saveRow = document.querySelector('.observation-save-row');
  const saveButton = document.getElementById('save-observation-btn');
  if (progress) progress.textContent = campaign ? `Next observation · ${campaign.day_progress}` : 'No observation period started';
  if (detail) detail.textContent = campaign ? `${campaign.start_date} through ${campaign.end_date} · ${campaign.image_count} image snapshots saved` : 'Start a 10-day campaign to save an observation.';
  if (startButton) startButton.textContent = campaign ? 'Start new 10-day period' : 'Start 10-day period';
  if (saveRow) saveRow.style.display = AppState.currentAnalysis ? 'flex' : 'none';
  if (saveButton) {
    const date = document.getElementById('observation-date')?.value || '';
    const withinCampaign = campaign && date >= campaign.start_date && date <= campaign.end_date;
    const reviewed = document.getElementById('human-review-confirmed')?.checked === true;
    saveButton.disabled = !campaign || !AppState.currentAnalysis || AppState.currentAnalysis.simulated || AppState.currentAnalysisSaved || !withinCampaign || !reviewed;
    saveButton.textContent = AppState.currentAnalysisSaved ? 'Observation saved' : 'Save Observation';
  }
}

function renderStudentsPage(data = { college_address: '', students: [] }) {
  const root = document.getElementById('students-page');
  if (!root) return;
  const saved = new Map((data.students || []).map(student => [student.student_id, student]));
  const records = Array.from({ length: 5 }, (_, index) => {
    const id = `DEMO-${String(index + 1).padStart(2, '0')}`;
    return saved.get(id) || { student_id: id, name: '', residential_address: '', one_way_distance_km: '', travel_mode: 'car', vehicle_type: 'car', fuel_type: 'unknown', commute_days_per_week: '', occupancy: 1 };
  });
  root.innerHTML = `
    <div class="page-heading"><div><span class="eyebrow">PRIVATE INPUTS · LOCAL BACKEND</span><h1>Student commute records</h1><p>Addresses are used only as stored form inputs. No routing is attempted; enter a user-provided one-way distance.</p></div></div>
    <div class="card college-address-card"><label class="form-label" for="college-address">College address (configured once)</label><input id="college-address" class="form-input" maxlength="300" required value="${safeText(data.college_address)}" placeholder="College destination address" /></div>
    <form id="student-records-form" class="student-record-list">${records.map((student, index) => `
      <details class="card student-record" ${index === 0 ? 'open' : ''}><summary><span>${safeText(student.student_id)}</span><strong>${safeText(student.name || 'Add student details')}</strong><span class="text-muted">${safeText(student.travel_mode || 'Commute mode')}</span></summary>
      <div class="student-fields">
        <input type="hidden" data-field="student_id" value="${safeText(student.student_id)}" />
        <label>Name / privacy-preserving display name<input class="form-input" data-field="name" maxlength="80" required value="${safeText(student.name)}" /></label>
        <label>Residential address<input class="form-input" data-field="residential_address" maxlength="300" required value="${safeText(student.residential_address)}" /></label>
        <label>One-way distance (km)<input class="form-input" data-field="one_way_distance_km" type="number" min="0.1" max="300" step="0.1" required value="${safeText(student.one_way_distance_km)}" /><small>User-provided; not calculated from address.</small></label>
        <label>Primary travel mode<select class="form-input" data-field="travel_mode">${[['car','Car'],['motorcycle','Motorcycle / scooter'],['public_transport','Public transport'],['cycling','Cycling'],['walking','Walking']].map(([value,label]) => `<option value="${value}" ${student.travel_mode === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
        <label>Vehicle type where applicable<select class="form-input" data-field="vehicle_type">${[['car','Car'],['motorcycle','Motorcycle / scooter'],['bus','Bus'],['none','Not applicable']].map(([value,label]) => `<option value="${value}" ${student.vehicle_type === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
        <label>Fuel / powertrain<select class="form-input" data-field="fuel_type">${[['unknown','Unknown'],['petrol','Petrol'],['diesel','Diesel'],['cng','CNG'],['electric','Electric']].map(([value,label]) => `<option value="${value}" ${student.fuel_type === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
        <label>Commute days per week<input class="form-input" data-field="commute_days_per_week" type="number" min="0.1" max="7" step="0.1" required value="${safeText(student.commute_days_per_week)}" /></label>
        <label>Vehicle occupancy (persons)<input class="form-input" data-field="occupancy" type="number" min="1" max="100" step="1" required value="${safeText(student.occupancy)}" /><small>Use an approximate passenger count for public transport.</small></label>
      </div></details>`).join('')}</form>
    <div class="card form-actions"><div><strong>Privacy and calculation note</strong><p class="text-sm text-muted">Student records remain in the local SQLite database. Dashboard, report, and recommendation payloads contain aggregates only. Existing demo factors are provisional and unapproved.</p></div><button class="btn btn-primary" id="save-students-btn">Save 5 student records</button></div>
    <div id="student-summary-panel"></div>`;
  document.getElementById('save-students-btn')?.addEventListener('click', saveStudentRecords);
  renderStudentSummary(data.summary || AppState.commuteSummary);
}

function renderStudentSummary(summary) {
  const root = document.getElementById('student-summary-panel');
  if (!root || !summary) return;
  root.innerHTML = `<div class="card student-summary"><span class="section-label">AGGREGATE SUMMARY · NO ADDRESSES SHOWN</span><div class="summary-stats"><div><strong>${summary.student_count || 0}</strong><span>Saved records</span></div><div><strong>${summary.calculated_student_count ? `${Number(summary.average_weekday_kg_co2).toFixed(2)} kg` : '—'}</strong><span>Average weekday estimate</span></div><div><strong>${summary.calculated_student_count ? `${Number(summary.observation_period_kg_co2_estimate).toFixed(2)} kg` : '—'}</strong><span>10-day period estimate</span></div></div><p class="text-xs text-muted">${safeText(summary.evidence_label || 'User-provided inputs')} · illustrative factor candidates are not validated.</p></div>`;
}

function renderInsightsPage() {
  const root = document.getElementById('insights-page');
  if (!root) return;
  stopTwinAnimation();
  const scenario = AppState.latestScenario?.result || AppState.latestScenario;
  const scenarioInputs = scenario?.assumptions || {};
  const summary = AppState.commuteSummary || {};
  const recs = AppState.latestRecommendations;
  const availableScenarios = scenario?.scenarios || {};
  if (!availableScenarios[AppState.selectedScenario]) AppState.selectedScenario = Object.keys(availableScenarios)[0] || 'carpool';
  const scenarioOptions = [
    ['carpool', 'Increase carpooling'],
    ['public_transport', 'Shift to public transport'],
    ['active_travel', 'Walking / cycling'],
    ['campus_shuttle', 'Campus shuttle']
  ].filter(([key]) => key in availableScenarios);
  root.innerHTML = `
    <div class="page-heading"><div><span class="eyebrow">TRANSPARENT ESTIMATES</span><h1>Insights &amp; Simulation</h1><p>Insights summarize saved commute records and parking snapshots. Simulation compares a selected intervention using deterministic calculations from student inputs.</p></div><button class="btn btn-outline" data-go-tab="3">Edit student inputs</button></div>
    <section class="scenario-flow-section"><div class="section-kicker">A · BASELINE AND DATA QUALITY</div><div class="card twin-context"><strong>Student commute baseline</strong><p>Uses saved, user-provided commute records and provisional factors. Parking photos are separate point-in-time observations and do not become trip counts.</p></div>
    <div class="scenario-baseline card"><div><span class="section-label">ESTIMATED BASELINE · STUDENT INPUTS</span><strong>${summary.annual_kg_co2 == null || summary.calculation_status === 'unavailable' ? 'Not available' : `${Number(summary.annual_kg_co2).toFixed(2)} kg CO₂/year`}</strong><span class="text-xs text-muted">${summary.unavailable_student_count || 0} records lack a configured factor · ${summary.student_count || 0} commute records</span></div><span class="badge badge-warning">Illustrative · unapproved factors</span></div></section>
    <section class="scenario-flow-section"><div class="section-kicker">B · SCENARIO CONTROLS</div><div class="card scenario-input-card"><div class="scenario-input-grid">
      <label>Car commute share shifted to carpool (%)<input id="scenario-carpool-share" class="form-input" type="number" min="0" max="100" value="${Number(scenarioInputs.carpool_share || 0) * 100}" /></label>
      <label>Target carpool occupancy<input id="scenario-carpool-occupancy" class="form-input" type="number" min="2" max="8" value="${scenarioInputs.carpool_occupancy || 2}" /></label>
      <label>Private trips shifted to public transport (%)<input id="scenario-transit-share" class="form-input" type="number" min="0" max="100" value="${Number(scenarioInputs.public_transport_share || 0) * 100}" /></label>
      <label>Bus occupancy assumption<input id="scenario-transit-occupancy" class="form-input" type="number" min="1" max="100" value="${scenarioInputs.transit_occupancy || 20}" /></label>
      <label>Eligible trips shifted to walking/cycling (%)<input id="scenario-active-share" class="form-input" type="number" min="0" max="100" value="${Number(scenarioInputs.active_travel_share || 0) * 100}" /></label>
      <label>Maximum active-travel distance (km)<input id="scenario-active-limit" class="form-input" type="number" min="0.1" max="300" step="0.1" value="${scenarioInputs.active_travel_limit_km || 5}" /></label>
      <label>Private commute share shifted to campus shuttle (%)<input id="scenario-shuttle-share" class="form-input" type="number" min="0" max="100" value="${Number(scenarioInputs.shuttle_shift_share || 0) * 100}" /></label>
      <label>Shuttle vehicles operating per day<input id="scenario-shuttle-vehicles" class="form-input" type="number" min="0" max="1000" value="${scenarioInputs.shuttle_daily_vehicles || 0}" /></label>
      <label>One-way shuttle trips per vehicle per day<input id="scenario-shuttle-trips" class="form-input" type="number" min="0" max="100" value="${scenarioInputs.shuttle_trips_per_vehicle_per_day || 0}" /></label>
      <label>One-way shuttle route (km)<input id="scenario-shuttle-route" class="form-input" type="number" min="0" max="300" value="${scenarioInputs.shuttle_one_way_route_km || 0}" /></label>
      <label>Shuttle operating days per year<input id="scenario-shuttle-operating-days" class="form-input" type="number" min="0" max="366" value="${scenarioInputs.shuttle_operating_days_per_year ?? 200}" /></label>
    </div><p class="text-xs text-muted">Scenario calculations use the current provisional category factors. Shuttle service emissions are included and can exceed the avoided private-vehicle emissions.</p><div class="scenario-actions"><button class="btn btn-primary" id="run-student-scenario-btn">Run Simulation</button><button class="btn btn-outline" id="reset-scenario-btn">Reset to baseline</button><span id="scenario-live-status" class="text-sm" role="status">${AppState.scenarioPending ? 'Recalculating with the latest inputs…' : safeText(AppState.scenarioError || '')}</span></div></div></section>
    <section class="scenario-flow-section"><div class="section-kicker">C · ANIMATED COMMUTE-FLOW VIEW</div><section class="card twin-card" aria-labelledby="twin-heading"><div class="twin-heading"><div><span class="section-label">ILLUSTRATIVE SIMULATION · NOT A LIVE CAMPUS TRAFFIC FEED</span><h2 id="twin-heading">Baseline and proposed mode mix</h2><p class="text-xs text-muted">Normalized symbols compare backend-derived weekly commute-day activity; they are not vehicle counts, traffic forecasts, or campus geography.</p></div><label>Intervention<select id="scenario-twin-select" class="form-input">${scenarioOptions.map(([key, label]) => `<option value="${key}" ${key === AppState.selectedScenario ? 'selected' : ''}>${label}</option>`).join('')}</select></label></div><div id="twin-visualization">${renderScenarioTwin(scenario, summary, AppState.selectedScenario, AppState.scenarioPending, AppState.scenarioError)}</div></section></section>
    <section class="scenario-flow-section"><div class="section-kicker">D · BEFORE-AND-AFTER COMPARISON</div><section class="card twin-card"><div id="scenario-comparison">${renderScenarioComparison(scenario, AppState.selectedScenario, AppState.scenarioPending, AppState.scenarioError)}</div></section><div class="scenario-results-grid">${scenarioOptions.map(([key, label]) => { const value = availableScenarios[key]; return `<article class="card scenario-result"><span class="section-label">${safeText(label.toUpperCase())}</span><strong>${Number(value.annual_kg_co2).toFixed(2)} kg CO₂/year</strong><span class="${value.reduction_kg_co2 >= 0 ? 'text-success' : 'text-danger'}">${value.reduction_kg_co2 >= 0 ? 'Reduction' : 'Increase'}: ${Math.abs(Number(value.reduction_kg_co2)).toFixed(2)} kg (${value.reduction_percent == null ? 'n/a' : `${Number(value.reduction_percent).toFixed(1)}%`})</span></article>`; }).join('') || '<div class="empty-state compact"><p>Add student records, adjust scenario inputs, then run a comparison.</p></div>'}</div></section>
    <section class="scenario-flow-section"><div class="section-kicker">E · RECOMMENDATIONS AND ASSUMPTIONS</div><div class="card recommendation-card"><div class="flex items-center justify-between"><div><span class="section-label">DATA-GROUNDED RECOMMENDATIONS</span><p class="text-sm text-muted">Aggregate student and saved parking evidence only. No names or addresses are sent.</p></div><button class="btn btn-outline" id="generate-recommendations-btn">Generate recommendations</button></div><div id="evidence-recommendations">${renderRecommendationHtml(recs)}</div></div>
    <details class="card caveat-card"><summary><strong>Calculation assumptions and evidence limits</strong></summary><p class="text-sm text-muted">Commute distance, weekly commute days, occupancy, and current provisional factors drive the backend estimate. A parking image is a point-in-time vehicle snapshot and is not used as commute activity. The animated symbols are a normalized explanation of aggregate commute records, not measured traffic. Factors are unapproved demonstration candidates; modeled outcomes are not measured future savings.</p></details></section>`;
  root.querySelector('[data-go-tab]')?.addEventListener('click', () => switchTab(3));
  document.getElementById('run-student-scenario-btn')?.addEventListener('click', runStudentScenario);
  document.getElementById('scenario-twin-select')?.addEventListener('change', event => {
    AppState.selectedScenario = event.target.value;
    document.getElementById('twin-visualization').innerHTML = renderScenarioTwin(AppState.latestScenario?.result || AppState.latestScenario, AppState.commuteSummary || {}, AppState.selectedScenario, AppState.scenarioPending, AppState.scenarioError);
    document.getElementById('scenario-comparison').innerHTML = renderScenarioComparison(AppState.latestScenario?.result || AppState.latestScenario, AppState.selectedScenario, AppState.scenarioPending, AppState.scenarioError);
    initTwinAnimation();
    animateScenarioComparison();
  });
  document.getElementById('reset-scenario-btn')?.addEventListener('click', resetScenarioInputs);
  let scenarioTimer;
  root.querySelectorAll('.scenario-input-grid input').forEach(input => input.addEventListener('input', () => {
    AppState.scenarioRequestVersion += 1;
    AppState.latestScenario = null;
    AppState.scenarioPending = true;
    AppState.scenarioError = null;
    const status = document.getElementById('scenario-live-status');
    if (status) status.textContent = 'Settings changed. Recalculating…';
    document.getElementById('twin-visualization').innerHTML = renderScenarioTwin(null, summary, AppState.selectedScenario, true, null);
    document.getElementById('scenario-comparison').innerHTML = renderScenarioComparison(null, AppState.selectedScenario, true, null);
    const resultCards = document.querySelector('.scenario-results-grid');
    if (resultCards) resultCards.innerHTML = '<div class="empty-state compact" role="status"><p>Recalculating from the changed inputs…</p></div>';
    clearTimeout(scenarioTimer);
    scenarioTimer = setTimeout(runStudentScenario, 500);
  }));
  document.getElementById('generate-recommendations-btn')?.addEventListener('click', () => generateRecommendationsForCampaign(false));
  initTwinAnimation();
  animateScenarioComparison();
}

function renderRecommendationHtml(recommendation) {
  if (!recommendation) return '<div class="empty-state compact"><p>Recommendations will appear after commute records or observations are saved.</p></div>';
  const cards = (recommendation.recommendations || []).map(item => `<article class="recommendation-item"><span class="section-label">PRIORITY ${safeText(item.priority)}</span><h3>${safeText(item.action || item.title)}</h3><p>${safeText(item.relevance || item.why_it_may_help)}</p><p class="text-xs text-muted"><strong>Assumptions:</strong> ${safeText(item.assumptions || 'See supplied demo inputs.')}</p><p class="text-xs text-muted"><strong>Constraints:</strong> ${safeText(item.constraints || item.practical_tradeoffs || 'Validate with campus stakeholders.')}</p><span class="badge badge-warning">${safeText(item.estimated_reduction || 'No emissions reduction calculated')}</span></article>`).join('');
  const llmStatus = recommendation.llm_status || 'unknown';
  const statusMessage = recommendation.fallback_flag
    ? (llmStatus === 'credentials_not_configured'
      ? 'AI-generated explanations are unavailable because the optional LLM provider and API key are not configured. To enable them, set CARBOSYNC_LLM_PROVIDER and CARBOSYNC_LLM_API_KEY in the backend environment. Deterministic scenario calculations remain available.'
      : 'AI-generated explanations are unavailable right now. Deterministic scenario calculations remain available.')
    : 'Qualitative wording was generated with the configured AI provider; numeric results still come from the deterministic calculation engine.';
  return `<div class="recommendation-status ${recommendation.fallback_flag ? 'fallback' : 'llm'}">${safeText(recommendation.label || 'Recommendation status unavailable')}</div><p class="text-sm">${safeText(statusMessage)}</p><p class="text-sm">${safeText(recommendation.summary || '')}</p><div class="recommendation-list">${cards}</div>`;
}

function renderScenarioTwin(scenario, summary, selectedKey, pending, error) {
  if (pending) return '<div class="empty-state compact" role="status"><p>Scenario results are being recalculated. The previous comparison is hidden until the new response arrives.</p></div>';
  if (error) return `<div class="alert alert-warning" role="status">${safeText(error)}</div>`;
  const selected = scenario?.scenarios?.[selectedKey];
  const representation = scenario?.flow_representation;
  const flow = representation?.scenarios?.[selectedKey];
  if (!selected || !flow || !representation?.baseline) return '<div class="empty-state compact"><p>Run a simulation with supported student commute records to see the illustrative mode flow.</p></div>';
  const modeInfo = [
    ['single_occupancy_car', 'Single-occupancy car', 'single-car'],
    ['carpool_vehicle', 'Carpool vehicle', 'carpool-car'],
    ['motorcycle', 'Motorcycle', 'motorcycle'],
    ['public_transport', 'Public transport', 'bus'],
    ['shuttle', 'Campus shuttle', 'shuttle'],
    ['active_travel', 'Walking / cycling', 'active']
  ];
  const makeSymbols = (profile, side) => {
    const available = modeInfo.map(([key, label, icon]) => ({ key, label, icon, value: Number(profile[key] || 0) })).filter(item => item.value > 0);
    const total = available.reduce((sum, item) => sum + item.value, 0);
    if (!total) return { symbols: '', modes: [] };
    const slots = 12;
    const allocations = available.map(item => {
      const exact = item.value / total * slots;
      return { ...item, count: Math.floor(exact), remainder: exact - Math.floor(exact) };
    });
    let remaining = slots - allocations.reduce((sum, item) => sum + item.count, 0);
    [...allocations].sort((a, b) => b.remainder - a.remainder).slice(0, remaining).forEach(item => { item.count += 1; });
    const tokens = allocations.flatMap(item => Array.from({ length: item.count }, (_, index) => ({ ...item, index })));
    const symbols = tokens.map((item, index) => {
      const route = `${side}-${item.icon === 'active' ? 'active' : 'vehicle'}`;
      const icon = item.icon === 'single-car' || item.icon === 'carpool-car'
        ? `<rect class="vehicle-body ${item.icon}" x="-20" y="-11" width="40" height="22" rx="6"/><rect class="vehicle-window" x="-11" y="-7" width="22" height="14" rx="3"/>${item.icon === 'carpool-car' ? '<circle class="passenger-dot" cx="-5" cy="0" r="2"/><circle class="passenger-dot" cx="5" cy="0" r="2"/>' : ''}`
        : item.icon === 'motorcycle'
          ? '<circle class="wheel" cx="-10" cy="6" r="4"/><circle class="wheel" cx="10" cy="6" r="4"/><path class="moto-shape" d="M-10 6 L-5 -2 L4 -2 L10 6 M-2 -2 L1 -7 L7 -7"/>'
          : item.icon === 'active'
            ? '<circle class="bike-wheel" cx="-11" cy="6" r="6"/><circle class="bike-wheel" cx="12" cy="6" r="6"/><path class="bike-shape" d="M-11 6 L-4 -3 L2 6 L12 6 L3 -5 M-4 -3 L-8 -3"/><circle class="person-head" cx="2" cy="-12" r="3"/><path class="person-shape" d="M2 -9 L-2 -2 L4 1"/>'
            : `<rect class="vehicle-body ${item.icon}" x="-26" y="-12" width="52" height="24" rx="5"/><rect class="bus-window" x="-20" y="-8" width="40" height="8" rx="2"/><circle class="wheel-dot" cx="-16" cy="12" r="2"/><circle class="wheel-dot" cx="16" cy="12" r="2"/>`;
      return `<g class="twin-token ${item.icon}" data-route="${route}" data-phase="${(index / tokens.length).toFixed(4)}" aria-hidden="true">${icon}</g>`;
    }).join('');
    return { symbols, modes: allocations.filter(item => item.count > 0) };
  };
  const baseline = makeSymbols(representation.baseline, 'baseline');
  const proposed = makeSymbols(flow, 'proposed');
  if (!baseline.symbols || !proposed.symbols) return '<div class="empty-state compact"><p>There is not enough supported mode data to compare baseline and scenario flows.</p></div>';
  const legendModes = [...baseline.modes, ...proposed.modes].filter((item, index, all) => all.findIndex(other => other.key === item.key) === index);
  const legend = legendModes.map(item => {
    const detail = item.key === 'carpool_vehicle' ? ` · target ${Number(scenario.assumptions?.carpool_occupancy || 2)}`
      : item.key === 'public_transport' ? ` · assumed occupancy ${Number(scenario.assumptions?.transit_occupancy || 20)}` : '';
    return `<span class="twin-legend-item"><i class="legend-dot ${item.icon}"></i>${safeText(item.label + detail)}</span>`;
  }).join('');
  const shuttleVehicles = Number(scenario.assumptions?.shuttle_daily_vehicles || 0);
  const explanation = representation.basis;
  const scenarioNames = { carpool: 'Carpool', public_transport: 'Public transport', active_travel: 'Walking / cycling', campus_shuttle: 'Campus shuttle' };
  return `<div class="twin-flow-view"><div class="twin-disclosure"><span class="badge badge-warning">Illustrative simulation — not a live campus traffic feed</span><span class="text-xs text-muted">Each lane uses 12 normalized symbols to compare the backend-derived weekly commute-day mix; symbols are not traffic counts.</span></div>
    <div class="twin-map-wrap"><svg class="twin-map" viewBox="0 0 1000 440" role="img" aria-label="Illustrative baseline and proposed commute mode flows. Animated symbols show normalized student commute activity, not live traffic or a geographic campus map.">
      <defs><pattern id="twin-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M 28 0 L 0 0 0 28" fill="none" stroke="#e7eee9" stroke-width="1"/></pattern><marker id="twin-direction" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#537a63"/></marker></defs>
      <rect width="1000" height="440" fill="#f5f8f5"/><rect width="1000" height="440" fill="url(#twin-grid)"/>
      <rect class="zone-origin" x="20" y="92" width="140" height="258" rx="18"/><text class="zone-title" x="90" y="264" text-anchor="middle">ORIGINS</text><text class="zone-subtitle" x="90" y="289" text-anchor="middle">Illustrative</text>
      <rect class="zone-campus" x="840" y="92" width="140" height="258" rx="18"/><rect class="campus-building" x="870" y="201" width="80" height="70" rx="8"/><path class="building-roof" d="M862 203 L910 172 L958 203 Z"/><text class="zone-title" x="910" y="301" text-anchor="middle">CAMPUS</text><text class="zone-subtitle" x="910" y="326" text-anchor="middle">Illustrative</text>
      <text class="lane-label baseline-label" x="500" y="63" text-anchor="middle">BASELINE · CURRENT COMMUTE MIX</text><text class="lane-label proposed-label" x="500" y="226" text-anchor="middle">PROPOSED · ${safeText(scenarioNames[selectedKey] || selectedKey)}</text>
      <path class="road-surface" d="M200 124 C320 92 400 111 493 145 S680 180 800 124"/><path class="road-center" d="M200 124 C320 92 400 111 493 145 S680 180 800 124"/><path class="cycle-surface" d="M200 184 C335 211 410 191 493 168 S680 145 800 184"/><path class="cycle-line" d="M200 184 C335 211 410 191 493 168 S680 145 800 184"/>
      <path class="road-surface" d="M200 286 C320 254 400 273 493 307 S680 342 800 286"/><path class="road-center" d="M200 286 C320 254 400 273 493 307 S680 342 800 286"/><path class="cycle-surface" d="M200 346 C335 373 410 353 493 330 S680 307 800 346"/><path class="cycle-line" d="M200 346 C335 373 410 353 493 330 S680 307 800 346"/>
      <path id="twin-baseline-vehicle-route" class="motion-route" d="M200 124 C320 92 400 111 493 145 S680 180 800 124"/><path id="twin-baseline-active-route" class="motion-route" d="M200 184 C335 211 410 191 493 168 S680 145 800 184"/>
      <path id="twin-proposed-vehicle-route" class="motion-route" d="M200 286 C320 254 400 273 493 307 S680 342 800 286"/><path id="twin-proposed-active-route" class="motion-route" d="M200 346 C335 373 410 353 493 330 S680 307 800 346"/>
      <path class="direction-arrow" d="M255 103 l34 -6" marker-end="url(#twin-direction)"/><path class="direction-arrow" d="M700 321 l34 -5" marker-end="url(#twin-direction)"/>
      ${baseline.symbols}${proposed.symbols}
    </svg></div><div class="twin-animation-controls"><div class="twin-legend">${legend}</div><div class="twin-control-buttons"><button class="btn btn-outline" type="button" data-twin-play aria-label="Play commute flow animation">▶ Play</button><button class="btn btn-outline" type="button" data-twin-pause aria-label="Pause commute flow animation">Ⅱ Pause</button><button class="btn btn-outline" type="button" data-twin-reset aria-label="Reset commute flow animation">↺ Reset</button></div></div>
    <p class="twin-animation-status text-xs text-muted" role="status" data-twin-status>${window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'Paused for reduced-motion preference. Play is available on request.' : 'Animated mode mix is illustrative; icon movement does not represent speed, distance, or traffic volume.'}</p>
    <details class="twin-assumption-details"><summary>How this view is derived</summary><p>${safeText(explanation)} Carpool, transit, active-travel, and shuttle shares are applied by the backend to aggregate commute activity. Active-travel eligibility uses the configured distance limit. Shuttle service emissions and operating assumptions are included in the separate deterministic comparison.</p>${selectedKey === 'campus_shuttle' ? `<p>Configured shuttle service: ${shuttleVehicles} vehicles/day × ${Number(scenario.assumptions?.shuttle_trips_per_vehicle_per_day || 0)} one-way trips/vehicle/day × ${Number(scenario.assumptions?.shuttle_one_way_route_km || 0)} km × ${Number(scenario.assumptions?.shuttle_operating_days_per_year || 0)} operating days/year. Symbols remain normalized and do not depict the fleet count.</p>` : ''}</details></div>`;
}
function stopTwinAnimation() {
  if (AppState.twinAnimationFrame) cancelAnimationFrame(AppState.twinAnimationFrame);
  AppState.twinAnimationFrame = null;
  AppState.twinAnimationPlaying = false;
}

function initTwinAnimation() {
  stopTwinAnimation();
  const root = document.getElementById('twin-visualization');
  const svg = root?.querySelector('.twin-map');
  if (!svg) return;
  const paths = {
    'baseline-vehicle': svg.querySelector('#twin-baseline-vehicle-route'),
    'baseline-active': svg.querySelector('#twin-baseline-active-route'),
    'proposed-vehicle': svg.querySelector('#twin-proposed-vehicle-route'),
    'proposed-active': svg.querySelector('#twin-proposed-active-route')
  };
  const tokens = [...svg.querySelectorAll('.twin-token')].map(node => ({ node, path: paths[node.dataset.route], phase: Number(node.dataset.phase || 0) })).filter(token => token.path);
  const status = root.querySelector('[data-twin-status]');
  let progress = 0;
  let lastFrame = 0;
  const update = timestamp => {
    if (!AppState.twinAnimationPlaying) return;
    if (document.hidden || !document.getElementById('tab-panel-5')?.classList.contains('active')) {
      AppState.twinAnimationPlaying = false;
      if (status) status.textContent = 'Animation paused while this section is not visible.';
      return;
    }
    if (!lastFrame || timestamp - lastFrame >= 32) {
      const elapsed = lastFrame ? Math.min(timestamp - lastFrame, 80) : 0;
      lastFrame = timestamp;
      progress = (progress + elapsed / 1000 * 0.035) % 1;
      tokens.forEach(token => {
        const length = token.path.getTotalLength();
        const distance = ((progress + token.phase) % 1) * length;
        const point = token.path.getPointAtLength(distance);
        const next = token.path.getPointAtLength(Math.min(length, distance + 1));
        const angle = Math.atan2(next.y - point.y, next.x - point.x) * 180 / Math.PI;
        token.node.setAttribute('transform', `translate(${point.x.toFixed(1)} ${point.y.toFixed(1)}) rotate(${angle.toFixed(1)})`);
      });
    }
    AppState.twinAnimationFrame = requestAnimationFrame(update);
  };
  const play = () => {
    if (!document.getElementById('tab-panel-5')?.classList.contains('active')) {
      if (status) status.textContent = 'Open Insights & Simulation to play the commute-flow animation.';
      return;
    }
    if (AppState.twinAnimationPlaying) return;
    AppState.twinAnimationUserPaused = false;
    AppState.twinAnimationPlaying = true;
    lastFrame = 0;
    if (status) status.textContent = 'Playing normalized, illustrative commute-mode flow.';
    AppState.twinAnimationFrame = requestAnimationFrame(update);
  };
  root.querySelector('[data-twin-play]')?.addEventListener('click', play);
  root.querySelector('[data-twin-pause]')?.addEventListener('click', () => {
    AppState.twinAnimationPlaying = false;
    AppState.twinAnimationUserPaused = true;
    if (AppState.twinAnimationFrame) cancelAnimationFrame(AppState.twinAnimationFrame);
    AppState.twinAnimationFrame = null;
    if (status) status.textContent = 'Animation paused. All scenario metrics remain available.';
  });
  root.querySelector('[data-twin-reset]')?.addEventListener('click', () => {
    progress = 0;
    AppState.twinAnimationPlaying = false;
    AppState.twinAnimationUserPaused = true;
    if (AppState.twinAnimationFrame) cancelAnimationFrame(AppState.twinAnimationFrame);
    AppState.twinAnimationFrame = null;
    tokens.forEach(token => {
      const point = token.path.getPointAtLength(token.phase * token.path.getTotalLength());
      token.node.setAttribute('transform', `translate(${point.x.toFixed(1)} ${point.y.toFixed(1)})`);
    });
    if (status) status.textContent = 'Animation reset. Press Play to view the illustrative flow.';
  });
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  tokens.forEach(token => {
    const point = token.path.getPointAtLength(token.phase * token.path.getTotalLength());
    token.node.setAttribute('transform', `translate(${point.x.toFixed(1)} ${point.y.toFixed(1)})`);
  });
  if (!reducedMotion && !AppState.twinAnimationUserPaused && document.getElementById('tab-panel-5')?.classList.contains('active')) play();
}

function animateScenarioComparison() {
  const root = document.getElementById('scenario-comparison');
  if (!root) return;
  const bars = [...root.querySelectorAll('.scenario-bar[data-target-width]')];
  const values = [...root.querySelectorAll('[data-target-kg]')];
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  requestAnimationFrame(() => {
    bars.forEach(bar => { bar.style.width = `${bar.dataset.targetWidth}%`; });
    if (reduceMotion) {
      values.forEach(node => { node.textContent = `${Number(node.dataset.targetKg).toFixed(2)} kg CO₂/year`; });
      return;
    }
    const start = performance.now();
    const tick = now => {
      const progress = Math.min(1, (now - start) / 500);
      const eased = 1 - (1 - progress) ** 3;
      values.forEach(node => { node.textContent = `${(Number(node.dataset.targetKg || 0) * eased).toFixed(2)} kg CO₂/year`; });
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}
function renderScenarioComparison(scenario, selectedKey, pending, error) {
  if (pending || error) return '';
  const selected = scenario?.scenarios?.[selectedKey];
  const baseline = Number(scenario?.baseline?.annual_kg_co2);
  if (!selected || !Number.isFinite(baseline)) return '';
  const value = Number(selected.annual_kg_co2);
  const difference = Number(selected.reduction_kg_co2);
  if (!Number.isFinite(value) || !Number.isFinite(difference)) return '';
  const maximum = Math.max(baseline, value, 1);
  const baselineWidth = Math.max(0, Math.min(100, baseline / maximum * 100));
  const scenarioWidth = Math.max(0, Math.min(100, value / maximum * 100));
  const label = difference > 0 ? 'Estimated reduction' : difference < 0 ? 'Estimated increase' : 'No estimated change';
  const percent = selected.reduction_percent == null ? 'Not available (zero baseline)' : `${Number(selected.reduction_percent).toFixed(1)}%`;
  const scenarioLabels = { carpool: 'Increase carpooling', public_transport: 'Shift to public transport', active_travel: 'Walking / cycling', campus_shuttle: 'Campus shuttle' };
  const shuttle = selectedKey === 'campus_shuttle' ? `<p class="text-xs text-muted">Shuttle service adds ${Number(scenario.shuttle_activity?.added_shuttle_annual_kg_co2 || 0).toFixed(2)} kg CO₂/year; modeled avoided private-vehicle emissions are ${Number(scenario.shuttle_activity?.avoided_private_annual_kg_co2 || 0).toFixed(2)} kg CO₂/year.</p>` : '';
  const explanation = difference > 0
    ? `Under these inputs, ${scenarioLabels[selectedKey]} has lower modeled emissions by ${difference.toFixed(2)} kg CO₂/year. This supports testing the intervention in planning, subject to validating the factors and assumptions.`
    : difference < 0
      ? `Under these inputs, ${scenarioLabels[selectedKey]} has higher modeled emissions by ${Math.abs(difference).toFixed(2)} kg CO₂/year. The current settings do not support presenting it as an emissions reduction.`
      : `Under these inputs, ${scenarioLabels[selectedKey]} does not change modeled annual emissions from baseline.`;
  const assumptions = selectedKey === 'carpool'
    ? `${Number(scenario.assumptions?.carpool_share || 0) * 100}% of car commute activity shifted; target occupancy ${Number(scenario.assumptions?.carpool_occupancy || 2)} persons.`
    : selectedKey === 'public_transport'
      ? `${Number(scenario.assumptions?.public_transport_share || 0) * 100}% of eligible private commute activity shifted; bus occupancy ${Number(scenario.assumptions?.transit_occupancy || 20)} persons.`
      : selectedKey === 'active_travel'
        ? `${Number(scenario.assumptions?.active_travel_share || 0) * 100}% of eligible trips shifted; one-way distance limit ${Number(scenario.assumptions?.active_travel_limit_km || 5)} km.`
        : `${Number(scenario.assumptions?.shuttle_shift_share || 0) * 100}% private commute share shifted; ${Number(scenario.assumptions?.shuttle_daily_vehicles || 0)} vehicles × ${Number(scenario.assumptions?.shuttle_trips_per_vehicle_per_day || 0)} one-way trips/day × ${Number(scenario.assumptions?.shuttle_one_way_route_km || 0)} km × ${Number(scenario.assumptions?.shuttle_operating_days_per_year || 0)} days/year.`;
  return `<div class="scenario-compare"><div class="scenario-bars" role="img" aria-label="Annual emissions comparison: baseline ${baseline.toFixed(2)} kg and scenario ${value.toFixed(2)} kg carbon dioxide per year"><div class="scenario-bar-row"><span>Baseline</span><div class="scenario-bar-track"><div class="scenario-bar baseline" data-target-width="${baselineWidth}" style="width:0%"></div></div><strong data-target-kg="${baseline}">0.00 kg CO₂/year</strong></div><div class="scenario-bar-row"><span>Scenario</span><div class="scenario-bar-track"><div class="scenario-bar proposed ${difference >= 0 ? 'lower' : 'higher'}" data-target-width="${scenarioWidth}" style="width:0%"></div></div><strong data-target-kg="${value}">0.00 kg CO₂/year</strong></div></div><div class="scenario-impact"><span class="section-label">${label.toUpperCase()}</span><strong class="${difference >= 0 ? 'text-success' : 'text-danger'}">${Math.abs(difference).toFixed(2)} kg CO₂/year</strong><span>${safeText(percent)}</span></div></div><div class="rule-explanation"><span class="section-label">RULE-BASED SCENARIO SIGNAL · NOT AI-GENERATED</span><h3>${safeText(scenarioLabels[selectedKey])}</h3><p><strong>Why:</strong> ${safeText(explanation)}</p><p><strong>Calculated impact:</strong> ${Math.abs(difference).toFixed(2)} kg CO₂/year ${difference > 0 ? 'lower' : difference < 0 ? 'higher' : 'unchanged'} than baseline${baseline > 0 ? ` (${(difference / baseline * 100).toFixed(1)}%)` : ' (percentage unavailable for a zero baseline)'}.</p><p><strong>Assumptions:</strong> ${safeText(assumptions)}</p><p class="text-xs text-muted">Deterministic estimate from saved commute activity and provisional, unapproved factors; not a measured outcome or feasibility assessment.</p>${shuttle}</div>`;
}

function resetScenarioInputs() {
  const defaults = { 'scenario-carpool-share': 0, 'scenario-carpool-occupancy': 2, 'scenario-transit-share': 0, 'scenario-transit-occupancy': 20, 'scenario-active-share': 0, 'scenario-active-limit': 5, 'scenario-shuttle-share': 0, 'scenario-shuttle-vehicles': 0, 'scenario-shuttle-trips': 0, 'scenario-shuttle-route': 0, 'scenario-shuttle-operating-days': 200 };
  Object.entries(defaults).forEach(([id, value]) => { const input = document.getElementById(id); if (input) input.value = value; });
  AppState.selectedScenario = 'carpool';
  const selector = document.getElementById('scenario-twin-select');
  if (selector) selector.value = 'carpool';
  runStudentScenario();
}

function renderReportPage(report) {
  const root = document.getElementById('report-page');
  if (!root) return;
  const observations = report?.observations || [];
  const campaign = report?.campaign;
  const commute = report?.student_commute || {};
  const snapshotRows = observations.length ? observations.map(row => `<tr><td>${safeText(row.observation_date)}</td><td>${safeText(row.inference_status)}</td><td>${Object.entries(row.counts || {}).map(([key,value]) => `${safeText(key)} ${safeText(value)}`).join(' · ')}</td><td>${row.human_reviewed == null ? 'Review status not captured (legacy record)' : row.human_reviewed ? row.corrected ? 'Human-reviewed · corrected' : 'Human-reviewed · confirmed' : 'Review not recorded'}</td><td>${safeText(String(row.image_sha256 || '').slice(0,16))}</td></tr>`).join('') : '<tr><td colspan="5">No saved parking observations.</td></tr>';
  const byMode = Object.entries(commute.by_mode || {}).map(([mode, values]) => `<tr><td>${safeText(mode)}</td><td>${safeText(values.students)}</td><td>${Number(values.annual_kg_co2).toFixed(2)} kg/year</td></tr>`).join('') || '<tr><td colspan="3">No saved student commute records.</td></tr>';
  const factorRows = Object.entries(commute.factor_register || {}).map(([category, factor]) => `<tr><td>${safeText(category)}</td><td>${safeText(factor.value)}</td><td>${safeText(factor.unit)}</td><td>${safeText(factor.status)}</td></tr>`).join('') || '<tr><td colspan="4">No factor register available.</td></tr>';
  const scenario = report?.scenario?.result || report?.scenario;
  const scenarioRows = scenario?.scenarios ? Object.entries(scenario.scenarios).map(([name, value]) => `<tr><td>${safeText(name.replace('_',' '))}</td><td>${Number(value.annual_kg_co2).toFixed(2)}</td><td>${Number(value.reduction_kg_co2).toFixed(2)}</td></tr>`).join('') : '<tr><td colspan="3">No scenario comparison saved.</td></tr>';
  const scenarioInputs = scenario?.assumptions || {};
  const scenarioAssumptions = scenario ? `<p class="text-xs text-muted">Inputs: carpool ${Number(scenarioInputs.carpool_share || 0) * 100}% at ${safeText(scenarioInputs.carpool_occupancy || 2)} occupants; public transport ${Number(scenarioInputs.public_transport_share || 0) * 100}% at ${safeText(scenarioInputs.transit_occupancy || 20)} occupants; active travel ${Number(scenarioInputs.active_travel_share || 0) * 100}% for trips up to ${safeText(scenarioInputs.active_travel_limit_km || 5)} km; shuttle ${Number(scenarioInputs.shuttle_shift_share || 0) * 100}% of private commute, ${safeText(scenarioInputs.shuttle_daily_vehicles || 0)} vehicles × ${safeText(scenarioInputs.shuttle_trips_per_vehicle_per_day || 0)} one-way trips/day × ${safeText(scenarioInputs.shuttle_one_way_route_km || 0)} km × ${safeText(scenarioInputs.shuttle_operating_days_per_year ?? 200)} operating days/year.</p>` : '';
  root.innerHTML = `<div class="page-heading report-toolbar"><div><span class="eyebrow">CARBONSYNC · DEMO REPORT</span><h1>Final report</h1><p>${safeText(campaign ? `Observation coverage: ${campaign.observed_day_count}/10 days · ${campaign.image_count} images` : 'No active 10-day observation period.')}</p></div><div class="flex gap-sm"><button class="btn btn-outline" id="refresh-report-btn">Refresh</button><button class="btn btn-primary" id="print-report-btn">Print / Save as PDF</button></div></div>
    <div class="card report-disclaimer"><strong>Evidence boundary</strong><p>${safeText(report?.privacy || 'Personal addresses are excluded from this report.')}</p><p>Parking images provide vehicle snapshots only. Commute emissions below are estimates from user-provided student activity and provisional factors. Coverage is ${campaign ? `${campaign.observed_day_count} of 10 campaign days` : 'not yet established'}.</p></div>
    <section class="card report-section"><h2>Parking observations</h2><div class="table-wrapper"><table><thead><tr><th>Date</th><th>Inference status</th><th>Saved class counts</th><th>Evidence</th><th>Image SHA-256 prefix</th></tr></thead><tbody>${snapshotRows}</tbody></table></div><p class="text-xs text-muted">Original image files are not retained by the backend; the analysis ID and image fingerprint provide provenance for each saved result.</p></section>
    <section class="card report-section"><h2>Student commute estimate</h2><div class="summary-stats"><div><strong>${commute.student_count || 0}</strong><span>Records</span></div><div><strong>${commute.average_weekday_kg_co2 == null ? '—' : `${Number(commute.average_weekday_kg_co2).toFixed(2)} kg`}</strong><span>Average weekday estimate</span></div><div><strong>${commute.observation_period_kg_co2_estimate == null ? '—' : `${Number(commute.observation_period_kg_co2_estimate).toFixed(2)} kg`}</strong><span>10-day estimate</span></div></div><p class="text-sm">${safeText(commute.methodology || '')}</p><div class="table-wrapper"><table><thead><tr><th>Mode</th><th>Students</th><th>Estimated emissions</th></tr></thead><tbody>${byMode}</tbody></table></div><p class="text-xs text-muted">${safeText((commute.limitations || []).join(' '))}</p></section>
    <section class="card report-section"><h2>Saved scenario comparison</h2><p class="text-sm text-muted">Deterministic calculations from scenario inputs; this is not a forecast. A negative change means emissions increase.</p><div class="table-wrapper"><table><thead><tr><th>Scenario</th><th>Annual kg CO₂</th><th>Reduction (+) / increase (−) vs baseline kg</th></tr></thead><tbody>${scenarioRows}</tbody></table></div>${scenarioAssumptions}</section>
    <section class="card report-section"><h2>Recommendations</h2>${renderRecommendationHtml(report?.recommendations)}</section>
    <section class="card report-section"><h2>Emission-factor register</h2><div class="table-wrapper"><table><thead><tr><th>Category</th><th>Value</th><th>Unit</th><th>Approval status</th></tr></thead><tbody>${factorRows}</tbody></table></div><p class="text-xs text-muted">Sources, geographic applicability, fuel coverage, and independent validation are not available for the existing candidates. Do not present these values as verified factors.</p></section>
    <section class="card report-section"><h2>Method and limitations</h2><p>Commute annual vehicle-kilometres are estimated as one-way distance × two legs × commute days per week × 52. Shared vehicle activity is allocated by entered occupancy. Emissions are vehicle-kilometres × the current category factor. Factors are demo candidates and are not verified or approved; electric commute records are not calculated without a configured grid factor. Addresses are not geocoded. Parking counts are not converted into trips or emissions.</p><p>Multiple images on the same date remain separate snapshots. Dashboard trends average same-day image counts rather than adding them. Inference accuracy on overhead parking images has not been established with a labeled evaluation set.</p></section>`;
  document.getElementById('refresh-report-btn')?.addEventListener('click', () => refreshCarbonSync(false));
  document.getElementById('print-report-btn')?.addEventListener('click', () => window.print());
}

async function saveStudentRecords() {
  const form = document.getElementById('student-records-form');
  const collegeAddress = document.getElementById('college-address');
  if (!form || !collegeAddress) return;
  if (!collegeAddress.reportValidity()) return;
  const firstInvalid = [...form.querySelectorAll('input, select')].find(input => !input.checkValidity());
  if (firstInvalid) {
    firstInvalid.closest('details')?.setAttribute('open', '');
    firstInvalid.reportValidity();
    firstInvalid.focus();
    return;
  }
  const students = [...form.querySelectorAll('.student-record')].map(card => {
    const row = {};
    card.querySelectorAll('[data-field]').forEach(input => row[input.dataset.field] = input.value);
    for (const field of ['one_way_distance_km','commute_days_per_week','occupancy']) row[field] = Number(row[field]);
    return row;
  });
  try {
    await API.saveStudents({ college_address: collegeAddress.value.trim(), students });
    showToast('Student commute records saved securely to the local database.', 'success');
    await refreshCarbonSync(true);
  } catch (error) { showToast(error.message, 'error'); }
}

async function saveCurrentObservation() {
  const campaign = AppState.currentCampaign;
  const analysis = AppState.currentAnalysis;
  if (!campaign || !analysis || analysis.simulated || !analysis.analysis_id) {
    showToast('Start a campaign and complete real inference before saving an observation.', 'warning');
    return;
  }
  const button = document.getElementById('save-observation-btn');
  const humanReviewed = document.getElementById('human-review-confirmed')?.checked === true;
  if (!humanReviewed) {
    showToast('Review the image and confirm its vehicle counts before saving.', 'warning');
    return;
  }
  button.disabled = true;
  try {
    const verified = CanvasEditor.getVerifiedCounts();
    const counts = {
      bicycle: verified.Bicycles || 0,
      car: verified.Cars || 0,
      motorcycle: verified['Motorcycles and scooters'] || 0,
      bus: verified['Buses and campus shuttles'] || 0,
      truck: verified['Other fuel-burning vehicles'] || 0
    };
    await API.saveObservation(campaign.campaign_id, {
      analysis_id: analysis.analysis_id,
      observation_date: document.getElementById('observation-date')?.value,
      counts,
      human_reviewed: humanReviewed
    });
    AppState.currentAnalysisSaved = true;
    showToast('Reviewed parking observation saved.', 'success');
    await refreshCarbonSync(true);
    updateParkingCampaignControls();
  } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
}

async function runStudentScenario() {
  const readNumber = id => Number(document.getElementById(id)?.value || 0);
  const button = document.getElementById('run-student-scenario-btn');
  if (!button) return;
  const requestVersion = ++AppState.scenarioRequestVersion;
  AppState.scenarioPending = true;
  AppState.scenarioError = null;
  AppState.latestScenario = null;
  button.disabled = true;
  const status = document.getElementById('scenario-live-status');
  if (status) status.textContent = 'Calculating with the latest scenario inputs…';
  const twinNode = document.getElementById('twin-visualization');
  if (twinNode) twinNode.innerHTML = renderScenarioTwin(null, AppState.commuteSummary || {}, AppState.selectedScenario, true, null);
  const comparisonNode = document.getElementById('scenario-comparison');
  if (comparisonNode) comparisonNode.innerHTML = '';
  const resultCards = document.querySelector('.scenario-results-grid');
  if (resultCards) resultCards.innerHTML = '<div class="empty-state compact" role="status"><p>Recalculating from the current inputs…</p></div>';
  const invalidInput = [...document.querySelectorAll('.scenario-input-grid input')].find(input => !input.checkValidity());
  if (invalidInput) {
    invalidInput.reportValidity();
    AppState.scenarioPending = false;
    AppState.scenarioError = 'Correct the highlighted scenario input before calculating.';
    if (status) status.textContent = AppState.scenarioError;
    document.getElementById('twin-visualization').innerHTML = renderScenarioTwin(null, AppState.commuteSummary || {}, AppState.selectedScenario, false, AppState.scenarioError);
    document.getElementById('scenario-comparison').innerHTML = '';
    button.disabled = false;
    return;
  }
  const shuttleShare = readNumber('scenario-shuttle-share');
  const shuttleService = [
    readNumber('scenario-shuttle-vehicles'),
    readNumber('scenario-shuttle-trips'),
    readNumber('scenario-shuttle-route')
  ];
  const configuredShuttleFields = shuttleService.filter(value => value > 0).length;
  const shuttleDays = readNumber('scenario-shuttle-operating-days');
  const shuttleValidationMessage = shuttleShare > 0 && (configuredShuttleFields !== shuttleService.length || shuttleDays <= 0)
    ? 'To calculate a shuttle shift, enter a positive vehicle count, one-way trips per vehicle, route distance, and operating days.'
    : configuredShuttleFields > 0 && (configuredShuttleFields !== shuttleService.length || shuttleDays <= 0)
      ? 'Complete all shuttle service settings or set the vehicle count, trips, and route distance to zero.'
      : null;
  if (shuttleValidationMessage) {
    AppState.scenarioPending = false;
    AppState.scenarioError = shuttleValidationMessage;
    if (status) status.textContent = shuttleValidationMessage;
    if (twinNode) twinNode.innerHTML = renderScenarioTwin(null, AppState.commuteSummary || {}, AppState.selectedScenario, false, shuttleValidationMessage);
    if (comparisonNode) comparisonNode.innerHTML = '';
    if (resultCards) resultCards.innerHTML = '<div class="empty-state compact"><p>Update the shuttle settings, then calculate again.</p></div>';
    button.disabled = false;
    return;
  }
  try {
    const result = await API.runStudentScenario({
      carpool_share: readNumber('scenario-carpool-share') / 100,
      carpool_occupancy: readNumber('scenario-carpool-occupancy'),
      public_transport_share: readNumber('scenario-transit-share') / 100,
      transit_occupancy: readNumber('scenario-transit-occupancy'),
      active_travel_share: readNumber('scenario-active-share') / 100,
        active_travel_limit_km: readNumber('scenario-active-limit'),
        shuttle_shift_share: readNumber('scenario-shuttle-share') / 100,
        shuttle_daily_vehicles: readNumber('scenario-shuttle-vehicles'),
        shuttle_trips_per_vehicle_per_day: readNumber('scenario-shuttle-trips'),
        shuttle_one_way_route_km: readNumber('scenario-shuttle-route'),
        shuttle_operating_days_per_year: readNumber('scenario-shuttle-operating-days')
    });
    if (requestVersion !== AppState.scenarioRequestVersion) return;
    AppState.latestScenario = { result };
    AppState.scenarioPending = false;
    AppState.scenarioError = null;
    renderInsightsPage();
    try { renderReportPage(await API.getFinalReport()); }
    catch (_) { showToast('Scenario calculated; the saved report could not be refreshed.', 'warning'); }
    showToast('Scenario comparison calculated and saved.', 'success');
  } catch (error) {
    if (requestVersion === AppState.scenarioRequestVersion) {
      AppState.latestScenario = null;
      AppState.scenarioPending = false;
      AppState.scenarioError = error.message || 'Scenario calculation could not be completed.';
      const liveStatus = document.getElementById('scenario-live-status');
      if (liveStatus) liveStatus.textContent = AppState.scenarioError;
      const twin = document.getElementById('twin-visualization');
      if (twin) twin.innerHTML = renderScenarioTwin(null, AppState.commuteSummary || {}, AppState.selectedScenario, false, AppState.scenarioError);
      const comparison = document.getElementById('scenario-comparison');
      if (comparison) comparison.innerHTML = '';
      showToast(AppState.scenarioError, 'error');
    }
  } finally {
    if (requestVersion === AppState.scenarioRequestVersion) {
      const currentButton = document.getElementById('run-student-scenario-btn');
      if (currentButton) currentButton.disabled = false;
    }
  }
}

async function generateRecommendationsForCampaign(silent = false) {
  try {
    const result = await API.generateEvidenceRecommendations();
    AppState.latestRecommendations = result;
    const panel = document.getElementById('evidence-recommendations');
    if (panel) panel.innerHTML = renderRecommendationHtml(result);
    if (!silent) showToast(result.fallback_flag ? 'Rule-based recommendations shown; LLM is unavailable.' : 'Privacy-preserving recommendations generated.', 'success');
    const report = await API.getFinalReport();
    AppState.report = report;
    renderReportPage(report);
    return result;
  } catch (error) {
    const panel = document.getElementById('evidence-recommendations');
    if (panel) panel.innerHTML = `<div class="alert alert-warning">${safeText(error.message)}</div>`;
    if (!silent) showToast(error.message, 'warning');
    return null;
  }
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

  if (mode_data.some(row => !Number.isFinite(row.avg_one_way_km) || row.avg_one_way_km <= 0)) {
    showToast('Enter an average one-way distance above zero for all four vehicle categories, or load the sample survey.', 'warning');
    if (btn) { btn.disabled = false; btn.innerHTML = 'Calculate Baseline Emissions →'; }
    return;
  }

  const payload = {
    annual_days: parseInt(document.getElementById('annual-days')?.value, 10) || 200,
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
    tbody.innerHTML = data.category_breakdown.map(row => {
      const daily = row.daily_vehicles ?? row.daily_vehicles_per_day ?? 0;
      const vkt = row.annual_vkt ?? row.annual_vkt_km_per_year ?? 0;
      const ef = row.emission_factor_kg_per_vkt ?? row.emission_factor_kg_co2_per_vehicle_km ?? 0.145;
      const tonnes = row.annual_tonnes_co2 ?? row.annual_emissions_tonnes_co2_per_year ?? 0;
      return `
      <tr>
        <td class="font-bold">${row.category}</td>
        <td class="font-mono">${daily}</td>
        <td class="font-mono">${Math.round(vkt).toLocaleString()}</td>
        <td class="font-mono">${ef}</td>
        <td class="font-mono font-bold text-accent">${tonnes.toFixed(2)}</td>
        <td><span class="badge badge-derived">[Derived calculation]</span></td>
      </tr>
      `;
    }).join('');
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
