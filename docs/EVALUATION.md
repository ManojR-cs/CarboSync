# Image evaluation tooling

The optional evaluation tool computes class-specific detections against a manually annotated COCO-style dataset. No image dataset or accuracy result is included in this repository; `evaluation/parking_annotations.example.json` is an empty schema example, not valid evaluation evidence.

Prepare a held-out, fully reviewed dataset and keep images and annotations out of public Git if they contain identifiable people, license plates, or location details. The evaluator validates annotation completeness, image files, class IDs, split metadata, duplicate/capture-session leakage, and box dimensions before inference. It uses the configured detector unchanged and requires the optional YOLO runtime and model weights.

Validate a dataset without loading the model:

```powershell
\.venv\Scripts\python.exe tools/evaluate_vehicle_detections.py `
  --annotations path/to/annotations.json `
  --images path/to/images `
  --validate-only
```

Run evaluation after validation by omitting `--validate-only`. The evaluator writes its report under the chosen output path; do not interpret metrics from an unrepresentative sample as campus-wide accuracy.
