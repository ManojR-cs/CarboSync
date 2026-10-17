"""Mocked API and service tests for the judges' demo flow."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image

from backend.demo_calculations import calculate_demo_analysis
from backend.main import app
from backend.recommendations import generate_recommendations
from backend.vehicle_detection import (
    DetectionFailed,
    DetectionResult,
    ImageInputError,
    count_coco_vehicle_classes,
    detect_vehicle_image,
    resolve_vehicle_class_ids,
    validate_image_bytes,
)


_png_buffer = BytesIO()
Image.new("RGB", (1, 1), color=(1, 2, 3)).save(_png_buffer, format="PNG")
PNG_1X1 = _png_buffer.getvalue()
FIXTURE_COUNTS = {
    "bicycle": 3,
    "car": 10,
    "motorcycle": 2,
    "bus": 1,
    "truck": 1,
}


def fixture_detections(counts=FIXTURE_COUNTS):
    class_ids = {
        "car": 2,
        "motorcycle": 3,
        "bus": 5,
        "truck": 7,
        "bicycle": 1,
    }
    return [
        {
            "class_id": class_ids[category],
            "category": category,
            "confidence": 0.9,
            "bounding_box_normalized": {
                "x_min": 0.1, "y_min": 0.2, "x_max": 0.3, "y_max": 0.4,
            },
        }
        for category in ("car", "motorcycle", "bus", "truck", "bicycle")
        for _ in range(counts[category])
    ]


def demo_request() -> dict:
    classes = ("bicycle", "car", "motorcycle", "bus", "truck")
    activities = {
        name: {
            "trips_per_vehicle_per_operating_day": 1,
            "avg_one_way_km": 10,
            "source_description": "Synthetic demo assumption; not a measured commute.",
        }
        for name in classes
    }
    values = {"car": 0.150, "motorcycle": 0.04, "bus": 0.8, "truck": 0.08}
    factors = {
        name: {
            "factor_id": f"DEMO_{name.upper()}",
            "vehicle_category": name,
            "value": values[name],
            "unit": "kg CO2/veh-km",
            "geographic_scope": "Illustrative demo only",
            "source_description": "User-supplied illustrative factor; not verified.",
            "source_reference": None,
            "applicability_notes": f"Demo applies only to {name}.",
            "limitations": "Unverified demo value; not approved for production.",
        }
        for name in ("car", "motorcycle", "bus", "truck")
    }
    return {
        "annual_operating_days": 200,
        "annual_days_source_description": "Synthetic test fixture only.",
        "vehicle_assumptions": activities,
        "illustrative_factors": factors,
        "scenario_assumptions": {
            "carpool_activity_reduction_share": 0.5,
            "shuttle_shift_share": 0.5,
            "active_travel_shift_share": 0.5,
            "active_travel_max_one_way_km": 15,
            "assumption_basis": "Synthetic shares for testing only.",
            "shuttle_service": {
                "daily_vehicles": 1,
                "trips_per_vehicle_per_operating_day": 2,
                "avg_one_way_km": 8,
                "source_description": "Synthetic shuttle-service assumption.",
            },
        },
    }


def multipart_body(image=PNG_1X1, assumptions=None, content_type="image/png"):
    boundary = "CarboSyncDemoBoundary"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"assumptions_json\"\r\n\r\n".encode(),
        json.dumps(assumptions or demo_request(), allow_nan=False).encode(),
        b"\r\n",
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
            f"filename=\"snapshot.png\"\r\nContent-Type: {content_type}\r\n\r\n"
        ).encode(),
        image,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


async def asgi_request(path, body, content_type, method="POST", include_length=True):
    sent = False
    messages = []

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    try:
        await app(
            {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"test"),
                (b"content-type", content_type.encode()),
                *(
                    [(b"content-length", str(len(body)).encode())]
                    if include_length
                    else []
                ),
            ],
            "server": ("test", 80),
            "client": ("127.0.0.1", 12345),
        },
        receive,
            send,
        )
    except Exception:
        # Starlette sends the generic server-error response before re-raising.
        pass
    start = next(m for m in messages if m["type"] == "http.response.start")
    raw = b"".join(
        m.get("body", b"") for m in messages if m["type"] == "http.response.body"
    )
    return start["status"], json.loads(raw), dict(start.get("headers", []))


class DemoApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "demo.sqlite3"
        self.env_patcher = patch.dict(
            os.environ, {"CARBOSYNC_DATABASE_PATH": str(self.database_path)}
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        self.temp_directory.cleanup()

    def request(self, image=PNG_1X1, assumptions=None, content_type="image/png"):
        body, multipart_type = multipart_body(image, assumptions, content_type)
        return asyncio.run(asgi_request("/api/demo/analyze", body, multipart_type))

    def test_empty_database_initializes_and_student_summary_endpoints_are_safe(self):
        status, students, _ = asyncio.run(asgi_request("/api/demo/students", b"", "application/json", "GET"))
        self.assertEqual(status, 200)
        self.assertEqual(students["students"], [])
        self.assertEqual(students["college_address"], "")
        self.assertTrue(self.database_path.is_file())

        status, summary, _ = asyncio.run(asgi_request("/api/demo/commute-summary", b"", "application/json", "GET"))
        self.assertEqual(status, 200)
        self.assertEqual(summary["student_count"], 0)
        self.assertEqual(summary["calculation_status"], "unavailable")
        self.assertIsNone(summary["annual_kg_co2"])
        self.assertNotIn("students", summary)

    def test_valid_upload_calculates_scenarios_and_persists_retrievable_analysis(self):
        detection = DetectionResult(
            deepcopy(FIXTURE_COUNTS),
            "data:image/jpeg;base64,dGVzdA==",
            "YOLO11n",
            0.35,
            detections=fixture_detections(),
            class_mapping={"bicycle": [1], "car": [2], "motorcycle": [3], "bus": [5], "truck": [7]},
            metadata={
                "weights_sha256": "b" * 64,
                "runtime_versions": {"python": "test", "ultralytics": "test", "torch": "test"},
                "supported_classes": {"2": "car", "3": "motorcycle"},
                "inference_settings": {
                    "confidence_threshold": 0.35,
                    "iou_threshold": 0.3,
                    "image_size": 1280,
                    "nms_mode": "class_aware",
                    "device": "cpu",
                },
            },
        )
        with patch("backend.main.detect_vehicle_image", return_value=detection):
            status, response, _ = self.request()
        self.assertEqual(status, 201)
        self.assertEqual(response["detections"]["motor_vehicle_total"], 14)
        self.assertEqual(response["detections"]["bicycle_total"], 3)
        self.assertEqual(response["model"]["confidence_threshold"], 0.35)
        self.assertEqual(response["model"]["weights_sha256"], "b" * 64)
        self.assertEqual(response["detection_mode"], "real")
        self.assertEqual(response["inference_status"], "completed_with_detections")
        self.assertEqual(response["detection_details"][0]["category"], "car")
        self.assertEqual(response["detections"]["details"], response["detection_details"])
        result = response["result"]
        self.assertEqual(result["approval_status"], "illustrative_unapproved")
        self.assertFalse(result["independently_verified"])
        self.assertEqual(len(result["scenarios"]), 3)
        self.assertEqual(result["baseline"]["annual_vehicle_km"], 56000)
        self.assertEqual(result["baseline"]["annual_kg_co2"], 9840)
        self.assertEqual(result["scenarios"][0]["estimated_emissions"]["annual_kg_co2"], 6840)
        self.assertTrue(result["recommendations"]["fallback_flag"])
        self.assertNotIn("data:image", json.dumps(result))
        status, saved, _ = asyncio.run(
            asgi_request(
                f"/api/demo/analyses/{response['analysis_id']}",
                b"",
                "application/json",
                "GET",
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(saved["detections"]["per_class"], FIXTURE_COUNTS)
        self.assertEqual(saved["detections"]["details"], response["detection_details"])
        self.assertEqual(saved["detections"]["model_metadata"]["weights_sha256"], "b" * 64)
        self.assertEqual(
            saved["detections"]["model_metadata"]["inference_settings"],
            response["model"]["inference_settings"],
        )
        self.assertEqual(
            saved["detections"]["class_mapping"],
            {"bicycle": [1], "car": [2], "motorcycle": [3], "bus": [5], "truck": [7]},
        )
        self.assertEqual(saved["result"]["baseline"], result["baseline"])
        self.assertIn("illustrative_factors", saved["assumptions"])
        self.assertNotIn("annotated_image_data_uri", json.dumps(saved))

    def test_invalid_type_malformed_image_and_detection_failure(self):
        with patch("backend.main.detect_vehicle_image") as detect:
            status, body, _ = self.request(content_type="text/plain")
            self.assertEqual(status, 415)
            self.assertEqual(body, {"error": True, "message": "Unsupported image type."})
            status, body, _ = self.request(image=b"not an image")
            self.assertEqual(status, 422)
            self.assertEqual(body, {"error": True, "message": "Request validation failed."})
            detect.assert_not_called()
        with patch(
            "backend.main.detect_vehicle_image",
            side_effect=DetectionFailed("Vehicle inference failed; no detection result was produced."),
        ):
            status, body, _ = self.request()
        self.assertEqual(status, 500)
        self.assertEqual(body["inference_status"], "failed")
        self.assertTrue(body["error"])
        self.assertNotIn("private model diagnostics", json.dumps(body))

    def test_upload_over_size_limit_and_missing_weights_are_safe(self):
        status, body, _ = self.request(image=b"x" * (10 * 1024 * 1024 + 1))
        self.assertEqual(status, 413, body)
        self.assertEqual(body, {"error": True, "message": "Uploaded image exceeds the allowed size."})
        missing_path = Path(self.temp_directory.name) / "missing.pt"
        with patch.dict(
            os.environ,
            {"CARBOSYNC_YOLO_MODEL_PATH": str(missing_path)},
        ):
            status, body, _ = self.request()
        self.assertEqual(status, 503)
        self.assertTrue(body["error"])
        self.assertEqual(body["inference_status"], "unavailable")
        self.assertIn("YOLO weights are unavailable", body["message"])
        self.assertNotIn(self.temp_directory.name, json.dumps(body))
        self.assertFalse(missing_path.exists(), "the service must not download weights")

        body, multipart_type = multipart_body(
            image=b"x" * (10 * 1024 * 1024 + 300 * 1024)
        )
        status, body, _ = asyncio.run(
            asgi_request(
                "/api/demo/analyze",
                body,
                multipart_type,
                include_length=False,
            )
        )
        self.assertEqual(status, 413, body)
        self.assertEqual(body, {"error": True, "message": "Uploaded image exceeds the allowed size."})

    def test_missing_or_invalid_assumptions_and_unknown_analysis(self):
        assumptions = demo_request()
        del assumptions["illustrative_factors"]["truck"]
        status, body, _ = self.request(assumptions=assumptions)
        self.assertEqual(status, 422)
        self.assertEqual(body, {"error": True, "message": "Request validation failed."})
        status, body, _ = asyncio.run(
            asgi_request("/api/demo/analyses/demo_unknown", b"", "application/json", "GET")
        )
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": True, "message": "Resource not found."})

    def test_simulated_detection_is_explicit_and_never_calls_yolo(self):
        assumptions = demo_request()
        assumptions["detection_mode"] = "simulated"
        assumptions["simulated_detection_counts"] = FIXTURE_COUNTS
        assumptions["simulated_detection_source_description"] = (
            "Synthetic counts for a presentation walkthrough."
        )
        with patch("backend.main.detect_vehicle_image") as detect:
            status, response, _ = self.request(assumptions=assumptions)
        self.assertEqual(status, 201)
        detect.assert_not_called()
        self.assertTrue(response["detections"]["simulated"])
        self.assertEqual(response["detections"]["mode"], "simulated")
        self.assertEqual(response["inference_status"], "simulated")
        self.assertEqual(
            response["detections"]["observation_scope"], "user_supplied_simulation"
        )
        self.assertEqual(response["detections"]["per_class"], FIXTURE_COUNTS)
        self.assertIsNone(response["annotated_image_data_uri"])
        self.assertIn("not analyzed", response["result"]["warnings"][0])
        self.assertIn("Simulated detection counts", response["result"]["evidence_label"])

    def test_simulated_mode_requires_explicit_complete_counts(self):
        assumptions = demo_request()
        assumptions["detection_mode"] = "simulated"
        status, body, _ = self.request(assumptions=assumptions)
        self.assertEqual(status, 422)
        self.assertEqual(body, {"error": True, "message": "Request validation failed."})


class DemoCalculationTests(unittest.TestCase):
    def test_coco_mapping_and_deterministic_formula(self):
        self.assertEqual(
            count_coco_vehicle_classes([1, 2, 2, 3, 5, 7, 0]),
            {"bicycle": 1, "car": 2, "motorcycle": 1, "bus": 1, "truck": 1},
        )
        result = calculate_demo_analysis(
            detection_counts=FIXTURE_COUNTS,
            request=demo_request(),
        )
        self.assertEqual(result["baseline"]["annual_vehicle_km"], 56000)
        self.assertEqual(result["baseline"]["annual_kg_co2"], 9840)
        self.assertEqual(result["scenarios"][0]["reduction_vs_baseline_tonnes"], 3.0)
        self.assertAlmostEqual(
            result["scenarios"][0]["percentage_reduction_vs_baseline"],
            30.48780487804878,
        )

    def test_invalid_nonfinite_factor_unit_and_unfeasible_share_rejected(self):
        request = demo_request()
        request["vehicle_assumptions"]["car"]["avg_one_way_km"] = float("inf")
        with self.assertRaises(ValueError):
            calculate_demo_analysis(detection_counts=FIXTURE_COUNTS, request=request)
        request = demo_request()
        request["illustrative_factors"]["car"]["unit"] = "kg CO2/pass-km"
        with self.assertRaises(ValueError):
            calculate_demo_analysis(detection_counts=FIXTURE_COUNTS, request=request)
        request = demo_request()
        request["scenario_assumptions"]["active_travel_shift_share"] = 1.1
        with self.assertRaises(ValueError):
            calculate_demo_analysis(detection_counts=FIXTURE_COUNTS, request=request)

    def test_positive_activity_rejects_zero_commute_distance(self):
        request = demo_request()
        request["vehicle_assumptions"]["car"]["avg_one_way_km"] = 0
        with self.assertRaisesRegex(ValueError, "car avg_one_way_km must be greater than 0"):
            calculate_demo_analysis(detection_counts=FIXTURE_COUNTS, request=request)

    def test_zero_activity_placeholder_allows_zero_distance(self):
        request = demo_request()
        for assumption in request["vehicle_assumptions"].values():
            assumption["trips_per_vehicle_per_operating_day"] = 0
            assumption["avg_one_way_km"] = 0
        result = calculate_demo_analysis(detection_counts=FIXTURE_COUNTS, request=request)
        self.assertEqual(result["baseline"]["annual_kg_co2"], 0)

    def test_active_shuttle_service_rejects_zero_route_distance(self):
        request = demo_request()
        request["scenario_assumptions"]["shuttle_service"]["avg_one_way_km"] = 0
        with self.assertRaisesRegex(ValueError, "shuttle avg_one_way_km must be greater than 0"):
            calculate_demo_analysis(detection_counts=FIXTURE_COUNTS, request=request)

    def test_scenario_changes_do_not_exceed_feasible_activity(self):
        request = demo_request()
        request["scenario_assumptions"]["carpool_activity_reduction_share"] = 1
        request["scenario_assumptions"]["active_travel_shift_share"] = 1
        request["scenario_assumptions"]["shuttle_service"]["daily_vehicles"] = 0
        result = calculate_demo_analysis(detection_counts=FIXTURE_COUNTS, request=request)
        total = result["baseline"]["annual_kg_co2"]
        self.assertLessEqual(result["scenarios"][0]["reduction_vs_baseline_tonnes"] * 1000, total)
        self.assertLessEqual(result["scenarios"][2]["reduction_vs_baseline_tonnes"] * 1000, total)


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.analysis = calculate_demo_analysis(
            detection_counts=FIXTURE_COUNTS, request=demo_request()
        )

    def test_missing_credentials_and_timeout_use_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            fallback = generate_recommendations(self.analysis)
        self.assertEqual(fallback["status"], "fallback")
        self.assertTrue(fallback["fallback_flag"])
        env = {
            "CARBOSYNC_LLM_PROVIDER": "openai_compatible",
            "CARBOSYNC_LLM_API_KEY": "test-secret",
            "CARBOSYNC_LLM_BASE_URL": "http://localhost:8080/v1",
            "CARBOSYNC_LLM_MODEL": "test-model",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "backend.recommendations.urlopen", side_effect=TimeoutError("secret error")
        ):
            fallback = generate_recommendations(self.analysis)
        self.assertEqual(fallback["llm_status"], "provider_unavailable")
        self.assertNotIn("test-secret", json.dumps(fallback))
        self.assertNotIn("secret error", json.dumps(fallback))

    def test_valid_provider_response_is_checked_and_image_is_not_sent(self):
        best = self.analysis["best_scenario"]["id"]
        draft = {
            "summary": "Review these options with campus transport staff.",
            "best_scenario": best,
            "recommendations": [{
                "priority": 1,
                "title": "Review shuttle operations",
                "why_it_may_help": "The comparison suggests this option may help under the supplied assumptions.",
                "practical_tradeoffs": "It requires operational planning and budget review.",
                "related_scenario": best,
            }],
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _limit):
                return json.dumps({"choices": [{"message": {"content": json.dumps(draft)}}]}).encode()

        env = {
            "CARBOSYNC_LLM_PROVIDER": "openai_compatible",
            "CARBOSYNC_LLM_API_KEY": "test-secret",
            "CARBOSYNC_LLM_BASE_URL": "http://localhost:8080/v1",
            "CARBOSYNC_LLM_MODEL": "test-model",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "backend.recommendations.urlopen", return_value=Response()
        ) as call:
            result = generate_recommendations(self.analysis)
        self.assertEqual(result["status"], "llm")
        self.assertEqual(result["best_scenario"]["id"], best)
        self.assertNotIn("test-secret", json.dumps(result))
        user_message = json.loads(call.call_args.args[0].data)["messages"][1]["content"]
        self.assertNotIn('"image"', user_message)

    def test_provider_cannot_invent_numeric_savings_or_change_best(self):
        draft = {
            "summary": "This saves 50 tonnes every year.",
            "best_scenario": "carpool",
            "recommendations": [],
        }

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _limit):
                return json.dumps({"choices": [{"message": {"content": json.dumps(draft)}}]}).encode()

        env = {
            "CARBOSYNC_LLM_PROVIDER": "openai_compatible",
            "CARBOSYNC_LLM_API_KEY": "test-secret",
            "CARBOSYNC_LLM_BASE_URL": "http://localhost:8080/v1",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "backend.recommendations.urlopen", return_value=Response()
        ):
            result = generate_recommendations(self.analysis)
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["llm_status"], "invalid_provider_response")


class ImageValidationTests(unittest.TestCase):
    def test_custom_model_labels_map_by_name_not_coco_id(self):
        self.assertEqual(
            resolve_vehicle_class_ids(
                {0: "truck", 1: "person", 2: "bike", 3: "motorbike", 4: "bus"}
            ),
            {0: "truck", 2: "bicycle", 3: "motorcycle", 4: "bus"},
        )

    def test_readable_image_and_mime_content_match(self):
        try:
            result = validate_image_bytes(PNG_1X1, "image/png")
        except ImageInputError:
            raise
        except ImportError:
            self.skipTest("Pillow is not installed")
        self.assertEqual(result.image_format, "RGB")
        with self.assertRaises(ImageInputError):
            validate_image_bytes(PNG_1X1, "image/jpeg")

    def test_detection_maps_classes_and_reuses_local_model(self):
        import backend.vehicle_detection as detector_module

        with tempfile.TemporaryDirectory() as directory:
            weight_path = Path(directory) / "local.pt"
            weight_path.write_bytes(b"test-only fake model marker")
            prior_model = detector_module._loaded_model
            prior_model_path = detector_module._loaded_model_path
            prior_model_hash = detector_module._loaded_model_sha256
            prior_model_metadata = detector_module._loaded_model_metadata
            fake_model = MagicMock()
            boxes = SimpleNamespace(
                cls=SimpleNamespace(tolist=lambda: [2, 0, 2, 3, 5, 4]),
                conf=SimpleNamespace(tolist=lambda: [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]),
                xyxyn=SimpleNamespace(
                    tolist=lambda: [
                        [0.1, 0.2, 0.3, 0.4],
                        [0.2, 0.3, 0.4, 0.5],
                        [0.3, 0.4, 0.5, 0.6],
                        [0.4, 0.5, 0.6, 0.7],
                        [0.5, 0.6, 0.7, 0.8],
                        [0.6, 0.7, 0.8, 0.9],
                    ]
                ),
            )
            class ArrayLike:
                def __getitem__(self, _key):
                    return self

            fake_result = SimpleNamespace(
                boxes=boxes,
                names={
                    0: "car",
                    1: "person",
                    2: "bicycle",
                    3: "motorcycle",
                    4: "truck",
                    5: "bus",
                },
                plot=ArrayLike,
            )
            fake_model.names = fake_result.names
            fake_model.task = "detect"
            fake_model.predict.return_value = [fake_result]
            fake_yolo = MagicMock(return_value=fake_model)
            fake_annotated = MagicMock()
            fake_annotated.save.side_effect = lambda buffer, **_: buffer.write(b"mock-jpeg")
            detector_module._loaded_model = None
            detector_module._loaded_model_path = None
            detector_module._loaded_model_sha256 = None
            detector_module._loaded_model_metadata = None
            try:
                with (
                    patch.dict(
                        os.environ,
                        {
                            "CARBOSYNC_YOLO_MODEL_PATH": str(weight_path),
                            "CARBOSYNC_YOLO_CONFIDENCE": "0.42",
                        },
                    ),
                    patch.dict(
                        sys.modules,
                        {"ultralytics": SimpleNamespace(YOLO=fake_yolo)},
                    ),
                    patch("PIL.Image.fromarray", return_value=fake_annotated),
                ):
                    first = detect_vehicle_image(object())
                    second = detect_vehicle_image(object())
            finally:
                detector_module._loaded_model = prior_model
                detector_module._loaded_model_path = prior_model_path
                detector_module._loaded_model_sha256 = prior_model_hash
                detector_module._loaded_model_metadata = prior_model_metadata

        self.assertEqual(
            first.counts,
            {"bicycle": 2, "car": 1, "motorcycle": 1, "bus": 1, "truck": 1},
        )
        self.assertEqual(first.detections[0]["category"], "bicycle")
        self.assertEqual(first.detections[0]["class_id"], 2)
        self.assertEqual(first.detections[0]["bounding_box_normalized"]["x_min"], 0.1)
        self.assertEqual(
            first.class_mapping,
            {"car": [0], "bicycle": [2], "motorcycle": [3], "truck": [4], "bus": [5]},
        )
        self.assertEqual(first.unmapped_vehicle_categories, [])
        self.assertEqual(first.confidence_threshold, 0.42)
        self.assertEqual(
            first.metadata["weights_sha256"],
            hashlib.sha256(b"test-only fake model marker").hexdigest(),
        )
        self.assertEqual(first.metadata["inference_settings"]["nms_mode"], "class_aware")
        self.assertEqual(first.inference_status, "completed_with_detections")
        self.assertEqual(
            {category: sum(item["category"] == category for item in first.detections)
             for category in first.counts},
            first.counts,
        )
        self.assertTrue(first.annotated_image_data_uri.startswith("data:image/jpeg;base64,"))
        self.assertEqual(second.counts, first.counts)
        fake_yolo.assert_called_once_with(str(weight_path.resolve()))
        self.assertEqual(fake_model.predict.call_count, 2)
        self.assertEqual(fake_model.predict.call_args.kwargs["device"], "cpu")
        self.assertFalse(fake_model.predict.call_args.kwargs["agnostic_nms"])
        self.assertEqual(fake_model.predict.call_args.kwargs["iou"], 0.30)
        self.assertEqual(fake_model.predict.call_args.kwargs["imgsz"], 640)

    def test_successful_empty_inference_is_distinct_from_failure(self):
        import backend.vehicle_detection as detector_module

        fake_model = MagicMock()
        class PlotArray:
            def __getitem__(self, _key):
                return self

        fake_result = SimpleNamespace(
            boxes=None,
            names={1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"},
            plot=lambda: PlotArray(),
        )

        fake_model.predict.return_value = [fake_result]
        fake_annotated = MagicMock()
        fake_annotated.save.side_effect = lambda buffer, **_: buffer.write(b"mock-jpeg")
        config = detector_module.DetectorConfig(
            Path("local-only/model.pt"), 0.15, 0.30, 1280, "class_aware"
        )
        with (
            patch("backend.vehicle_detection._load_model", return_value=fake_model),
            patch("backend.vehicle_detection.get_detector_config", return_value=config),
            patch("backend.vehicle_detection._loaded_model_metadata", {"weights_sha256": "a" * 64}),
            patch("PIL.Image.fromarray", return_value=fake_annotated),
        ):
            empty = detect_vehicle_image(object())
            self.assertEqual(empty.inference_status, "completed_no_detections")
            self.assertFalse(empty.detections)
            self.assertEqual(sum(empty.counts.values()), 0)
            fake_model.predict.side_effect = RuntimeError("private inference diagnostic")
            with self.assertRaises(DetectionFailed):
                detect_vehicle_image(object())


if __name__ == "__main__":
    unittest.main()
