"""Deterministic annual tailpipe CO2 calculations."""

from dataclasses import dataclass
import math


EXPECTED_EMISSION_FACTOR_UNIT = "kg CO2/veh-km"


@dataclass(frozen=True)
class EmissionFactor:
    """A configurable emission factor with an explicit vehicle-distance unit.

    Values supplied from examples or benchmarks are not implied to be
    authoritative. The API layer requires factor provenance; this pure
    calculation value object stores only the numeric value and unit.
    """

    value: float
    unit: str

    def __post_init__(self) -> None:
        _validate_finite_number("emission factor", self.value)
        if self.value < 0:
            raise ValueError("emission factor must be greater than or equal to 0")
        if self.unit != EXPECTED_EMISSION_FACTOR_UNIT:
            raise ValueError(
                f"emission factor unit must be {EXPECTED_EMISSION_FACTOR_UNIT!r}; "
                f"got {self.unit!r}"
            )


@dataclass(frozen=True)
class AnnualEmissions:
    """Annual travel and tailpipe emissions for one vehicle category."""

    annual_vkt_km: float
    annual_emissions_kg_co2: float
    annual_emissions_tonnes_co2: float


def _validate_finite_number(name: str, value: object) -> None:
    # bool is an int subclass, but is not a meaningful measurement input.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be finite")


def calculate_annual_emissions(
    *,
    daily_vehicles: float,
    one_way_distance_km: float,
    academic_days_per_year: int,
    emission_factor: EmissionFactor,
) -> AnnualEmissions:
    """Calculate annual VKT and tailpipe CO2 for a single vehicle category.

    Formula: daily vehicles [vehicles/day] * one-way distance [km/trip] *
    2 [trips/day] * academic days [days/year] = annual VKT [vehicle-km/year].
    Annual VKT is multiplied by the supplied factor [kg CO2/vehicle-km].
    """
    _validate_finite_number("daily_vehicles", daily_vehicles)
    if daily_vehicles < 0:
        raise ValueError("daily_vehicles must be greater than or equal to 0")

    _validate_finite_number("one_way_distance_km", one_way_distance_km)
    if one_way_distance_km <= 0:
        raise ValueError("one_way_distance_km must be greater than 0")

    if isinstance(academic_days_per_year, bool) or not isinstance(
        academic_days_per_year, int
    ):
        raise TypeError("academic_days_per_year must be an integer number of days")
    if not 1 <= academic_days_per_year <= 366:
        raise ValueError("academic_days_per_year must be between 1 and 366")

    if not isinstance(emission_factor, EmissionFactor):
        raise TypeError("emission_factor must be an EmissionFactor")

    annual_vkt_km = (
        daily_vehicles * one_way_distance_km * 2 * academic_days_per_year
    )
    annual_emissions_kg_co2 = (
        annual_vkt_km * emission_factor.value
    )
    _validate_finite_number("annual_vkt_km", annual_vkt_km)
    _validate_finite_number("annual_emissions_kg_co2", annual_emissions_kg_co2)
    return AnnualEmissions(
        annual_vkt_km=annual_vkt_km,
        annual_emissions_kg_co2=annual_emissions_kg_co2,
        annual_emissions_tonnes_co2=annual_emissions_kg_co2 / 1000,
    )
