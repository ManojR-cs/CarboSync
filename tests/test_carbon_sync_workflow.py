"""Focused persistence and calculation checks for the CarbonSync demo flow."""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend import main
from backend.database import get_parking_observations, save_demo_analysis
from backend.recommendations import generate_evidence_recommendations


class CarbonSyncWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_directory.name) / "workflow.sqlite3"
        self.env = patch.dict(os.environ, {"CARBOSYNC_DATABASE_PATH": str(self.db_path)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp_directory.cleanup()

    def test_student_records_aggregate_without_exposing_addresses_and_scenario_is_deterministic(self):
        payload = main.StudentsUpdate.model_validate({
            "college_address": "Private campus address",
            "students": [{
                "student_id": "DEMO-01", "name": "Demo Person", "residential_address": "Private home address",
                "one_way_distance_km": 10, "travel_mode": "car", "vehicle_type": "car",
                "fuel_type": "petrol", "commute_days_per_week": 5, "occupancy": 1,
            }],
        })
        main.save_students(payload)
        summary = main.commute_summary()
        self.assertEqual(summary["annual_kg_co2"], 754.0)
        self.assertEqual(summary["average_weekday_kg_co2"], 2.9)
        self.assertEqual(summary["observation_period_kg_co2_estimate"], 29.0)
        self.assertNotIn("Private home address", str(summary))
        scenario = main.student_scenario(main.StudentScenarioInput(carpool_share=1, carpool_occupancy=2))
        self.assertEqual(scenario["baseline"]["annual_kg_co2"], 754.0)
        self.assertEqual(scenario["scenarios"]["carpool"]["annual_kg_co2"], 377.0)
        self.assertEqual(main.latest_student_scenario()["scenario"]["inputs"]["carpool_share"], 1)
        response_text = str(scenario)
        for private_value in ("Private campus address", "Private home address", "Demo Person", "DEMO-01"):
            self.assertNotIn(private_value, response_text)

    def test_scenario_flow_profiles_follow_backend_shares_and_active_distance_eligibility(self):
        main.save_students(main.StudentsUpdate.model_validate({
            "college_address": "Campus",
            "students": [
                {"student_id": "FLOW-01", "name": "One", "residential_address": "Private 1", "one_way_distance_km": 3, "travel_mode": "car", "vehicle_type": "car", "fuel_type": "petrol", "commute_days_per_week": 5, "occupancy": 1},
                {"student_id": "FLOW-02", "name": "Two", "residential_address": "Private 2", "one_way_distance_km": 12, "travel_mode": "motorcycle", "vehicle_type": "motorcycle", "fuel_type": "petrol", "commute_days_per_week": 5, "occupancy": 1},
                {"student_id": "FLOW-03", "name": "Three", "residential_address": "Private 3", "one_way_distance_km": 2, "travel_mode": "walking", "vehicle_type": None, "fuel_type": "unknown", "commute_days_per_week": 5, "occupancy": 1},
            ],
        }))
        result = main.student_scenario(main.StudentScenarioInput(
            carpool_share=0.5, public_transport_share=0.5,
            active_travel_share=0.5, active_travel_limit_km=5,
            shuttle_shift_share=0.5, shuttle_daily_vehicles=1,
            shuttle_trips_per_vehicle_per_day=2, shuttle_one_way_route_km=4,
            shuttle_operating_days_per_year=200,
        ))
        profiles = result["flow_representation"]["scenarios"]
        self.assertEqual(profiles["carpool"]["single_occupancy_car"], 2.5)
        self.assertEqual(profiles["carpool"]["carpool_vehicle"], 2.5)
        self.assertEqual(profiles["public_transport"]["public_transport"], 5.0)
        self.assertEqual(profiles["active_travel"]["active_travel"], 7.5)
        self.assertEqual(profiles["campus_shuttle"]["shuttle"], 5.0)
        self.assertEqual(sum(profiles["active_travel"].values()), 15)
        response_text = str(result)
        for private_value in ("Campus", "Private 1", "Private 2", "Private 3", "One", "Two", "Three", "FLOW-01", "FLOW-02", "FLOW-03"):
            self.assertNotIn(private_value, response_text)

    def test_no_student_activity_is_reported_as_unavailable_not_zero_emissions(self):
        summary = main._student_summary([], period_days=10)
        self.assertEqual(summary["calculation_status"], "unavailable")
        self.assertIsNone(summary["annual_kg_co2"])
        self.assertIsNone(summary["average_weekday_kg_co2"])
        self.assertIsNone(summary["observation_period_kg_co2_estimate"])

    def test_campaign_saves_empty_successful_inference_and_rejects_duplicate_image(self):
        campaign = main.start_observation_campaign(main.CampaignCreate(start_date=date(2026, 10, 16)))
        analysis_id = "demo_test_analysis"
        counts = {"bicycle": 0, "car": 0, "motorcycle": 0, "bus": 0, "truck": 0}
        save_demo_analysis(
            analysis_id=analysis_id,
            created_at="2026-10-16T00:00:00Z",
            detections={
                "mode": "real", "simulated": False, "image_sha256": "a" * 64,
                "per_class": counts, "model_metadata": {"name": "test model"},
                "inference_status": "completed_no_detections",
            },
            assumptions={},
            result={},
        )
        payload = main.ObservationSave(
            analysis_id=analysis_id,
            observation_date=date(2026, 10, 16),
            counts=counts,
        )
        with self.assertRaises(HTTPException) as review_error:
            main.save_observation(campaign["campaign_id"], payload)
        self.assertEqual(review_error.exception.status_code, 409)
        payload = payload.model_copy(update={"human_reviewed": True})
        saved = main.save_observation(campaign["campaign_id"], payload)
        self.assertEqual(saved["inference_status"], "completed_no_detections")
        self.assertTrue(saved["human_reviewed"])
        self.assertEqual(main.current_campaign()["campaign"]["day_progress"], "1/10 days")
        with self.assertRaises(HTTPException) as error:
            main.save_observation(campaign["campaign_id"], payload)
        self.assertEqual(error.exception.status_code, 409)
        observations = get_parking_observations(campaign["campaign_id"])
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["counts"]["car"], 0)
        self.assertTrue(observations[0]["human_reviewed"])
        report = main.final_report()
        self.assertNotIn("residential_address", str(report))

    def test_shuttle_scenario_includes_added_service_emissions_and_can_increase_emissions(self):
        main.save_students(main.StudentsUpdate.model_validate({
            "college_address": "Campus",
            "students": [{
                "student_id": "DEMO-02", "name": "Person", "residential_address": "Home",
                "one_way_distance_km": 5, "travel_mode": "car", "vehicle_type": "car",
                "fuel_type": "petrol", "commute_days_per_week": 5, "occupancy": 1,
            }],
        }))
        result = main.student_scenario(main.StudentScenarioInput(
            shuttle_shift_share=1, shuttle_daily_vehicles=10,
            shuttle_trips_per_vehicle_per_day=8, shuttle_one_way_route_km=30,
            shuttle_operating_days_per_year=200,
        ))
        shuttle = result["scenarios"]["campus_shuttle"]
        self.assertGreater(shuttle["annual_kg_co2"], result["baseline"]["annual_kg_co2"])
        self.assertLess(shuttle["reduction_kg_co2"], 0)
        self.assertGreater(result["shuttle_activity"]["added_shuttle_annual_kg_co2"], 0)
        self.assertGreater(result["shuttle_activity"]["shuttle_vehicle_km_per_year"], 0)

    def test_shuttle_scenario_rejects_incomplete_service_and_zero_baseline_is_safe(self):
        with self.assertRaises(ValueError):
            main.StudentScenarioInput(shuttle_shift_share=0.5)
        main.save_students(main.StudentsUpdate.model_validate({
            "college_address": "Campus",
            "students": [{
                "student_id": "DEMO-03", "name": "Person", "residential_address": "Home",
                "one_way_distance_km": 1, "travel_mode": "walking", "vehicle_type": None,
                "fuel_type": "unknown", "commute_days_per_week": 5, "occupancy": 1,
            }],
        }))
        result = main.student_scenario(main.StudentScenarioInput())
        self.assertEqual(result["baseline"]["annual_kg_co2"], 0)
        self.assertIsNone(result["scenarios"]["carpool"]["reduction_percent"])

    def test_rule_based_recommendations_are_explicit_and_do_not_claim_savings(self):
        result = generate_evidence_recommendations({
            "student_mode_counts": {"car": 2}, "daily_mean_vehicle_counts": {"car": 3},
            "observed_days": 1, "student_count": 2,
            "student_commute_summary": {"annual_kg_co2": 1},
            "private_address": "must never be passed",
        })
        self.assertTrue(result["fallback_flag"])
        self.assertIn("LLM unavailable", result["label"])
        self.assertNotIn("private_address", str(result))
        self.assertTrue(all(item["estimated_reduction"] == "Not calculated from current data" for item in result["recommendations"]))


if __name__ == "__main__":
    unittest.main()
