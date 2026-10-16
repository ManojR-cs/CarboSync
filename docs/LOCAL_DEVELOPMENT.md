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

Real YOLO inference additionally needs a compatible Ultralytics/PyTorch installation and a model weights file obtained separately. Install the optional runtime with `.\setup_backend.ps1 -WithYolo`. Set `CARBOSYNC_YOLO_MODEL_PATH` in `.env` to the weights file. The API starts without either; real image analysis then returns an unavailable error instead of fake detections. Mock mode does not analyze uploaded images.

## Tests and checks

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --check frontend/js/app.js
node --check frontend/js/api.js
node --check frontend/js/scenarios.js
```

Automated detection tests mock the model. They do not need network access, a GPU, or LLM credentials. The optional real-model smoke test is skipped if its local weights, runtime, or sample image are absent.
