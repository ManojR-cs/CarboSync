# CarbonSync deployment preparation

This document describes the current deployment shape and the remaining gates. It does **not** mean the app is safe to expose publicly. Keep the current demo on loopback until the privacy and access-control blockers below are resolved.

## Current runtime

- FastAPI entry point: `backend.main:app`.
- The local PowerShell runner binds `127.0.0.1:8001`; the static frontend is served separately at `http://localhost:5500/`.
- The same API can serve the frontend from the FastAPI process when `CARBOSYNC_SERVE_FRONTEND=1`. This same-origin arrangement is the simplest Render shape and avoids a separate frontend CORS setup.
- `GET /health` reports API health separately from detector readiness. Its detector metadata includes the configured weights hash, supported classes, runtime versions, and inference settings. A healthy API response does not mean the detector is ready.
- The configured local detector is YOLO11x at `backend/models/yolo11x.pt`; the `.pt` file is ignored by Git. Missing weights fail closed: the backend does not silently download or switch models.
- `CARBOSYNC_DATABASE_PATH` selects the SQLite file. The default is `carbosync.db` at the repository root, and database files are Git-ignored.
- Image upload is limited to 10 MiB and 40 megapixels; supported formats are JPEG, PNG, and WebP.
- LLM recommendations are optional. No LLM credentials are needed for deterministic commute calculations or scenario calculations.

## Render preparation commands

For one Render Web Service that serves both API and frontend:

- **Build command:** `pip install -r requirements-yolo.txt`
- **Start command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Required environment:** `CARBOSYNC_SERVE_FRONTEND=1`, `CARBOSYNC_DATABASE_PATH=/var/data/carbosync.db`, `CARBOSYNC_YOLO_MODEL_PATH=/var/data/yolo11x.pt`, and an exact `CARBOSYNC_CORS_ORIGINS` value for any separate trusted browser origin. Same-origin frontend/API requests do not require CORS.
- Choose a supported Python 3.11 runtime. The current local runtime was Python 3.11.7, Ultralytics 8.4.177, and Torch 2.14.1. `requirements-yolo.txt` pins Ultralytics but does not pin the platform-sensitive Torch build; verify the installed versions and model load on Render before treating the service as ready.

The start command uses Render's injected `$PORT` and binds `0.0.0.0`. The current local PowerShell script intentionally stays on loopback and is not a production start command.

## Required Render dashboard setup

1. Create a Web Service from the repository and configure the build/start commands above.
2. Attach a persistent disk mounted at `/var/data` before expecting the SQLite database or model weights to survive restarts. Set the corresponding environment paths to files on that mount.
3. Provision the exact YOLO11x weights file onto the disk using an approved private artifact-transfer method. The weights are not in Git; no download-on-start mechanism is implemented. Verify `GET /health` reports `detector.status = ready` and the expected SHA-256 after provisioning.
4. Keep one service instance and one Uvicorn worker while using SQLite. SQLite on a local persistent disk is not shared across horizontally scaled instances and is not a managed multi-writer database.
5. Set `CARBOSYNC_CORS_ORIGINS` to a comma-separated allowlist of exact HTTPS origins only if the frontend is hosted separately. Do not use `*`.
6. Leave the optional LLM settings empty unless an authorized provider/key is configured. Never put secrets in frontend files or the repository; provider failures must continue to use the clearly labeled rule-based fallback.
7. Verify `/health`, `/api/demo/commute-summary`, an actual model inference, the saved-observation workflow, SQLite persistence after restart, and the front-end workflow against the deployed service before any demo URL is shared.

For a separately hosted static frontend, configure `window.CARBOSYNC_API_BASE` before `js/api.js` loads, or put the API origin in `<meta name="carbonsync-api-base" content="https://your-api-origin">`. Configure the backend CORS allowlist for that exact frontend origin. Do not point the production frontend at `localhost` or `127.0.0.1`.

## Blocking risks before public deployment

- **No authentication or authorization:** student CRUD, campaign writes, and analysis endpoints are unauthenticated. CORS is not access control. `GET /api/demo/students` returns names and residential addresses to any caller who can reach the service. Do not enter real student personal data or expose this service publicly until access control and data-minimization requirements are implemented and reviewed.
- **No approved emission factors:** the student commute and scenario factors are explicitly provisional candidates. Their geographic, fuel, occupancy, and source applicability have not been validated. They are not suitable for an operational campus inventory or emissions claims.
- **No parking-domain accuracy evidence:** the current detector can return zero for a parking photo containing visible cars. Model readiness and successful inference do not establish detection accuracy. Keep human review enabled and collect a held-out annotated evaluation set before reporting detector performance.
- **Model and database operations are manual:** the model weights are not in Git, and SQLite requires a mounted persistent disk. A missing mount or wrong path prevents durable operation or detector readiness.
- **No application-level rate limiting:** upload size and image dimensions are bounded, but the public API has no authentication or request-rate controls.
- **Public image directory:** the legacy `/detection_results` static mount is disabled by default. Do not set `CARBOSYNC_SERVE_DETECTION_RESULTS=1` on a public service; that directory can contain uploaded source images and would be publicly readable.
- **Dependency reproducibility:** Ultralytics is pinned, but Torch is resolved for the host platform. Record and validate the actual Render runtime rather than assuming it matches the laptop.

Until authentication, the model provisioning path, persistent storage, and a production build smoke test are verified, the project is **not deployment-ready for public or personal data**. A restricted synthetic-data demonstration can be considered only after a private deployment and permissions review.
