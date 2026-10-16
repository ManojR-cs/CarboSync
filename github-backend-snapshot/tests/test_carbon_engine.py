"""Focused tests for the documented deterministic carbon calculation."""

import math
import unittest

from backend.carbon_engine import (
    EXPECTED_EMISSION_FACTOR_UNIT,
    EmissionFactor,
    calculate_annual_emissions,
)


class CarbonEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        # Benchmark-provided value only; this is not asserted to be an
        # authoritative emission factor.
        self.benchmark_factor = EmissionFactor(
            value=0.150,
            unit=EXPECTED_EMISSION_FACTOR_UNIT,
        )

    def calculate(self, **overrides):
        inputs = {
            "daily_vehicles": 50,
            "one_way_distance_km": 15.0,
            "academic_days_per_year": 200,
            "emission_factor": self.benchmark_factor,
        }
        inputs.update(overrides)
        return calculate_annual_emissions(**inputs)

    def test_documented_45_tonne_benchmark(self) -> None:
        result = self.calculate()
        self.assertEqual(result.annual_vkt_km, 300_000)
        self.assertEqual(result.annual_emissions_kg_co2, 45_000)
        self.assertEqual(result.annual_emissions_tonnes_co2, 45)

    def test_zero_vehicles_produces_zero_emissions(self) -> None:
        result = self.calculate(daily_vehicles=0)
        self.assertEqual(result.annual_vkt_km, 0)
        self.assertEqual(result.annual_emissions_kg_co2, 0)
        self.assertEqual(result.annual_emissions_tonnes_co2, 0)

    def test_zero_emission_factor_produces_zero_emissions(self) -> None:
        factor = EmissionFactor(0, EXPECTED_EMISSION_FACTOR_UNIT)
        result = self.calculate(emission_factor=factor)
        self.assertGreater(result.annual_vkt_km, 0)
        self.assertEqual(result.annual_emissions_kg_co2, 0)

    def test_rejects_non_finite_calculation_result(self) -> None:
        factor = EmissionFactor(1.0e308, EXPECTED_EMISSION_FACTOR_UNIT)
        with self.assertRaisesRegex(
            ValueError,
            "annual_emissions_kg_co2 must be finite",
        ):
            self.calculate(emission_factor=factor)

    def test_factor_is_explicit_and_configurable(self) -> None:
        factor = EmissionFactor(0.1, EXPECTED_EMISSION_FACTOR_UNIT)
        result = self.calculate(emission_factor=factor)
        self.assertEqual(result.annual_emissions_kg_co2, 30_000)

    def test_rejects_negative_vehicles(self) -> None:
        with self.assertRaisesRegex(ValueError, "daily_vehicles"):
            self.calculate(daily_vehicles=-1)

    def test_rejects_non_numeric_or_boolean_measurements(self) -> None:
        for value in ("50", True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, "daily_vehicles"):
                    self.calculate(daily_vehicles=value)

    def test_rejects_non_finite_measurements(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite"):
                    self.calculate(daily_vehicles=value)

    def test_rejects_non_positive_distance(self) -> None:
        for value in (0, -0.1):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "one_way_distance_km"):
                    self.calculate(one_way_distance_km=value)

    def test_rejects_invalid_academic_days(self) -> None:
        for value in (0, -1, 367):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "academic_days_per_year"):
                    self.calculate(academic_days_per_year=value)
        for value in (200.0, True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, "academic_days_per_year"):
                    self.calculate(academic_days_per_year=value)

    def test_rejects_negative_or_non_numeric_factor(self) -> None:
        with self.assertRaisesRegex(ValueError, "emission factor"):
            EmissionFactor(-0.1, EXPECTED_EMISSION_FACTOR_UNIT)
        with self.assertRaisesRegex(TypeError, "emission factor"):
            EmissionFactor("0.15", EXPECTED_EMISSION_FACTOR_UNIT)

    def test_rejects_wrong_factor_units(self) -> None:
        with self.assertRaisesRegex(ValueError, "emission factor unit"):
            EmissionFactor(0.04, "kg CO2/pass-km")

    def test_rejects_factor_of_wrong_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "EmissionFactor"):
            self.calculate(emission_factor=0.15)


if __name__ == "__main__":
    unittest.main()
