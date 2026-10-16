"""Focused detector configuration and model-readiness regression tests."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import backend.vehicle_detection as detector
from backend.vehicle_detection import (
    DetectionUnavailable,
    get_detector_config,
    detect_vehicle_image,
    validate_image_bytes,
)


class DetectorConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.prior = (
            detector._loaded_model,
            detector._loaded_model_path,
            detector._loaded_model_sha256,
            detector._loaded_model_metadata,
        )
        detector._loaded_model = None
        detector._loaded_model_path = None
        detector._loaded_model_sha256 = None
        detector._loaded_model_metadata = None

    def tearDown(self):
        (
            detector._loaded_model,
            detector._loaded_model_path,
            detector._loaded_model_sha256,
            detector._loaded_model_metadata,
        ) = self.prior

    def test_model_path_is_deterministic_and_relative_to_project(self):
        project_root = Path(detector.__file__).resolve().parent.parent
        with patch.dict(os.environ, {"CARBOSYNC_YOLO_MODEL_PATH": "backend/models/yolo11x.pt"}):
            config = get_detector_config()
        self.assertEqual(config.model_path, (project_root / "backend/models/yolo11x.pt").resolve())
        self.assertEqual(config.model_path.name, "yolo11x.pt")

    def test_missing_explicit_weights_do_not_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.pt"
            with patch.dict(os.environ, {"CARBOSYNC_YOLO_MODEL_PATH": str(missing)}):
                self.assertEqual(detector.get_detector_config().model_path, missing.resolve())
                with self.assertRaisesRegex(DetectionUnavailable, "weights are unavailable"):
                    detector._load_model()
            self.assertFalse(missing.exists())

    def test_invalid_inference_settings_are_rejected(self):
        invalid_values = (
            ("CARBOSYNC_YOLO_CONFIDENCE", "0"),
            ("CARBOSYNC_YOLO_CONFIDENCE", "nan"),
            ("CARBOSYNC_YOLO_IOU", "1"),
            ("CARBOSYNC_YOLO_IMAGE_SIZE", "0"),
            ("CARBOSYNC_YOLO_IMAGE_SIZE", "1290"),
            ("CARBOSYNC_YOLO_NMS_MODE", "sometimes"),
        )
        for key, value in invalid_values:
            with self.subTest(setting=key, value=value):
                with patch.dict(os.environ, {key: value}):
                    with self.assertRaises(DetectionUnavailable):
                        get_detector_config()

    def test_class_aware_nms_is_the_default(self):
        with patch.dict(os.environ, {"CARBOSYNC_YOLO_NMS_MODE": "class_aware"}):
            config = get_detector_config()
        self.assertFalse(config.agnostic_nms)
        self.assertEqual(config.nms_mode, "class_aware")

    def test_weights_hash_runtime_and_class_metadata(self):
        names = {2: "car", 3: "motorcycle", 1: "bicycle", 5: "bus", 7: "truck"}
        fake_model = SimpleNamespace(names=names, task="detect")
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "weights.pt"
            weights.write_bytes(b"fixed fake weights for deterministic hash test")
            expected_hash = hashlib.sha256(weights.read_bytes()).hexdigest()
            with (
                patch.dict(os.environ, {"CARBOSYNC_YOLO_MODEL_PATH": str(weights)}),
                patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=MagicMock(return_value=fake_model))}),
            ):
                metadata = detector.get_detector_metadata()
        self.assertEqual(metadata["weights_sha256"], expected_hash)
        self.assertEqual(metadata["name"], "weights")
        self.assertEqual(metadata["supported_classes"]["2"], "car")
        self.assertEqual(metadata["supported_classes"]["3"], "motorcycle")
        self.assertEqual(metadata["model_class_names"]["2"], "car")
        self.assertIn("python", metadata["runtime_versions"])
        self.assertIn("ultralytics", metadata["runtime_versions"])
        self.assertIn("torch", metadata["runtime_versions"])
        self.assertEqual(metadata["inference_settings"]["nms_mode"], "class_aware")
        self.assertNotIn("path", metadata)
        self.assertNotIn(directory, str(metadata))

    def test_invalid_weights_report_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "invalid.pt"
            weights.write_bytes(b"not a model")
            with (
                patch.dict(os.environ, {"CARBOSYNC_YOLO_MODEL_PATH": str(weights)}),
                patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=MagicMock(side_effect=ValueError("private")))}),
            ):
                with self.assertRaisesRegex(DetectionUnavailable, "weights could not be loaded"):
                    detector._load_model()

    def test_real_model_smoke_when_local_weights_are_available(self):
        config = get_detector_config()
        if not config.model_path.is_file():
            self.skipTest("configured local model weights are unavailable")
        if importlib.util.find_spec("ultralytics") is None:
            self.skipTest("Ultralytics is not installed")
        image_path = Path(__file__).resolve().parents[1] / "test_images" / "Test1.jpg"
        if not image_path.is_file():
            self.skipTest("local smoke image is unavailable")
        image = validate_image_bytes(image_path.read_bytes(), "image/jpeg").image
        result = detect_vehicle_image(image)
        self.assertIn(
            result.inference_status,
            {"completed_with_detections", "completed_no_detections"},
        )
        self.assertEqual(sum(result.counts.values()), len(result.detections))
        self.assertRegex(result.metadata["weights_sha256"], r"^[a-f0-9]{64}$")


if __name__ == "__main__":
    unittest.main()
