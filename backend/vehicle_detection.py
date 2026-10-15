"""Lazy YOLO11n vehicle detection with bounded, in-memory image handling."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import threading
import base64


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


_model_lock = threading.Lock()
_inference_lock = threading.Lock()
_loaded_model = None
_loaded_model_path: Path | None = None


def _load_model():
    global _loaded_model, _loaded_model_path
    path = _configured_model_path()
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
                    "YOLO runtime is unavailable; install the declared backend dependencies."
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
            class_ids = result.boxes.cls.tolist() if result.boxes is not None else []
            counts = count_coco_vehicle_classes(class_ids)
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
    return DetectionResult(
        counts=counts,
        annotated_image_data_uri=data_uri,
        model="YOLO11n",
        confidence_threshold=threshold,
    )
