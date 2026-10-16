"""Run reproducible vehicle detection evaluation against COCO JSON labels.

This tool uses the configured detector unchanged. It does not expose threshold
or model overrides; evaluation datasets should remain held out from tuning.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLASSES = ("car", "motorcycle", "bicycle", "bus", "truck")
ALIASES = {
    "car": "car",
    "motorcycle": "motorcycle",
    "motorbike": "motorcycle",
    "bike": "bicycle",
    "bicycle": "bicycle",
    "bus": "bus",
    "truck": "truck",
}


def canonical_class(name: object) -> str:
    normalized = str(name).strip().lower().replace("_", " ")
    if normalized not in ALIASES:
        raise ValueError(f"Unsupported annotation class: {name!r}")
    return ALIASES[normalized]


def box_iou(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


def _validate_box(box: object, label: str) -> tuple[float, float, float, float]:
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise ValueError(f"{label} must contain four coordinates")
    values = tuple(float(value) for value in box)
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{label} coordinates must be finite")
    if values[2] <= values[0] or values[3] <= values[1]:
        raise ValueError(f"{label} must have positive width and height")
    return values  # type: ignore[return-value]


def evaluate_records(
    ground_truth: dict[str, list[dict[str, Any]]],
    predictions: dict[str, list[dict[str, Any]]],
    *,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Greedily match predictions by descending confidence, one GT per box.

    Matching is class-specific. A same-class prediction overlapping a GT that
    is already matched is counted as a duplicate false positive.
    """
    if not math.isfinite(iou_threshold) or not 0 < iou_threshold <= 1:
        raise ValueError("IoU threshold must be in (0, 1]")
    image_ids = list(ground_truth)
    total = {name: Counter() for name in CLASSES}
    image_results = []
    empty_image_false_positives = 0
    empty_image_count = 0

    for image_id in image_ids:
        gt_by_class: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
        pred_by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in ground_truth[image_id]:
            category = canonical_class(record["category"])
            gt_by_class[category].append(_validate_box(record["box"], "ground-truth box"))
        for record in predictions.get(image_id, []):
            category = canonical_class(record["category"])
            score = float(record["confidence"])
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("Prediction confidence must be finite and in [0, 1]")
            pred_by_class[category].append({
                "box": _validate_box(record["box"], "prediction box"),
                "confidence": score,
            })

        image_counts = {}
        gt_total = sum(len(items) for items in gt_by_class.values())
        fp_total = 0
        for category in CLASSES:
            truth = gt_by_class[category]
            guesses = sorted(pred_by_class[category], key=lambda item: item["confidence"], reverse=True)
            matched_truth: set[int] = set()
            tp = fp = duplicates = 0
            for prediction in guesses:
                overlaps = [(box_iou(prediction["box"], box), index) for index, box in enumerate(truth)]
                eligible = [(iou, index) for iou, index in overlaps if iou >= iou_threshold]
                unmatched = [(iou, index) for iou, index in eligible if index not in matched_truth]
                if unmatched:
                    _iou, best = max(unmatched)
                    matched_truth.add(best)
                    tp += 1
                else:
                    fp += 1
                    if eligible:
                        duplicates += 1
            fn = len(truth) - tp
            total[category].update(tp=tp, fp=fp, fn=fn, duplicates=duplicates)
            fp_total += fp
            image_counts[category] = {
                "ground_truth": len(truth),
                "predicted": len(guesses),
                "count_error": len(guesses) - len(truth),
                "absolute_count_error": abs(len(guesses) - len(truth)),
            }
        if gt_total == 0:
            empty_image_count += 1
            empty_image_false_positives += fp_total
        image_results.append({
            "image_id": image_id,
            "ground_truth_count": gt_total,
            "prediction_count": sum(len(items) for items in pred_by_class.values()),
            "empty_image": gt_total == 0,
            "false_positives": fp_total,
            "per_class": image_counts,
        })

    per_class = {}
    for category in CLASSES:
        counts = total[category]
        precision_denominator = counts["tp"] + counts["fp"]
        recall_denominator = counts["tp"] + counts["fn"]
        errors = [item["per_class"][category]["absolute_count_error"] for item in image_results]
        per_class[category] = {
            "ground_truth_instances": recall_denominator,
            "true_positives": counts["tp"],
            "false_positives": counts["fp"],
            "false_negatives_missed": counts["fn"],
            "duplicate_false_positives": counts["duplicates"],
            "precision": counts["tp"] / precision_denominator if precision_denominator else None,
            "recall": counts["tp"] / recall_denominator if recall_denominator else None,
            "count_error_sum": sum(item["per_class"][category]["count_error"] for item in image_results),
            "mean_count_error_per_image": (
                sum(item["per_class"][category]["count_error"] for item in image_results) / len(image_results)
                if image_results else None
            ),
            "mean_absolute_count_error_per_image": sum(errors) / len(errors) if errors else None,
        }
    return {
        "iou_threshold": iou_threshold,
        "image_count": len(image_ids),
        "empty_image_count": empty_image_count,
        "false_positives_on_empty_images": empty_image_false_positives,
        "ground_truth_class_distribution": {
            category: total[category]["tp"] + total[category]["fn"] for category in CLASSES
        },
        "per_class": per_class,
        "images": image_results,
    }


def _load_coco(path: Path) -> tuple[dict[str, Any], dict[Any, dict[str, Any]], dict[Any, list[dict[str, Any]]]]:
    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read COCO annotation JSON: {exc}") from exc
    if not isinstance(dataset, dict):
        raise ValueError("Annotation document must be a COCO JSON object")
    images = dataset.get("images")
    categories = dataset.get("categories")
    annotations = dataset.get("annotations")
    if not isinstance(images, list) or not isinstance(categories, list) or not isinstance(annotations, list):
        raise ValueError("COCO JSON requires images, annotations, and categories arrays")
    if not images:
        raise ValueError("Dataset must contain at least one fully reviewed image")
    image_map: dict[Any, dict[str, Any]] = {}
    group_splits: dict[str, str] = {}
    for image in images:
        if not isinstance(image, dict) or "id" not in image:
            raise ValueError("Every image needs an id")
        image_id = image["id"]
        if isinstance(image_id, (dict, list, bool)) or image_id is None:
            raise ValueError("Image ids must be non-null JSON strings or numbers")
        if image_id in image_map:
            raise ValueError(f"Duplicate image id: {image_id}")
        if not isinstance(image.get("image_identifier"), str) or not image["image_identifier"].strip():
            raise ValueError(f"Image {image_id!r} needs a stable image_identifier")
        if (
            not isinstance(image.get("file_name"), str)
            or not image["file_name"].strip()
            or isinstance(image.get("width"), bool)
            or isinstance(image.get("height"), bool)
            or not isinstance(image.get("width"), int)
            or not isinstance(image.get("height"), int)
            or min(image["width"], image["height"]) <= 0
        ):
            raise ValueError(f"Image {image_id!r} needs file_name and positive width/height")
        if image.get("split") not in {"development", "evaluation"}:
            raise ValueError(f"Image {image_id!r} split must be development or evaluation")
        if image.get("annotation_complete") is not True:
            raise ValueError(
                f"Image {image_id!r} must be exhaustively annotated and set annotation_complete=true"
            )
        provenance = image.get("annotation_provenance")
        required_provenance = ("annotator", "source", "annotated_at", "guideline_version")
        if not isinstance(provenance, dict) or any(not str(provenance.get(key, "")).strip() for key in required_provenance):
            raise ValueError(f"Image {image_id!r} needs complete annotation_provenance")
        group = str(image.get("capture_session_id") or image.get("location_id") or "").strip()
        if not group:
            raise ValueError(f"Image {image_id!r} needs capture_session_id or location_id")
        prior_split = group_splits.setdefault(group, image["split"])
        if prior_split != image["split"]:
            raise ValueError(f"Data leakage: capture/location group {group!r} spans splits")
        image_map[image_id] = image

    category_ids: dict[Any, str] = {}
    for category in categories:
        if not isinstance(category, dict) or "id" not in category:
            raise ValueError("Every COCO category needs an id")
        category_id = category["id"]
        if isinstance(category_id, (dict, list, bool)) or category_id is None:
            raise ValueError("Category ids must be non-null JSON strings or numbers")
        if category_id in category_ids:
            raise ValueError(f"Duplicate category id: {category_id}")
        category_ids[category_id] = canonical_class(category.get("name"))

    ground_truth: dict[Any, list[dict[str, Any]]] = {image_id: [] for image_id in image_map}
    annotation_ids: set[Any] = set()
    for annotation in annotations:
        if not isinstance(annotation, dict):
            raise ValueError("Each COCO annotation must be an object")
        if "id" not in annotation:
            raise ValueError("Every COCO annotation needs a unique id")
        annotation_id = annotation["id"]
        if isinstance(annotation_id, (dict, list, bool)) or annotation_id is None:
            raise ValueError("Annotation ids must be non-null JSON strings or numbers")
        if annotation_id in annotation_ids:
            raise ValueError(f"Duplicate annotation id: {annotation_id}")
        annotation_ids.add(annotation_id)
        if annotation.get("image_id") not in image_map:
            raise ValueError(f"Annotation references unknown image {annotation.get('image_id')!r}")
        category_id = annotation.get("category_id")
        if isinstance(category_id, (dict, list, bool)) or category_id is None:
            raise ValueError("Annotation category_id must be a valid COCO category id")
        if category_id not in category_ids:
            raise ValueError(f"Annotation references unknown category {category_id!r}")
        bbox = annotation.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("COCO bbox must be [x, y, width, height]")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in bbox):
            raise ValueError("Annotation bbox coordinates must be numeric")
        x, y, width, height = (float(value) for value in bbox)
        image = image_map[annotation["image_id"]]
        if not all(math.isfinite(value) for value in (x, y, width, height)) or width <= 0 or height <= 0:
            raise ValueError("Annotation bbox coordinates must be finite and have positive size")
        if x < 0 or y < 0 or x + width > image["width"] or y + height > image["height"]:
            raise ValueError("Annotation bbox must stay within the image bounds")
        normalized = [x / image["width"], y / image["height"], (x + width) / image["width"], (y + height) / image["height"]]
        ground_truth[annotation["image_id"]].append({
            "category": category_ids[annotation["category_id"]],
            "box": normalized,
        })
    return dataset, image_map, ground_truth


def validate_dataset(annotation_path: Path, images_root: Path) -> dict[str, Any]:
    """Validate annotations and all referenced images without loading YOLO."""
    dataset, image_map, ground_truth = _load_coco(annotation_path)
    near_duplicate_warnings = _check_duplicate_splits(image_map, images_root)
    split_counts = Counter(image["split"] for image in image_map.values())
    class_counts = Counter(
        annotation["category"]
        for image_annotations in ground_truth.values()
        for annotation in image_annotations
    )
    return {
        "valid": True,
        "image_count": len(image_map),
        "annotation_count": sum(len(items) for items in ground_truth.values()),
        "split_image_counts": dict(split_counts),
        "class_distribution": {category: class_counts[category] for category in CLASSES},
        "categories": dataset["categories"],
        "near_duplicate_warnings": near_duplicate_warnings,
    }


def _ensure_safe_image_path(images_root: Path, file_name: str) -> Path:
    root = images_root.resolve()
    image_path = (root / file_name).resolve()
    if image_path != root and root not in image_path.parents:
        raise ValueError(f"Image path escapes the configured images directory: {file_name!r}")
    return image_path


def _average_hash(image_path: Path) -> int:
    from PIL import Image, ImageOps

    try:
        with Image.open(image_path) as image:
            resized = ImageOps.grayscale(image).resize((8, 8))
            pixels = [resized.getpixel((x, y)) for y in range(8) for x in range(8)]
    except (OSError, ValueError) as exc:
        raise ValueError(f"Image file is unreadable: {image_path.name}") from exc
    average = sum(pixels) / len(pixels)
    return sum((1 << index) for index, pixel in enumerate(pixels) if pixel >= average)


def _image_size(image_path: Path) -> tuple[int, int]:
    from PIL import Image

    try:
        with Image.open(image_path) as image:
            return image.size
    except (OSError, ValueError) as exc:
        raise ValueError(f"Image file is unreadable: {image_path.name}") from exc


def _check_duplicate_splits(image_map: dict[Any, dict[str, Any]], images_root: Path) -> list[str]:
    records = []
    for image_id, image in image_map.items():
        path = _ensure_safe_image_path(images_root, image["file_name"])
        if not path.is_file():
            raise ValueError(f"Image file not found for id {image_id!r}: {image['file_name']}")
        if _image_size(path) != (image["width"], image["height"]):
            raise ValueError(f"COCO dimensions do not match image file for id {image_id!r}")
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append((image_id, image["split"], content_hash, _average_hash(path)))
    warnings = []
    for index, current in enumerate(records):
        for other in records[index + 1:]:
            if current[1] == other[1]:
                continue
            if current[2] == other[2]:
                raise ValueError(f"Exact duplicate image crosses splits: {current[0]!r}, {other[0]!r}")
            distance = (current[3] ^ other[3]).bit_count()
            if distance <= 4:
                warnings.append(f"Possible near-duplicate across splits: {current[0]!r}, {other[0]!r} (average-hash distance {distance}/64)")
    return warnings


def run_evaluation(annotation_path: Path, images_root: Path, split: str) -> dict[str, Any]:
    dataset, image_map, all_ground_truth = _load_coco(annotation_path)
    duplicate_warnings = _check_duplicate_splits(image_map, images_root)
    selected = sorted(
        (image_id for image_id, image in image_map.items() if image["split"] == split),
        key=str,
    )
    if not selected:
        raise ValueError(f"No images are assigned to the {split!r} split")

    # Import the project detector only when a dataset evaluation is actually run.
    sys.path.insert(0, str(ROOT))
    from backend.vehicle_detection import detect_vehicle_image, get_detector_metadata, validate_image_bytes

    metadata = get_detector_metadata()
    predictions = {}
    for image_id in selected:
        image_info = image_map[image_id]
        image_path = _ensure_safe_image_path(images_root, image_info["file_name"])
        image_bytes = image_path.read_bytes()
        suffix = image_path.suffix.lower()
        content_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(suffix)
        if content_type is None:
            raise ValueError(f"Unsupported image extension for {image_path.name!r}")
        validated = validate_image_bytes(image_bytes, content_type)
        result = detect_vehicle_image(validated.image)
        predictions[image_id] = [
            {"category": item["category"], "confidence": item["confidence"], "box": [
                item["bounding_box_normalized"]["x_min"],
                item["bounding_box_normalized"]["y_min"],
                item["bounding_box_normalized"]["x_max"],
                item["bounding_box_normalized"]["y_max"],
            ]}
            for item in result.detections
        ]
    selected_truth = {image_id: all_ground_truth[image_id] for image_id in selected}
    report = evaluate_records(selected_truth, predictions, iou_threshold=0.5)
    split_sizes = Counter(image["split"] for image in image_map.values())
    report.update({
        "dataset": {
            "source": str(annotation_path.name),
            "split": split,
            "split_image_counts": dict(split_sizes),
            "all_images": len(image_map),
            "annotation_categories": dataset["categories"],
            "annotation_image_ids": [image_map[image_id].get("image_identifier", str(image_id)) for image_id in selected],
            "annotation_provenance_by_image": {
                str(image_id): image_map[image_id]["annotation_provenance"]
                for image_id in selected
            },
            "near_duplicate_warnings": duplicate_warnings,
        },
        "model": metadata,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True, help="COCO JSON with split and annotation provenance metadata")
    parser.add_argument("--images", type=Path, required=True, help="Directory containing the original images")
    parser.add_argument("--split", choices=("development", "evaluation"), help="Required unless --validate-only is used")
    parser.add_argument("--output", type=Path, help="Path for the JSON metrics report; required for evaluation")
    parser.add_argument("--validate-only", action="store_true", help="Validate annotations, files, dimensions, and split leakage without loading YOLO")
    args = parser.parse_args()
    try:
        if args.validate_only:
            validation = validate_dataset(args.annotations, args.images)
            print(json.dumps(validation, indent=2))
            return 0
        if not args.split:
            parser.error("--split is required unless --validate-only is used")
        if not args.output:
            parser.error("--output is required when running evaluation")
        report = run_evaluation(args.annotations, args.images, args.split)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(f"Evaluation report written to {args.output}")
    print(f"Images: {report['image_count']}; IoU threshold: {report['iou_threshold']:.2f}")
    print(json.dumps(report["per_class"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
