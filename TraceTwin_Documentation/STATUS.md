# CarboSync Project Status

**Current milestone:** Portable backend setup and React API handoff implemented; real YOLO setup on a target laptop remains pending
**Updated:** 2026-10-16

This status distinguishes automated tests from capabilities that still require local model/provider configuration.

## Implementation status

| Component | Current evidence | Status |
|---|---|---|
| B1–B3 health, assessment, commute, provenance, and factor governance | backend/main.py, backend/database.py, backend/factor_registry.py | Implemented; existing approved registry remains intentionally empty |
| YOLO image service | backend/vehicle_detection.py | Implemented with lazy cached CPU inference, bounded image validation, actual model-name class mapping, per-box details, configurable local `.pt` path and confidence; live inference remains blocked until runtime and weights are provided |
| Demo estimate and scenarios | backend/demo_calculations.py, backend/demo_schemas.py | Implemented deterministic illustrative estimates and three editable scenarios; all factors and activity assumptions are explicit request inputs |
| Demo routes and persistence | backend/main.py, backend/database.py | Implemented POST /api/demo/analyze and GET /api/demo/analyses/{analysis_id}; structured snapshots persist, source/annotated images do not |
| Recommendations | backend/recommendations.py | Implemented optional OpenAI-compatible adapter, schema checks, and deterministic fallback; no live provider call was made |
| Portable Windows setup | `requirements.txt`, `requirements-yolo.txt`, `.env.example`, `setup_backend.ps1`, `run_backend.ps1` | Core API requirements are pinned; optional YOLO/PyTorch install is separate; scripts support a project venv or an existing Python environment |
| Explicit simulated detector | `backend/demo_schemas.py`, `backend/main.py` | Implemented separately from inference; requires complete user-supplied counts, labels response as simulated, ignores image for detection, and returns no annotated detection image |
| Existing frontend/human-review workflow | repository inventory | Not implemented |
| Production emissions results | empty approved registry and demo factor policy | Not available; demo outputs are illustrative and unapproved |

The demo does not infer daily traffic, unique vehicles, distance, fuel, occupancy, trip purpose, or annual activity from an image. It does not extrapolate to a campus population. Values 0.145 and 0.150 have not been approved; 0.150 remains a test fixture.

## Test and runtime evidence

All commands below ran from the repository root using the existing project virtual environment with bytecode writing disabled. API suites use isolated temporary SQLite databases and mock YOLO/LLM calls. They do not prove real detector accuracy or live provider behavior.

| Exact command | Observed result |
|---|---|
| & '.\.venv\Scripts\python.exe' -B -m unittest tests.test_carbon_engine -v | 13 passed, exit code 0 |
| & '.\.venv\Scripts\python.exe' -B -m unittest tests.test_commute_api -v | 32 passed, exit code 0 |
| & '.\.venv\Scripts\python.exe' -B -m unittest tests.test_demo_api -v | 15 passed, exit code 0 |
| & '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -v | 60 passed, 0 failures, 0 errors, exit code 0 |
| `setup_backend.ps1 -PythonExe '.\.venv\Scripts\python.exe' -SkipInstall` | Core imports verified; no packages installed |
| `run_backend.ps1 -PythonExe '.\.venv\Scripts\python.exe' -EnvFile <temporary test config> -Port 8766` | Server started; `.env` values loaded; configured CORS origin allowed and unlisted origin omitted |
| PowerShell AST parse of `setup_backend.ps1` and `run_backend.ps1` | Both scripts parsed successfully |

Historical counts: 33 tests passed before B3; after B3, the focused API suite had 32 passes and the full suite had 45 passes. An earlier demo-backend verification had 57 passes. All are superseded by the current 60-test result above.

Earlier loopback checks also verified `/health`, `/docs`, `/openapi.json`, and the expected missing-model 503. The current smoke evidence follows and supersedes the earlier route/CORS checks.

A fresh loopback Uvicorn smoke check returned HTTP 200 from `/health`, `/docs`, and `/openapi.json`. With `CARBOSYNC_CORS_ORIGINS=http://localhost:5173`, the response included the matching `Access-Control-Allow-Origin`, unlisted origins received no allow-origin header, and multipart preflight returned 200. A multipart simulated analysis returned 201, explicitly reported simulated counts, and was retrievable with HTTP 200. The saved result used the no-key deterministic recommendation fallback. A real-mode request returned safe actionable HTTP 503 because this environment has no Ultralytics package or model weights. No real inference was performed.

## Setup still needed for image inference

Run `setup_backend.ps1` for the pinned core API dependencies. For a new inference environment use `setup_backend.ps1 -WithYolo`, or select a compatible existing environment and confirm it has Ultralytics/PyTorch plus the core API dependencies. Provide authorized Ultralytics `.pt` weights at `backend/models/yolo11n.pt` or configure `CARBOSYNC_YOLO_MODEL_PATH`. No model weights are committed or downloaded automatically. `CARBOSYNC_YOLO_CONFIDENCE` controls the threshold. Until runtime and weights are installed, simulated mode works while real mode returns an actionable 503.

Optional live narrative requires CARBOSYNC_LLM_PROVIDER=openai_compatible, CARBOSYNC_LLM_API_KEY, and optional CARBOSYNC_LLM_BASE_URL/CARBOSYNC_LLM_MODEL. No key is stored in SQLite or returned. Without credentials, deterministic fallback recommendations are used.

## Remaining limits

- Actual YOLO inference, weight compatibility, detection accuracy, and annotated output from the real model remain unverified.
- The React frontend's actual local origin is unknown; `.env.example` shows common Vite port 5173 values that must be replaced if the frontend uses another origin.
- No frontend, human correction, campus-specific validated activity survey, environmental integration, approved emission factor, or production emissions inventory is included.
- Fuel and powertrain applicability cannot be checked from current request fields.
- The optional LLM provider was tested with mocks only.
- Image detections remain snapshot counts; scenario outputs are illustrative simulations, not measured or guaranteed reductions.
