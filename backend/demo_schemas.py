"""Validated request contract for the explicitly illustrative demo workflow."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictInt, field_validator, model_validator


VehicleClass = Literal["bicycle", "car", "motorcycle", "bus", "truck"]
MotorClass = Literal["car", "motorcycle", "bus", "truck"]


class DemoModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class VehicleAssumption(DemoModel):
    trips_per_vehicle_per_operating_day: Annotated[FiniteFloat, Field(ge=0, le=20)]
    avg_one_way_km: Annotated[FiniteFloat, Field(ge=0, le=300)]
    source_description: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator(
        "trips_per_vehicle_per_operating_day", "avg_one_way_km", mode="before"
    )
    @classmethod
    def require_json_numbers(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("assumptions must be JSON numbers")
        return value

    @field_validator("source_description")
    @classmethod
    def require_description(cls, value: str) -> str:
        if not value:
            raise ValueError("source_description must not be blank")
        return value


class DemoFactor(DemoModel):
    factor_id: Annotated[str, Field(pattern=r"^DEMO_[A-Z0-9_]{2,24}$")]
    vehicle_category: MotorClass
    value: Annotated[FiniteFloat, Field(ge=0, le=2)]
    unit: Literal["kg CO2/veh-km"]
    geographic_scope: Annotated[str, Field(min_length=1, max_length=200)]
    source_description: Annotated[str, Field(min_length=1, max_length=500)]
    source_reference: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    applicability_notes: Annotated[str, Field(min_length=1, max_length=500)]
    limitations: Annotated[str, Field(min_length=1, max_length=1000)]

    @field_validator("value", mode="before")
    @classmethod
    def require_json_number(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("factor value must be a JSON number")
        return value

    @field_validator(
        "geographic_scope",
        "source_description",
        "source_reference",
        "applicability_notes",
        "limitations",
    )
    @classmethod
    def reject_blank_optional_or_required_text(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("text must not be blank")
        return value


class ShuttleService(DemoModel):
    daily_vehicles: Annotated[FiniteFloat, Field(ge=0, le=10000)]
    trips_per_vehicle_per_operating_day: Annotated[FiniteFloat, Field(ge=0, le=100)]
    avg_one_way_km: Annotated[FiniteFloat, Field(ge=0, le=300)]
    source_description: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator(
        "daily_vehicles",
        "trips_per_vehicle_per_operating_day",
        "avg_one_way_km",
        mode="before",
    )
    @classmethod
    def require_json_numbers(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("shuttle assumptions must be JSON numbers")
        return value

    @field_validator("source_description")
    @classmethod
    def require_description(cls, value: str) -> str:
        if not value:
            raise ValueError("source_description must not be blank")
        return value


class ScenarioAssumptions(DemoModel):
    carpool_activity_reduction_share: Annotated[FiniteFloat, Field(ge=0, le=1)]
    shuttle_shift_share: Annotated[FiniteFloat, Field(ge=0, le=1)]
    active_travel_shift_share: Annotated[FiniteFloat, Field(ge=0, le=1)]
    active_travel_max_one_way_km: Annotated[FiniteFloat, Field(gt=0, le=300)]
    assumption_basis: Annotated[str, Field(min_length=1, max_length=1000)]
    shuttle_service: ShuttleService

    @field_validator(
        "carpool_activity_reduction_share",
        "shuttle_shift_share",
        "active_travel_shift_share",
        "active_travel_max_one_way_km",
        mode="before",
    )
    @classmethod
    def require_json_numbers(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("scenario assumptions must be JSON numbers")
        return value

    @field_validator("assumption_basis")
    @classmethod
    def require_basis(cls, value: str) -> str:
        if not value:
            raise ValueError("assumption_basis must not be blank")
        return value


class DemoAnalysisRequest(DemoModel):
    annual_operating_days: Annotated[StrictInt, Field(ge=1, le=366)]
    annual_days_source_description: Annotated[str, Field(min_length=1, max_length=500)]
    vehicle_assumptions: dict[VehicleClass, VehicleAssumption]
    illustrative_factors: dict[MotorClass, DemoFactor]
    scenario_assumptions: ScenarioAssumptions

    @field_validator("annual_days_source_description")
    @classmethod
    def require_annual_days_description(cls, value: str) -> str:
        if not value:
            raise ValueError("annual_days_source_description must not be blank")
        return value

    @model_validator(mode="after")
    def require_complete_maps(self) -> "DemoAnalysisRequest":
        vehicle_keys = {"bicycle", "car", "motorcycle", "bus", "truck"}
        factor_keys = {"car", "motorcycle", "bus", "truck"}
        if set(self.vehicle_assumptions) != vehicle_keys:
            raise ValueError("vehicle_assumptions must define all five detected classes")
        if set(self.illustrative_factors) != factor_keys:
            raise ValueError("illustrative_factors must define all four motor classes")
        for category, factor in self.illustrative_factors.items():
            if factor.vehicle_category != category:
                raise ValueError("illustrative factor category must match its map key")
        return self
