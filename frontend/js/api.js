/**
 * TraceTwin — api.js
 * REST client wrapping fetch() with error handling.
 * Automatically routes to mocks when USE_MOCKS = true.
 */

const API_BASE = 'http://127.0.0.1:8000';

// ── API Wrapper ────────────────────────────────────────────────
const API = {

  // POST /api/assessments
  async createAssessment(payload) {
    if (window.USE_MOCKS) {
      const res = await mockApiCall({ ...MOCK_ASSESSMENT, ...payload });
      return res.data;
    }
    return await request('POST', '/api/assessments', payload);
  },

  // POST /api/assessments/{id}/images  (multipart)
  async uploadImage(assessmentId, formData) {
    if (window.USE_MOCKS) {
      const res = await mockApiCall(MOCK_CV_DETECTIONS, 1400);
      return res.data;
    }
    return await uploadFile(`/api/assessments/${assessmentId}/images`, formData);
  },

  // POST /api/assessments/{id}/verify
  async verifyDetections(assessmentId, payload) {
    if (window.USE_MOCKS) {
      const res = await mockApiCall(MOCK_VERIFY_RESPONSE, 600);
      return res.data;
    }
    return await request('POST', `/api/assessments/${assessmentId}/verify`, payload);
  },

  // POST /api/assessments/{id}/commute-inputs
  async submitCommuteInputs(assessmentId, payload) {
    if (window.USE_MOCKS) {
      const res = await mockApiCall(MOCK_BASELINE);
      return res.data;
    }
    return await request('POST', `/api/assessments/${assessmentId}/commute-inputs`, payload);
  },

  // POST /api/assessments/{id}/simulate
  async runSimulation(assessmentId, payload) {
    if (window.USE_MOCKS) {
      const res = await mockApiCall(MOCK_SCENARIO, 1200);
      return res.data;
    }
    return await request('POST', `/api/assessments/${assessmentId}/simulate`, payload);
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
      const msg = data?.detail || data?.message || `HTTP ${res.status}`;
      throw new APIError(msg, res.status, data);
    }
    return data;
  } catch (err) {
    if (err instanceof APIError) throw err;
    throw new APIError('Network error — is the backend running?', 0, null);
  }
}

async function uploadFile(path, formData) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      body: formData   // no Content-Type header; browser sets multipart boundary
    });
    const data = await res.json();
    if (!res.ok) throw new APIError(data?.detail || `HTTP ${res.status}`, res.status, data);
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
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}

async function checkBackendStatus() {
  if (window.USE_MOCKS) return 'mock';
  const isOnline = await pingBackend();
  return isOnline ? 'online' : 'offline';
}
