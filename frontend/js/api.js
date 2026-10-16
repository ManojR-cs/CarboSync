/**
 * TraceTwin — api.js
 * REST client wrapping fetch() with error handling.
 * Automatically routes to mocks when USE_MOCKS = true.
 */

const browserLocation = window.location || { hostname: '', port: '', origin: '' };
const localStaticPreview = ['localhost', '127.0.0.1'].includes(browserLocation.hostname)
  && browserLocation.port === '5500';
const configuredApiBase = window.CARBOSYNC_API_BASE
  || globalThis.document?.querySelector('meta[name="carbonsync-api-base"]')?.content?.trim()
  || (localStaticPreview ? 'http://127.0.0.1:8001' : browserLocation.origin);
const API_BASE = configuredApiBase.replace(/\/$/, '');

// ── API Wrapper ────────────────────────────────────────────────
const API = {

  // POST /api/assessments
  async createAssessment(payload) {
    if (window.USE_MOCKS) {
      const res = await mockApiCall({ ...MOCK_ASSESSMENT, ...payload });
      return res.data;
    }
    return await request('POST', '/api/assessments', {});
  },

  // POST /api/assessments/{id}/images  (multipart)
  async uploadImage(assessmentId, formData) {
    if (window.USE_MOCKS) {
      await mockApiCall({ status: 'simulated' }, 700);
      return {
        image_id: 'img_simulated',
        width: 0,
        height: 0,
        detections: [],
        counts: {},
        detection_mode: 'simulated',
        inference_status: 'simulated',
        model_metadata: null,
        snapshot_summary: {},
        simulated: true,
        warning: 'Mock mode does not analyze uploaded images. Connect the live backend to run vehicle detection.'
      };
    }
    const image = formData.get('file');
    if (!image) throw new APIError('Choose an image to analyze.', 0, null);
    const dimensions = await readImageDimensions(image);
    const demoForm = new FormData();
    demoForm.append('image', image, image.name);
    demoForm.append('assumptions_json', JSON.stringify(buildDemoAssumptions({
      detectionMode: 'real',
      emptyActivity: true
    })));
    if (window.AppState?.currentCampaign?.campaign_id) {
      demoForm.append('observation_campaign_id', window.AppState.currentCampaign.campaign_id);
    }
    const analysis = await uploadFile('/api/demo/analyze', demoForm);
    const details = analysis.detection_details || analysis.detections?.details || [];
    const categories = {
      car: 'Cars', motorcycle: 'Motorcycles and scooters', bus: 'Buses and campus shuttles',
      truck: 'Other fuel-burning vehicles', bicycle: 'Bicycles'
    };
    return {
      ...analysis,
      image_id: analysis.analysis_id,
      image_sha256: analysis.image_sha256,
      width: dimensions.width,
      height: dimensions.height,
      model: analysis.model?.name || analysis.detections?.model || 'Local YOLO',
      confidence_threshold: analysis.model?.confidence_threshold ?? null,
      model_metadata: analysis.model || null,
      inference_status: analysis.inference_status || analysis.detections?.inference_status || 'failed',
      detections: details.map((d, index) => {
        const box = d.bounding_box_normalized || {};
        return {
          detection_id: `det_${String(index + 1).padStart(2, '0')}`,
          category: categories[d.category] || d.category,
          confidence: d.confidence,
          box: {
            x_min: Math.round((box.x_min || 0) * dimensions.width),
            y_min: Math.round((box.y_min || 0) * dimensions.height),
            x_max: Math.round((box.x_max || 0) * dimensions.width),
            y_max: Math.round((box.y_max || 0) * dimensions.height)
          }
        };
      }),
      annotated_image_url: analysis.annotated_image_data_uri,
      counts: analysis.detections?.per_class || {},
      simulated: Boolean(analysis.detections?.simulated),
      warning: (analysis.result?.warnings || []).join(' ')
    };
  },

  async getCampaign() {
    return request('GET', '/api/demo/campaigns/current');
  },
  async startCampaign(startDate) {
    return request('POST', '/api/demo/campaigns', { start_date: startDate, duration_days: 10 });
  },
  async saveObservation(campaignId, payload) {
    return request('POST', `/api/demo/campaigns/${encodeURIComponent(campaignId)}/observations`, payload);
  },
  async getStudents() {
    return request('GET', '/api/demo/students');
  },
  async saveStudents(payload) {
    return request('PUT', '/api/demo/students', payload);
  },
  async getCommuteSummary() {
    return request('GET', '/api/demo/commute-summary');
  },
  async getFinalReport() {
    return request('GET', '/api/demo/final-report');
  },
  async runStudentScenario(payload) {
    return request('POST', '/api/demo/student-scenarios', payload);
  },
  async latestScenario() {
    return request('GET', '/api/demo/scenarios/latest');
  },
  async generateEvidenceRecommendations() {
    return request('POST', '/api/demo/recommendations/generate', {});
  },
  async latestRecommendations() {
    return request('GET', '/api/demo/recommendations/latest');
  },

  // POST /api/assessments/{id}/verify
  async verifyDetections(assessmentId, payload) {
    if (window.USE_MOCKS) {
      const res = await mockApiCall(MOCK_VERIFY_RESPONSE, 600);
      return res.data;
    }
    return {
      status: 'confirmed_in_browser',
      evidence_label: 'Human-reviewed observation (not saved by this backend branch)',
      verified_counts: payload.verified_counts
    };
  },

  // POST /api/assessments/{id}/commute-inputs
  async submitCommuteInputs(assessmentId, payload) {
    if (window.USE_MOCKS) {
      const res = await mockApiCall(MOCK_BASELINE);
      return res.data;
    }

    const factors = {
      'Cars': { id: 'EF_CAR_DEF', val: 0.145, title: 'TraceTwin illustrative candidate; unverified' },
      'Motorcycles and scooters': { id: 'EF_MOTO_DEF', val: 0.035, title: 'TraceTwin illustrative candidate; unverified' },
      'Buses and campus shuttles': { id: 'EF_BUS_DEF', val: 0.850, title: 'TraceTwin illustrative candidate; unverified' },
      'Other fuel-burning vehicles': { id: 'EF_OTHER_DEF', val: 0.078, title: 'TraceTwin illustrative candidate; unverified' }
    };

    let formattedPayload = payload;
    if (!payload.calculation_mode) {
      formattedPayload = {
        calculation_mode: 'candidate',
        annual_days: payload.annual_days || 200,
        annual_days_provenance: {
          origin: 'user_provided',
          method: 'Academic calendar schedule',
          source_description: 'University annual operating schedule'
        },
        sample_size: payload.sample_size || 18,
        population_total: payload.population_total || 4500,
        mode_data: (payload.mode_data || []).map(m => {
          const f = factors[m.category] || factors['Cars'];
          return {
            category: m.category,
            daily_vehicles: Math.max(0, parseFloat(m.daily_vehicles) || 0),
            daily_vehicles_provenance: {
              origin: 'user_provided',
              method: 'User-entered commute survey',
              source_description: 'User-entered aggregate activity count'
            },
            avg_one_way_km: parseFloat(m.avg_one_way_km),
            avg_one_way_km_provenance: {
              origin: 'user_provided',
              method: 'Campus commute survey average',
              source_description: 'Student and staff commute survey'
            },
            occupancy: Math.max(1.0, parseFloat(m.occupancy) || 1.0),
            candidate_factor: {
              factor_id: f.id,
              version: 'v1',
              value: f.val,
              unit: 'kg CO2/veh-km',
              provenance: {
                origin: 'user_supplied',
                factor_id: f.id,
                metric_scope: 'Tailpipe_CO2',
                geographic_scope: 'Campus regional',
                source_title: 'TraceTwin demo candidate factor; unverified',
                approximation_notes: 'Fleet average tailpipe CO2 factor'
              }
            }
          };
        })
      };
    }
    const result = await request('POST', `/api/assessments/${assessmentId}/commute-inputs`, formattedPayload);
    const breakdown = (result.category_breakdown || []).map(row => ({
      ...row,
      daily_vehicles: row.daily_vehicles_per_day,
      annual_vkt: row.annual_vkt_km_per_year,
      emission_factor_kg_per_vkt: row.emission_factor_kg_co2_per_vehicle_km,
      annual_tonnes_co2: row.annual_emissions_tonnes_co2_per_year
    }));
    return {
      ...result,
      total_annual_vkt: result.annual_vkt_total_km_per_year,
      total_annual_tonnes_co2: result.annual_emissions_tonnes_co2_per_year,
      category_breakdown: breakdown
    };
  },

  // POST /api/assessments/{id}/simulate
  async runSimulation(assessmentId, payload) {
    if (window.USE_MOCKS) {
      const res = await mockApiCall(MOCK_SCENARIO, 1200);
      return res.data;
    }
    if (!AppState.currentImageFile || !AppState.commuteInputs) {
      throw new APIError('Upload an image and calculate the commute baseline before running scenarios.', 0, null);
    }
    const form = new FormData();
    form.append('image', AppState.currentImageFile, AppState.currentImageFile.name);
    const assumptions = buildDemoAssumptions({
      detectionMode: 'simulated',
      counts: getCommuteCounts(),
      scenarioParams: payload
    });
    form.append('assumptions_json', JSON.stringify(assumptions));
    const analysis = await uploadFile('/api/demo/analyze', form);
    const scenarios = analysis.result?.scenarios || [];
    const byId = Object.fromEntries(scenarios.map(scenario => [scenario.id, scenario]));
    const baseline = analysis.result?.baseline?.annual_tonnes_co2 ?? 0;
    const active = byId.active_travel;
    const carpool = byId.carpool;
    const shuttle = byId.campus_shuttle;
    const shuttleResult = shuttle?.estimated_emissions || {};
    const added = shuttleResult.category_breakdown?.shuttle_service_added?.annual_tonnes_co2 ?? 0;
    const shuttleTotal = shuttleResult.annual_tonnes_co2 ?? baseline;
    const recommendationData = analysis.result?.recommendations || {};
    return {
      baseline_tonnes_co2: baseline,
      scenario_1_tonnes_co2: active?.estimated_emissions?.annual_tonnes_co2 ?? baseline,
      scenario_2_tonnes_co2: carpool?.estimated_emissions?.annual_tonnes_co2 ?? baseline,
      scenario_3_tonnes_co2: shuttleTotal,
      net_savings_tonnes_co2: baseline - Math.min(
        active?.estimated_emissions?.annual_tonnes_co2 ?? baseline,
        carpool?.estimated_emissions?.annual_tonnes_co2 ?? baseline,
        shuttleTotal
      ),
      avoided_private_tonnes_co2: baseline - shuttleTotal + added,
      added_shuttle_tonnes_co2: added,
      fallback_activated: recommendationData.fallback_flag,
      recommendations: recommendationData.recommendations || [],
      best_scenario: analysis.result?.best_scenario,
      demo_analysis_id: analysis.analysis_id
    };
  }
};

// ── Core Fetch Utilities ──────────────────────────────────────

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }
  };
  if (body) opts.body = JSON.stringify(body);

  try {
    const res = await fetch(`${API_BASE}${path}`, opts);
    const data = await res.json();

    if (!res.ok) {
      const msg = data?.message || data?.detail || `HTTP ${res.status}`;
      throw new APIError(msg, res.status, data);
    }
    return data;
  } catch (err) {
    if (err instanceof APIError) throw err;
    throw new APIError('Network error — is the backend running?', 0, null);
  }
}

const DEMO_FACTORS = {
  car: { id: 'DEMO_CAR', value: 0.145 },
  motorcycle: { id: 'DEMO_MOTORCYCLE', value: 0.035 },
  bus: { id: 'DEMO_BUS', value: 0.850 },
  truck: { id: 'DEMO_TRUCK', value: 0.078 }
};

function buildDemoAssumptions({ detectionMode = 'real', counts = null, scenarioParams = null, emptyActivity = false } = {}) {
  const categoryInputs = {
    car: 0, motorcycle: 1, bus: 2, truck: 3
  };
  const distances = {};
  for (const [category, row] of Object.entries(categoryInputs)) {
    const value = parseFloat(document.getElementById(`distance-${row}`)?.value);
    distances[category] = Number.isFinite(value) ? value : 0;
  }
  distances.bicycle = 0;
  const annualDays = parseInt(document.getElementById('annual-days')?.value, 10) || 200;
  const trips = emptyActivity ? 0 : 1;
  const annualDaysSource = 'User-entered annual operating days in the assessment form.';
  const assumptions = {
    annual_operating_days: annualDays,
    annual_days_source_description: annualDaysSource,
    vehicle_assumptions: Object.fromEntries(['bicycle', 'car', 'motorcycle', 'bus', 'truck'].map(category => [category, {
      trips_per_vehicle_per_operating_day: trips,
      avg_one_way_km: distances[category],
      source_description: emptyActivity
        ? 'Temporary zero activity placeholder while the image is reviewed; not a measured commute input.'
        : 'Illustrative activity assumption based on the current commute form.'
    }])),
    illustrative_factors: Object.fromEntries(Object.entries(DEMO_FACTORS).map(([category, factor]) => [category, {
      factor_id: factor.id,
      vehicle_category: category,
      value: factor.value,
      unit: 'kg CO2/veh-km',
      geographic_scope: 'Illustrative; geography not validated',
      source_description: 'TraceTwin frontend demo setting; not verified or approved.',
      source_reference: null,
      applicability_notes: 'Demonstration value only; fuel and powertrain are not checked.',
      limitations: 'Not an approved factor. Replace with a justified local factor before operational use.'
    }]))
  };
  const scenario = scenarioParams || {
    s1_remote_pct: 0.2, s2_carpool_pct: 0.3, s3_routes: 2, s3_trips_per_day: 4, s3_route_km: 12, s3_shifted: 50
  };
  const currentCounts = counts || { bicycle: 0, car: 0, motorcycle: 0, bus: 0, truck: 0 };
  const privateVehicles = Math.max(1, currentCounts.car + currentCounts.motorcycle);
  const shuttleShare = Math.min(1, Math.max(0, Number(scenario.s3_shifted || 0) / privateVehicles));
  assumptions.scenario_assumptions = {
    carpool_activity_reduction_share: Number(scenario.s2_carpool_pct || 0),
    shuttle_shift_share: shuttleShare,
    active_travel_shift_share: Number(scenario.s1_remote_pct || 0),
    active_travel_max_one_way_km: Math.max(0.1, parseFloat(document.getElementById('active-travel-limit')?.value) || 5),
    assumption_basis: 'Editable frontend demo settings; not measured or guaranteed policy effects.',
    shuttle_service: {
      daily_vehicles: Number(scenario.s3_routes || 0),
      trips_per_vehicle_per_operating_day: Number(scenario.s3_trips_per_day || 0),
      avg_one_way_km: Number(scenario.s3_route_km || 0),
      source_description: 'User-entered illustrative shuttle scenario settings.'
    }
  };
  if (detectionMode === 'simulated') {
    assumptions.detection_mode = 'simulated';
    assumptions.simulated_detection_counts = Object.fromEntries(['bicycle', 'car', 'motorcycle', 'bus', 'truck'].map(category => [category, Math.max(0, Math.round(Number(currentCounts[category] || 0)))]));
    assumptions.simulated_detection_source_description = 'User-entered commute survey activity counts; these are not image detections.';
  }
  return assumptions;
}

function getCommuteCounts() {
  const categoryRows = { car: 0, motorcycle: 1, bus: 2, truck: 3 };
  return Object.fromEntries(Object.entries(categoryRows).map(([category, row]) => [
    category, parseInt(document.getElementById(`vehicles-${row}`)?.value, 10) || 0
  ]).concat([['bicycle', 0]]));
}

async function readImageDimensions(file) {
  if (typeof createImageBitmap === 'function') {
    const bitmap = await createImageBitmap(file);
    const dimensions = { width: bitmap.width, height: bitmap.height };
    bitmap.close();
    return dimensions;
  }
  return await new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
    image.onerror = () => reject(new APIError('The selected image could not be read.', 0, null));
    image.src = URL.createObjectURL(file);
  });
}

async function uploadFile(path, formData) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      body: formData   // no Content-Type header; browser sets multipart boundary
    });
    const data = await res.json();
    if (!res.ok) throw new APIError(data?.message || data?.detail || `HTTP ${res.status}`, res.status, data);
    return data;
  } catch (err) {
    if (err instanceof APIError) throw err;
    throw new APIError('Upload failed — is the backend running?', 0, null);
  }
}

// ── Custom Error Class ────────────────────────────────────────
class APIError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.body = body;
  }
}

// ── Connectivity Check ────────────────────────────────────────
async function pingBackend() {
  try {
    // First readiness check may lazily load the local YOLO weights.
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(30000) });
    return res.ok;
  } catch {
    return false;
  }
}

async function checkBackendStatus() {
  if (window.USE_MOCKS) return 'mock';
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(30000) });
    if (!res.ok) return 'offline';
    const health = await res.json();
    return health.detector?.status === 'ready' ? 'online' : 'detector-unavailable';
  } catch {
    return 'offline';
  }
}
