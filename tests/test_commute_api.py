"""Focused API contract tests without an extra HTTP test-client dependency."""

import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from backend.main import app, configured_cors_origins
from backend.carbon_engine import EXPECTED_EMISSION_FACTOR_UNIT
from backend.database import database_connection, initialize_schema


FACTOR = {
    "factor_id": "EF_TEST_01",
    "version": "fixture-v1",
    "value": 0.150,
    "unit": EXPECTED_EMISSION_FACTOR_UNIT,
    "provenance": {
        "origin": "test_data",
        "factor_id": "EF_TEST_01",
        "metric_scope": "Tailpipe_CO2",
        "geographic_scope": "Not applicable (benchmark fixture)",
        "source_title": "TraceTwin TEST_PLAN.md benchmark",
        "source_url": None,
        "version_year": None,
        "approximation_notes": "Test fixture only; not an authoritative factor.",
    },
}


def activity_provenance(origin: str = "user_provided") -> dict:
    result = {
        "origin": origin,
        "method": "Aggregate test fixture entry",
        "source_description": "Synthetic test data; not a real campus observation.",
    }
    if origin == "observed":
        result["observation_period"] = "synthetic test observation period"
    return result


def valid_payload() -> dict:
    categories = (
        "Cars",
        "Motorcycles and scooters",
        "Buses and campus shuttles",
        "Other fuel-burning vehicles",
    )
    return {
        "calculation_mode": "candidate",
        "annual_days": 200,
        "annual_days_provenance": activity_provenance(),
        "sample_size": 18,
        "population_total": 4500,
        "mode_data": [
            {
                "category": category,
                "daily_vehicles": 50 if category == "Cars" else 0,
                "daily_vehicles_provenance": activity_provenance(),
                "avg_one_way_km": 15,
                "avg_one_way_km_provenance": activity_provenance(),
                "occupancy": 1 if category == "Cars" else 35,
                "candidate_factor": deepcopy(FACTOR),
                "factor_reference": None,
            }
            for category in categories
        ],
    }


async def asgi_request(
    method: str,
    path: str,
    payload: dict | None = None,
    headers: list[tuple[bytes, bytes]] | None = None,
    capture_server_error: bool = False,
) -> tuple[int, dict, dict[bytes, bytes]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    messages = []
    received = False

    async def receive() -> dict:
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"test")]
        + ([(b"content-type", b"application/json")] if payload is not None else [])
        + (headers or []),
        "server": ("test", 80),
        "client": ("127.0.0.1", 12345),
    }
    try:
        await app(scope, receive, send)
    except Exception:
        # Starlette's server-error middleware sends the 500 response and then
        # re-raises the original error. Capture it only for that ASGI test.
        if not capture_server_error:
            raise
    response_start = next(
        message
        for message in messages
        if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return (
        response_start["status"],
        json.loads(response_body) if response_body.startswith(b"{") else {},
        dict(response_start.get("headers", [])),
    )


class CommuteApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test.sqlite3"
        self.database_path_patcher = patch.dict(
            os.environ,
            {"CARBOSYNC_DATABASE_PATH": str(self.database_path)},
        )
        self.database_path_patcher.start()
        status, response, _ = asyncio.run(
            asgi_request("POST", "/api/assessments", {})
        )
        self.assertEqual(status, 201)
        self.assessment_id = response["assessment_id"]

    def tearDown(self) -> None:
        self.database_path_patcher.stop()
        self.temp_directory.cleanup()

    def request(self, payload: dict) -> tuple[int, dict]:
        status, response, _ = asyncio.run(
            asgi_request(
                "POST",
                f"/api/assessments/{self.assessment_id}/commute-inputs",
                payload,
            )
        )
        return status, response

    def retrieve(self, assessment_id: str | None = None) -> tuple[int, dict]:
        status, response, _ = asyncio.run(
            asgi_request(
                "GET",
                f"/api/assessments/{assessment_id or self.assessment_id}",
            )
        )
        return status, response

    def test_assessment_creation_returns_distinct_persisted_ids(self) -> None:
        status, response, _ = asyncio.run(
            asgi_request("POST", "/api/assessments", {})
        )
        self.assertEqual(status, 201)
        self.assertTrue(response["assessment_id"].startswith("ast_"))
        self.assertGreater(len(response["assessment_id"]), 4)
        self.assertTrue(response["created_at"].endswith("Z"))

        get_status, saved = self.retrieve(response["assessment_id"])
        self.assertEqual(get_status, 200)
        self.assertEqual(saved["assessment_id"], response["assessment_id"])
        self.assertEqual(saved["created_at"], response["created_at"])
        self.assertEqual(saved["commute_calculations"], [])

        _, another, _ = asyncio.run(asgi_request("POST", "/api/assessments", {}))
        self.assertNotEqual(response["assessment_id"], another["assessment_id"])

    def test_valid_request_returns_reproducible_benchmark(self) -> None:
        status, response = self.request(valid_payload())
        self.assertEqual(status, 200)
        self.assertEqual(response["assessment_id"], self.assessment_id)
        self.assertEqual(response["annual_vkt_total_km_per_year"], 300_000)
        self.assertEqual(response["annual_emissions_kg_co2_per_year"], 45_000)
        self.assertEqual(response["annual_emissions_tonnes_co2_per_year"], 45)
        self.assertFalse(response["is_campus_projection"])
        self.assertEqual(response["calculation_mode"], "candidate")
        self.assertEqual(response["approval_status"], "unapproved")
        self.assertEqual(
            response["calculation_method_version"],
            "commute_tailpipe_co2_v1",
        )
        self.assertFalse(response["independently_verified"])
        self.assertEqual(
            response["b3_metadata"],
            {
                "availability": "available_b3",
                "activity_provenance": "available",
                "factor_governance": "candidate_unapproved",
                "calculation_method_version": "commute_tailpipe_co2_v1",
            },
        )
        car = response["category_breakdown"][0]
        self.assertEqual(car["emission_factor_kg_co2_per_vehicle_km"], 0.150)
        self.assertEqual(car["factor_snapshot"]["origin"], "test_data")
        self.assertEqual(car["factor_snapshot"]["approval_status"], "candidate")
        self.assertTrue(
            car["factor_snapshot"]["version"].startswith("candidate-sha256:")
        )
        self.assertEqual(car["factor_snapshot"]["declared_version"], "fixture-v1")

    def test_saved_inputs_and_calculation_are_retrievable_after_reopen(self) -> None:
        payload = valid_payload()
        status, response = self.request(payload)
        self.assertEqual(status, 200)

        # Each request opens and closes its own connection. Reopening and
        # initializing the same database must leave the saved data available.
        reopened = sqlite3.connect(self.database_path)
        try:
            reopened.execute("PRAGMA foreign_keys = ON")
            initialize_schema(reopened)
            reopened.commit()
        finally:
            reopened.close()

        get_status, assessment = self.retrieve()
        self.assertEqual(get_status, 200)
        self.assertEqual(len(assessment["commute_calculations"]), 1)
        saved = assessment["commute_calculations"][0]
        self.assertTrue(saved["calculation_id"].startswith("calc_"))
        self.assertEqual(saved["inputs"], payload)
        self.assertEqual(saved["inputs"]["mode_data"][0]["candidate_factor"], FACTOR)
        self.assertEqual(
            saved["inputs"]["annual_days_provenance"],
            payload["annual_days_provenance"],
        )
        self.assertEqual(saved["result"], response)
        self.assertEqual(saved["result"]["annual_vkt_total_km_per_year"], 300_000)
        self.assertEqual(saved["result"]["annual_emissions_kg_co2_per_year"], 45_000)
        self.assertEqual(saved["result"]["annual_emissions_tonnes_co2_per_year"], 45)

    def test_corrupt_persisted_json_returns_generic_internal_error(self) -> None:
        status, response = self.request(valid_payload())
        self.assertEqual(status, 200)

        private_marker = "corrupted-json-private-marker-91ff"
        with database_connection() as connection:
            with connection:
                row = connection.execute(
                    "SELECT calculation_id FROM commute_calculations WHERE assessment_id = ?",
                    (self.assessment_id,),
                ).fetchone()
                self.assertIsNotNone(row)
                connection.execute(
                    "UPDATE commute_calculations SET inputs_json = ? WHERE calculation_id = ?",
                    (f"not-json:{private_marker}", row["calculation_id"]),
                )

        status, response, _ = asyncio.run(
            asgi_request(
                "GET",
                f"/api/assessments/{self.assessment_id}",
                capture_server_error=True,
            )
        )
        self.assertEqual(status, 500)
        self.assertEqual(
            response,
            {"error": True, "message": "An unexpected error occurred."},
        )

        response_text = json.dumps(response)
        for internal_detail in (
            private_marker,
            "JSONDecodeError",
            "Traceback",
            "sqlite3",
        ):
            with self.subTest(internal_detail=internal_detail):
                self.assertNotIn(internal_detail, response_text)

    def test_unknown_assessment_is_not_created_by_commute_request(self) -> None:
        status, response, _ = asyncio.run(
            asgi_request(
                "POST",
                "/api/assessments/unknown-assessment/commute-inputs",
                valid_payload(),
            )
        )
        self.assertEqual(status, 404)
        self.assertEqual(
            response,
            {"error": True, "message": "Resource not found."},
        )
        get_status, get_response = self.retrieve("unknown-assessment")
        self.assertEqual(get_status, 404)
        self.assertEqual(
            get_response,
            {"error": True, "message": "Resource not found."},
        )

    def test_invalid_input_does_not_save_a_calculation(self) -> None:
        payload = valid_payload()
        payload["mode_data"][0]["avg_one_way_km"] = -1
        status, response = self.request(payload)
        self.assertEqual(status, 422)
        self.assertEqual(
            response,
            {"error": True, "message": "Request validation failed."},
        )
        _, assessment = self.retrieve()
        self.assertEqual(assessment["commute_calculations"], [])

    def test_failed_persistence_does_not_leave_calculation_record(self) -> None:
        with database_connection() as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TRIGGER reject_commute_calculation
                    BEFORE INSERT ON commute_calculations
                    BEGIN
                        SELECT RAISE(ABORT, 'injected persistence failure');
                    END
                    """
                )

        status, response, _ = asyncio.run(
            asgi_request(
                "POST",
                f"/api/assessments/{self.assessment_id}/commute-inputs",
                valid_payload(),
                capture_server_error=True,
            )
        )
        self.assertEqual(status, 500)
        self.assertEqual(
            response,
            {"error": True, "message": "An unexpected error occurred."},
        )
        _, assessment = self.retrieve()
        self.assertEqual(assessment["commute_calculations"], [])

    def test_foreign_key_enforcement_rejects_orphan_calculation(self) -> None:
        with database_connection() as connection:
            self.assertEqual(
                connection.execute("PRAGMA foreign_keys").fetchone()[0],
                1,
            )
            with self.assertRaises(sqlite3.IntegrityError):
                with connection:
                    connection.execute(
                        """
                        INSERT INTO commute_calculations
                            (calculation_id, assessment_id, created_at,
                             inputs_json, result_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        ("calc_orphan", "missing-assessment", "now", "{}", "{}"),
                    )

    def test_database_paths_are_isolated(self) -> None:
        other_path = Path(self.temp_directory.name) / "other.sqlite3"
        with patch.dict(
            os.environ,
            {"CARBOSYNC_DATABASE_PATH": str(other_path)},
        ):
            status, response = self.retrieve()
        self.assertEqual(status, 404)
        self.assertEqual(
            response,
            {"error": True, "message": "Resource not found."},
        )
        self.assertTrue(self.database_path.exists())
        self.assertTrue(other_path.exists())

    def test_invalid_input_returns_client_error(self) -> None:
        payload = valid_payload()
        payload["mode_data"][0]["avg_one_way_km"] = -1
        status, response = self.request(payload)
        self.assertEqual(status, 422)
        self.assertEqual(
            response,
            {"error": True, "message": "Request validation failed."},
        )

    def test_boolean_measurement_returns_client_error(self) -> None:
        payload = valid_payload()
        payload["mode_data"][0]["daily_vehicles"] = True
        status, _ = self.request(payload)
        self.assertEqual(status, 422)

    def test_missing_required_field_returns_client_error(self) -> None:
        payload = valid_payload()
        del payload["annual_days"]
        status, response = self.request(payload)
        self.assertEqual(status, 422)
        self.assertEqual(
            response,
            {"error": True, "message": "Request validation failed."},
        )

    def test_candidate_factor_wrong_unit_is_rejected(self) -> None:
        payload = valid_payload()
        payload["mode_data"][0]["candidate_factor"]["unit"] = "kg CO2/pass-km"
        status, response = self.request(payload)
        self.assertEqual(status, 422)
        self.assertEqual(
            response,
            {"error": True, "message": "Request validation failed."},
        )

    def test_calculation_mode_is_required_and_restricted(self) -> None:
        missing = valid_payload()
        del missing["calculation_mode"]
        status, _ = self.request(missing)
        self.assertEqual(status, 422)

        unsupported = valid_payload()
        unsupported["calculation_mode"] = "automatic"
        status, response = self.request(unsupported)
        self.assertEqual(status, 422)
        self.assertEqual(
            response,
            {"error": True, "message": "Request validation failed."},
        )

    def test_approved_mode_fails_safely_while_registry_is_empty(self) -> None:
        from backend.factor_registry import APPROVED_FACTOR_REGISTRY

        self.assertEqual(len(APPROVED_FACTOR_REGISTRY), 0)
        payload = valid_payload()
        payload["calculation_mode"] = "approved"
        for mode in payload["mode_data"]:
            del mode["candidate_factor"]
            mode["factor_reference"] = {
                "factor_id": "EF_CAR_IN_01",
                "version": "1",
            }

        status, response, _ = asyncio.run(
            asgi_request(
                "POST",
                f"/api/assessments/{self.assessment_id}/commute-inputs",
                payload,
            )
        )
        self.assertEqual(status, 503)
        self.assertEqual(
            response,
            {
                "error": True,
                "message": "Approved emission factors are currently unavailable.",
            },
        )
        _, assessment = self.retrieve()
        self.assertEqual(assessment["commute_calculations"], [])

    def test_approved_mode_rejects_caller_supplied_factor_values(self) -> None:
        payload = valid_payload()
        payload["calculation_mode"] = "approved"
        for mode in payload["mode_data"]:
            del mode["candidate_factor"]
            mode["factor_reference"] = {"factor_id": "EF_TEST_01", "version": "1"}
            mode["emission_factor"] = deepcopy(FACTOR)
        status, response = self.request(payload)
        self.assertEqual(status, 422)
        self.assertEqual(
            response,
            {"error": True, "message": "Request validation failed."},
        )

    def test_candidate_cannot_claim_approval_or_verified_source(self) -> None:
        approval_override = valid_payload()
        approval_override["mode_data"][0]["candidate_factor"][
            "approval_status"
        ] = "approved"
        status, _ = self.request(approval_override)
        self.assertEqual(status, 422)

        verified_claim = valid_payload()
        verified_claim["mode_data"][0]["candidate_factor"]["provenance"][
            "origin"
        ] = "verified_reference"
        status, response = self.request(verified_claim)
        self.assertEqual(status, 422)
        self.assertEqual(
            response,
            {"error": True, "message": "Request validation failed."},
        )

        legacy_factor_path = valid_payload()
        legacy_factor_path["mode_data"][0]["emission_factor"] = deepcopy(FACTOR)
        status, _ = self.request(legacy_factor_path)
        self.assertEqual(status, 422)

    def test_candidate_mode_does_not_modify_approved_registry(self) -> None:
        from backend.factor_registry import APPROVED_FACTOR_REGISTRY

        before = dict(APPROVED_FACTOR_REGISTRY)
        status, response = self.request(valid_payload())
        self.assertEqual(status, 200)
        self.assertEqual(dict(APPROVED_FACTOR_REGISTRY), before)
        self.assertEqual(response["approval_status"], "unapproved")

    def test_0145_remains_an_unapproved_candidate(self) -> None:
        from backend.factor_registry import APPROVED_FACTOR_REGISTRY

        payload = valid_payload()
        candidate = payload["mode_data"][0]["candidate_factor"]
        candidate["factor_id"] = "EF_CAR_145"
        candidate["value"] = 0.145
        candidate["provenance"]["factor_id"] = "EF_CAR_145"
        candidate["provenance"]["origin"] = "user_supplied"
        candidate["provenance"]["source_title"] = "Unverified candidate supplied for test"

        status, response = self.request(payload)
        self.assertEqual(status, 200)
        self.assertEqual(response["approval_status"], "unapproved")
        car = response["category_breakdown"][0]["factor_snapshot"]
        self.assertEqual(car["value"], 0.145)
        self.assertEqual(car["approval_status"], "candidate")
        self.assertEqual(len(APPROVED_FACTOR_REGISTRY), 0)

    def test_candidate_factor_snapshot_version_tracks_immutable_content(self) -> None:
        status, first = self.request(valid_payload())
        self.assertEqual(status, 200)
        original_version = first["category_breakdown"][0]["factor_snapshot"][
            "version"
        ]

        changed_payload = valid_payload()
        changed_payload["mode_data"][0]["candidate_factor"]["value"] = 0.151
        status, changed = self.request(changed_payload)
        self.assertEqual(status, 200)
        changed_version = changed["category_breakdown"][0]["factor_snapshot"][
            "version"
        ]
        self.assertNotEqual(original_version, changed_version)

        status, repeated = self.request(valid_payload())
        self.assertEqual(status, 200)
        self.assertEqual(
            repeated["category_breakdown"][0]["factor_snapshot"]["version"],
            original_version,
        )

    def test_each_activity_value_requires_its_own_provenance(self) -> None:
        mutations = (
            lambda payload: payload.pop("annual_days_provenance"),
            lambda payload: payload["mode_data"][0].pop(
                "daily_vehicles_provenance"
            ),
            lambda payload: payload["mode_data"][0].pop(
                "avg_one_way_km_provenance"
            ),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                payload = valid_payload()
                mutate(payload)
                status, response = self.request(payload)
                self.assertEqual(status, 422)
                self.assertEqual(
                    response,
                    {"error": True, "message": "Request validation failed."},
                )

    def test_provenance_rejects_bad_origins_and_blank_required_text(self) -> None:
        cases = []
        invalid_origin = valid_payload()
        invalid_origin["annual_days_provenance"]["origin"] = "inferred"
        cases.append(invalid_origin)
        blank_method = valid_payload()
        blank_method["mode_data"][0]["daily_vehicles_provenance"][
            "method"
        ] = "   "
        cases.append(blank_method)
        blank_description = valid_payload()
        blank_description["mode_data"][0]["avg_one_way_km_provenance"][
            "source_description"
        ] = " \t "
        cases.append(blank_description)

        for payload in cases:
            with self.subTest(payload=payload):
                status, response = self.request(payload)
                self.assertEqual(status, 422)
                self.assertEqual(
                    response,
                    {"error": True, "message": "Request validation failed."},
                )

    def test_provenance_requires_method_and_source_description(self) -> None:
        missing_method = valid_payload()
        del missing_method["annual_days_provenance"]["method"]
        missing_description = valid_payload()
        del missing_description["mode_data"][0]["daily_vehicles_provenance"][
            "source_description"
        ]
        for payload in (missing_method, missing_description):
            with self.subTest(payload=payload):
                status, response = self.request(payload)
                self.assertEqual(status, 422)
                self.assertEqual(
                    response,
                    {"error": True, "message": "Request validation failed."},
                )

    def test_observation_period_is_conditional_and_trimmed(self) -> None:
        missing_period = valid_payload()
        missing_period["annual_days_provenance"] = activity_provenance("observed")
        del missing_period["annual_days_provenance"]["observation_period"]
        status, _ = self.request(missing_period)
        self.assertEqual(status, 422)

        non_observed_period = valid_payload()
        non_observed_period["annual_days_provenance"][
            "observation_period"
        ] = "not applicable"
        status, _ = self.request(non_observed_period)
        self.assertEqual(status, 422)

        null_non_observed_period = valid_payload()
        null_non_observed_period["annual_days_provenance"][
            "observation_period"
        ] = None
        status, _ = self.request(null_non_observed_period)
        self.assertEqual(status, 422)

        trimmed = valid_payload()
        provenance = trimmed["annual_days_provenance"]
        provenance.update(
            {
                "origin": "observed",
                "method": "  calendar review  ",
                "source_description": "  Observed academic calendar  ",
                "observation_period": "  2025-2026 academic year  ",
                "source_reference": "  internal-calendar-01  ",
            }
        )
        status, response = self.request(trimmed)
        self.assertEqual(status, 200)
        self.assertEqual(
            response["annual_days_provenance"],
            {
                "origin": "observed",
                "method": "calendar review",
                "source_description": "Observed academic calendar",
                "observation_period": "2025-2026 academic year",
                "source_reference": "internal-calendar-01",
            },
        )

    def test_occupancy_does_not_affect_calculation_and_projection_stays_false(self) -> None:
        first = valid_payload()
        status_one, result_one = self.request(first)
        self.assertEqual(status_one, 200)

        second = valid_payload()
        for mode in second["mode_data"]:
            mode["occupancy"] = mode["occupancy"] + 10
        status_two, result_two = self.request(second)
        self.assertEqual(status_two, 200)
        self.assertEqual(
            result_one["annual_emissions_kg_co2_per_year"],
            result_two["annual_emissions_kg_co2_per_year"],
        )
        self.assertFalse(result_one["is_campus_projection"])
        self.assertFalse(result_two["is_campus_projection"])

    def test_legacy_b2_metadata_is_response_only(self) -> None:
        legacy_result = {"annual_emissions_kg_co2_per_year": 12.5}
        with database_connection() as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO commute_calculations
                        (calculation_id, assessment_id, created_at,
                         inputs_json, result_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "calc_legacy_b2",
                        self.assessment_id,
                        "2025-01-01T00:00:00Z",
                        json.dumps({"legacy": True}),
                        json.dumps(legacy_result),
                    ),
                )

        status, assessment = self.retrieve()
        self.assertEqual(status, 200)
        saved = next(
            item
            for item in assessment["commute_calculations"]
            if item["calculation_id"] == "calc_legacy_b2"
        )
        self.assertEqual(
            saved["result"]["b3_metadata"],
            {
                "availability": "unavailable_legacy_b2",
                "activity_provenance": "unavailable",
                "factor_governance": "unavailable",
                "calculation_method_version": None,
            },
        )
        with database_connection() as connection:
            stored = connection.execute(
                "SELECT result_json FROM commute_calculations WHERE calculation_id = ?",
                ("calc_legacy_b2",),
            ).fetchone()[0]
        self.assertEqual(json.loads(stored), legacy_result)

    def test_health_endpoint(self) -> None:
        with patch(
            "backend.main.get_detector_metadata",
            return_value={"name": "yolo11x", "weights_sha256": "a" * 64},
        ):
            status, response, _ = asyncio.run(asgi_request("GET", "/health"))
        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "healthy")
        self.assertEqual(response["detector"]["status"], "ready")
        self.assertEqual(response["detector"]["name"], "yolo11x")

    def test_health_reports_detector_unavailable_without_failing_api(self) -> None:
        from backend.vehicle_detection import DetectionUnavailable

        with patch(
            "backend.main.get_detector_metadata",
            side_effect=DetectionUnavailable("Configured YOLO weights are unavailable."),
        ):
            status, response, _ = asyncio.run(asgi_request("GET", "/health"))
        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "healthy")
        self.assertEqual(response["detector"]["status"], "unavailable")

    def test_health_distinguishes_broken_model_from_missing_optional_model(self) -> None:
        from backend.vehicle_detection import DetectorInitializationFailed

        with patch(
            "backend.main.get_detector_metadata",
            side_effect=DetectorInitializationFailed("YOLO weights could not be initialized."),
        ):
            status, response, _ = asyncio.run(asgi_request("GET", "/health"))
        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "healthy")
        self.assertEqual(response["detector"]["status"], "failed")

    def test_docs_route_remains_available(self) -> None:
        status, _, _ = asyncio.run(asgi_request("GET", "/docs"))
        self.assertEqual(status, 200)

    def test_unknown_route_uses_standard_error_envelope(self) -> None:
        status, response, _ = asyncio.run(asgi_request("GET", "/missing"))
        self.assertEqual(status, 404)
        self.assertEqual(
            response,
            {"error": True, "message": "Resource not found."},
        )

    def test_http_error_hides_arbitrary_detail_through_asgi(self) -> None:
        from starlette.exceptions import HTTPException

        async def sensitive_http_error():
            raise HTTPException(
                status_code=418,
                detail="sensitive internal diagnostic",
            )

        app.add_api_route(
            "/__test/http-error",
            sensitive_http_error,
            methods=["GET"],
        )
        route = app.router.routes[-1]
        try:
            status, response, _ = asyncio.run(
                asgi_request("GET", "/__test/http-error")
            )
        finally:
            app.router.routes.remove(route)
        self.assertEqual(status, 418)
        self.assertEqual(
            response,
            {"error": True, "message": "Request could not be completed."},
        )
        self.assertNotIn("sensitive internal diagnostic", json.dumps(response))

    def test_unexpected_error_is_generic_through_asgi(self) -> None:
        async def unexpected_error():
            raise RuntimeError("private exception text")

        app.add_api_route(
            "/__test/server-error",
            unexpected_error,
            methods=["GET"],
        )
        route = app.router.routes[-1]
        try:
            status, response, _ = asyncio.run(
                asgi_request(
                    "GET",
                    "/__test/server-error",
                    capture_server_error=True,
                )
            )
        finally:
            app.router.routes.remove(route)
        self.assertEqual(status, 500)
        self.assertEqual(
            response,
            {"error": True, "message": "An unexpected error occurred."},
        )
        self.assertNotIn("private exception text", json.dumps(response))

    def test_cors_origins_are_configurable_and_preflight_is_supported(self) -> None:
        self.assertEqual(
            configured_cors_origins(" http://localhost:5500, ,https://example.test "),
            ["http://localhost:5500", "https://example.test"],
        )
        status, _, response_headers = asyncio.run(
            asgi_request(
                "OPTIONS",
                "/health",
                headers=[
                    (b"origin", b"http://localhost:5500"),
                    (b"access-control-request-method", b"GET"),
                    (b"access-control-request-private-network", b"true"),
                ],
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            response_headers[b"access-control-allow-origin"],
            b"http://localhost:5500",
        )
        self.assertEqual(
            response_headers[b"access-control-allow-private-network"], b"true"
        )
        self.assertNotIn(b"access-control-allow-credentials", response_headers)

        denied_status, _, denied_headers = asyncio.run(
            asgi_request(
                "OPTIONS",
                "/health",
                headers=[
                    (b"origin", b"https://unapproved.example"),
                    (b"access-control-request-method", b"GET"),
                ],
            )
        )
        self.assertEqual(denied_status, 400)
        self.assertNotIn(b"access-control-allow-origin", denied_headers)


if __name__ == "__main__":
    unittest.main()
