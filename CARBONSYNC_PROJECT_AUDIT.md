# CarbonSync Project Audit

**Audit date:** 2026-10-16  
**Repository:** `ManojR-cs/CarboSync` (local folder `Trace_Twin`)  
**Scope:** Read-only technical audit. The only new file created for this task is this report.  
**Evidence boundary:** Local checked-out `main` is at `480bdb8`; `origin/Backend` is at `f06c7cd`. The fetched `Backend` source is materialized at `github-backend-snapshot/` for inspection. That directory is a source snapshot, not a separate Git checkout. The root working tree was already dirty before this report: modified backend/frontend files and untracked images, test scripts, and the snapshot are present. Those files were preserved and were not treated as changes made by this audit.

## 1. Executive summary

The repository contains a working FastAPI backend for two distinct workflows: (1) a provenance-aware commute emissions calculator, and (2) an illustrative image-to-demo-analysis workflow that can perform local YOLO inference, deterministic calculations, scenario arithmetic, optional LLM narratives, and SQLite persistence. The six-tab browser frontend exists on the local `main` tree, but the fetched `Backend` branch intentionally contains no frontend; its documentation says the client is external and human review is not implemented by that branch.

The primary reason the shown vehicle labels/boxes can look wrong is not a single isolated label-format defect. The backend uses general-purpose COCO YOLO11 weights and has no demonstrated accuracy evaluation on the project's overhead parking domain. Inference uses CPU, confidence filtering and Ultralytics postprocessing, but no parking-specific training, tiling, tracking, or validation set. The screenshot's displayed confidence values (92%, 87%, 83%, 95%, 79%, 74%, 81%) and categories match values in the frontend's static `MOCK_CV_DETECTIONS` fixture; the fixture also contains an additional 88% motorcycle entry that is not clearly visible in the screenshot. Therefore, the screenshot is strong evidence of mock rendering, not evidence that the model made those predictions. Current local frontend code warns and returns no boxes in mock mode; the screenshot likely came from an earlier UI state/version.

The biggest integration risk is that root `backend/main.py` and `backend/vehicle_detection.py` are locally modified beyond the fetched branch. The root adds `/images`, `/verify`, and `/simulate` endpoints; those routes are absent from `origin/Backend`. The current frontend adapter correctly sends image analysis and scenario analysis to the branch's `/api/demo/analyze`, but other labels and UI flows still suggest assessment-linked uploads and persistent human review even though the branch does not provide those behaviors. Verification is browser-only and its corrections are not automatically fed into the baseline form.

Emission outputs are appropriately marked illustrative/unapproved in the backend, but they must not be presented as campus annual inventory: the image gives a single point-in-time visible-object count. Annual travel activity, trip cycle count, distance, operating days and factors are separately supplied assumptions. No factor is approved in the production registry. The demo scenario code does calculate net shuttle emissions, including added service emissions, and can show increases, but scenario inputs are illustrative and one frontend control labelled as carpool occupancy is ignored by the engine.

**Overall status:** useful local demo foundation; not yet a validated campus transport measurement or decision-support product. Highest priorities are align frontend with the actual branch contract, establish a parking-image evaluation dataset and model selection gate, keep detections/review/provenance linked through calculations, govern emission factors and activity data, and close frontend security/accessibility/integration gaps.

## 2. Actual architecture and technology stack

| Layer | Implemented technology and execution path | Status |
|---|---|---|
| Browser UI | Static HTML/CSS and plain JavaScript; six tab panels, custom canvas editor, Chart.js loaded from jsDelivr. No frontend router or build manifest was found. | Present on local `main`; absent from fetched `Backend` snapshot. |
| API | FastAPI + Pydantic v2, served by Uvicorn; request schemas, validation, error envelopes, CORS allowlist. | Implemented in `github-backend-snapshot/backend/main.py`. |
| Computer vision | Optional Ultralytics YOLO `.pt` model; Pillow validates/normalizes images; model is lazily loaded and cached, inference runs on CPU. | Real inference path implemented, but runtime and weights are external local requirements. |
| Calculation | Pure Python deterministic functions for annual vehicle-kilometres, tailpipe CO2 and three demo scenarios. | Implemented; factor approval and real activity evidence remain absent. |
| LLM | Optional OpenAI-compatible Chat Completions HTTP call using Python `urllib`; a rule-based fallback runs when unavailable or rejected. | Implemented behind environment variables; not required for numeric results. |
| Persistence | Standard-library SQLite with assessments, commute calculation snapshots, and demo analysis snapshots. | Implemented. Raw and annotated image bytes are not stored in branch implementation. |
| Tests | `unittest` suites for carbon math, commute API, demo API/math/image validation/LLM guards. | 60 tests pass in both the snapshot and local `tests` tree; separate root detection CLI report checks also pass. |

The root local working tree has extra uncommitted backend endpoints and modified model settings. Those differences are not on the fetched branch commit and should not be confused with its API contract. Git status at audit time included modified `backend/main.py`, `backend/vehicle_detection.py`, `frontend/index.html`, `frontend/js/api.js`, `frontend/js/app.js`, `frontend/js/canvas_editor.js`, `frontend/js/charts.js`, `frontend/js/scenarios.js`, plus untracked `detection_results/`, `test_images/`, `test_vehicle_detection.py`, `vehicle_detection.py`, and `github-backend-snapshot/`.

## 3. Current feature status

| Feature | Status | Evidence / limitation |
|---|---|---|
| Assessment creation and retrieval | Working | `POST /api/assessments`, `GET /api/assessments/{id}` persist and retrieve IDs/calculations. Assessment metadata beyond ID/time is not accepted in the branch schema. |
| Real parking image inference | Partially working | Implemented in `/api/demo/analyze` if optional runtime and local `.pt` weights are available. Not run as a model-quality evaluation during this audit. |
| Car vs motorcycle distinction | Implemented | Actual model name table is mapped by recognized class names; standard COCO names map to separate `car` and `motorcycle`. Performance on top-down images is unverified. |
| Detection counts/boxes/confidences | Working at API-contract level | Counts and normalized coordinates are built from model output after Ultralytics prediction postprocessing. No application-level second duplicate filter or tracking. |
| Detection review UI | Partially working locally | Canvas permits reclassifying/deleting/drawing boxes. Verification returns a browser confirmation only; branch has no persistence endpoint. Edited counts do not automatically prefill the commute category counts. |
| Commute emissions | Working as an explicitly supplied calculation | B3 requires activity/factor provenance and returns VKT and CO2; candidate factors are unapproved. Occupancy is stored but does not change output. |
| Demo annual estimate from photo | Illustrative only | A single snapshot count is multiplied by explicit assumed trips, distances and operating days. This is not measured annual activity. |
| LLM recommendations | Partially working/optional | Triggered after `/api/demo/analyze` calculations; missing credentials select deterministic fallback. Frontend renders recommendations only after its scenario call, not directly from the real upload result. |
| Digital twin scenarios | Illustrative deterministic arithmetic | Carpool, shuttle, and active-travel activity adjustments are calculated. No demand, capacity, mode-choice, occupancy, rebound, or route assignment model. |
| Scenario history | Missing | Demo results can be retrieved by `analysis_id`, but are not associated with an assessment or exposed as a scenario-run history. |
| Professional CarbonSync branding | Missing | Page title, visible brand and descriptive content still say TraceTwin. |
| Automated frontend/backend integration coverage | Missing | No browser or frontend integration suite is present. Backend tests use mocked inference/provider behavior. |

## 4. Vehicle detection and counting assessment

### Actual model and inference path

The fetched backend's `backend/vehicle_detection.py`:

- Accepts JPEG, PNG or WebP, validates MIME/content match, limits input to 10 MiB and 40 megapixels, and converts through Pillow to RGB (`validate_image_bytes`).
- Reads `CARBOSYNC_YOLO_MODEL_PATH`; default path is `backend/models/yolo11n.pt`. It does not download weights. If the file or Ultralytics dependency is absent, real mode returns a safe 503 instead of fabricated boxes (`_configured_model_path`, `_load_model`).
- Lazily initializes and reuses the configured model. It calls `model.predict(source=image, conf=threshold, verbose=False, device="cpu")`; default confidence is `0.35` from `CARBOSYNC_YOLO_CONFIDENCE`. It does not set `iou`, `agnostic_nms`, `imgsz`, or `max_det` in the fetched branch; Ultralytics prediction defaults therefore apply. The returned `result.boxes` is already postprocessed by the Ultralytics prediction path. There is no extra application-level NMS/deduplication.
- Maps names `bicycle`, `car`, `motorcycle`/`motorbike`, `bus`, and `truck` to separate categories. Standard COCO IDs are documented as bicycle 1, car 2, motorcycle 3, bus 5, truck 7; actual inference maps by the model's names, so custom class ID order can differ. No unrecognized category is counted.
- Counts each returned mapped box once, filters non-finite confidence/coordinates, clamps normalized box values to `[0,1]`, draws a backend annotation and returns a JPEG data URI. It has no object tracking, temporal deduplication, image tiling, or human correction persistence.

The model weights are not tracked in `origin/Backend`; setup requires that a compatible `.pt` file be provided locally. The working folder currently contains ignored `yolo11n.pt`, `yolo11s.pt`, `yolo11m.pt`, and `yolo11x.pt` files, but only `yolo11n.pt` is the fetched branch default. The root working tree's locally modified detector chooses the largest available local weight, changes confidence to `0.15`, and adds `iou=0.30`, `agnostic_nms=True`, and `imgsz=1280`. Those experimental edits are not in `origin/Backend` and were not subjected to a controlled accuracy comparison. Their comment says class-agnostic NMS prevents cross-class suppression; Ultralytics documentation defines it as suppressing overlapping boxes across classes, so that comment/setting requires correction or validation before use ([Ultralytics predict documentation](https://docs.ultralytics.com/modes/predict)). Lowering confidence can increase recall but also false positives; a larger input size trades CPU time for detail. Neither change establishes accuracy.

### Why labels can be wrong

1. COCO weights are general-purpose, not trained or validated for this project's overhead/near-overhead parking imagery. Vehicle appearance, scale, occlusion, paint/roof appearance and perspective differ from common street-view examples. Small/partially occluded motorcycles are particularly liable to be missed or confused.
2. The screenshot's confidence set and mock box count match `frontend/js/mocks.js`'s `MOCK_CV_DETECTIONS` fixture exactly. It shows static mock labels placed on an image, not a real inference result. A prior frontend version evidently displayed that fixture; the currently checked-out `frontend/js/api.js` mock path returns an empty list plus an explicit warning.
3. The shown labels visually overlap each other because boxes/labels are rendered onto a small viewport. Crowded label placement is a presentation problem separate from model class prediction. The branch returns boxes and an annotation but does not optimize browser label placement.
4. The configured branch threshold is fixed by environment (default 0.35) and is not calibrated on a held-out campus set. No prediction confidence is a probability of correctness without calibration.
5. No suitable labeled evaluation dataset, per-class precision/recall, mAP, count error, confusion matrix, or human-reviewed benchmark was found. Accuracy is **unverified**; no numerical accuracy claim is supportable.

### Duplicate boxes and correction

Ultralytics applies its configured/default prediction postprocessing (including NMS for conventional models); branch code then counts returned boxes directly. There is no separate duplicate suppression, and no temporal tracker because input is one image. Tight parking can produce overlapping boxes; NMS can suppress adjacent objects or leave duplicates depending on threshold and model output. This must be measured against labeled images rather than tuned by visual intuition. The local detector's class-agnostic NMS option can suppress overlaps across different classes, contrary to its nearby comment.

On local `main`, users can edit/delete/add boxes through the canvas and the browser computes reviewed counts. However, `API.verifyDetections` returns `{status:"confirmed_in_browser"...}` without calling the backend; it does not persist the edited boxes/counts. `confirmVerification` stores `AppState.cvCounts` but the commute form flow does not consume that state to populate its activity counts. So review currently doesn't establish a persisted observation or reliably drive the baseline.

## 5. Emissions methodology and factor audit

### Current formulas and units

For the B3 commute endpoint, `backend/carbon_engine.py` computes, for category `k`:

```text
annual VKT_k [vehicle-km/year]
  = daily vehicles_k [vehicles/day]
    × one-way distance_k [km/one-way trip]
    × 2 [one-way legs/commute cycle]
    × operating days [days/year]

annual tailpipe CO2_k [kg CO2/year]
  = annual VKT_k × EF_k [kg CO2/vehicle-km]
annual tonnes CO2_k = annual kg CO2_k / 1,000
```

The B3 request requires one-way distance, annual days, occupancy, candidate factor or approved registry reference, and provenance. Occupancy is included in snapshots but intentionally not applied in this vehicle-based formula. There is no fuel/powertrain input in activity data, so the API records that applicability was not checked. The calculation is explicitly `is_campus_projection: false`.

The demo analysis uses a different explicit formula: `detected snapshot count × assumed commute cycles per vehicle per operating day × assumed one-way km × 2 × annual operating days`, then factor multiplication. The endpoint requires caller-supplied assumptions and candidate factors. Demo factor values and activity descriptions are not checked for source authenticity or scientific validity. The frontend B3 and demo paths both use values such as car `0.145`, motorcycle `0.035`, bus `0.850`, truck `0.078 kg CO2/vehicle-km`; these are unapproved candidates, not validated universal factors. The root frontend may label them “illustrative candidate; unverified,” but it still supplies them automatically.

### Sufficiency and recommended methodology

A parking image alone is not sufficient evidence for annual emissions. It may support a single-image count of visible objects at a stated location/time, subject to detection error. It does not establish vehicle arrivals per day, unique vehicles/commuters, trip purpose, roundtrips, annual operating days, route distance, occupancy, fuel, powertrain, or year-round activity. Counts must not be silently labeled as daily vehicles or annual totals.

Use a transparent category/activity/factor record with provenance and preserve three distinct quantities:

1. **Observed count:** visible detections by category, timestamp/site, image ID/hash, model/version, threshold, reviewer edits and review status.
2. **Activity estimate:** measured or explicitly assumed vehicle commute cycles/day and one-way distance, with observation/survey period and source. If expanding sample counts to population, disclose sample frame, sample size, weighting and uncertainty.
3. **Emissions estimate:** vehicle-km × a category/fuel-specific factor with units/scope/source/version. State that current boundary is tailpipe CO2; do not mix CO2e or electricity generation without a separate declared boundary.

Formula above is internally consistent for a roundtrip cycle. Avoid multiplying vehicle counts by occupancy in vehicle-based emissions; if reporting passenger-km, calculate that as vehicle-km × occupants and keep it as a different metric. For shuttles, calculate actual added service vehicle-km × bus factor, subtract only the private-vehicle activity credibly displaced, and report net change including negative savings. For all factors, record authoritative source and applicable geography/year/fuel class, verify units and category applicability, and obtain documented project-owner review before marking approved. Scientific validity is not inferred from example values or citations in planning docs.

### Factor governance

`backend/factor_registry.py` is intentionally empty. Approved-mode requests therefore return HTTP 503; this is safe behavior, but means production-approved calculation is unavailable. Candidate mode requires provenance, but caller-supplied source text is not independently authenticated. The frontend hardcodes illustrative candidate factors and provenance strings. There is no factor management screen or reviewed factor migration/table.

## 6. LLM recommendation pipeline audit

### Execution flow

`POST /api/demo/analyze` validates the image and assumptions; in real mode it runs YOLO and obtains counts, then `calculate_demo_analysis`, then calls `generate_recommendations` in a worker thread before saving/returning the result. The prompt context includes calculated baseline, three scenario emissions and deltas, scenario assumptions, limitations, and computed best scenario. The image itself is not sent. The provider is optional OpenAI-compatible Chat Completions using environment settings `CARBOSYNC_LLM_PROVIDER`, `CARBOSYNC_LLM_API_KEY`, `CARBOSYNC_LLM_BASE_URL`, and `CARBOSYNC_LLM_MODEL` (default model `gpt-4o-mini`). Timeout is 4 seconds.

Expected JSON includes summary, 1–5 recommendations with priority/title/why/tradeoffs/related scenario, and best scenario. Pydantic rejects invalid shape; code rejects a changed best-scenario ID and narrative containing digits, URLs, citations/research claims or guarantee language. Missing key/provider, unsupported config/provider failure, timeout and invalid answer fall back to a deterministic two-card plan. Calculations remain deterministic.

### Gaps and risks

- LLM is called automatically for both real and simulated demo analysis. But the frontend upload displays detections and ignores that call's recommendation output; later scenario interaction sends a second, simulated-count analysis and renders its recommendations. So the UI's displayed narrative is from the later scenario request, not necessarily the exact analysis record associated with image results.
- The fallback cards are generic process advice plus the computed best scenario, not tailored detailed operations guidance. They are honestly labeled rule-based in the response, though UI copy says “pre-approved recommendation IDs” and deterministic savings injection that do not match the backend response schema. No recommendation IDs or savings values are returned by `recommendations.py`.
- The LLM's free-text fields are rendered through `innerHTML` in `frontend/js/scenarios.js`. Because an external model response is untrusted and schema validation checks string shape/content claims but not HTML, escape text or build DOM nodes before rendering to prevent script/markup injection.
- LLM service credentials stay in backend environment variables and are not sent to the frontend. The frontend contains only an API base URL. Never set the API key in browser configuration.
- Provider `base_url` accepts HTTPS or localhost/127.0.0.1 HTTP; no domain allowlist or egress policy is present. This is environment-controlled, not user input, but deployment must protect config access.
- The documented 4-second timeout is per recommendation call; no request-wide deadline or rate limiter is evident. Concurrent uploads may each wait on the provider.

## 7. Digital twin and scenario simulation audit

`backend/demo_calculations.py` starts from five class counts (bicycle excluded from motor tailpipe totals) and per-class activity assumptions. It computes a baseline, then:

- **Carpool:** reduces car activity by `carpool_activity_reduction_share`. It does not model passenger occupancy, newly shared trips, pickup detours or vehicle fill; it is a reduced-activity sensitivity assumption.
- **Campus shuttle:** reduces car and motorcycle activity by one common shift share, calculates the remaining private emissions, adds shuttle vehicle count × assumed trips × route distance × 2 × days × bus factor. This correctly allows net emissions to increase and reports shuttle added activity/emissions separately. It is not a ridership/capacity/route-demand model.
- **Active travel:** applies a reduction only to car/motorcycle categories whose assumed one-way distance is at or below the submitted max distance. The endpoint accepts up to 300 km; frontend defaults to 5 km. It does not prove mode shift uptake.

Each scenario records assumptions, estimated emissions, change and reduction versus baseline, percent reduction (nullable for zero baseline), comparison label, and limitations. `best_scenario` chooses the lowest of the three interventions, not necessarily a scenario lower than baseline; the caller should inspect deltas. The math is deterministic and the input snapshot is stored with the analysis ID.

Important UI mismatch: carpool occupancy (2.5 default) exists in the interface/state but is not sent in `buildDemoAssumptions` and is unused by the API formula. “Remote days” UI slider maps to the backend's active-travel share, but the API calls it active travel; remote work and active travel are not equivalent activity mechanisms. The shuttle slider says commuters diverted, but adapter turns that into a *share of detected/user-entered cars plus motorcycles* (capped at 100%); this uses a point count as a daily activity population. Frontend results use user-entered commute counts in explicitly simulated mode, while the uploaded photo only supplies the earlier visual review. These are two different evidence paths and should be labeled distinctly.

The 5 km limit is a frontend editable default (`frontend/index.html`) and backend scenario assumption, not an empirical/validated universal cutoff. Enforce sensible domain bounds and show eligible categories/trips. There is no baseline “do nothing” option in the best-scenario list; if every intervention is worse, best still means lowest among interventions. Consider explicitly including baseline in ranking and display net change/sign clearly.

### Additional local-only scenario route

Uncommitted root `backend/main.py` adds `/api/assessments/{id}/simulate`. This endpoint is absent from fetched `Backend`. It falls back to a hard-coded 45 t baseline, uses fixed 80% reduction logic for remote days, 40% carpool savings, and a fixed 11.9 t shuttle emissions addition, then calls the recommendation pipeline with a reduced fake calculation. It ignores detailed source activity, route VKT and supplied shuttle factor. It should not be treated as a trustworthy demo simulation or deployed accidentally. Root `backend/main.py` also adds `/images` and `/verify`; their behavior differs from the branch contract, including verification returning a success-shaped response without validating assessment existence or persisting the observation.

## 8. Frontend and CarbonSync UI audit

### Current information architecture

The local frontend is a single HTML document with six tab panels: overview, parking CV audit, commute data, baseline emissions, digital twin scenarios, AI policy cards. Navigation is custom JS tab switching. CSS is split across `main.css`, `components.css`, and `canvas.css`; charts use a remote Chart.js CDN dependency. The visual interface has substantial demo content and an editing canvas, but all prominent brand/title copy still says TraceTwin. A real CarbonSync release needs consistent title, logo/name, page metadata, recommendation copy and labels.

### Main interaction issues

- Assessment creation accepts no metadata on branch and returned assessment ID is not passed to `/api/demo/analyze`; upload analysis is independent. The UI currently describes an assessment process, while backend demo analysis is a separate record.
- Image review can edit boxes but confirmation only stores browser state; there is no review persistence. The counts do not prefill the subsequent commute inputs (`AppState.cvCounts` is assigned but never read elsewhere).
- The image upload's live adapter posts placeholder zero activity to `/api/demo/analyze` so that it can receive detections. This produces a persisted demo analysis and runs recommendations even though those numerical results are zero/placeholder; the frontend discards that recommendation and uses another analysis when scenarios run.
- Commute entry sends activity fields and factor candidates to the B3 endpoint; it maps branch field names and renders KPI/table results. The frontend's default category values and sample survey must be clearly labeled as demo data, not actual observations.
- Scenario UI labels “remote days” as active travel and includes occupancy/detour text that is not represented in backend math. The 5 km eligibility setting is editable but the engine only uses distance threshold and shift share.
- Chart/KPI UI needs clear evidence labels, units, candidate-factor warnings, model identity/threshold, scenario parameter snapshots, zero-baseline and negative-savings states. Some copy currently implies projected campus values and preapproved recommendations more strongly than backend data supports. The “Campus Projection Total” toggle only changes the label and banner; it does not calculate or display a projection. The scenario chart is initially seeded with `MOCK_SCENARIO` before the live calculation completes, so the initial chart can show static sample values in live mode.
- Mock status is inferred from `/health` only; `/health` indicates API process is up, not that YOLO weights exist. This is acceptable only if real analysis separately shows the backend's actionable 503. A manual toggle can set live mode while offline.

### Design system/page structure proposal (audit only)

Use a restrained CarbonSync identity with one type scale, spacing grid, semantic colors, consistent card/table/button components, and color-independent status chips. Keep six workflow stages but make the path explicit: **Assessment → Image & review → Commute activity → Baseline → Scenarios → Recommendations**. At each step show data source, unit, confidence/evidence status and editable assumptions. Separate “observed detections” from “survey activity counts.” Build a clear image review panel with detected/reviewed counts, model/threshold, zoomable image, keyboard-selectable detections, add/reclassify/delete controls and persistent confirmation state. Build baseline KPI cards with VKT and tailpipe CO2; show factors and sources in an expandable audit table. Compare baseline, scenario emissions, delta and added shuttle emissions in the same units. Recommendations should link to the exact scenario/assessment and show whether LLM or fallback produced them. Implement responsive table/canvas behavior and accessible focus/labels/live announcements.

### Accessibility/responsiveness and interaction evidence

The main document sets `lang`, viewport and tab roles, but accessible relationships are partial; inspect `aria-labelledby` references because tab button IDs must match, labels for some number fields are omitted, image canvas controls need keyboard equivalents, and color/status is heavily visual. The canvas interaction needs keyboard/screen-reader alternatives. CSS includes responsive rules, but no automated viewport or keyboard tests were found. CDN dependency means charts may fail offline. Loading spinners and toasts exist; systematic empty/error/retry behavior and persistence restoration are incomplete.

## 9. API inventory and data flow

The actual fetched branch routes are:

| Method/path | Request | Response / behavior |
|---|---|---|
| `GET /health` | None | `{"status":"healthy"}`; only process health. |
| `POST /api/assessments` | JSON `{}` (extra keys forbidden) | `201`, generated `assessment_id`, `created_at`; saves minimal assessment. |
| `GET /api/assessments/{assessment_id}` | Path ID | Assessment and ordered saved commute calculation snapshots; `404` if missing. |
| `POST /api/assessments/{assessment_id}/commute-inputs` | Strict JSON B3 schema: calculation mode, annual days/provenance, sample size/population, exactly four categories with counts, one-way distances, occupancy, activity provenance, and candidate factor provenance or exact approved factor reference | Deterministic category breakdown, annual VKT, kg/t CO2, method version, evidence/governance flags; saved under assessment. Approved mode currently unavailable because registry is empty. |
| `POST /api/demo/analyze` | Multipart `image` (JPEG/PNG/WebP ≤10 MiB/40 MP) + JSON-string `assumptions_json`; real detection is default. Simulated mode requires all five explicit counts and source description. Assumptions require operating days, activity for all five classes, factors for four motor classes, and scenario parameters/shuttle service. | `201`, analysis ID/time, detection mode/counts/details/normalized boxes/model metadata/annotation data URI, baseline/scenario/recommendations/limitations; stored in SQLite. No uploaded image stored. |
| `GET /api/demo/analyses/{analysis_id}` | Path ID | Persisted detections, assumptions and result; no image bytes. |

Error responses generally use `{"error":true,"message":"..."}` for validation/HTTP errors; safe public messages suppress details. Upload body has an early size middleware. CORS defaults to ports 5500 for localhost and 127.0.0.1; `.env.example` instead lists Vite 5173 and explicitly asks the developer to set the actual UI origin. The current local browser origin is 5500, which matches backend default.

Current frontend adapter integration:

1. `GET /health` switches mock/live flag.
2. `POST /api/assessments` creates an ID.
3. Image upload adapter extracts the selected file and posts `/api/demo/analyze` with required assumptions; transforms normalized boxes into original-image pixel coordinates for canvas.
4. Verification uses a local return object only; no backend request.
5. Baseline posts `/api/assessments/{id}/commute-inputs` with candidate factors.
6. Scenario run posts the same image to `/api/demo/analyze` with `detection_mode:"simulated"` and commute form counts, then maps scenario response into the UI shape.

Thus there is no single linked persisted chain from image detection → user-corrected counts → commute baseline → scenarios. These currently become separately stored demo and assessment records.

## 10. Security, reliability, persistence concerns

- **LLM-rendered HTML:** untrusted provider prose reaches template strings assigned to `innerHTML`; escape it or use text nodes.
- **Local-only API:** run scripts default to loopback, which is appropriate for demo. No auth/authorization, rate limiting, CSRF defenses, deployment threat model or user identity exists; do not expose publicly without controls.
- **Upload validation:** MIME, content, size, pixel count and body size limits are good controls. The image is converted to RGB. No file is persisted in the branch, which reduces privacy exposure.
- **SQLite:** paths are configurable; each access opens a connection and initializes schema, with foreign keys and timeout. Tables store JSON snapshots. No retention/deletion, migration framework, backup/restore strategy, or assessment-linked demo-image record is provided. Database filesystem permissions and encryption are deployment responsibilities.
- **CORS/secrets:** exact origins, no credentials by default. LLM key stays server-side. `.env.example` contains blank key and sample config only; ensure real `.env` remains ignored and never committed.
- **Model supply chain:** ignored local weights are outside the Git commit and no checksum/provenance signature is stored. Model name in response derives partly from filename, which is not a cryptographic identity. Record version/hash and validated class list for reproducible audit trails.
- **Reliability/performance:** CPU-only inference and optional heavy dependencies can make latency high; only one inference lock serializes calls in a process. No measured latency/SLO or client request timeout is apparent. YOLO dependency is optional, so `/health` can pass when inference cannot run.
- **Local extra route safety:** uncommitted `/images` implementation writes a normalized image copy into `detection_results/` with a name derived from upload filename and suppresses save failures. It creates additional persistent image data absent from the branch design; assess collision/retention and filename handling before keeping it. Local `/verify` returns “confirmed” without persistence, which is a misleading audit trail.
- **Frontend markup:** scenario cards interpolate provider text. Other dynamic content also uses `innerHTML`; check all dynamic values and limit to trusted fixed identifiers or escape output.

## 11. Existing test outcomes and gaps

### Executed during this audit

| Command | Result |
|---|---|
| In `github-backend-snapshot`: `py -3.11 -m unittest discover -s tests -v` | **60 tests passed** in 1.983 s. Covers carbon math, commute API/provenance, demo API, simulated mode, mocked detection mapping, image validation, scenario arithmetic, LLM fallback and guardrails. |
| In local root: `py -3.11 -m unittest discover -s tests -v` | **60 tests passed** in 1.977 s. |
| In local root: `py -3.11 -m unittest -v test_vehicle_detection` | **4 tests passed** in 9.943 s. These validate CLI missing-argument/missing-image behavior and pre-existing JSON/image artifact structure; they do not rerun or validate the CV model's accuracy. |

These tests are not a vehicle-detection benchmark. Backend unit tests mock model inference and provider calls; they establish API/formula behaviors, not real weights' ability to detect cars or motorcycles. The standalone root test checks report files already present. No frontend tests, browser end-to-end tests, CORS test from the actual page origin, real-model smoke test on a labeled dataset, persistence across UI reload, or full workflow integration test exists. No test files were modified by the audit.

### Priority test gaps

1. Build a consented, representative, manually labeled parking-image set with splits by site/camera/time; score per-class precision/recall, mAP, count MAE and confidence calibration; include cars, motorcycles, occlusion, shadows, empty lots and crowded rows.
2. Test the real model/runtime/weights/configuration together, including unavailable weights and unsupported class names, and archive weight SHA/version with results.
3. Browser/API end-to-end test for assessment creation, real upload, rendered boxes, review correction, persisted confirmation, baseline calculation, scenario run, recommendation display and analysis retrieval.
4. Contract tests ensure frontend payloads match branch schema and reject silent mock/real mixing.
5. Scenario property tests across no activity, zero baseline, full shifts, all interventions worse than baseline, eligible/ineligible 5 km boundary, high/zero shuttle service, and negative net reduction.
6. Frontend tests for keyboard accessibility, narrow viewports, provider-content escaping, loading/error/retry/empty state, chart CDN absence, and refresh recovery.

## 12. Prioritized implementation roadmap and acceptance criteria

| Priority / phase | Work and dependencies | Acceptance criteria |
|---|---|---|
| **P0 — Freeze the API contract and integration slice** | Decide the branch/API version and remove accidental reliance on local-only endpoints; align UI routes and assessment association. Depends on preserving currently useful local changes while explicitly reviewing them. | From a clean documented setup, frontend calls only branch-supported endpoints; create/upload/analysis retrieval/baseline/scenario each return expected schemas; no success message implies persistence where none exists; uploaded detection analysis and its assessment linkage are traceable. |
| **P0 — Honest detection baseline/evaluation** | Obtain representative labeled parking images and agree class taxonomy; benchmark current YOLO and compare confidence/input-size/NMS variants before model tuning. | Published test report includes dataset composition/split, model/weight hash, per-class precision/recall and count error; performance targets are agreed in advance; no claim of accuracy is made without those results; fallback/errors never fabricate boxes. |
| **P1 — Persist review and carry corrections forward** | Add a real observation/review record linked to assessment and image hash; define correction schema and audit events. | Review save/read survives refresh; API validates counts/boxes and records model output plus reviewer changes; baseline defaults to reviewed counts only when the user explicitly chooses them; provenance labels remain intact. |
| **P1 — Factor and activity governance** | Select authoritative, geographically/applicability-appropriate factor sources; review factors and define survey/traffic sampling procedure. | Approved registry contains immutable source/version/unit/scope/category/fuel applicability and owner decision; approved mode works only for approved records; candidate/demo values remain visibly unapproved; counts and activity input have distinct source/period fields; projections disclose method/uncertainty. |
| **P1 — Scenario semantic correctness** | Rename/match controls to engine semantics; decide occupancy, carpool detour, shuttle activity and active-travel eligibility models. | Every parameter shown in UI is sent and affects a documented formula or is removed; baseline is included in comparison; outputs report VKT and net CO2 change, shuttle added/avoided emissions, assumptions and negative savings; deterministic replay from saved request yields identical output. |
| **P1 — Safe recommendation rendering and linkage** | Escape untrusted LLM prose, align UI to backend schema, and decide whether recommendations attach to image or scenario record. | XSS payloads render as inert text; rendered recommendation record identifies analysis ID/provider/fallback; recommendation link is same scenario data shown; numeric savings come only from deterministic result. |
| **P2 — CarbonSync product UI and accessibility** | Apply brand system/page structure after workflow contract stabilizes. | CarbonSync identity is consistent across title/header/copy; each stage has source/unit/evidence labels; responsive layout, keyboard-only flow, screen-reader names, focus states and accessible chart summaries pass manual and automated checks. |
| **P2 — Reliability/operations** | Add lifecycle policy, model integrity metadata, backend readiness, performance monitoring and deployment controls. | Health distinguishes API readiness and detector availability; explicit limits/timeouts and observable error IDs; retention/deletion behavior tested; no credentials in client/logs; external deployment requires auth/rate controls and documented backup/restore. |
| **P2 — Integration test suite** | Add browser/API test harness only after contract freeze. | CI exercises real application wiring with mocked YOLO/provider for deterministic cases plus an opt-in local-model smoke test; tests cover all major workflow states and evidence that no fake detections appear in real mode. |

## 13. Five highest-priority technical problems and safest first phase

1. **No measured accuracy for overhead parking detection; the supplied screenshot matches static mock boxes.** The product currently cannot substantiate model quality or confidence.
2. **Frontend/backend state is fragmented.** Detection, browser correction, baseline and scenario data are not one persisted assessment workflow; review edits do not drive the calculation.
3. **Unapproved factors and snapshot-to-annual extrapolation risk.** A single photo is not daily activity, and no production factor has been approved.
4. **Uncommitted local API/model changes diverge from the fetched Backend branch.** In particular, local `/simulate` uses hard-coded reductions and a fixed shuttle emissions constant.
5. **Untrusted LLM recommendation content is inserted as HTML.** This creates an avoidable browser injection risk and the UI's recommendation contract claims fields the API does not return.

**Safest first implementation phase:** freeze a minimal vertical-slice contract using the fetched branch's `/api/demo/analyze` and B3 commute API; explicitly decide which uncommitted local changes to retain; keep demo mode/evidence labels clear; then wire a single assessment ID through upload, reviewed-count persistence, baseline and scenario results. Do not tune/promote the detector until a representative labeled evaluation set exists, and do not label annual results as verified campus emissions until activity data and emission factors have documented sources and approvals.

## Source map

Important implementation evidence is in these files (relative to repository root):

- **API routes, request validation, CORS, image analysis orchestration:** `github-backend-snapshot/backend/main.py` (`configured_cors_origins`, `CreateAssessmentRequest`, `CommuteInput`, `/health`, `/api/assessments`, `/api/assessments/{id}/commute-inputs`, `/api/demo/analyze`, `/api/demo/analyses/{id}`).
- **Image validation, model path, class mapping, confidence, inference/counting:** `github-backend-snapshot/backend/vehicle_detection.py` (`COCO_VEHICLE_CLASSES`, `validate_image_bytes`, `_configured_model_path`, `_confidence_threshold`, `_load_model`, `detect_vehicle_image`).
- **Demo assumptions schema:** `github-backend-snapshot/backend/demo_schemas.py` (`DemoAnalysisRequest`, `VehicleAssumption`, `DemoFactor`, `ScenarioAssumptions`).
- **Demo baseline and scenarios:** `github-backend-snapshot/backend/demo_calculations.py` (`_estimate`, `calculate_demo_analysis`, `_scenario`).
- **B3 emissions formula:** `github-backend-snapshot/backend/carbon_engine.py` (`EmissionFactor`, `calculate_annual_emissions`).
- **Factor approval state:** `github-backend-snapshot/backend/factor_registry.py` (`APPROVED_FACTOR_REGISTRY`).
- **LLM prompt, provider, guards, fallback:** `github-backend-snapshot/backend/recommendations.py` (`_fallback`, `_contains_untrusted_claims`, `generate_recommendations`).
- **Persistence tables and JSON snapshots:** `github-backend-snapshot/backend/database.py` (`initialize_schema`, save/retrieve functions).
- **Backend setup, env and frontend handoff:** `github-backend-snapshot/BACKEND_SETUP.md`, `github-backend-snapshot/.env.example`, `github-backend-snapshot/requirements.txt`, `github-backend-snapshot/requirements-yolo.txt`.
- **Current UI branding, tabs, forms, 5 km limit, scenario/recommendation text:** `frontend/index.html`.
- **Frontend API adapter and demo assumptions:** `frontend/js/api.js`.
- **Browser-only review and workflow:** `frontend/js/app.js`, `frontend/js/canvas_editor.js`.
- **Scenario rendering and LLM content insertion:** `frontend/js/scenarios.js`.
- **Static mock boxes and mock scenario data:** `frontend/js/mocks.js`.
- **Executable backend suites:** `tests/test_carbon_engine.py`, `tests/test_commute_api.py`, `tests/test_demo_api.py`; standalone artifact assertions are in `test_vehicle_detection.py`.
- **Planning vs implementation distinctions:** `github-backend-snapshot/TraceTwin_Documentation/BACKEND.md`, `METHODOLOGY.md`, `SOURCES_AND_ASSUMPTIONS.md`, `STATUS.md`, `TEST_PLAN.md`.

Where the code cannot establish actual model accuracy, factor scientific validity, source authenticity, campus activity representativeness, LLM provider availability, or deployed security posture, this audit marks those items unverified rather than inferring them from documentation or sample outputs.
