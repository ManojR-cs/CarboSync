"""Lazy YOLO11n vehicle detection with bounded, in-memory image handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import os
from pathlib import Path
import threading
import base64
from math import isfinite


COCO_VEHICLE_CLASSES = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageInputError(ValueError):
    """The upload is not a supported, readable, safely sized image."""


class DetectionUnavailable(RuntimeError):
    """Model dependencies or explicitly configured weights are unavailable."""


@dataclass(frozen=True)
class ValidatedImage:
    image: object
    image_format: str


@dataclass(frozen=True)
class DetectionResult:
    counts: dict[str, int]
    annotated_image_data_uri: str
    model: str
    confidence_threshold: float
    detections: list[dict[str, object]] = field(default_factory=list)
    class_mapping: dict[str, list[int]] = field(default_factory=dict)
    unmapped_vehicle_categories: list[str] = field(default_factory=list)


def validate_image_bytes(data: bytes, declared_content_type: str | None) -> ValidatedImage:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ImageInputError("Image is empty or exceeds the 10 MiB limit.")
    allowed_content_types = {"image/jpeg", "image/png", "image/webp"}
    if declared_content_type not in allowed_content_types:
        raise ImageInputError("Upload must be a JPEG, PNG, or WebP image.")
    try:
        from PIL import Image

        with Image.open(BytesIO(data)) as probe:
            if probe.format not in ALLOWED_IMAGE_FORMATS:
                raise ImageInputError("Image format is not supported.")
            expected_formats = {
                "image/jpeg": "JPEG",
                "image/png": "PNG",
                "image/webp": "WEBP",
            }
            if probe.format != expected_formats[declared_content_type]:
                raise ImageInputError("Declared image type does not match image content.")
            width, height = probe.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ImageInputError("Image dimensions are outside the supported limit.")
            probe.verify()
        image = Image.open(BytesIO(data)).convert("RGB")
    except ImageInputError:
        raise
    except Exception as exc:
        # Pillow raises several format-specific exceptions. Keep those details
        # internal and expose one safe client message at the API boundary.
        raise ImageInputError("Uploaded file is not a readable image.") from exc
    return ValidatedImage(image=image, image_format="RGB")


def _configured_model_path() -> Path:
    raw = os.getenv("CARBOSYNC_YOLO_MODEL_PATH")
    path = (
        Path(raw).expanduser()
        if raw
        else Path(__file__).resolve().parent / "models" / "yolo11n.pt"
    )
    return path.resolve()


def _confidence_threshold() -> float:
    raw = os.getenv("CARBOSYNC_YOLO_CONFIDENCE", "0.35")
    try:
        threshold = float(raw)
    except ValueError as exc:
        raise DetectionUnavailable("YOLO confidence configuration is invalid.") from exc
    if not 0 < threshold <= 1:
        raise DetectionUnavailable("YOLO confidence configuration is invalid.")
    return threshold


def count_coco_vehicle_classes(class_ids: list[int]) -> dict[str, int]:
    counts = {name: 0 for name in COCO_VEHICLE_CLASSES.values()}
    for class_id in class_ids:
        name = COCO_VEHICLE_CLASSES.get(int(class_id))
        if name is not None:
            counts[name] += 1
    return counts


_CANONICAL_CLASS_NAMES = {
    "bicycle": "bicycle",
    "bike": "bicycle",
    "car": "car",
    "motorcycle": "motorcycle",
    "motorbike": "motorcycle",
    "bus": "bus",
    "truck": "truck",
}


def resolve_vehicle_class_ids(class_names: dict | list | tuple) -> dict[int, str]:
    """Map actual model labels to supported vehicle categories.

    COCO IDs are used only by the COCO fixture/helper. For inference, use the
    names loaded from the configured model so custom class ordering is safe.
    """
    items = class_names.items() if isinstance(class_names, dict) else enumerate(class_names)
    mapped: dict[int, str] = {}
    for raw_id, raw_name in items:
        try:
            class_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        name = str(raw_name).strip().lower().replace("_", " ")
        category = _CANONICAL_CLASS_NAMES.get(name)
        if category:
            mapped[class_id] = category
    return mapped


_model_lock = threading.Lock()
_inference_lock = threading.Lock()
_loaded_model = None
_loaded_model_path: Path | None = None


def _load_model():
    global _loaded_model, _loaded_model_path
    path = _configured_model_path()
    if path.suffix.lower() != ".pt":
        raise DetectionUnavailable(
            "The configured detector must be an Ultralytics PyTorch .pt weights file."
        )
    if not path.is_file():
        raise DetectionUnavailable(
            "YOLO11n weights are unavailable. Set CARBOSYNC_YOLO_MODEL_PATH to a local model file."
        )
    with _model_lock:
        if _loaded_model is None or _loaded_model_path != path:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise DetectionUnavailable(
                    "YOLO runtime is unavailable; install requirements-yolo.txt."
                ) from exc
            try:
                _loaded_model = YOLO(str(path))
                _loaded_model_path = path
            except Exception as exc:
                raise DetectionUnavailable("Configured YOLO weights could not be loaded.") from exc
    return _loaded_model


def detect_vehicle_image(image: object) -> DetectionResult:
    model = _load_model()
    threshold = _confidence_threshold()
    try:
        with _inference_lock:
            result = model.predict(
                source=image,
                conf=threshold,
                verbose=False,
                device="cpu",
            )[0]
            actual_names = getattr(result, "names", None) or getattr(model, "names", None)
            if actual_names is None:
                raise DetectionUnavailable(
                    "The configured model does not expose class names; vehicle classes cannot be verified."
                )
            class_mapping = resolve_vehicle_class_ids(actual_names)
            if not class_mapping:
                raise DetectionUnavailable(
                    "The configured model has no recognized bicycle, car, motorcycle, bus, or truck classes."
                )
            boxes = result.boxes
            class_ids = boxes.cls.tolist() if boxes is not None else []
            confidences = boxes.conf.tolist() if boxes is not None else []
            normalized_boxes = boxes.xyxyn.tolist() if boxes is not None else []
            counts = {name: 0 for name in COCO_VEHICLE_CLASSES.values()}
            details: list[dict[str, object]] = []
            for class_id, confidence, coordinates in zip(
                class_ids, confidences, normalized_boxes
            ):
                class_id_int = int(class_id)
                category = class_mapping.get(class_id_int)
                if category is None:
                    continue
                confidence_value = float(confidence)
                if not isfinite(confidence_value) or not 0 <= confidence_value <= 1:
                    continue
                x1, y1, x2, y2 = (float(value) for value in coordinates)
                if not all(isfinite(value) for value in (x1, y1, x2, y2)):
                    continue
                counts[category] += 1
                details.append(
                    {
                        "class_id": class_id_int,
                        "category": category,
                        "confidence": confidence_value,
                        "bounding_box_normalized": {
                            "x_min": max(0.0, min(1.0, x1)),
                            "y_min": max(0.0, min(1.0, y1)),
                            "x_max": max(0.0, min(1.0, x2)),
                            "y_max": max(0.0, min(1.0, y2)),
                        },
                    }
                )
            plotted = result.plot()
            # Ultralytics returns a BGR NumPy array; Pillow expects RGB.
            from PIL import Image

            annotated = Image.fromarray(plotted[:, :, ::-1])
            annotated.thumbnail((2048, 2048))
            buffer = BytesIO()
            annotated.save(buffer, format="JPEG", quality=85, optimize=True)
    except DetectionUnavailable:
        raise
    except Exception as exc:
        raise DetectionUnavailable("Vehicle detection could not be completed.") from exc
    data_uri = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    configured_name = _configured_model_path().name
    model_label = (
        "YOLO11n"
        if configured_name.lower() == "yolo11n.pt"
        else f"Custom YOLO model ({configured_name})"
    )
    category_class_ids: dict[str, list[int]] = {}
    for class_id, category in class_mapping.items():
        category_class_ids.setdefault(category, []).append(class_id)
    return DetectionResult(
        counts=counts,
        annotated_image_data_uri=data_uri,
        model=model_label,
        confidence_threshold=threshold,
        detections=details,
        class_mapping=category_class_ids,
        unmapped_vehicle_categories=sorted(
            set(COCO_VEHICLE_CLASSES.values()) - set(class_mapping.values())
        ),
    )
