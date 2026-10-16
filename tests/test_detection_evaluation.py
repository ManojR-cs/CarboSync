"""Deterministic tests for the dependency-light evaluation metrics."""

import unittest
import json
from pathlib import Path
import tempfile
from PIL import Image

from tools.evaluate_vehicle_detections import _load_coco, evaluate_records, validate_dataset


def box(category, coordinates, confidence=0.9):
    return {"category": category, "box": coordinates, "confidence": confidence}


class DetectionEvaluationTests(unittest.TestCase):
    def _dataset(self, splits=("development", "evaluation")):
        return {
            "images": [
                {
                    "id": index + 1,
                    "image_identifier": f"image-{index + 1}",
                    "file_name": f"image-{index + 1}.jpg",
                    "width": 100,
                    "height": 80,
                    "split": split,
                    "annotation_complete": True,
                    "location_id": "north-lot",
                    "capture_session_id": f"session-{split}",
                    "annotation_provenance": {
                        "annotator": "reviewer-1",
                        "source": "CVAT COCO export",
                        "annotated_at": "2026-10-16",
                        "guideline_version": "parking-boxes-v1",
                    },
                }
                for index, split in enumerate(splits)
            ],
            "annotations": [],
            "categories": [{"id": 1, "name": "car"}, {"id": 2, "name": "motorcycle"}],
        }

    def test_coco_annotations_keep_empty_images_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps(self._dataset()), encoding="utf-8")
            _doc, images, truth = _load_coco(path)
        self.assertEqual(len(images), 2)
        self.assertEqual(truth, {1: [], 2: []})
        self.assertEqual(images[1]["annotation_provenance"]["annotator"], "reviewer-1")

    def test_coco_rejects_shared_capture_session_across_splits(self):
        document = self._dataset()
        document["images"][1]["capture_session_id"] = document["images"][0]["capture_session_id"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Data leakage"):
                _load_coco(path)

    def test_coco_rejects_unannotated_images_instead_of_treating_them_as_empty(self):
        document = self._dataset(("development",))
        document["images"] = document["images"][:1]
        document["images"][0]["annotation_complete"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "annotation_complete=true"):
                _load_coco(path)

    def test_coco_rejects_empty_schema_example_as_a_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps({"images": [], "annotations": [], "categories": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "at least one fully reviewed image"):
                _load_coco(path)

    def test_validate_dataset_checks_files_dimensions_and_split_counts(self):
        document = self._dataset(("development",))
        document["images"] = document["images"][:1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "labels.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Image file not found for id 1"):
                validate_dataset(path, root)

            (root / "image-1.jpg").write_bytes(b"not an image")
            with self.assertRaisesRegex(ValueError, "Image file is unreadable"):
                validate_dataset(path, root)

            Image.new("RGB", (100, 80), color="white").save(root / "image-1.jpg", format="JPEG")
            report = validate_dataset(path, root)
        self.assertTrue(report["valid"])
        self.assertEqual(report["image_count"], 1)
        self.assertEqual(report["split_image_counts"], {"development": 1})

    def test_validate_dataset_rejects_dimension_mismatch(self):
        document = self._dataset(("development",))
        document["images"] = document["images"][:1]
        document["images"][0]["width"] = 99
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new("RGB", (100, 80), color="white").save(root / "image-1.jpg", format="JPEG")
            path = root / "labels.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "dimensions do not match"):
                validate_dataset(path, root)

    def test_coco_reports_duplicate_image_ids(self):
        document = self._dataset()
        document["images"][1]["id"] = document["images"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate image id"):
                _load_coco(path)

    def test_coco_rejects_unsupported_class_and_invalid_box(self):
        document = self._dataset(("development",))
        document["images"] = document["images"][:1]
        document["annotations"] = [{"id": 1, "image_id": 1, "category_id": 99, "bbox": [1, 2, 10, 20]}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown category"):
                _load_coco(path)
            document["categories"].append({"id": 99, "name": "person"})
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported annotation class"):
                _load_coco(path)
            document["categories"][-1]["name"] = "car"
            document["annotations"][0]["category_id"] = 99
            document["annotations"][0]["bbox"] = [95, 5, 10, 10]
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "within the image bounds"):
                _load_coco(path)

    def test_one_to_one_matching_and_duplicate_count(self):
        truth = {"p1": [{"category": "car", "box": [0.1, 0.1, 0.5, 0.5]}]}
        predictions = {"p1": [
            box("car", [0.1, 0.1, 0.5, 0.5], 0.9),
            box("car", [0.12, 0.12, 0.48, 0.48], 0.8),
        ]}
        report = evaluate_records(truth, predictions)
        self.assertEqual(report["per_class"]["car"]["true_positives"], 1)
        self.assertEqual(report["per_class"]["car"]["false_positives"], 1)
        self.assertEqual(report["per_class"]["car"]["duplicate_false_positives"], 1)
        self.assertEqual(report["per_class"]["car"]["precision"], 0.5)
        self.assertEqual(report["per_class"]["car"]["recall"], 1.0)

    def test_wrong_class_counts_as_miss_and_false_positive(self):
        truth = {"p1": [{"category": "motorcycle", "box": [0.1, 0.1, 0.5, 0.5]}]}
        predictions = {"p1": [box("car", [0.1, 0.1, 0.5, 0.5])]}
        report = evaluate_records(truth, predictions)
        self.assertEqual(report["per_class"]["car"]["false_positives"], 1)
        self.assertEqual(report["per_class"]["motorcycle"]["false_negatives_missed"], 1)

    def test_empty_image_false_positives_and_per_image_count_mae(self):
        truth = {"empty": [], "with_car": [{"category": "car", "box": [0, 0, 1, 1]}]}
        predictions = {"empty": [box("car", [0, 0, 0.2, 0.2])]}
        report = evaluate_records(truth, predictions)
        self.assertEqual(report["empty_image_count"], 1)
        self.assertEqual(report["false_positives_on_empty_images"], 1)
        self.assertEqual(report["per_class"]["car"]["mean_absolute_count_error_per_image"], 1.0)

    def test_invalid_iou_threshold_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_records({}, {}, iou_threshold=0)


if __name__ == "__main__":
    unittest.main()
