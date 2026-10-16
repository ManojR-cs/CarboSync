"""Controlled, versioned emission-factor registry.

The registry intentionally contains no approved factors until the project
owner has approved a record with supporting review evidence. Candidate factors
are request data and are never inserted here.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping


FactorStatus = Literal["candidate", "approved", "retired"]


@dataclass(frozen=True)
class RegisteredFactor:
    factor_id: str
    version: str
    value: float
    unit: str
    metric_scope: str
    geographic_scope: str
    vehicle_categories: tuple[str, ...]
    fuel_powertrain_applicability: str
    source_title: str
    source_url: str | None
    source_version_year: int | None
    approximation_notes: str
    limitations: str
    approval_status: FactorStatus
    review_evidence: str | None
    owner_approval_decision: str | None


# Immutable and intentionally empty: no reviewed, owner-approved production
# factor has been supplied to this repository.
APPROVED_FACTOR_REGISTRY: Mapping[tuple[str, str], RegisteredFactor] = (
    MappingProxyType({})
)


def resolve_approved_factor(
    factor_id: str,
    version: str,
) -> RegisteredFactor | None:
    """Resolve one exact immutable registry version, if present."""
    return APPROVED_FACTOR_REGISTRY.get((factor_id, version))
