# CarboSync

CarboSync is a campus commute emissions analysis demo. It combines optional computer vision for vehicle counts from a parking image with a backend digital twin that compares illustrative commute scenarios and carbon reduction actions.

## Hackathon problem and solution

Campus teams need a way to explore commute patterns and possible lower carbon alternatives. CarboSync provides a small local web app for entering commute assumptions, reviewing parking images, comparing scenarios, and visualizing the aggregate mode mix. Backend calculations are deterministic and the animated twin visualizes returned results; the animation is not live traffic.

## Start on Windows

You can download the repository as a ZIP from GitHub and extract it. Git and Node.js are not required. Windows PowerShell and a network connection are needed for first-time installation. The regular app needs 64-bit Python 3.11 or 3.12; setup creates a project-local `.venv` and installs the pinned API dependencies. If Python is missing, the setup script offers Windows Package Manager installation of Python 3.12 after asking first. This can require internet, Windows Package Manager availability, and permission to install software. Nothing installs silently.

In PowerShell, change to the extracted folder and run:

```powershell
.\Start-CarboSync.ps1
```

The script installs the core backend on first run, creates `.env` from `.env.example` only if `.env` does not already exist, starts the backend with the static frontend, and opens the browser. Keep the PowerShell window open while using the app; press Ctrl+C or close that window to stop the server. If Windows blocks local scripts, try `powershell -ExecutionPolicy Bypass -File .\Start-CarboSync.ps1` for this invocation. Organization policy may still block scripts.

The app opens at [http://127.0.0.1:8001/](http://127.0.0.1:8001/). Health is [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health), and interactive API documentation is [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs).

### Manual setup and run

If compatible Python is already installed, the equivalent first-time commands are:

```powershell
.\setup_backend.ps1
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Start the complete app (frontend included) with:

```powershell
.\run_backend.ps1
```

Stop it with Ctrl+C. For API-only development, set `CARBOSYNC_SERVE_FRONTEND=0` in `.env`. To use the frontend from a separate development server instead, run `py -3.12 -m http.server 5500 --directory frontend` and set `CARBOSYNC_SERVE_FRONTEND=0`; the example CORS list permits that local origin. This separate server is optional and not needed by judges.

## Features and workflow

1. Enter commute activity and explicit assumptions in the local dashboard.
2. Optionally upload a JPEG, PNG, or WebP parking image for real YOLO inference; review/correct the returned boxes before saving an observation.
3. Compare backend-calculated commute scenarios and recommendations.
4. View aggregate mode flows in the animated digital twin.

Without weights, the detector is unavailable and image analysis returns an actionable error. No fabricated vehicle detections or counts are returned. The application itself runs without YOLO. Recommendations have a deterministic local fallback; an LLM API key is not required.

## Optional YOLO vehicle detection

YOLO uses Ultralytics YOLO11n, a small COCO-pretrained detector suitable for a CPU live demo. Install its larger Ultralytics/PyTorch dependencies and download weights only when you choose to enable inference:

```powershell
.\setup_yolo.ps1
```

This one-time command installs `requirements-yolo.txt` and asks Ultralytics to fetch `yolo11n.pt` into `backend/models/`. It needs network access to the Ultralytics GitHub release assets and several hundred megabytes of dependency downloads. The API never downloads a model during startup. Weight files are ignored by Git.

The default detector path is `backend/models/yolo11n.pt`. To use another readable Ultralytics detection `.pt` file, set `CARBOSYNC_YOLO_MODEL_PATH` in `.env` to its absolute path or a path relative to the repository root. The nano model recognizes COCO vehicle classes bicycle, car, motorcycle, bus, and truck. It does not recognize occupancy, fuel/powertrain, distance, trip purpose, or whether a vehicle is unique. Campus-scene accuracy has not been validated against a held-out annotated dataset. Outputs are detections from model inference, not verified travel measurements.

CPU is the default and requires no GPU. On a machine with a compatible CUDA-enabled PyTorch installation, set `CARBOSYNC_YOLO_DEVICE=0` (or `cuda:0`) to select GPU 0. Check `nvidia-smi` and PyTorch's official installation instructions if CUDA is unavailable; the project does not replace the installed PyTorch package automatically. Other common settings are `CARBOSYNC_YOLO_CONFIDENCE=0.15`, `CARBOSYNC_YOLO_IOU=0.30`, `CARBOSYNC_YOLO_IMAGE_SIZE=640`, and `CARBOSYNC_YOLO_NMS_MODE=class_aware`.

The detector health state is one of `ready`, `unavailable` (missing optional dependencies/weights/configuration), or `failed` (present weights/runtime could not initialize). A requested image analysis reports a 503 actionable detector error when unavailable; it never silently substitutes mock data. If a download fails, check network/proxy access and available disk space, then rerun `setup_yolo.ps1`. It refuses to overwrite an existing `yolo11n.pt`.

## Data, privacy, and configuration

The local SQLite database defaults to `carbosync.db` in the repository root. Tables are created repeatably on access; an empty database is valid and does not receive seeded student data. Back it up by stopping the app and copying the database file. Reset only after making a backup and confirming the file contains no records you need; deleting it permanently removes local records. `CARBOSYNC_DATABASE_PATH` can select another absolute or repository-relative path.

The demo has unauthenticated local routes that can store and return student names, identifiers, and residential addresses. Use only synthetic or otherwise authorized data, and keep the server bound to `127.0.0.1`. Do not expose it publicly or enter real student data. CORS does not provide authentication.

Copy `.env.example` to `.env` to change settings. The launcher creates it only if missing and never replaces an existing `.env`. Supported variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CARBOSYNC_CORS_ORIGINS` | `http://localhost:5500,http://127.0.0.1:5500` | Exact browser origins allowed by the API; no wildcard. |
| `CARBOSYNC_SERVE_FRONTEND` | `0` in the API; launcher enables it | Serve the static `frontend/` app from the backend root. |
| `CARBOSYNC_PORT` | `8001` in the Windows launcher | Local port used by `Start-CarboSync.ps1`. `run_backend.ps1` instead accepts `-Port`. |
| `CARBOSYNC_SERVE_DETECTION_RESULTS` | `0` | Explicitly expose generated detection files. Keep disabled for normal use. |
| `CARBOSYNC_DATABASE_PATH` | `carbosync.db` | SQLite file path; relative paths use the repository root. |
| `CARBOSYNC_YOLO_MODEL_PATH` | `backend/models/yolo11n.pt` | Local Ultralytics `.pt` weights. No startup download occurs. |
| `CARBOSYNC_YOLO_CONFIDENCE` | `0.15` | Minimum detection confidence, between 0 and 1. |
| `CARBOSYNC_YOLO_IOU` | `0.30` | NMS IoU threshold, greater than 0 and less than 1. |
| `CARBOSYNC_YOLO_IMAGE_SIZE` | `640` | Inference image size, multiple of 32 (32–4096). |
| `CARBOSYNC_YOLO_NMS_MODE` | `class_aware` | `class_aware` or `class_agnostic`. |
| `CARBOSYNC_YOLO_DEVICE` | `cpu` | `cpu`, `mps`, or supported GPU index such as `0` / `cuda:0`. |
| `CARBOSYNC_LLM_PROVIDER` | blank | Optional provider selector; blank uses deterministic fallback. |
| `CARBOSYNC_LLM_API_KEY` | blank | Optional secret for configured LLM recommendations; do not commit it. |
| `CARBOSYNC_LLM_BASE_URL` | `https://api.openai.com/v1` | Optional OpenAI-compatible API base URL. |
| `CARBOSYNC_LLM_MODEL` | `gpt-4o-mini` | Optional model name for the configured provider. |

## Estimates and known limitations

All emissions and scenario values are illustrative estimates based on user-entered commute days, distances, occupancy, and candidate factors. They are not approved or independently verified campus inventory results. A single image is a point-in-time snapshot, not daily traffic or unique commuters. YOLO cannot infer trips, occupancy, fuel, powertrain, or distance. The digital twin is an aggregate diagram rather than geographic simulation. The application has no authentication and is intended for local judging only.

## Tests and development

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --check frontend/js/app.js
node --check frontend/js/api.js
node --check frontend/js/scenarios.js
```

Python tests use mocked YOLO for deterministic detector coverage. A real inference smoke test runs only when the optional weights, runtime, and `test_images/Test1.jpg` are available. Node.js is only needed for the optional JavaScript syntax checks, not for the app. Detection dataset evaluation and methodology are described in [docs/EVALUATION.md](docs/EVALUATION.md) and [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Deployment

There is no Render deployment manifest in this repository. The historical `/var/data/carbosync.db` and `/var/data/yolo11x.pt` values are not proof that a Render disk exists or either file is present. For a Render instance, explicitly configure `CARBOSYNC_DATABASE_PATH` to a writable persistent-disk path and attach/mount that disk; otherwise SQLite data may be ephemeral. For inference, install `requirements-yolo.txt`, provision a compatible `.pt` file on persistent or baked image storage, and set `CARBOSYNC_YOLO_MODEL_PATH` to its actual path. Do not rely on startup downloads or claim inference readiness until `/health` reports `detector.status: ready` and a real image inference has been verified. The current student-record API is not safe for public hosting; see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
