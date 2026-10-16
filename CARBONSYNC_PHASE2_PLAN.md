# CarbonSync Phase 2 — Detection Evaluation and Emissions Engine Audit

**Prepared:** 2026-10-16  
**Branch:** `main` (`480bdb8`)  
**Scope:** Reproducible detector evaluation workflow, evidence-based calculation audit, and narrowly scoped input validation fix. No detector thresholds or weights were changed.

## Executive findings

- There is no suitable manually annotated parking-image dataset in the workspace. Existing parking photos are unlabelled, and the three `test_images/Test1.jpg`–`Test3.jpg` assets are 640×640 black placeholder images containing only their filenames. Existing detection-result images are predictions/annotated outputs, not ground truth. Accuracy is therefore unmeasured.
- A minimal evaluation workflow was added at `tools/evaluate_vehicle_detections.py`. It reads COCO bounding-box annotations with split/provenance metadata, uses the configured detector unchanged, checks exact and likely near-duplicate cross-split images, and reports one-to-one class-specific metrics at IoU 0.5. Example JSON contains no fabricated images or labels.
- No literal `22.97` appears in the source tree, and the local `carbosync.db` has zero commute calculations and zero demo analyses. Its exact historical input values cannot be recovered from this workspace. The current B3 formula that could have produced a user-entered number is documented below.
- A separate static mock shows `24.62 t/year`, but its listed category totals sum to `23.94504 t/year` (`23.95` rounded), so that mock total is internally inconsistent and is not the origin of a verifiable `22.97` result.
- Demo shuttle arithmetic includes added shuttle emissions and can report a negative scenario reduction. Baseline-zero percentage is `null`, avoiding division by zero. However, the legacy assessment `/simulate` route uses ungrounded percentage shortcuts and a fixed `11.9 t/year` shuttle add-on; it is not used by the current frontend adapter, which calls `/api/demo/analyze` in explicit simulated mode.
- The demo calculation accepted a zero route distance despite positive trips and also accepted zero commute distance with positive activity. These cases produce impossible zero-distance emissions. They now fail validation while zero-distance placeholders remain allowed when trips are zero.

## 1. Workspace preservation and evidence boundary

At inspection, the current branch was `main` at `480bdb8`; recent history includes `4fdcb56` and `f06c7cd`. The working tree already contained modified files and untracked audit, snapshot, image, and test assets. They were preserved. No branch operation, install, commit, push, reset, stash, or cleanup was performed. The fetched `github-backend-snapshot/` was inspected as a snapshot only and left untouched.

The current local detector uses `backend/models/yolo11x.pt`; Phase 1 configured confidence `0.15`, IoU `0.30`, image size `1280`, class-aware NMS, CPU inference, and a SHA-256 model identity. No inference settings or weights were changed in Phase 2.

## 2. Available images and evaluation suitability

| Assets | Observed contents | Evaluation suitability |
|---|---|---|
| `test_images/Test1.jpg`, `Test2.jpg`, `Test3.jpg` | 640×640 black images with only a filename rendered | Not usable for vehicle accuracy; keep as existing smoke fixtures only. |
| `detection_results/cv1_original.jpg` | 331×220 parking scene with several cars and a small road user | Potential pilot annotation image, but low resolution and source/capture provenance is missing. Not a held-out evaluation record yet. |
| `detection_results/cv2_original.jpg` | 547×300 overhead parking area with multiple cars | Potential pilot annotation image; no source/capture provenance or labels. |
| `detection_results/*detected.jpg`, `*counts.json` | Existing detector results and rendered output | Not ground truth; cannot be used to score the same detector. |
| `detection_results/cv1_original_original.jpg` | Visually related version of the `cv1` parking scene | Treat as a likely near-duplicate; keep any related versions in one split. |

Exact-byte hashes differ across available photos, but the available examples are too few and provenance is insufficient to assign a defensible development/evaluation split. No images were copied, edited, or committed. `/evaluation_data/`, `/test_images/`, and `/detection_results/` are ignored by Git so private/local image assets stay out of future commits by default; existing files remain on disk.

## 3. Annotation and evaluation workflow

### Annotation format

Use COCO object-detection JSON. `evaluation/parking_annotations.example.json` documents the base structure and classes: `car`, `motorcycle`, `bicycle`, `bus`, and `truck`. Each `images[]` record must also include:

```json
{
  "id": "unique-image-id",
  "image_identifier": "stable non-sensitive identifier",
  "file_name": "image-file.jpg",
  "width": 1600,
  "height": 900,
  "split": "development",
  "location_id": "site-or-zone-id",
  "capture_session_id": "date-camera-session-id",
  "annotation_provenance": {
    "annotator": "annotator-id",
    "source": "CVAT COCO export plus reviewed metadata",
    "annotated_at": "2026-10-16",
    "guideline_version": "parking-boxes-v1"
  }
}
```

COCO `annotations[].bbox` values are pixel `[x, y, width, height]` boxes; category IDs map through `categories[]`. Preserve images with no vehicles by including an image entry and no annotation entries. CVAT/another box annotator may be used, but merge the required split, site/session, stable ID, and annotation-provenance fields into its COCO export. Avoid real names in annotator metadata; use IDs. The committed example is schema-only and contains no invented annotations.

### Annotation rules

1. Draw one tight axis-aligned box for each visible vehicle instance. Include partially occluded vehicles when a reviewer can confidently identify the supported class; box the visible extent and annotate the instance once.
2. Label cars and motorcycles separately. Use `bicycle` for pedal cycles, `bus` for buses/shuttles, and `truck` for trucks. Do not infer fuel, occupancy, trip purpose, or whether a parked vehicle belongs to a commuter.
3. If class identity cannot be resolved by review, do not force a label. Record the ambiguity in the annotation notes and exclude that image from scored metrics until adjudicated; retain it in a separate difficult-image pool.
4. Include empty parking images and difficult conditions: dense/overlapping stalls, shadows, glare, small objects, occlusion, image edges, unusual vehicle orientations, and motorcycles near cars.
5. Have a second reviewer adjudicate ambiguous labels and a sample of boxes. Keep the source file/image hash, annotator ID, annotation date, guideline version, and any adjudication note with the record.

### Dataset split policy

- First assign entire capture sessions to development or held-out evaluation. If session IDs are unavailable, split by location. Never split adjacent frames or crops from one original capture across splits.
- The evaluator rejects a shared session/location group across splits, rejects exact-image hashes crossing splits, and warns when an 8×8 average-hash distance is at most 4/64. Manually review warnings and keep near-duplicates together.
- Use development images to inspect errors and, in a later explicitly approved tuning phase, select settings. Freeze model hash and inference settings before running the held-out evaluation set. Do not use held-out metrics to tune and then report those same metrics as final performance.
- Keep original/private images under ignored `evaluation_data/`; share only approved, de-identified images and annotations.

### Running the evaluator

1. Put original images under a local directory such as `evaluation_data/images/` and prepare `evaluation_data/parking_annotations.coco.json` in the format above.
2. Keep image file names relative to the `--images` root and ensure COCO width/height match the actual files.
3. Run each split separately from the repository root:

```powershell
py -3.11 tools/evaluate_vehicle_detections.py `
  --annotations evaluation_data/parking_annotations.coco.json `
  --images evaluation_data/images `
  --split development `
  --output evaluation_data/reports/development.json

py -3.11 tools/evaluate_vehicle_detections.py `
  --annotations evaluation_data/parking_annotations.coco.json `
  --images evaluation_data/images `
  --split evaluation `
  --output evaluation_data/reports/evaluation.json
```

The evaluator uses the single existing model configuration; it provides no threshold or model override. The JSON records model hash, runtime versions, inference settings, IoU threshold, split sizes, class distribution, per-class precision/recall, mean absolute count error per image, false positives on empty images, false positives/duplicates, and missed detections. A metric with a zero denominator is `null`. Reports contain image IDs and provenance, not copies of the image bytes.

### Current evaluation status

The evaluator implementation was unit-tested on deterministic synthetic boxes only. These tests verify the metric code, not YOLO accuracy. Since there are no real annotations, no measured precision, recall, count error, duplicate rate, or false-positive rate is reported. Real-model accuracy remains unmeasured until reviewed labels are supplied.

## 4. Exact emissions calculation trace and `22.97 t/year`

### B3 commute endpoint

`POST /api/assessments/{assessment_id}/commute` (see `backend/main.py`, `CandidateModeInput`, and `calculate_commute_inputs`) calculates each category as:

```text
annual vehicle-km/category
  = daily vehicles [vehicles/day]
    × one-way distance [km/one-way trip]
    × 2 [one-way legs/commute cycle]
    × annual operating days [days/year]

annual kg CO2/category
  = annual vehicle-km × factor [kg CO2/vehicle-km]
annual tonnes CO2 = annual kg CO2 / 1000
```

The endpoint requires the caller to provide daily vehicle counts, one-way distances, annual days, factor provenance or an approved factor reference, plus occupancy and a sample size. Occupancy and sample size are stored but do not affect the vehicle-km calculation. `population_total` is also metadata, not an expansion multiplier. The result sets `is_campus_projection: false`. Thus the endpoint does not derive daily activity from an image; users can enter an activity estimate, but it must not be conflated with a snapshot count.

The local frontend's candidate factor values are `0.145` car, `0.035` motorcycle, `0.850` bus, and `0.078 kg CO2/vehicle-km` for the other fuel-burning category. They are explicitly unverified demo candidates; provenance text supplied by a caller is not independent evidence. `backend/factor_registry.py` is deliberately empty, so approved mode currently has no approved production factors. The records omit reviewed fuel/powertrain compatibility. Treat every value as provisional; no factor can be called scientifically validated based on this repository.

### Demo image endpoint

`POST /api/demo/analyze` calls `backend/demo_calculations.py`. For each motor-vehicle class it uses the detection count from that image and then assumes the request's commute cycles per vehicle per operating day, one-way distance, roundtrip multiplier, annual operating days, and illustrative factor. It does not infer daily traffic, unique commuters, image coverage, fuel, powertrain, or occupancy from the image. The frontend's first upload currently uses `trips_per_vehicle_per_operating_day = 0` as a temporary placeholder while detections are reviewed; scenarios later use explicit simulated activity counts and set trips to one. Bicycles are not included in tailpipe motor emissions.

`22.97` is not present as a literal in the current source, nor can it be found in the local database: `carbosync.db` contains zero commute calculations and zero demo analyses. Therefore the specific prior value is unverified and its exact inputs cannot be reconstructed here. If it came from a real B3 request, it was the sum over four user-entered categories of `daily_vehicles × one-way_km × 2 × annual_days × factor / 1000`; the request values and saved output are needed to prove the result. If it came from the legacy simulation endpoint, its baseline was the latest persisted commute result or a hard-coded fallback of 45 t/year, not an image-derived calculation.

The frontend mock baseline is not a source for `22.97`: it displays `24.62`, while its own four line items calculate to 12,342.4 + 3,542 + 6,120 + 1,940.64 = **23,945.04 kg = 23.94504 t/year**, not 24.62. This is static mock data and must not be shown as an actual calculation.

## 5. Scenario formula audit

| Scenario path | Current behavior | Audit result |
|---|---|---|
| Demo baseline | Each supplied vehicle count × assumed trip cycles × distance × 2 × days × class factor | Unit-consistent as an illustrative vehicle-activity formula. Snapshot count is not measured daily volume; image coverage is not modeled. |
| Carpool | Reduces assumed car activity by `carpool_activity_reduction_share` | Numerical emissions are recalculated. It does not use occupancy or prove fewer vehicle trips; the frontend occupancy control does not affect this calculation. |
| Active travel | Reduces car/motorcycle activity at/below the supplied distance limit | Numerical tailpipe emissions recalculate; only distance eligibility is applied. No life-cycle walking/cycling emissions are included. |
| Demo shuttle | Removes the assumed car/motorcycle share, calculates supplied shuttle vehicle trips × one-way route × 2 × days × bus factor, then adds that emissions quantity to the remaining private modes | Shuttle emissions are included; `reduction_vs_baseline` can be negative. Baseline-zero percentages are `null`, not divided by zero. No route capacity or displaced-rider evidence exists. |
| Legacy `/api/assessments/{id}/simulate` | Uses arbitrary 80%/40%/50% savings coefficients and fixed `11.9 t/year` added shuttle emissions | Not a physical activity model; no shuttle distance/vehicle-km factor. It can mislead if called. Current frontend adapter uses `/api/demo/analyze`, but this legacy route remains in local `backend/main.py`. |

All demo factors and scenario inputs remain explicitly unapproved/illustrative. The backend uses numerical scenario results, not LLM-generated savings, for its demo calculation. The LLM receives already calculated numbers for narrative recommendations. No verified campus inventory or policy effect is established.

### Focused calculation defect fixed

`backend/demo_calculations.py` previously permitted zero commute distance when a category had positive vehicle count and positive estimated trips, and zero shuttle route distance while shuttle vehicles/trips were active. Both silently produce zero emissions. It now rejects these inconsistent active-distance assumptions. Zero distance remains allowed when trips are zero, preserving the image-upload placeholder flow. Three deterministic tests cover the behavior. No factor, trip, count, or scenario formula was otherwise changed.

## 6. Files changed in this phase

- `tools/evaluate_vehicle_detections.py` — COCO metadata validation, safe image path handling, split leakage checks, average-hash near-duplicate warnings, inference using existing settings, and one-to-one class-specific metrics at IoU 0.5.
- `evaluation/parking_annotations.example.json` — schema-only example; no images or invented labels.
- `tests/test_detection_evaluation.py` — deterministic precision/recall, count-error, duplicate, class-error, empty-image, and threshold validation tests.
- `backend/demo_calculations.py` and `tests/test_demo_api.py` — conditional rejection of zero distances when active trips are estimated, preserving zero-activity placeholders.
- `.gitignore` — ignores local evaluation data and the existing local test/detection image directories to reduce accidental image commits. Existing image files were not removed.
- `CARBONSYNC_PHASE2_PLAN.md` — this audit, workflow instructions, findings, proposed follow-up, and acceptance criteria.

No frontend redesign, LLM integration, detector tuning, dependency change, or weight change was made.

## 7. Proposed next implementation steps

1. Collect an approved, privacy-reviewed sample of parking images spanning locations, capture sessions, times, vehicle density, weather/lighting, empty lots, and difficult overlaps. Record how the image sample represents the target campus activity.
2. Annotate cars/motorcycles separately and include practical counts of bicycles, buses, and trucks. Have a second reviewer adjudicate a subset. Add provenance and group-level split assignments before running any metrics.
3. Run development evaluation and inspect per-image false positives, misses, duplicates, class confusions, and count error. Keep the held-out split untouched during any tuning.
4. Freeze the model hash/settings and run the held-out evaluation once. Report sample sizes and uncertainty alongside the per-class metrics; do not claim general campus performance from a small or unrepresentative set.
5. Separately obtain authoritative, applicable factor sources and project-owner approval. Add image coverage/sample expansion, daily vehicle activity, commute distance, operating days, category/powertrain, and provenance as distinct inputs before describing outputs as annual emissions.
6. Replace or retire the legacy fixed-coefficient `/simulate` route in a later scoped task; preserve existing API consumers until the route contract is checked.

## 8. Tests and acceptance criteria

### Detection evaluation

- Test one-to-one matching so a ground-truth vehicle cannot create multiple true positives.
- Test duplicate detections, missed detections, wrong-class boxes, empty-image false positives, class counts, and null precision/recall denominators.
- Test invalid COCO dimensions, unsupported categories, missing provenance/split, unsafe paths, exact cross-split duplicates, and shared capture/location groups.
- Acceptance: identical annotations/predictions and frozen model/config yield the same metrics; every report identifies data split, IoU=0.5, model hash, runtime, and all inference settings; no real performance result is emitted without annotations.

### Emissions and scenarios

- Positive estimated activity with zero distance is rejected; zero-activity placeholders remain valid.
- Active shuttle trips with zero route distance are rejected.
- Test shuttle emissions greater than displaced private emissions produce negative shuttle savings and net positive emissions change.
- Test zero baseline returns no percentage (not NaN/Infinity), and all units remain vehicle-km/year, kg CO2/year, and tonnes CO2/year.
- Acceptance: every factor snapshot states value, units, category, source/provenance, year/geographic scope when known, tailpipe CO2 versus CO2e, and approval status; missing/unverified assumptions remain disclosed.

Final verification during this task: `py -3.11 -m unittest discover -s tests -v` passed all 79 tests; `py -3.11 -m unittest -v test_vehicle_detection` passed all 4 tests; all frontend JavaScript syntax checks and Python byte-compilation checks passed. `git diff --check` still reports an inherited trailing blank line in the pre-existing modified `backend/main.py` and line-ending warnings in previously modified frontend files. No real annotated evaluation was run.

## 9. Risks and unresolved assumptions

- The available actual images may be copyrighted, sensitive, or too low resolution; provenance and permission need confirmation before they become an evaluation set.
- The COCO annotation schema stores split and provenance as additional image-record fields; annotator exports need metadata enrichment and validation.
- Average-hash alerts are a review aid, not a guarantee against near-duplicate leakage. Session/location grouping and human review remain required.
- The current one-to-one matching uses confidence-ordered greedy matching per class. This is transparent and reproducible for the requested IoU=0.5 count/precision/recall metrics, but is not a complete COCO mAP evaluator.
- CO2 factors do not include sources, fuel/powertrain match, or approval. The current factor registry is empty. Do not present annual results as independently verified or as CO2e.
- The exact origin of the prior `22.97 t/year` value is not verifiable from the current database/source; the original request payload or screenshot/history would be needed.
- Detector settings remain experimental. Potential confidence, image-size, NMS, tiling, or model changes belong in a later development-only experiment and must be measured on labels before held-out evaluation.

## 10. Five highest-priority follow-up problems

1. No approved annotated parking-image dataset; detector precision/recall/count error are unknown.
2. Snapshot counts can be mistaken for daily travel activity; image coverage and activity expansion are absent.
3. Candidate emission factors have no independently verified source/applicability and the approved registry is empty.
4. Legacy assessment simulation uses arbitrary percentage savings and a fixed shuttle amount rather than route/service vehicle-km.
5. Current image review and annotation provenance are not persisted as a reviewed evaluation dataset; split leakage controls need human governance as well as tooling.

The safest next phase is data collection and annotation governance, followed by frozen-baseline evaluation. Do not tune on the held-out evaluation split or make annual emissions claims until activity and factor provenance are separately established.
