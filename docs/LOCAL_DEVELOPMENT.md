# Local development

## Requirements

Windows PowerShell and 64-bit Python 3.11 or 3.12 are needed for the core backend. The setup script creates `.venv` and installs `requirements.txt`. If it cannot find a supported Python, it offers Windows Package Manager installation of Python 3.12; confirm only if you want that system prerequisite installed. Otherwise install Python from [python.org](https://www.python.org/downloads/) and rerun. Keep network access available for pip. No Git or Node.js installation is needed to run the application.

## Complete app

From an extracted repository folder:

```powershell
.\Start-CarboSync.ps1
```

On first launch it installs backend dependencies, copies `.env.example` to `.env` only when `.env` is absent, serves `frontend/` through FastAPI, and opens the browser. Use Ctrl+C in that PowerShell window to stop the server. URLs: `http://127.0.0.1:8001/`, `/health`, and `/docs`.

Manual setup is ` .\setup_backend.ps1 ` followed by `if (-not (Test-Path .env)) { Copy-Item .env.example .env }`; launch with ` .\run_backend.ps1 `. Both scripts resolve paths from their own location, so the caller's current directory can differ from the project root. Do not run setup over a broken existing `.venv`: inspect it and move/repair it deliberately first. Existing database and `.env` files are left intact.

## Optional detector

Real inference is optional. Run ` .\setup_yolo.ps1 ` for the larger Ultralytics/PyTorch runtime and a one-time YOLO11n download to `backend/models/yolo11n.pt`. The server does not download weights. The small COCO model supports bicycle, car, motorcycle, bus, and truck. Set another model with `CARBOSYNC_YOLO_MODEL_PATH`. CPU is default; `CARBOSYNC_YOLO_DEVICE=0` selects GPU 0 when a compatible PyTorch/CUDA runtime is installed.

Without YOLO dependencies or weights, the basic API and UI still run; health reports `unavailable`, and image-analysis requests return a clear 503. It does not use fabricated detections.

## Database and configuration

SQLite defaults to `carbosync.db` in the repository root. Relative `CARBOSYNC_DATABASE_PATH` values also resolve from that root. Schema creation is repeatable and there are no automatic sample student records. Stop the app before making a backup. Do not delete a database until its data has been reviewed and backed up.

`.env.example` lists all supported `CARBOSYNC_*` environment variables. The launcher reads `.env` for its process and does not overwrite it. The LLM provider, key, base URL, and model are optional; blank provider/key uses local deterministic recommendation fallback.

## Tests

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --check frontend/js/app.js
node --check frontend/js/api.js
node --check frontend/js/scenarios.js
```

The tests mock model loading/inference. A real smoke test is skipped unless a local model, Ultralytics, and `test_images/Test1.jpg` exist. Use the separate static frontend server only if developing it independently: `py -3.12 -m http.server 5500 --directory frontend`; set `CARBOSYNC_SERVE_FRONTEND=0` and keep only the exact local origins in `CARBOSYNC_CORS_ORIGINS`.

## Troubleshooting

- **No Python / wrong version:** install 64-bit Python 3.12, reopen PowerShell and rerun. Python 3.13 is currently rejected by project setup.
- **PowerShell blocks scripts:** run `powershell -ExecutionPolicy Bypass -File .\Start-CarboSync.ps1` if permitted by your device policy.
- **pip fails:** check network/proxy access and rerun ` .\setup_backend.ps1 `. Existing environments are reused; a damaged `.venv` is not overwritten.
- **Port is busy:** stop the other process or set a different `-Port` for `run_backend.ps1`, then use the matching URL. Launcher default is 8001; startup diagnostics are written to ignored `backend.stderr.log`.
- **Detector unavailable:** install with ` .\setup_yolo.ps1 ` or set the model path to an existing readable `.pt` file. A failed first-time model download requires access to GitHub release assets and disk space.
- **Detector failed:** ensure weights are Ultralytics-compatible detection weights and `requirements-yolo.txt` is installed. Check `/health` for the safe diagnostic.
- **Database errors:** verify `CARBOSYNC_DATABASE_PATH` points to a writable file/directory. On a fresh local start, tables are created automatically. Back up before changing paths or removing a database.
- **Browser cannot reach API:** keep the launcher window open and use the displayed loopback URL. If using a separate frontend server, verify the port and exact `CARBOSYNC_CORS_ORIGINS` values.
