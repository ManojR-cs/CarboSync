# CarboSync Project Status

**Current milestone:** Judges' demo backend implemented; owner review and local YOLO setup remain pending
**Updated:** 2026-10-16

This status distinguishes automated tests from capabilities that still require local model/provider configuration.

## Implementation status

| Component | Current evidence | Status |
|---|---|---|
| B1–B3 health, assessment, commute, provenance, and factor governance | backend/main.py, backend/database.py, backend/factor_registry.py | Implemented; existing approved registry remains intentionally empty |
| YOLO11n image service | backend/vehicle_detection.py | Implemented with COCO vehicle mapping, image validation, lazy cached CPU inference, configurable local path and threshold; actual model inference is blocked until runtime and weights are provided |
| Demo estimate and scenarios | backend/demo_calculations.py, backend/demo_schemas.py | Implemented deterministic illustrative estimates and three editable scenarios; all factors and activity assumptions are explicit request inputs |
| Demo routes and persistence | backend/main.py, backend/database.py | Implemented POST /api/demo/analyze and GET /api/demo/analyses/{analysis_id}; structured snapshots persist, source/annotated images do not |
| Recommendations | backend/recommendations.py | Implemented optional OpenAI-compatible adapter, schema checks, and deterministic fallback; no live provider call was made |
| Existing frontend/human-review workflow | repository inventory | Not implemented |
| Production emissions results | empty approved registry and demo factor policy | Not available; demo outputs are illustrative and unapproved |

The demo does not infer daily traffic, unique vehicles, distance, fuel, occupancy, trip purpose, or annual activity from an image. It does not extrapolate to a campus population. Values 0.145 and 0.150 have not been approved; 0.150 remains a test fixture.

## Test and runtime evidence

All commands below ran from the repository root using the existing project virtual environment with bytecode writing disabled. API suites use isolated temporary SQLite databases and mock YOLO/LLM calls. They do not prove real detector accuracy or live provider behavior.

| Exact command | Observed result |
|---|---|
| & '.\.venv\Scripts\python.exe' -B -m unittest tests.test_carbon_engine -v | 13 passed, exit code 0 |
| & '.\.venv\Scripts\python.exe' -B -m unittest tests.test_commute_api -v | 32 passed, exit code 0 |
| & '.\.venv\Scripts\python.exe' -B -m unittest tests.test_demo_api -v | 12 passed, exit code 0 |
| & '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -v | 57 passed, 0 failures/errors, exit code 0 |

Historical B3 baseline recorded before this demo work: 33 tests passed before B3; after B3, the focused API suite had 32 passes and the complete suite had 45 passes. The current 57-test result includes the 12 demo tests and supersedes those counts for the current tree.

Loopback Uvicorn smoke check: GET /health returned 200 and {"status":"healthy"}; GET /docs and GET /openapi.json returned 200. A valid multipart request reached POST /api/demo/analyze and returned the documented safe 503 because local YOLO weights/runtime are unavailable. Invalid JSON content type returned the safe 422 envelope. The full successful pipeline was exercised with mocked detection in the API tests.

A loopback Uvicorn smoke check returned HTTP 200 from /health, /docs, and /openapi.json. A multipart demo request against the live server returned safe HTTP 503 because no local YOLO weights/runtime are configured. A request with the wrong content type returned the safe 422 envelope. This is the expected missing-model behavior, not evidence of live inference.

## Setup still needed for image inference

Install requirements.txt in the project virtual environment. Provide an authorized YOLO11n weight file at backend/models/yolo11n.pt or configure CARBOSYNC_YOLO_MODEL_PATH. The repository contains no model weights and the application never downloads them automatically. CARBOSYNC_YOLO_CONFIDENCE controls the threshold. Without those resources, the API starts normally and returns safe 503 for analysis requests.

Optional live narrative requires CARBOSYNC_LLM_PROVIDER=openai_compatible, CARBOSYNC_LLM_API_KEY, and optional CARBOSYNC_LLM_BASE_URL/CARBOSYNC_LLM_MODEL. No key is stored in SQLite or returned. Without credentials, deterministic fallback recommendations are used.

## Remaining limits

- Actual YOLO inference, weight compatibility, detection accuracy, and annotated output from the real model remain unverified.
- No frontend, human correction, campus-specific validated activity survey, environmental integration, approved emission factor, or production emissions inventory is included.
- Fuel and powertrain applicability cannot be checked from current request fields.
- The optional LLM provider was tested with mocks only.
- Image detections remain snapshot counts; scenario outputs are illustrative simulations, not measured or guaranteed reductions.
