# CarboSync Project Context

This is a short handoff for contributors. `BACKEND.md` is the single current API contract.

## Product intent

The PRD describes a campus commute-emissions platform. The repository implements the B1–B3 assessment/calculation foundation and a separate judges' demo backend for snapshot detection, illustrative estimates, scenario simulations, persistence, and optional guarded recommendations. Frontend and human review remain unimplemented.

## Current implementation facts

- `backend/main.py` implements `GET /health`, assessment creation/retrieval, and commute calculation.
- `backend/carbon_engine.py` calculates direct tailpipe CO2 deterministically using `daily vehicles × one-way km × 2 × annual days × kg CO2/veh-km`.
- `backend/database.py` persists assessment metadata and JSON input/result snapshots in SQLite. `CARBOSYNC_DATABASE_PATH` selects a database; otherwise the development file is repository-root `carbosync.db`.
- `backend/factor_registry.py` contains an immutable, empty approved-factor registry. Approved calculations return a safe unavailable response until owner-approved records with review evidence are supplied.
- Candidate calculations require explicit `calculation_mode: "candidate"` and `candidate_factor`; they are labeled unapproved and do not alter the registry.
- New calculations require separate provenance for daily vehicle counts, one-way distance, and annual days. Provenance checks completeness and format; it does not prove truth or representativeness.
- New calculations use backend method identifier `commute_tailpipe_co2_v1`. Legacy B2 snapshots are not rewritten; retrieval identifies unavailable B3 metadata.
- The latest test commands and observed counts are recorded in `STATUS.md`.
- The separate demo API is POST /api/demo/analyze and GET /api/demo/analyses/{analysis_id}. It uses illustrative factors from explicit request assumptions, never the approved registry.

## Boundaries to preserve

- A parking image is a point-in-time observation, not daily arrivals, unique commuters, or annual activity. No conversion is implemented.
- Occupancy remains required by the request but is unused in the current formula.
- `sample_size` and `population_total` do not trigger extrapolation. `is_campus_projection` remains false.
- Direct tailpipe CO2 is distinct from CO2e, lifecycle emissions, and passenger-kilometre factors.
- `0.150 kg CO2/veh-km` is a test fixture. `0.145` remains an unverified candidate. Neither is approved.
- Fuel/powertrain is not provided in the activity request. The API checks vehicle category only and makes no fuel/powertrain compatibility claim.
- No student names, IDs, exact addresses, or raw attendance records should be collected or persisted.

## Working rules

- Keep implemented, tested, proposed, and unresolved claims separate.
- Coordinate future API contract changes with consumers, but do not treat old mock payloads as live schemas.
- The project owner is responsible for approving factors and recording review evidence.
- The demo includes a lazy YOLO11n detector for COCO classes. Local model weights and runtime setup are required; there are no included weights and no automatic download. A parking image remains a point-in-time count only.
- Demo estimates and all three scenarios are explicitly illustrative. They require activity, factor, and scenario assumptions; no values are silently selected. Images are not persisted or sent to the LLM.
- Demo recommendations use an optional OpenAI-compatible provider and otherwise return deterministic fallback content. The API key is environment-only and is not persisted.
- Institutional authorization for student-register access and external data-provider permissions remain unverified; current B3 does not integrate those systems.
- Do not start later product features without explicit authorization.
