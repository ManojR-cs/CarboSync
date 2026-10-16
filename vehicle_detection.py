"""CLI smoke runner that uses the same detector configuration as the API."""

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime
from pathlib import Path

from backend.vehicle_detection import (
    DetectionFailed,
    DetectionUnavailable,
    ImageInputError,
    detect_vehicle_image,
    validate_image_bytes,
)


OUTPUT_FOLDER = Path("detection_results")
MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
REPORT_NAMES = {
    "bicycle": "Bicycle",
    "car": "Car",
    "motorcycle": "Motorcycle",
    "bus": "Bus",
    "truck": "Truck",
}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage:")
        print("python vehicle_detection.py test_images/Test1.jpg")
        return 1

    image_path = Path(sys.argv[1]).expanduser().resolve()
    if not image_path.is_file():
        print(f"ERROR: Image not found: {image_path}")
        return 1
    mime_type = MIME_TYPES.get(image_path.suffix.lower())
    if not mime_type:
        print("ERROR: Image must be JPEG, PNG, or WebP.")
        return 1

    try:
        validated = validate_image_bytes(image_path.read_bytes(), mime_type)
        result = detect_vehicle_image(validated.image)
    except (ImageInputError, DetectionUnavailable, DetectionFailed) as exc:
        print(f"ERROR: {exc}")
        return 2

    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    output_image = OUTPUT_FOLDER / f"{image_path.stem}_detected.jpg"
    encoded_image = result.annotated_image_data_uri.partition(",")[2]
    try:
        output_image.write_bytes(base64.b64decode(encoded_image, validate=True))
    except (ValueError, OSError):
        print("ERROR: Could not save annotated image.")
        return 2

    counts = {REPORT_NAMES[name]: result.counts[name] for name in REPORT_NAMES}
    report = {
        "project": "CarbonSync",
        "model": result.model,
        "model_metadata": result.metadata,
        "image": image_path.name,
        "inference_status": result.inference_status,
        "confidence_threshold": result.confidence_threshold,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "counts": counts,
        "motor_vehicle_total": sum(counts[name] for name in ("Car", "Motorcycle", "Bus", "Truck")),
        "bicycle_total": counts["Bicycle"],
        "all_selected_objects": sum(counts.values()),
        "detections": result.detections,
        "note": "Single-image detections are not traffic-flow counts or annual emissions.",
    }
    output_json = OUTPUT_FOLDER / f"{image_path.stem}_counts.json"
    try:
        output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError:
        print("ERROR: Could not save detection report.")
        return 2

    print(f"Inference status: {result.inference_status}")
    print(f"Model: {result.model} (SHA-256 {result.metadata['weights_sha256']})")
    for name, count in counts.items():
        print(f"{name}: {count}")
    print(f"Annotated image saved: {output_image}")
    print(f"Detection report saved: {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
