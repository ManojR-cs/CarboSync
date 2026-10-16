"""Deterministic illustrative demo estimates and scenario simulations."""

from __future__ import annotations

from math import isfinite
import hashlib
import json
from typing import Any


MOTOR_CLASSES = ("car", "motorcycle", "bus", "truck")
ALL_CLASSES = ("bicycle", *MOTOR_CLASSES)
DEMO_METHOD_VERSION = "demo_snapshot_tailpipe_estimate_v1"
FACTOR_UNIT = "kg CO2/veh-km"


def _number(value: Any, label: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    number = float(value)
    if not isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{label} is outside the supported range")
    return number


def _share(value: Any, label: str) -> float:
    return _number(value, label, minimum=0, maximum=1)


def _estimate(
    counts: dict[str, int],
    activity: dict[str, dict[str, Any]],
    factors: dict[str, dict[str, Any]],
    annual_days: int,
) -> dict[str, Any]:
    breakdown: dict[str, dict[str, float]] = {}
    total_vkt = 0.0
    total_kg = 0.0
    for category in MOTOR_CLASSES:
        count = counts.get(category, 0)
        assumption = activity[category]
        factor = factors[category]
        trips = _number(
            assumption["trips_per_vehicle_per_operating_day"],
            f"{category} trips_per_vehicle_per_operating_day",
            minimum=0,
            maximum=20,
        )
        distance = _number(
            assumption["avg_one_way_km"],
            f"{category} avg_one_way_km",
            minimum=0,
            maximum=300,
        )
        value = _number(factor["value"], f"{category} factor", minimum=0, maximum=2)
        if factor["unit"] != FACTOR_UNIT:
            raise ValueError(f"{category} factor unit must be {FACTOR_UNIT}")
        vkt = count * trips * distance * 2 * annual_days
        kg = vkt * value
        if not isfinite(vkt) or not isfinite(kg):
            raise ValueError("calculation result is not finite")
        breakdown[category] = {
            "annual_vehicle_km": vkt,
            "annual_kg_co2": kg,
            "annual_tonnes_co2": kg / 1000,
            "factor_snapshot": {
                **factor,
                "version": "demo-sha256:"
                + hashlib.sha256(
                    json.dumps(
                        factor,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest(),
                "metric_scope": "Tailpipe_CO2",
                "approval_status": "illustrative_unapproved",
                "provenance": "request_supplied_illustrative",
                "fuel_powertrain_checked": False,
            },
        }
        total_vkt += vkt
        total_kg += kg
    return {
        "annual_vehicle_km": total_vkt,
        "annual_kg_co2": total_kg,
        "annual_tonnes_co2": total_kg / 1000,
        "category_breakdown": breakdown,
    }


def calculate_demo_analysis(
    *,
    detection_counts: dict[str, int],
    request: dict[str, Any],
) -> dict[str, Any]:
    """Calculate one illustrative baseline and three feasible activity scenarios.

    A "trip" is one assumed campus commute cycle for a detected vehicle on an
    operating day. Each cycle is represented as two one-way legs in the formula.
    """
    counts = {name: detection_counts.get(name, 0) for name in ALL_CLASSES}
    for name, count in counts.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"{name} detection count is invalid")
    annual_days = request["annual_operating_days"]
    if isinstance(annual_days, bool) or not isinstance(annual_days, int) or not 1 <= annual_days <= 366:
        raise ValueError("annual_operating_days must be between 1 and 366")
    activity = request["vehicle_assumptions"]
    factors = request["illustrative_factors"]
    baseline = _estimate(counts, activity, factors, annual_days)
    scenario_config = request["scenario_assumptions"]
    carpool_share = _share(
        scenario_config["carpool_activity_reduction_share"],
        "carpool_activity_reduction_share",
    )
    shuttle_share = _share(
        scenario_config["shuttle_shift_share"], "shuttle_shift_share"
    )
    active_share = _share(
        scenario_config["active_travel_shift_share"],
        "active_travel_shift_share",
    )
    short_trip_limit = _number(
        scenario_config["active_travel_max_one_way_km"],
        "active_travel_max_one_way_km",
        minimum=0.01,
        maximum=300,
    )
    carpool_counts = dict(counts)
    carpool_counts["car"] = counts["car"] * (1 - carpool_share)
    carpool = _estimate(carpool_counts, activity, factors, annual_days)

    shuttle_counts = dict(counts)
    for category in ("car", "motorcycle"):
        shuttle_counts[category] = counts[category] * (1 - shuttle_share)
    private_after_shift = _estimate(shuttle_counts, activity, factors, annual_days)
    shuttle = scenario_config["shuttle_service"]
    shuttle_vehicles = _number(
        shuttle["daily_vehicles"], "shuttle daily_vehicles", minimum=0, maximum=10000
    )
    shuttle_trips = _number(
        shuttle["trips_per_vehicle_per_operating_day"],
        "shuttle trips_per_vehicle_per_operating_day",
        minimum=0,
        maximum=100,
    )
    shuttle_distance = _number(
        shuttle["avg_one_way_km"], "shuttle avg_one_way_km", minimum=0, maximum=300
    )
    shuttle_factor = _number(
        factors["bus"]["value"], "bus factor", minimum=0, maximum=2
    )
    shuttle_added_kg = (
        shuttle_vehicles * shuttle_trips * shuttle_distance * 2 * annual_days * shuttle_factor
    )
    shuttle_result = dict(private_after_shift)
    shuttle_result["annual_vehicle_km"] += (
        shuttle_vehicles * shuttle_trips * shuttle_distance * 2 * annual_days
    )
    shuttle_result["annual_kg_co2"] += shuttle_added_kg
    shuttle_result["annual_tonnes_co2"] = shuttle_result["annual_kg_co2"] / 1000
    shuttle_result["category_breakdown"] = dict(private_after_shift["category_breakdown"])
    shuttle_result["category_breakdown"]["shuttle_service_added"] = {
        "annual_vehicle_km": shuttle_vehicles * shuttle_trips * shuttle_distance * 2 * annual_days,
        "annual_kg_co2": shuttle_added_kg,
        "annual_tonnes_co2": shuttle_added_kg / 1000,
    }

    active_counts = dict(counts)
    eligible_categories = []
    for category in ("car", "motorcycle"):
        if activity[category]["avg_one_way_km"] <= short_trip_limit:
            eligible_categories.append(category)
            active_counts[category] = counts[category] * (1 - active_share)
    active = _estimate(active_counts, activity, factors, annual_days)

    scenarios = [
        _scenario(
            "carpool",
            "Illustrative carpool activity consolidation",
            baseline,
            carpool,
            {
                "carpool_activity_reduction_share": carpool_share,
                "assumption_basis": scenario_config["assumption_basis"],
            },
            "Reduces the assumed car vehicle-trip activity share. YOLO does not identify occupancy or prove that trips can be shared.",
        ),
        _scenario(
            "campus_shuttle",
            "Illustrative campus shuttle shift",
            baseline,
            shuttle_result,
            {
                "private_vehicle_shift_share": shuttle_share,
                "shuttle_service": shuttle,
                "assumption_basis": scenario_config["assumption_basis"],
            },
            "Removes the selected assumed car and motorcycle activity share and adds the explicitly supplied shuttle service. This is not a demand or capacity model.",
        ),
        _scenario(
            "active_travel",
            "Illustrative short-trip active travel shift",
            baseline,
            active,
            {
                "active_travel_shift_share": active_share,
                "max_one_way_km": short_trip_limit,
                "eligible_categories": eligible_categories,
                "assumption_basis": scenario_config["assumption_basis"],
            },
            "Applies only to assumed car or motorcycle trips at or below the supplied distance limit. Walking and cycling have no motor-vehicle tailpipe emissions in this calculation.",
        ),
    ]
    best = min(scenarios, key=lambda item: item["estimated_emissions"]["annual_tonnes_co2"])
    return {
        "calculation_method_version": DEMO_METHOD_VERSION,
        "calculation_mode": "demo_illustrative",
        "approval_status": "illustrative_unapproved",
        "evidence_label": "Illustrative estimate based on a single-image snapshot and explicit assumptions",
        "independently_verified": False,
        "metric_scope": "Tailpipe_CO2",
        "emissions_unit": "kg CO2 and tonnes CO2",
        "formula": "count × assumed commute cycles per operating day × one-way km × 2 × operating days; kg CO2 = vehicle-km × illustrative factor",
        "trip_definition": "One assumed campus commute cycle per detected vehicle per operating day; the formula counts two one-way legs per cycle.",
        "baseline_assumptions": request,
        "baseline": baseline,
        "scenarios": scenarios,
        "best_scenario": {"id": best["id"], "name": best["name"]},
        "limitations": [
            "A single image is a point-in-time snapshot, not daily traffic, unique commuters, trip purpose, or annual activity.",
            "Trips, distances, operating days, factors, and scenario shares are supplied demo assumptions; this output is not an approved campus inventory.",
            "YOLO cannot determine occupancy, fuel or powertrain, distance, or trip purpose.",
            "Illustrative factors are not scientifically validated or approved production factors.",
        ],
    }


def _scenario(
    identifier: str,
    name: str,
    baseline: dict[str, Any],
    result: dict[str, Any],
    assumptions: dict[str, Any],
    limitations: str,
) -> dict[str, Any]:
    base_tonnes = baseline["annual_tonnes_co2"]
    scenario_tonnes = result["annual_tonnes_co2"]
    reduction = base_tonnes - scenario_tonnes
    return {
        "id": identifier,
        "name": name,
        "label": "Illustrative simulation; not measured or guaranteed savings",
        "assumptions": assumptions,
        "estimated_emissions": result,
        "change_vs_baseline_tonnes": scenario_tonnes - base_tonnes,
        "reduction_vs_baseline_tonnes": reduction,
        "percentage_reduction_vs_baseline": (
            (reduction / base_tonnes * 100) if base_tonnes > 0 else None
        ),
        "comparison": "lower than baseline" if reduction > 0 else "equal to baseline" if reduction == 0 else "higher than baseline",
        "limitations": limitations,
    }
