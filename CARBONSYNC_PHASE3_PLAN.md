# CarbonSync Phase 3 — Real-Data Validation Preparation

**Prepared:** 2026-10-16  
**Purpose:** Beginner-friendly instructions for collecting and annotating real parking images, validating the dataset, and running the existing fixed-configuration evaluator. No model tuning or accuracy claims are part of this phase.

## Current state and workspace findings

- The current branch remains `main`. Pre-existing local changes and untracked files were preserved; no branch/history or dependency operations were performed.
- The existing test-image directory contains only three 640×640 black placeholder images (`Test1.jpg`, `Test2.jpg`, `Test3.jpg`). They are not parking data and must not be included in an accuracy evaluation.
- `detection_results/` contains a few real-looking parking images, previous inference outputs, and count JSON. The original images have no complete human annotations or capture-session provenance. A related `cv1` image variant is a probable near-duplicate. These files remain unscored and are not promoted as evaluation data.
- There is no populated `evaluation_data/` dataset. It is Git-ignored for local images, labels, and reports.
- The evaluator uses COCO bounding boxes and current detector configuration only. It does not tune or accept a model/confidence override. It now has `--validate-only`, which validates the dataset without importing/loading the detector. Every image must explicitly say `annotation_complete: true`, so a missing annotation cannot silently be treated as a true empty image.

## 1. Collecting a suitable parking-image sample

1. Obtain authorization from the campus/site owner before capturing or using images. Avoid public-road capture where possible. Follow applicable privacy, security, and retention rules; restrict access to raw image files and do not put them in Git.
2. Capture genuine images from the actual intended camera/viewpoints and target operating conditions. Include varied parking densities, empty lots, different capture sessions, shadows/glare, small vehicles, vehicle-edge crops, occlusion, and close car/motorcycle pairs. Do not collect only clear, full cars.
3. Preserve each original image byte-for-byte. Do not save an annotated image over the original. Keep a non-sensitive stable image ID and the original image SHA-256 in a separate secure collection log if needed.
4. Record site/zone ID, capture session ID (camera/session/date range, not a person's identity), capture date/time, resolution, view type, and permission/source record. Use the least sensitive metadata that still enables grouping and provenance.
5. Include true empty parking images, but only mark them exhaustively annotated after a human has reviewed the full image and confirmed there are no visible supported vehicles. An unreviewed or partly reviewed image is not an empty ground-truth image.
6. Aim for adequate examples of every class the demo will claim to detect. An evaluation set with only cars cannot support a motorcycle recall claim. Collect multiple independent sessions and sites where possible so one burst or one parking lot does not dominate.

### Local Windows folder layout

From the repository root, create the local-only folders:

```powershell
New-Item -ItemType Directory -Force .\evaluation_data\images | Out-Null
New-Item -ItemType Directory -Force .\evaluation_data\reports | Out-Null
```

Copy only authorized original images into `evaluation_data\images\`. The directory is ignored by Git. Before annotation, verify that files are the originals you intended to evaluate:

```powershell
Get-ChildItem .\evaluation_data\images -File |
  Get-FileHash -Algorithm SHA256 |
  Select-Object Path, Hash
```

## 2. Human annotation in COCO format

Use a bounding-box annotation tool that can export COCO object-detection JSON (for example, a COCO-capable CVAT project). Export labels, then enrich the COCO `images` records with the project fields listed below; common exports do not preserve all project-specific metadata. Keep the exported COCO file under the ignored `evaluation_data\` directory.

The schema is documented in [evaluation/parking_annotations.example.json](C:/Users/yasha/OneDrive/Documents/Trace_Twin/evaluation/parking_annotations.example.json). It intentionally contains no images or labels. For every `images[]` record, provide:

- `id`: unique JSON string or number within this dataset.
- `image_identifier`: stable, non-sensitive identifier for a human-readable report.
- `file_name`: path relative to `evaluation_data\images\` (do not use absolute paths or `..`).
- `width`, `height`: actual pixel dimensions; the validator checks them against the file.
- `split`: exactly `development` or `evaluation`.
- `annotation_complete`: exactly `true` only after a human reviewed the entire image and labeled every visible supported vehicle. This is required even for a genuinely empty image.
- `capture_session_id` or `location_id`: non-sensitive split group identifier.
- `annotation_provenance`: nonempty `annotator`, `source`, `annotated_at`, and `guideline_version` fields. Use an annotator ID, not a personal name.

The COCO `categories[]` names supported are `car`, `motorcycle` (alias `motorbike` accepted), `bicycle` (alias `bike` accepted), `bus`, and `truck`. Each annotation uses `[x, y, width, height]` in pixels, with positive width/height and coordinates within the original image. Image dimensions and IDs must match. Do not invent counts or draw labels from model boxes and then call them ground truth.

### Consistent box rules

- Use one tight, axis-aligned box per visible physical vehicle. Include partly occluded instances only when the visible evidence is sufficient to identify the class; draw the box around the visible vehicle extent.
- Separate cars and motorcycles. Label bicycles, buses/shuttles, and trucks where visible and identifiable. Do not infer powertrain, occupancy, commuter status, or travel activity.
- Resolve ambiguous class assignments with a second reviewer before marking an image complete. If ambiguity cannot be resolved, keep the image outside the scored dataset until adjudicated; do not label it as an empty image.
- Preserve genuinely empty images with an `images[]` record, `annotation_complete: true`, and no `annotations[]` rows for that image.
- Have a second reviewer inspect all difficult images and a sample of ordinary images. Keep annotation guideline version and adjudication notes in the secure annotation log or COCO metadata.

## 3. Development/reference data versus held-out evaluation

Keep these uses separate:

| Data group | Use | May inform detector changes? | May support final reported metrics? |
|---|---|---:|---:|
| Training data (only if future fine-tuning is approved) | Fit new model weights | Yes | No; never evaluate on training images. |
| Development/reference data | Establish annotation examples, find failure modes, and later compare proposed settings | May inform a later tuning phase | No final held-out claim. |
| Final evaluation data | Independent, human-reviewed measure after model/settings are frozen | No | Yes, once, for the declared model/configuration. |

This repository contains no project-specific training annotations and no approved fine-tuned weights. The current configured YOLO11x model is a pretrained baseline. Do not call development/reference images training data unless they were actually used to fit weights.

Assign whole capture sessions to one split. If sessions are unavailable, assign whole locations. Keep burst frames, crops, edited copies, and near-duplicates together. Do not repeatedly inspect evaluation results while adjusting confidence, IoU, image size, NMS, weights, or preprocessing. The validator rejects a group crossing splits and exact file duplicates across splits; it warns about likely near-duplicates for human review. A warning must be resolved before final scoring.

## 4. Validate annotations and images first

Run from the repository root. This checks the complete COCO file and all image files without loading YOLO or producing accuracy metrics:

```powershell
py -3.11 .\tools\evaluate_vehicle_detections.py `
  --annotations .\evaluation_data\parking_annotations.coco.json `
  --images .\evaluation_data\images `
  --validate-only
```

Validation checks required arrays and metadata, duplicate image/category/annotation IDs, supported class labels, annotation image/category references, finite positive in-bounds COCO boxes, missing/unreadable image files, declared-versus-actual dimensions, safe relative image paths, split group leakage, exact duplicate images, and likely near-duplicates. If it fails, fix the dataset export/metadata and rerun validation. If it prints near-duplicate warnings, review those images and keep any related captures in one split before proceeding.

The validation summary reports image and annotation totals, split counts, class distribution, and warnings. It does not calculate detector performance.

## 5. Run reproducible evaluation

The evaluator uses the existing configuration from `backend/vehicle_detection.py` and reports its loaded model metadata. At Phase 2 the configured defaults were:

- Model: `backend/models/yolo11x.pt` (deterministic project-root resolution; `CARBOSYNC_YOLO_MODEL_PATH` may name another explicit local path).
- Confidence `0.15`, IoU `0.30`, image size `1280`, class-aware NMS, CPU.
- The model hash and installed Python/Ultralytics/Torch versions are written into each metrics report. Confirm the hash matches the intended frozen model before interpreting results.

No evaluator flag changes those settings. Do not run the final split until the model file and environment are fixed. The evaluator CLI requires the actual argument names `--annotations`, `--images`, `--split`, and `--output`:

```powershell
py -3.11 .\tools\evaluate_vehicle_detections.py `
  --annotations .\evaluation_data\parking_annotations.coco.json `
  --images .\evaluation_data\images `
  --split development `
  --output .\evaluation_data\reports\development.json

py -3.11 .\tools\evaluate_vehicle_detections.py `
  --annotations .\evaluation_data\parking_annotations.coco.json `
  --images .\evaluation_data\images `
  --split evaluation `
  --output .\evaluation_data\reports\evaluation.json
```

The tool evaluates only images with COCO annotations and `annotation_complete: true`; it never falls back to test placeholders, mock boxes, or unannotated predictions. A true empty image is a labeled image record with explicit complete-review metadata and zero vehicle annotations. Reports include model hash/runtime/settings, split size, class distribution, one-to-one class-specific matches at IoU 0.5, and image-level error details. Keep the output reports local if their IDs/provenance are sensitive.

## 6. Interpreting results and sample size

- **Precision** = true-positive detections / all predicted detections for that class. Low precision means false detections are common. It is `null` if the model predicted no examples of a class; that is not evidence of good precision.
- **Recall** = true-positive detections / all annotated instances of that class. Low recall means vehicles were missed. It is `null` when the evaluation split contains no ground-truth examples of that class; no class claim is possible.
- **Count error** is predicted count minus annotated count for each image/class. Positive means overcount; negative means undercount. **Mean absolute count error (MAE)** averages the absolute per-image difference, including reviewed empty images.
- **False positives on empty images** counts detections in images a human explicitly confirmed have no supported vehicles. Review them individually; empty images with no complete annotation are rejected rather than scored as empty.
- **Duplicates and misses** are reported separately: a same-class prediction matching a ground-truth box already claimed by a higher-confidence prediction is a duplicate false positive; unmatched ground-truth boxes are misses. Wrong-class predictions become a false positive for the predicted class and a miss for the true class.
- Read results per class and inspect denominators (`ground_truth_instances`, `true_positives`, and `false_positives`), not just a pooled score. The evaluator reports point estimates and does not calculate confidence intervals.

There is no universal image/vehicle count that guarantees a reliable conclusion. A class represented by only a handful of vehicles or a single capture session is too small for a stable class-specific claim: one error can change its metrics substantially, and frames from one session are correlated. Treat fewer than roughly 30 annotated instances of a class across at least 10 independent sessions as an **exploratory screening heuristic only**, not a statistical guarantee. For stronger claims, plan sample size before evaluation and report confidence intervals that account for capture-session clustering. If the interval is broad or crosses the project's pre-agreed acceptance threshold, evidence is inconclusive.

## 7. Demo readiness acceptance criteria

Before describing the detector as ready for a real-data demo:

1. Dataset validation succeeds; every scored image has complete human annotation and provenance; no unresolved split-leakage or near-duplicate warning remains.
2. The evaluation split is representative of the actual demo view and includes true empty scenes, cars, motorcycles, and the other classes the demo will claim to detect across multiple sessions. Classes absent from ground truth are explicitly “not evaluated.”
3. The evaluation report's weight hash and runtime/settings match the frozen intended configuration. The held-out set has not been used to change that configuration.
4. Review per-class precision/recall, count MAE, empty-image false positives, duplicates, and misses against acceptance thresholds agreed before viewing final results. The thresholds must reflect the demo's risk (e.g. whether an incorrect vehicle count would be shown as fact); this repository does not set or validate those thresholds.
5. If per-class denominators are small, sessions are not diverse, or uncertainty is too wide, label the demo output as experimental and do not make accuracy claims. A successful software smoke test alone is not a readiness decision.
6. Demonstrate the live UI clearly labels actual inference status and does not mix mock/simulated output with measured detections.

## 8. Remaining limitations and evidence needed

- No suitable COCO annotations or capture provenance exist yet, so no real precision, recall, count MAE, empty-image false-positive rate, or demo accuracy conclusion is available.
- The source images' permission, privacy status, capture context, and representativeness have not been verified. The existing `detection_results` examples are not approved as an evaluation set.
- The average-hash near-duplicate check is a warning aid, not a complete near-duplicate detector; session/location metadata and manual review remain necessary.
- Matching uses confidence-ordered greedy one-to-one matching at IoU 0.5; this is not COCO mAP. Confidence intervals are not generated by the current script.
- Detection accuracy on top-down/overhead parking images, especially motorcycle recall and close-vehicle duplicate behavior, remains unverified.
- Evaluation metrics measure boxes against human labels, not the emissions model. An image does not establish daily commuters, image coverage, travel distance, operating days, occupancy, fuel/powertrain, or annual emissions. Existing emission factors remain unverified and unchanged.

## 9. Files changed and checks

Phase 3 changes are limited to `CARBONSYNC_PHASE3_PLAN.md`, `tools/evaluate_vehicle_detections.py` (`--validate-only` and stricter complete-annotation/COCO checks), `evaluation/parking_annotations.example.json` (schema requirements), and `tests/test_detection_evaluation.py` (dataset validation regression cases). Existing changes to model weights/configuration, detector thresholds, emissions factors/formulas, frontend, and unrelated files are preserved.

Validation commands and test outcomes are reported in the task completion message. No real-data metrics will be reported until approved image data and complete annotations are supplied.
