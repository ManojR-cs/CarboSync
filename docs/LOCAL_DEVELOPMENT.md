# Local development

## Requirements

- Windows PowerShell
- 64-bit Python 3.11 or 3.12
- Node.js only if you want to run the JavaScript syntax checks

## Run the app

From the repository root:

```powershell
.\setup_backend.ps1
Copy-Item .env.example .env
.\run_backend.ps1
```

The setup script installs only the small API runtime. In another terminal, start the static frontend:

```powershell
py -m http.server 5500 --directory frontend
```

Open http://127.0.0.1:5500/. API health: http://127.0.0.1:8001/health. Interactive API documentation: http://127.0.0.1:8001/docs.

The example `.env` targets this local static frontend. Keep the real `.env` file private; it is ignored by Git. The database is local SQLite at `carbosync.db` unless `CARBOSYNC_DATABASE_PATH` is set.

## Optional image inference

Real YOLO inference additionally needs the optional Ultralytics/PyTorch runtime and a local model weights file. The checked-in `.env.example` points to `backend/models/yolo11x.pt`; a `yolo11n.pt` in the repository root will not satisfy that setting. Weights are intentionally excluded from Git.

From the repository root, install the optional runtime:

```powershell
.\setup_backend.ps1 -WithYolo
```

To fetch the configured YOLO11x weights through Ultralytics, run:

```powershell
New-Item -ItemType Directory -Force backend\models | Out-Null
.\.venv\Scripts\python.exe -c "from ultralytics import YOLO; YOLO('backend/models/yolo11x.pt')"
```

If you have `yolo11n.pt` instead, put it at `backend/models/yolo11n.pt` and set `CARBOSYNC_YOLO_MODEL_PATH=backend/models/yolo11n.pt` in your local `.env`. Use the same model file when comparing results; changing weights changes detections. The backend checks the configured path and reports inference as unavailable if the file is missing or Ultralytics is not installed. It does not invent detections. Mock mode does not analyze uploaded images.

## Tests and checks

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --check frontend/js/app.js
node --check frontend/js/api.js
node --check frontend/js/scenarios.js
```

Automated detection tests mock the model. They do not need network access, a GPU, or LLM credentials. The optional real-model smoke test is skipped if its local weights, runtime, or sample image are absent.
