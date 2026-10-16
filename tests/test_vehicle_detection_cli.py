"""Smoke checks for the optional image-detection command-line entry point."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "detect_image.py"


class VehicleDetectionCliTests(unittest.TestCase):
    def test_missing_argument_shows_usage(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
        self.assertIn("tools/detect_image.py", result.stdout)

    def test_missing_image_returns_actionable_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "missing-image.jpg"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Image not found", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
