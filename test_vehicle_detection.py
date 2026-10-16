import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "vehicle_detection.py"
TEST_IMAGES = ROOT / "test_images"
RESULTS = ROOT / "detection_results"


class VehicleDetectionTests(unittest.TestCase):

    def test_missing_argument(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)

    def test_missing_image(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "test_images/does_not_exist.jpg",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Image not found", result.stdout)

    def test_existing_reports_are_valid(self):
        for image_name in ("Test1", "Test2", "Test3"):
            with self.subTest(image=image_name):
                report_path = RESULTS / f"{image_name}_counts.json"
                self.assertTrue(report_path.is_file(), f"Report file missing: {report_path}")

                with report_path.open(encoding="utf-8") as file:
                    report = json.load(file)

                self.assertEqual(report["project"], "CarboSync")
                self.assertIsInstance(report["model"], str)
                self.assertTrue(report["model"])
                if "model_metadata" in report:
                    self.assertRegex(report["model_metadata"]["weights_sha256"], r"^[a-f0-9]{64}$")
                    self.assertIn("inference_settings", report["model_metadata"])

                counts = report["counts"]
                for vehicle in (
                    "Bicycle", "Car", "Motorcycle", "Bus", "Truck"
                ):
                    self.assertIn(vehicle, counts)
                    self.assertIsInstance(counts[vehicle], int)
                    self.assertGreaterEqual(counts[vehicle], 0)

                expected_total = sum(counts.values())
                self.assertEqual(
                    report["all_selected_objects"], expected_total
                )
                self.assertEqual(
                    report["motor_vehicle_total"],
                    counts["Car"] + counts["Motorcycle"]
                    + counts["Bus"] + counts["Truck"],
                )

    def test_annotated_images_exist(self):
        for image_name in ("Test1", "Test2", "Test3"):
            with self.subTest(image=image_name):
                self.assertTrue(
                    (RESULTS / f"{image_name}_detected.jpg").is_file(),
                    f"Annotated image missing: {RESULTS / f'{image_name}_detected.jpg'}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
