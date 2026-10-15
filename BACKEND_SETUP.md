# Portable Backend Setup and Frontend Handoff

This guide covers the existing FastAPI application. The repository does not include a React app. The backend contract in [`TraceTwin_Documentation/BACKEND.md`](TraceTwin_Documentation/BACKEND.md) is the source of truth for all API fields.

## Supported local setup

- Windows 10/11, 64-bit.
- Python 3.11 or 3.12, 64-bit. The current automated suite was run with Python 3.12.14.
- The core API can start without Ultralytics or model weights. Real image inference requires the optional Ultralytics/PyTorch environment and a compatible local `.pt` weights file.
- Dependencies used by the core API are pinned in `requirements.txt`. `requirements-yolo.txt` adds the bounded Ultralytics 8.3 series and its heavyweight inference dependencies.

## Clone and install

Clone the backend branch after it is published:

```powershell
git clone --branch Backend --single-branch https://github.com/ManojR-cs/CarboSync.git
cd CarboSync
```

Create `.venv` and install the small core runtime:

```powershell
.\setup_backend.ps1
```

The script uses an existing `.venv` when present; otherwise it creates one with the `python` command on PATH. It accepts only Python 3.11 or 3.12. To use a separate existing YOLO environment without creating another environment:

```powershell
.\setup_backend.ps1 -PythonExe 'D:\path\to\your-yolo-env\Scripts\python.exe' -SkipInstall
```

`-SkipInstall` checks the core imports without changing that environment. If core imports are missing, install the pinned API requirements into the chosen interpreter deliberately:

```powershell
& 'D:\path\to\your-yolo-env\Scripts\python.exe' -m pip install -r requirements.txt
```

For a new environment that also needs Ultralytics, run `.\setup_backend.ps1 -WithYolo`. This can install a large PyTorch runtime. If the laptop already has a working, compatible YOLO/PyTorch setup, use that interpreter instead and do not install another copy. Verify it with:

```powershell
& 'D:\path\to\your-yolo-env\Scripts\python.exe' -c "import ultralytics, torch; print(ultralytics.__version__, torch.__version__)"
```

No setup command downloads model weights.

## Configure and run

Copy the safe example configuration and edit it locally:

```powershell
Copy-Item .env.example .env
notepad .env
```

`run_backend.ps1` reads simple `NAME=value` lines from `.env` into that server process only, changes to the repository root, and starts Uvicorn on loopback. It does not print the values.

```powershell
.\run_backend.ps1
```

Then open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). The direct command, if you have already set the same environment variables in PowerShell, is:

```powershell
& '.\.venv\Scripts\python.exe' -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Environment variables

| Variable | Purpose | Example / default |
|---|---|---|
| `CARBOSYNC_DATABASE_PATH` | SQLite location, relative to repository root when relative | `carbosync.db` |
| `CARBOSYNC_CORS_ORIGINS` | Comma-separated exact browser origins; no wildcard | `.env.example` shows common Vite origins on port 5173; replace them with the frontend's actual origin |
| `CARBOSYNC_YOLO_MODEL_PATH` | Local Ultralytics PyTorch `.pt` weights path | `backend/models/yolo11n.pt` |
| `CARBOSYNC_YOLO_CONFIDENCE` | Detection confidence threshold in `(0, 1]` | `0.35` |
| `CARBOSYNC_LLM_PROVIDER` | Optional provider selector | `openai_compatible`; blank uses fallback |
| `CARBOSYNC_LLM_API_KEY` | Optional provider credential | Blank uses fallback; never commit a real key |
| `CARBOSYNC_LLM_BASE_URL` | Optional OpenAI-compatible API base | `https://api.openai.com/v1` |
| `CARBOSYNC_LLM_MODEL` | Optional provider model | `gpt-4o-mini` |

The application accepts Ultralytics `.pt` weights only. The default expected file is `yolo11n.pt`; put it at `backend/models/yolo11n.pt`, or set `CARBOSYNC_YOLO_MODEL_PATH` to the local file. The model path can be absolute on each laptop and is never returned by an API response. Weights are ignored by Git. Obtain weights through the team's approved source and place them locally; the backend and setup scripts do not download them.

The detector reads the configured model's actual class-name table. The standard COCO names `bicycle`, `car`, `motorcycle`, `bus`, and `truck` map to their matching categories; the standard COCO IDs are 1, 2, 3, 5, and 7 respectively. Custom weights may order class IDs differently. The response reports `class_mapping` as category-to-ID-lists and `unmapped_vehicle_categories`; a custom model must use recognized class names for categories to count. Unknown labels are ignored. The detector runs on CPU with the configured threshold and returns normalized box coordinates, confidence, counts, and an annotated JPEG data URI.

If Ultralytics or weights are missing, the API still starts. A real-mode analysis returns HTTP 503 with an actionable message to install the optional YOLO dependencies and configure compatible local weights. It does not fall back to fabricated results.

## Frontend integration

Use `http://127.0.0.1:8000` as the local API base. Configure CORS with the exact origin shown in the React dev server (for example, `http://localhost:5173`). CORS origins must include the scheme and port. Do not use `*`; credentials are disabled.

The single analysis route is `POST /api/demo/analyze`. It accepts `multipart/form-data` with:

- `image`: JPEG, PNG, or WebP image, maximum 10 MiB and 40 megapixels.
- `assumptions_json`: JSON string matching the assumptions structure in `TraceTwin_Documentation/BACKEND.md`, Section 7. Factors and activity assumptions must be explicit; the backend supplies no factor defaults.

In real mode, omit `detection_mode` or set it to `real`. For a UI walkthrough without model weights, explicitly set `detection_mode: "simulated"`, provide all five `simulated_detection_counts`, and a `simulated_detection_source_description`. The uploaded image is validated but not analyzed; the response has `simulated: true`, no annotation, and a warning. Never display simulated counts as image detections.

Example React/browser client code (the `assumptions` object must use the complete schema linked above):

```js
const API_BASE = "http://127.0.0.1:8000";

async function analyzeImage(file, assumptions, onLoading) {
  onLoading(true);
  try {
    const form = new FormData();
    form.append("image", file);
    form.append("assumptions_json", JSON.stringify(assumptions));

    const response = await fetch(`${API_BASE}/api/demo/analyze`, {
      method: "POST",
      body: form, // Let the browser set the multipart boundary.
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.message || `Request failed (${response.status})`);
    }
    return body;
  } finally {
    onLoading(false);
  }
}

async function retrieveAnalysis(analysisId) {
  const response = await fetch(
    `${API_BASE}/api/demo/analyses/${encodeURIComponent(analysisId)}`
  );
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || `Request failed (${response.status})`);
  return body;
}
```

Show a loading state while the upload is being processed. The public error shape is `{"error":true,"message":"..."}`; display its safe `message` and allow retry for 503/network errors. For 413/415/422 errors, explain the image or assumptions need correction. An optional image preview is separate from the returned `annotated_image_data_uri`.

Abbreviated response excerpt from real mode. The detection array shown is partial; ellipses indicate omitted fields/items rather than literal response values. Other example values are from the synthetic test fixture, not a real campus result:

```json
{
  "analysis_id": "demo_<generated-id>",
  "created_at": "<UTC timestamp>",
  "detection_mode": "real",
  "detections": {
    "mode": "real",
    "simulated": false,
    "per_class": {"bicycle": 3, "car": 10, "motorcycle": 2, "bus": 1, "truck": 1},
    "details": [{
      "class_id": 1,
      "category": "bicycle",
      "confidence": 0.88,
      "bounding_box_normalized": {"x_min": 0.02, "y_min": 0.1, "x_max": 0.3, "y_max": 0.6}
    }, {
      "class_id": 2,
      "category": "car",
      "confidence": 0.91,
      "bounding_box_normalized": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.5, "y_max": 0.7}
    }],
    "motor_vehicle_total": 14,
    "bicycle_total": 3,
    "all_vehicle_total": 17,
    "observation_scope": "single_image_snapshot",
    "model": "YOLO11n",
    "confidence_threshold": 0.35,
    "class_mapping": {"bicycle": [1], "car": [2], "motorcycle": [3], "bus": [5], "truck": [7]},
    "unmapped_vehicle_categories": []
  },
  "model": {"name": "YOLO11n", "confidence_threshold": 0.35, "detection_mode": "real", "simulated": false, "class_mapping": {"bicycle": [1], "car": [2], "motorcycle": [3], "bus": [5], "truck": [7]}, "unmapped_vehicle_categories": []},
  "detection_details": [{"class_id": 1, "category": "bicycle", "confidence": 0.88, "bounding_box_normalized": {"x_min": 0.02, "y_min": 0.1, "x_max": 0.3, "y_max": 0.6}}, {"class_id": 2, "category": "car", "confidence": 0.91, "bounding_box_normalized": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.5, "y_max": 0.7}}],
  "annotated_image_data_uri": "data:image/jpeg;base64,...",
  "result": {
    "calculation_method_version": "demo_snapshot_tailpipe_estimate_v1",
    "calculation_mode": "demo_illustrative",
    "approval_status": "illustrative_unapproved",
    "evidence_label": "Illustrative estimate based on a single-image snapshot and explicit assumptions",
    "independently_verified": false,
    "baseline": {"annual_vehicle_km": 56000, "annual_kg_co2": 9840, "annual_tonnes_co2": 9.84, "category_breakdown": {"car": {"annual_vehicle_km": 40000, "annual_kg_co2": 6000, "annual_tonnes_co2": 6, "factor_snapshot": {"factor_id": "DEMO_CAR", "value": 0.15, "unit": "kg CO2/veh-km", "approval_status": "illustrative_unapproved"}}}},
    "scenarios": [
      {"id": "carpool", "name": "Illustrative carpool activity consolidation", "label": "Illustrative simulation; not measured or guaranteed savings", "assumptions": {"carpool_activity_reduction_share": 0.5}, "estimated_emissions": {"annual_tonnes_co2": 6.84}, "change_vs_baseline_tonnes": -3, "reduction_vs_baseline_tonnes": 3, "percentage_reduction_vs_baseline": 30.487804878, "comparison": "lower than baseline", "limitations": "..."},
      {"id": "campus_shuttle", "name": "Illustrative campus shuttle shift", "label": "Illustrative simulation; not measured or guaranteed savings", "assumptions": {"private_vehicle_shift_share": 0.5}, "estimated_emissions": {"annual_tonnes_co2": 11.8}, "change_vs_baseline_tonnes": 1.96, "reduction_vs_baseline_tonnes": -1.96, "percentage_reduction_vs_baseline": -19.918699187, "comparison": "higher than baseline", "limitations": "..."},
      {"id": "active_travel", "name": "Illustrative short-trip active travel shift", "label": "Illustrative simulation; not measured or guaranteed savings", "assumptions": {"active_travel_shift_share": 0.5, "max_one_way_km": 15}, "estimated_emissions": {"annual_tonnes_co2": 6.68}, "change_vs_baseline_tonnes": -3.16, "reduction_vs_baseline_tonnes": 3.16, "percentage_reduction_vs_baseline": 32.113821138, "comparison": "lower than baseline", "limitations": "..."}
    ],
    "best_scenario": {"id": "active_travel", "name": "Illustrative short-trip active travel shift"},
    "recommendations": {"status": "fallback", "fallback_flag": true, "label": "Rule-based plan (AI unavailable)", "best_scenario": {"id": "active_travel", "name": "Illustrative short-trip active travel shift"}, "recommendations": []},
    "warnings": [],
    "limitations": ["A single image is a point-in-time snapshot, not daily traffic..."]
  }
}
```

The annotated image is returned in the upload response as a data URI and is not stored. Retrieval is `GET /api/demo/analyses/{analysis_id}`; it returns the saved structured snapshot, not the image. The response contains illustrative estimates, not approved or measured campus emissions. The frontend must not calculate authoritative emissions itself.

## Run tests

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -v
```

The automated detector and recommendation tests use mocks; they require no weights, GPU, external key, or network. A live inference check requires a compatible `.pt` file and `ultralytics`/PyTorch already installed in the selected interpreter. Configure those on each laptop and test a real image there before claiming detection works on that machine.
