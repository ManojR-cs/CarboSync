# CarbonSync

**A campus commute emissions demo with an animated digital twin.** CarbonSync combines a human-reviewed parking-image workflow with backend-calculated commute estimates and scenario comparisons.

> All emissions values and scenario outcomes are illustrative estimates from explicit assumptions. They are not verified campus inventory results. The commute-flow animation is a diagram, not live traffic or a geographically accurate campus model.

## Try it locally

Requirements: Windows, Python 3.11 or 3.12, and PowerShell. No LLM key is needed. The regular setup runs the UI and deterministic calculations; YOLO/PyTorch and model weights are optional and only needed for real image inference.

```powershell
git clone https://github.com/ManojR-cs/CarboSync.git
cd CarboSync
```

Install backend dependencies and start the API:

```powershell
.\setup_backend.ps1
Copy-Item .env.example .env
.\run_backend.ps1
```

In a second PowerShell window, serve the frontend:

```powershell
py -m http.server 5500 --directory frontend
```

Open [http://127.0.0.1:5500/](http://127.0.0.1:5500/). The API health page and interactive docs are at [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health) and [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs).

The local frontend expects the API on port `8001`. Keep `.env` local; it is ignored by Git. For setup options, environment variables, and detector installation see [Local development](docs/LOCAL_DEVELOPMENT.md).

## What the demo does

- Reviews parking images with optional local YOLO inference and manual correction. Without YOLO or weights, the API still starts and reports that real image analysis is unavailable; it does not fabricate detections.
- Calculates commute and scenario estimates on the backend from explicit inputs and factors.
- Shows baseline-versus-scenario mode flows from the successful backend response. Play, pause, and reset only animate the returned aggregate flow profile.
- Uses a deterministic recommendation fallback when no optional LLM provider is configured.
- Stores local demo data in SQLite (`carbosync.db` by default).

## Verify

```powershell
\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --check frontend/js/app.js
node --check frontend/js/api.js
node --check frontend/js/scenarios.js
```

The automated detector tests use mocks and do not require a model or GPU. A real inference check requires the optional runtime and a compatible `.pt` model file. To use the image-evaluation utility, see [Evaluation tooling](docs/EVALUATION.md).

## Project layout

```text
backend/       API, calculations, persistence, optional detection
frontend/      Static dashboard and animated commute-flow visualization
tests/         Backend and frontend regression tests
tools/         Image detection and evaluation utilities
evaluation/    Empty annotation schema example
docs/          Local setup, methodology, evaluation, deployment limits
```

## Deployment status

The full backend is intended for loopback-only local demos at this time. It has unauthenticated routes that can return names and residential addresses, so it must not be exposed to the public internet or receive real student data. No public deployment is configured. See [Deployment readiness](docs/DEPLOYMENT.md) for the specific blockers and the work required before hosting it publicly.

## Method and limitations

The backend owns the numerical calculations; the browser visualizes backend results and does not calculate emissions. Factors are provisional and results are labelled illustrative. A single parking photo is only a point-in-time image, not daily traffic. Detector performance has not been established on a held-out annotated campus dataset. See [Methodology](docs/METHODOLOGY.md).
