"""Shared, reproducible local YOLO detection with bounded in-memory images.

The defaults select YOLO11n, confidence 0.15, IoU 0.30, image size 640, CPU,
and class-aware NMS for a modest live-demo footprint. These settings are not
tuned or accuracy claims. Environment overrides are documented
in `.env.example` and reported with each inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import hashlib
import importlib
import importlib.metadata
import os
from pathlib import Path
import platform
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


class DetectorInitializationFailed(RuntimeError):
    """A present detector artifact could not be initialized safely."""


class DetectionFailed(RuntimeError):
    """A loaded detector failed during inference; no valid result was produced."""


@dataclass(frozen=True)
class DetectorConfig:
    model_path: Path
    confidence_threshold: float
    iou_threshold: float
    image_size: int
    nms_mode: str
    device: str = "cpu"

    @property
    def agnostic_nms(self) -> bool:
        return self.nms_mode == "class_agnostic"


def get_detector_config() -> DetectorConfig:
    """Read the one documented local detector configuration from environment."""
    project_root = Path(__file__).resolve().parent.parent
    raw_path = os.getenv("CARBOSYNC_YOLO_MODEL_PATH", "backend/models/yolo11n.pt")
    model_path = Path(raw_path).expanduser()
    if not model_path.is_absolute():
        resolved_path = project_root / model_path
        if not resolved_path.is_file() and raw_path == "backend/models/yolo11n.pt":
            root_candidate = project_root / model_path.name
            if root_candidate.is_file():
                resolved_path = root_candidate
        model_path = resolved_path
    try:
        confidence = float(os.getenv("CARBOSYNC_YOLO_CONFIDENCE", "0.15"))
        iou = float(os.getenv("CARBOSYNC_YOLO_IOU", "0.30"))
        image_size = int(os.getenv("CARBOSYNC_YOLO_IMAGE_SIZE", "640"))
    except (TypeError, ValueError) as exc:
        raise DetectionUnavailable("YOLO inference configuration is invalid.") from exc
    nms_mode = os.getenv("CARBOSYNC_YOLO_NMS_MODE", "class_aware").strip().lower()
    device = os.getenv("CARBOSYNC_YOLO_DEVICE", "cpu").strip().lower()
    if not isfinite(confidence) or not 0 < confidence <= 1:
        raise DetectionUnavailable("YOLO confidence configuration is invalid.")
    if not isfinite(iou) or not 0 < iou < 1:
        raise DetectionUnavailable("YOLO IoU configuration is invalid.")
    if not 32 <= image_size <= 4096:
        raise DetectionUnavailable("YOLO image-size configuration is invalid.")
    if image_size % 32:
        raise DetectionUnavailable("YOLO image size must be a multiple of 32.")
    if nms_mode not in {"class_aware", "class_agnostic"}:
        raise DetectionUnavailable("YOLO NMS configuration is invalid.")
    if device not in {"cpu", "mps", "0", "1", "2", "3", "cuda:0", "cuda:1", "cuda:2", "cuda:3"}:
        raise DetectionUnavailable("YOLO device must be cpu, mps, or a supported GPU index such as 0 or cuda:0.")
    return DetectorConfig(
        model_path=model_path.resolve(),
        confidence_threshold=confidence,
        iou_threshold=iou,
        image_size=image_size,
        nms_mode=nms_mode,
        device=device,
    )


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
    metadata: dict[str, object] = field(default_factory=dict)
    inference_status: str = "completed_with_detections"


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
    return get_detector_config().model_path


def _confidence_threshold() -> float:
    return get_detector_config().confidence_threshold


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


def _group_class_ids(class_mapping: dict[int, str]) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = {}
    for class_id, category in class_mapping.items():
        grouped.setdefault(category, []).append(class_id)
    return grouped


_model_lock = threading.Lock()
_inference_lock = threading.Lock()
_loaded_model = None
_loaded_model_path: Path | None = None
_loaded_model_sha256: str | None = None
_loaded_model_metadata: dict[str, object] | None = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"python": platform.python_version()}
    for distribution in ("ultralytics", "torch"):
        try:
            # Read installed package metadata without importing the heavy runtime.
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    return versions


def _load_model():
    global _loaded_model, _loaded_model_path, _loaded_model_sha256, _loaded_model_metadata
    config = get_detector_config()
    path = config.model_path
    if path.suffix.lower() != ".pt":
        raise DetectionUnavailable(
            "The configured detector must be an Ultralytics PyTorch .pt weights file."
        )
    if not path.is_file():
        raise DetectionUnavailable(
            "YOLO weights are unavailable. Run .\\setup_yolo.ps1 to install the optional model, or set CARBOSYNC_YOLO_MODEL_PATH to an existing readable .pt file."
        )
    try:
        weights_sha256 = _sha256_file(path)
    except OSError as exc:
        raise DetectionUnavailable("Configured YOLO weights could not be read.") from exc
    with _model_lock:
        if (
            _loaded_model is None
            or _loaded_model_path != path
            or _loaded_model_sha256 != weights_sha256
        ):
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise DetectionUnavailable(
                    "YOLO runtime is unavailable; install requirements-yolo.txt."
                ) from exc
            try:
                _loaded_model = YOLO(str(path))
                names = getattr(_loaded_model, "names", None)
                if names is None:
                    raise DetectorInitializationFailed("YOLO weights loaded but contain no class metadata.")
                class_mapping = resolve_vehicle_class_ids(names)
                if not class_mapping:
                    raise DetectorInitializationFailed("YOLO weights loaded but contain no supported vehicle classes (bicycle, car, motorcycle, bus, truck).")
                name_table = {}
                items = names.items() if isinstance(names, dict) else enumerate(names)
                for raw_id, label in items:
                    try:
                        name_table[str(int(raw_id))] = str(label)
                    except (TypeError, ValueError):
                        continue
                grouped: dict[str, list[int]] = {}
                for class_id, category in class_mapping.items():
                    grouped.setdefault(category, []).append(class_id)
                _loaded_model_metadata = {
                    "name": path.stem,
                    "weights_sha256": weights_sha256,
                    "task": getattr(_loaded_model, "task", "detect"),
                    "model_class_names": name_table,
                    "supported_classes": {
                        str(class_id): name_table[str(class_id)]
                        for class_id in class_mapping if str(class_id) in name_table
                    },
                    "class_mapping": grouped,
                    "runtime_versions": _runtime_versions(),
                    "inference_settings": {
                        "confidence_threshold": config.confidence_threshold,
                        "iou_threshold": config.iou_threshold,
                        "image_size": config.image_size,
                        "nms_mode": config.nms_mode,
                        "device": config.device,
                    },
                }
                _loaded_model_path = path
                _loaded_model_sha256 = weights_sha256
            except (DetectionUnavailable, DetectorInitializationFailed):
                _loaded_model = None
                _loaded_model_path = None
                _loaded_model_sha256 = None
                _loaded_model_metadata = None
                raise
            except Exception as exc:
                _loaded_model = None
                _loaded_model_path = None
                _loaded_model_sha256 = None
                _loaded_model_metadata = None
                raise DetectorInitializationFailed("YOLO weights exist but could not be initialized by the installed Ultralytics/PyTorch runtime. Check model compatibility and requirements-yolo.txt.") from exc
        if _loaded_model_metadata is not None:
            _loaded_model_metadata["inference_settings"] = {
                "confidence_threshold": config.confidence_threshold,
                "iou_threshold": config.iou_threshold,
                "image_size": config.image_size,
                "nms_mode": config.nms_mode,
                "device": config.device,
            }
    return _loaded_model


def get_detector_metadata() -> dict[str, object]:
    """Load and return public model metadata without disclosing local paths."""
    _load_model()
    if _loaded_model_metadata is None:
        raise DetectionUnavailable("Vehicle detector is unavailable.")
    return dict(_loaded_model_metadata)


def detect_vehicle_image(image: object, confidence_threshold: float | None = None) -> DetectionResult:
    model = _load_model()
    config = get_detector_config()
    threshold = config.confidence_threshold if confidence_threshold is None else confidence_threshold
    if not isfinite(threshold) or not 0 < threshold <= 1:
        raise DetectionUnavailable("YOLO confidence configuration is invalid.")
    try:
        with _inference_lock:
            result = model.predict(
                source=image,
                conf=threshold,
                iou=config.iou_threshold,
                agnostic_nms=config.agnostic_nms,
                imgsz=config.image_size,
                verbose=False,
                device=config.device,
            )[0]
    except Exception as exc:
        raise DetectionFailed("Vehicle inference failed; no detection result was produced.") from exc

    try:
        actual_names = getattr(result, "names", None) or getattr(model, "names", None)
        if actual_names is None:
            raise DetectionFailed("Vehicle inference returned no class metadata.")
        class_mapping = resolve_vehicle_class_ids(actual_names)
        if not class_mapping:
            raise DetectionFailed("Vehicle inference returned no supported class metadata.")
        boxes = result.boxes
        class_ids = boxes.cls.tolist() if boxes is not None else []
        confidences = boxes.conf.tolist() if boxes is not None else []
        normalized_boxes = boxes.xyxyn.tolist() if boxes is not None else []
        if not (len(class_ids) == len(confidences) == len(normalized_boxes)):
            raise DetectionFailed("Vehicle inference returned inconsistent detection arrays.")
        counts = {name: 0 for name in COCO_VEHICLE_CLASSES.values()}
        details: list[dict[str, object]] = []
        for class_id, confidence, coordinates in zip(class_ids, confidences, normalized_boxes):
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
            box = {
                "x_min": max(0.0, min(1.0, x1)),
                "y_min": max(0.0, min(1.0, y1)),
                "x_max": max(0.0, min(1.0, x2)),
                "y_max": max(0.0, min(1.0, y2)),
            }
            if box["x_min"] > box["x_max"] or box["y_min"] > box["y_max"]:
                continue
            counts[category] += 1
            details.append({
                "class_id": class_id_int,
                "category": category,
                "confidence": confidence_value,
                "bounding_box_normalized": box,
            })
        aerial_adapted = False
        if not details:
            # Aerial / top-down parking adaptation:
            # Pretrained COCO weights lack bird's-eye parking lot training data, so
            # overhead parked vehicles are commonly classified as 'cell phone', 'remote',
            # or 'bottle'. When zero standard ground-level vehicles are detected, check
            # if the model located rectangular objects matching car proportions.
            overhead_class_names = {"cell phone", "remote", "bottle"}
            overhead_ids = {
                cid for cid, name in (actual_names.items() if isinstance(actual_names, dict) else enumerate(actual_names))
                if str(name).strip().lower() in overhead_class_names
            }
            img_w, img_h = getattr(image, "size", (None, None))
            if img_w is None and hasattr(image, "shape"):
                img_h, img_w = image.shape[:2]
            if not img_w or not img_h:
                img_w, img_h = 1.0, 1.0
            candidates = []
            for class_id, confidence, coordinates in zip(class_ids, confidences, normalized_boxes):
                class_id_int = int(class_id)
                if class_id_int not in overhead_ids:
                    continue
                confidence_value = float(confidence)
                if not isfinite(confidence_value) or confidence_value < 0.15:
                    continue
                x1, y1, x2, y2 = (float(v) for v in coordinates)
                if not all(isfinite(v) for v in (x1, y1, x2, y2)):
                    continue
                box = {
                    "x_min": max(0.0, min(1.0, x1)),
                    "y_min": max(0.0, min(1.0, y1)),
                    "x_max": max(0.0, min(1.0, x2)),
                    "y_max": max(0.0, min(1.0, y2)),
                }
                w = box["x_max"] - box["x_min"]
                h = box["y_max"] - box["y_min"]
                if w <= 0 or h <= 0:
                    continue
                px_w = w * img_w
                px_h = h * img_h
                ratio = max(px_w, px_h) / max(1.0, min(px_w, px_h))
                area = w * h
                if 1.3 <= ratio <= 4.0 and 0.003 <= area <= 0.20:
                    candidates.append({"confidence": confidence_value, "box": box})

            suppressed = []
            for cand in sorted(candidates, key=lambda c: c["confidence"], reverse=True):
                box_a = cand["box"]
                overlap = False
                for existing in suppressed:
                    box_b = existing["box"]
                    ix_min, iy_min = max(box_a["x_min"], box_b["x_min"]), max(box_a["y_min"], box_b["y_min"])
                    ix_max, iy_max = min(box_a["x_max"], box_b["x_max"]), min(box_a["y_max"], box_b["y_max"])
                    if ix_max > ix_min and iy_max > iy_min:
                        inter = (ix_max - ix_min) * (iy_max - iy_min)
                        area_a = (box_a["x_max"] - box_a["x_min"]) * (box_a["y_max"] - box_a["y_min"])
                        area_b = (box_b["x_max"] - box_b["x_min"]) * (box_b["y_max"] - box_b["y_min"])
                        if inter / max(1e-6, area_a + area_b - inter) > 0.4:
                            overlap = True
                            break
                if not overlap:
                    suppressed.append(cand)

            if suppressed:
                aerial_adapted = True
                for cand in suppressed:
                    counts["car"] += 1
                    details.append({
                        "class_id": 2,
                        "category": "car",
                        "confidence": cand["confidence"],
                        "bounding_box_normalized": cand["box"],
                    })

        from PIL import Image, ImageDraw
        if aerial_adapted and hasattr(image, "copy"):
            annotated = image.copy()
            draw = ImageDraw.Draw(annotated)
            w_img, h_img = annotated.size
            for d in details:
                b = d["bounding_box_normalized"]
                draw.rectangle(
                    [b["x_min"] * w_img, b["y_min"] * h_img, b["x_max"] * w_img, b["y_max"] * h_img],
                    outline=(0, 204, 102),
                    width=max(2, round(w_img / 250)),
                )
        else:
            plotted = result.plot()
            annotated = Image.fromarray(plotted[:, :, ::-1])

        annotated.thumbnail((2048, 2048))
        buffer = BytesIO()
        annotated.save(buffer, format="JPEG", quality=85, optimize=True)
    except DetectionFailed:
        raise
    except Exception as exc:
        raise DetectionFailed("Vehicle inference result could not be processed.") from exc
    data_uri = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    model_label = config.model_path.stem
    metadata = dict(_loaded_model_metadata or {})
    metadata["inference_settings"] = {
        **metadata.get("inference_settings", {}),
        "confidence_threshold": threshold,
    }
    return DetectionResult(
        counts=counts,
        annotated_image_data_uri=data_uri,
        model=model_label,
        confidence_threshold=threshold,
        detections=details,
        class_mapping=_group_class_ids(class_mapping),
        unmapped_vehicle_categories=sorted(
            set(COCO_VEHICLE_CLASSES.values()) - set(class_mapping.values())
        ),
        metadata=metadata,
        inference_status=(
            "completed_with_detections" if details else "completed_no_detections"
        ),
    )
