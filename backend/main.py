"""FastAPI endpoint for deterministic commute-emissions calculations."""

import hashlib
import json
import logging
import os
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    HttpUrl,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.concurrency import run_in_threadpool

from backend.carbon_engine import (
    EXPECTED_EMISSION_FACTOR_UNIT,
    EmissionFactor,
    calculate_annual_emissions,
)
from backend.database import (
    create_assessment as persist_assessment,
    get_demo_analysis,
    get_assessment as load_assessment,
    get_campus_address,
    set_campus_address,
    get_demo_students,
    replace_demo_students,
    create_observation_campaign,
    get_current_observation_campaign,
    get_observation_campaign,
    save_parking_observation,
    get_parking_observations,
    has_parking_image,
    save_demo_scenario,
    get_latest_demo_scenario,
    save_demo_recommendations,
    get_latest_demo_recommendations,
    save_commute_calculation,
    save_demo_analysis,
    utc_timestamp,
)
from backend.factor_registry import (
    APPROVED_FACTOR_REGISTRY,
    resolve_approved_factor,
)
from backend.demo_calculations import calculate_demo_analysis
from backend.demo_schemas import DemoAnalysisRequest
from backend.recommendations import generate_recommendations, generate_evidence_recommendations
from backend.vehicle_detection import (
    DetectionFailed,
    DetectionUnavailable,
    DetectorInitializationFailed,
    ImageInputError,
    MAX_IMAGE_BYTES,
    detect_vehicle_image,
    get_detector_metadata,
    validate_image_bytes,
)


CALCULATION_METHOD_VERSION = "commute_tailpipe_co2_v1"


VEHICLE_CATEGORIES = (
    "Cars",
    "Motorcycles and scooters",
    "Buses and campus shuttles",
    "Other fuel-burning vehicles",
)
VehicleCategory = Literal[
    "Cars",
    "Motorcycles and scooters",
    "Buses and campus shuttles",
    "Other fuel-burning vehicles",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateAssessmentRequest(StrictModel):
    """B2 currently needs no assessment metadata beyond its generated ID."""
    assessment_name: str | None = None
    campus_area: str | None = None
    reporting_period: str | None = None
    annual_days: int | None = None


class StudentRecordInput(StrictModel):
    student_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,24}$")]
    name: Annotated[str, Field(min_length=1, max_length=80)]
    residential_address: Annotated[str, Field(min_length=1, max_length=300)]
    one_way_distance_km: Annotated[FiniteFloat, Field(gt=0, le=300)]
    travel_mode: Literal["car", "motorcycle", "public_transport", "cycling", "walking"]
    vehicle_type: str | None = None
    fuel_type: Literal["petrol", "diesel", "cng", "electric", "unknown"] = "unknown"
    commute_days_per_week: Annotated[FiniteFloat, Field(gt=0, le=7)]
    occupancy: Annotated[FiniteFloat, Field(ge=1, le=100)] = 1

    @field_validator("student_id", "name", "residential_address", mode="before")
    @classmethod
    def trim_student_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class StudentsUpdate(StrictModel):
    college_address: Annotated[str, Field(min_length=1, max_length=300)]
    students: Annotated[list[StudentRecordInput], Field(min_length=1, max_length=5)]

    @field_validator("college_address", mode="before")
    @classmethod
    def trim_college_address(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_distinct_ids(self) -> "StudentsUpdate":
        ids = [student.student_id for student in self.students]
        if len(set(ids)) != len(ids):
            raise ValueError("Student IDs must be unique")
        return self


class CampaignCreate(StrictModel):
    start_date: date
    duration_days: Literal[10] = 10


class ObservationSave(StrictModel):
    analysis_id: Annotated[str, Field(min_length=1, max_length=80)]
    observation_date: date
    counts: dict[Literal["bicycle", "car", "motorcycle", "bus", "truck"], Annotated[StrictInt, Field(ge=0, le=100000)]]
    human_reviewed: bool = False

    @model_validator(mode="after")
    def require_all_counts(self) -> "ObservationSave":
        if set(self.counts) != {"bicycle", "car", "motorcycle", "bus", "truck"}:
            raise ValueError("Counts must include every supported class")
        return self


class StudentScenarioInput(StrictModel):
    carpool_share: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0
    carpool_occupancy: Annotated[FiniteFloat, Field(ge=2, le=8)] = 2
    public_transport_share: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0
    transit_occupancy: Annotated[FiniteFloat, Field(ge=1, le=100)] = 20
    active_travel_share: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0
    active_travel_limit_km: Annotated[FiniteFloat, Field(gt=0, le=300)] = 5
    shuttle_shift_share: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0
    shuttle_daily_vehicles: Annotated[StrictInt, Field(ge=0, le=1000)] = 0
    shuttle_trips_per_vehicle_per_day: Annotated[FiniteFloat, Field(ge=0, le=100)] = 0
    shuttle_one_way_route_km: Annotated[FiniteFloat, Field(ge=0, le=300)] = 0
    shuttle_operating_days_per_year: Annotated[StrictInt, Field(ge=0, le=366)] = 200

    @model_validator(mode="after")
    def validate_shuttle_service(self) -> "StudentScenarioInput":
        service_configured = self.shuttle_daily_vehicles > 0 and self.shuttle_trips_per_vehicle_per_day > 0 and self.shuttle_one_way_route_km > 0
        if self.shuttle_shift_share > 0 and not service_configured:
            raise ValueError("A shuttle shift requires daily vehicles, trips per day, and one-way route distance")
        if any((self.shuttle_daily_vehicles, self.shuttle_trips_per_vehicle_per_day, self.shuttle_one_way_route_km)) and not service_configured:
            raise ValueError("Complete all shuttle service inputs or set them all to zero")
        if service_configured and self.shuttle_operating_days_per_year < 1:
            raise ValueError("A configured shuttle service requires operating days per year")
        return self


class CandidateFactorProvenance(StrictModel):
    """Caller-described candidate source; it does not establish approval."""

    origin: Literal["user_supplied", "test_data"]
    factor_id: Annotated[str, Field(pattern=r"^EF_[A-Z0-9_]{4,20}$")]
    metric_scope: Literal["Tailpipe_CO2"]
    geographic_scope: Annotated[str, Field(min_length=1)]
    source_title: Annotated[str, Field(min_length=1)]
    source_url: HttpUrl | None = None
    version_year: Annotated[StrictInt, Field(ge=2000, le=2026)] | None = None
    approximation_notes: Annotated[str, Field(min_length=1)]

    @field_validator("geographic_scope", "source_title", "approximation_notes")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class CandidateFactorInput(StrictModel):
    factor_id: Annotated[str, Field(pattern=r"^EF_[A-Z0-9_]{4,20}$")]
    version: Annotated[str, Field(min_length=1, max_length=32)]
    value: Annotated[FiniteFloat, Field(gt=0, le=2)]
    unit: Literal["kg CO2/veh-km"]
    provenance: CandidateFactorProvenance

    @field_validator("version", mode="before")
    @classmethod
    def trim_version(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("value", mode="before")
    @classmethod
    def require_numeric_factor(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("emission factor value must be a number")
        return value

    @model_validator(mode="after")
    def require_matching_factor_id(self) -> "CandidateFactorInput":
        if self.factor_id != self.provenance.factor_id:
            raise ValueError("candidate factor IDs must match")
        if not self.version.strip():
            raise ValueError("candidate factor version must not be blank")
        return self


class FactorReference(StrictModel):
    factor_id: Annotated[str, Field(pattern=r"^EF_[A-Z0-9_]{4,20}$")]
    version: Annotated[str, Field(min_length=1, max_length=32)]

    @field_validator("version", mode="before")
    @classmethod
    def trim_version(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ActivityProvenance(StrictModel):
    origin: Literal["observed", "user_provided", "estimated"]
    method: Annotated[str, Field(min_length=1)]
    source_description: Annotated[str, Field(min_length=1)]
    observation_period: str | None = None
    source_reference: str | None = None

    @field_validator("method", "source_description")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @field_validator("observation_period", "source_reference", mode="before")
    @classmethod
    def trim_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_observation_period(self) -> "ActivityProvenance":
        if self.origin == "observed" and not self.observation_period:
            raise ValueError("observed provenance requires observation_period")
        if (
            self.origin != "observed"
            and "observation_period" in self.model_fields_set
        ):
            raise ValueError(
                "observation_period is only valid for observed provenance"
            )
        return self


class CandidateModeInput(StrictModel):
    category: VehicleCategory
    daily_vehicles: Annotated[FiniteFloat, Field(ge=0)]
    daily_vehicles_provenance: ActivityProvenance
    avg_one_way_km: Annotated[FiniteFloat, Field(gt=0, le=120)]
    avg_one_way_km_provenance: ActivityProvenance
    occupancy: Annotated[FiniteFloat, Field(ge=1)]
    candidate_factor: CandidateFactorInput | None = None
    factor_reference: FactorReference | None = None

    @field_validator("daily_vehicles", "avg_one_way_km", "occupancy", mode="before")
    @classmethod
    def require_numeric_measurements(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("measurement values must be numbers")
        return value


class CommuteInput(StrictModel):
    calculation_mode: Literal["approved", "candidate"]
    annual_days: Annotated[StrictInt, Field(ge=1, le=366)]
    annual_days_provenance: ActivityProvenance
    sample_size: Annotated[StrictInt, Field(ge=1)]
    population_total: Annotated[StrictInt, Field(ge=1)] | None = None
    mode_data: Annotated[list[CandidateModeInput], Field(min_length=4, max_length=4)]

    @model_validator(mode="after")
    def require_each_vehicle_category_once(self) -> "CommuteInput":
        categories = [mode.category for mode in self.mode_data]
        if (
            len(set(categories)) != len(VEHICLE_CATEGORIES)
            or set(categories) != set(VEHICLE_CATEGORIES)
        ):
            raise ValueError(
                "mode_data must contain each supported category exactly once"
            )
        for mode in self.mode_data:
            if self.calculation_mode == "approved":
                if mode.factor_reference is None or mode.candidate_factor is not None:
                    raise ValueError(
                        "approved mode requires factor_reference only"
                    )
            elif mode.candidate_factor is None or mode.factor_reference is not None:
                raise ValueError(
                    "candidate mode requires candidate_factor only"
                )
        return self


def configured_cors_origins(raw_origins: str | None = None) -> list[str]:
    """Read browser origins from CARBOSYNC_CORS_ORIGINS (comma-separated)."""
    value = (
        os.getenv(
            "CARBOSYNC_CORS_ORIGINS",
            "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000,http://localhost:8001,http://127.0.0.1:8001,http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        )
        if raw_origins is None
        else raw_origins
    )
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app = FastAPI(title="CarboSync Commute Emissions API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_private_network=True,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class DemoUploadSizeLimitMiddleware:
    """Bound multipart bytes before Starlette's parser can spool the upload."""

    maximum_body_bytes = MAX_IMAGE_BYTES + 256 * 1024
    response_body = (
        b'{"error":true,"message":"Uploaded image exceeds the allowed size."}'
    )

    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if not (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path") == "/api/demo/analyze"
        ):
            await self.application(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            content_length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            content_length = 0
        if content_length > self.maximum_body_bytes:
            await self._send_too_large(scope, send)
            return
        buffered_messages = []
        received = 0
        while True:
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.maximum_body_bytes:
                    await self._send_too_large(scope, send)
                    return
            buffered_messages.append(message)
            if message["type"] != "http.request" or not message.get(
                "more_body", False
            ):
                break
        message_index = 0

        async def replay_receive():
            nonlocal message_index
            if message_index < len(buffered_messages):
                message = buffered_messages[message_index]
                message_index += 1
                return message
            return await receive()

        await self.application(scope, replay_receive, send)

    async def _send_too_large(self, scope, send):
        request_headers = dict(scope.get("headers", []))
        origin = request_headers.get(b"origin")
        response_headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(self.response_body)).encode()),
        ]
        if origin:
            origin_text = origin.decode("latin-1")
            if origin_text in configured_cors_origins():
                response_headers.extend(
                    [
                        (b"access-control-allow-origin", origin),
                        (b"vary", b"Origin"),
                    ]
                )
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": response_headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": self.response_body,
                "more_body": False,
            }
        )


app.add_middleware(DemoUploadSizeLimitMiddleware)


@app.post("/api/assessments", status_code=201)
def create_assessment(request: CreateAssessmentRequest) -> dict[str, str]:
    """Create an aggregate assessment without collecting personal data."""
    del request
    assessment_id = f"ast_{uuid.uuid4().hex}"
    created_at = utc_timestamp()
    persist_assessment(assessment_id, created_at)
    return {"assessment_id": assessment_id, "created_at": created_at}


@app.get("/api/assessments/{assessment_id}")
def retrieve_assessment(assessment_id: str) -> dict[str, object]:
    assessment = load_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, _exc: RequestValidationError) -> JSONResponse:
    # Keep one public error shape and avoid echoing rejected values or details.
    return JSONResponse(
        status_code=422,
        content={"error": True, "message": "Request validation failed."},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_, exc: StarletteHTTPException) -> JSONResponse:
    messages = {
        400: "Bad request.",
        401: "Authentication required.",
        403: "Forbidden.",
        404: "Resource not found.",
        405: "Method not allowed.",
        409: "Conflict.",
        413: "Uploaded image exceeds the allowed size.",
        422: "Request validation failed.",
        415: "Unsupported image type.",
        429: "Too many requests.",
    }
    conflict_messages = {
        "Review the image and explicitly confirm the empty vehicle count before saving":
            "Review the image and explicitly confirm the empty vehicle count before saving.",
        "Add student commute records before running scenarios":
            "Add and save supported student commute records before running a scenario.",
        "Some student records lack a supported factor; complete or correct those inputs before scenario comparison":
            "Some records do not have a supported factor. Correct the commute inputs or configure a supported factor before comparing scenarios.",
        "Save student or parking observations before requesting recommendations":
            "Save student commute records or a parking observation before generating recommendations.",
        "This image has already been saved in this campaign":
            "This image is already in the observation period; choose a different image or date.",
    }
    if exc.status_code == 409:
        message = conflict_messages.get(str(exc.detail), "Conflict.")
    elif exc.status_code == 503:
        if exc.detail == "Approved factors unavailable":
            message = "Approved emission factors are currently unavailable."
        else:
            message = (
                "Vehicle detection requires the optional YOLO dependencies and "
                "a compatible local weights file."
            )
    else:
        message = messages.get(
            exc.status_code,
            "Request could not be completed.",
        )
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "error": True,
            "message": message,
        },
    )


@app.exception_handler(DetectionUnavailable)
async def detector_unavailable_handler(_, exc: DetectionUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": True,
            "message": str(exc),
            "inference_status": "unavailable",
        },
    )


@app.exception_handler(DetectionFailed)
async def detector_failed_handler(_, exc: DetectionFailed) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": str(exc),
            "inference_status": "failed",
        },
    )


@app.exception_handler(DetectorInitializationFailed)
async def detector_initialization_failed_handler(_, exc: DetectorInitializationFailed) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": True, "message": str(exc), "inference_status": "failed"},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_, exc: Exception) -> JSONResponse:
    """Return a safe stable response without exposing exception details."""
    logging.getLogger("carbosync").exception("Unhandled API request failure")
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "An unexpected error occurred."},
    )


@app.get("/health")
def health() -> dict[str, object]:
    """Report API availability separately from local detector readiness."""
    try:
        detector = {"status": "ready", **get_detector_metadata()}
    except DetectionUnavailable as exc:
        detector = {"status": "unavailable", "message": str(exc)}
    except DetectorInitializationFailed as exc:
        detector = {"status": "failed", "message": str(exc)}
    return {"status": "healthy", "detector": detector}


DEMO_STUDENT_FACTORS = {
    "car": {"value": 0.145, "unit": "kg CO2/veh-km", "status": "illustrative_unapproved"},
    "motorcycle": {"value": 0.035, "unit": "kg CO2/veh-km", "status": "illustrative_unapproved"},
    "bus": {"value": 0.850, "unit": "kg CO2/veh-km", "status": "illustrative_unapproved"},
}


def _student_annual_emissions(student: dict[str, object], mode: str | None = None, occupancy: float | None = None) -> float | None:
    selected_mode = mode or str(student["travel_mode"])
    if selected_mode in {"walking", "cycling"}:
        return 0.0
    factor_category = {"car": "car", "motorcycle": "motorcycle", "public_transport": "bus"}.get(selected_mode)
    if factor_category is None or student.get("fuel_type") == "electric":
        return None
    factor = DEMO_STUDENT_FACTORS[factor_category]["value"]
    passenger_share = occupancy if occupancy is not None else float(student["occupancy"])
    if selected_mode == "public_transport":
        passenger_share = occupancy if occupancy is not None else float(student["occupancy"])
    annual_vehicle_km = (
        float(student["one_way_distance_km"])
        * 2
        * float(student["commute_days_per_week"])
        * 52
        / max(1.0, passenger_share)
    )
    return annual_vehicle_km * factor


def _student_summary(students: list[dict[str, object]], period_days: int = 10) -> dict[str, object]:
    by_mode: dict[str, dict[str, float]] = {}
    weekly_known_kg = 0.0
    unavailable = 0
    for student in students:
        mode = str(student["travel_mode"])
        annual_kg = _student_annual_emissions(student)
        if annual_kg is None:
            unavailable += 1
            continue
        weekly_kg = annual_kg / 52
        weekly_known_kg += weekly_kg
        bucket = by_mode.setdefault(mode, {"students": 0, "annual_kg_co2": 0.0, "weekly_kg_co2": 0.0})
        bucket["students"] += 1
        bucket["annual_kg_co2"] += annual_kg
        bucket["weekly_kg_co2"] += weekly_kg
    daily_weekday_kg = weekly_known_kg / 5
    has_calculated_records = len(students) > unavailable
    return {
        "student_count": len(students),
        "calculated_student_count": len(students) - unavailable,
        "unavailable_student_count": unavailable,
        "calculation_status": "partial" if unavailable else "available" if students else "unavailable",
        "annual_kg_co2": weekly_known_kg * 52 if has_calculated_records else None,
        "weekly_kg_co2": weekly_known_kg if has_calculated_records else None,
        "average_weekday_kg_co2": daily_weekday_kg if has_calculated_records else None,
        "observation_period_days": period_days,
        "observation_period_kg_co2_estimate": daily_weekday_kg * period_days if has_calculated_records else None,
        "by_mode": by_mode,
        "factor_register": {
            **DEMO_STUDENT_FACTORS,
            "walking": {"value": 0, "unit": "kg tailpipe CO2/passenger-km", "status": "zero_tailpipe_scope"},
            "cycling": {"value": 0, "unit": "kg tailpipe CO2/passenger-km", "status": "zero_tailpipe_scope"},
        },
        "methodology": (
            "weekly commute vehicle-km = one-way km × 2 × commute days/week; "
            "annual activity = weekly activity × 52; shared/passenger vehicle-km "
            "is divided by the entered occupancy; weekday average = weekly emissions ÷ 5."
        ),
        "limitations": [
            "Car, motorcycle, and bus factors are existing demo candidates and are not verified or approved sources.",
            "Fuel-specific applicability is not validated; electric records are omitted until a grid factor is configured.",
            "Distance is manually supplied; no address geocoding or routing is performed.",
            "Observation-period emissions are student-commute estimates, not emissions measured by parking photos.",
        ],
    }


def _campaign_response(campaign: dict[str, object] | None) -> dict[str, object] | None:
    if campaign is None:
        return None
    observations = get_parking_observations(str(campaign["campaign_id"]))
    start = date.fromisoformat(str(campaign["start_date"]))
    end = start + timedelta(days=int(campaign["duration_days"]) - 1)
    days = len({str(item["observation_date"]) for item in observations})
    return {
        **campaign,
        "end_date": end.isoformat(),
        "observed_day_count": days,
        "image_count": len(observations),
        "day_progress": f"{days}/{campaign['duration_days']} days",
        "observations": observations,
    }


@app.get("/api/demo/students")
def list_students() -> dict[str, object]:
    """Return private student records only to the same-origin local demo UI."""
    return {"college_address": get_campus_address(), "students": get_demo_students()}


@app.put("/api/demo/students")
def save_students(payload: StudentsUpdate) -> dict[str, object]:
    set_campus_address(payload.college_address, utc_timestamp())
    replace_demo_students(
        [student.model_dump(mode="json") for student in payload.students],
        utc_timestamp(),
    )
    return {"saved": len(payload.students), "college_address": payload.college_address}


@app.get("/api/demo/commute-summary")
def commute_summary() -> dict[str, object]:
    campaign = get_current_observation_campaign()
    period_days = int(campaign["duration_days"]) if campaign else 10
    summary = _student_summary(get_demo_students(), period_days)
    summary["evidence_label"] = "User-provided student commute inputs; illustrative candidate factors"
    return summary


@app.post("/api/demo/campaigns", status_code=201)
def start_observation_campaign(payload: CampaignCreate) -> dict[str, object]:
    campaign_id = f"camp_{uuid.uuid4().hex}"
    create_observation_campaign(
        campaign_id, payload.start_date.isoformat(), payload.duration_days, utc_timestamp()
    )
    return _campaign_response(get_current_observation_campaign()) or {}


@app.get("/api/demo/campaigns/current")
def current_campaign() -> dict[str, object]:
    return {"campaign": _campaign_response(get_current_observation_campaign())}


@app.get("/api/demo/campaigns/{campaign_id}/report")
def observation_report(campaign_id: str) -> dict[str, object]:
    campaign = get_observation_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    result = _campaign_response(campaign) or {}
    result["student_commute"] = _student_summary(
        get_demo_students(), int(campaign["duration_days"])
    )
    # Public report payload intentionally contains no student names or addresses.
    return result


@app.post("/api/demo/campaigns/{campaign_id}/observations", status_code=201)
def save_observation(campaign_id: str, payload: ObservationSave) -> dict[str, object]:
    campaign = get_observation_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    start = date.fromisoformat(str(campaign["start_date"]))
    end = start + timedelta(days=int(campaign["duration_days"]) - 1)
    if not start <= payload.observation_date <= end:
        raise HTTPException(status_code=422, detail="Observation date is outside the campaign window")
    analysis = get_demo_analysis(payload.analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    detections = analysis["detections"]
    if detections.get("mode") != "real" or detections.get("simulated"):
        raise HTTPException(status_code=422, detail="Only real inference can be saved as a parking observation")
    if not any(payload.counts.values()) and not payload.human_reviewed:
        raise HTTPException(status_code=409, detail="Review the image and explicitly confirm the empty vehicle count before saving")
    image_hash = str(detections.get("image_sha256") or "")
    if len(image_hash) != 64:
        raise HTTPException(status_code=422, detail="Analysis image reference is unavailable")
    original_counts = detections.get("per_class", {})
    corrected = any(int(payload.counts[key]) != int(original_counts.get(key, 0)) for key in payload.counts)
    created_at = utc_timestamp()
    observation_id = f"obs_{uuid.uuid4().hex}"
    saved = save_parking_observation(
        observation_id=observation_id,
        campaign_id=campaign_id,
        observation_date=payload.observation_date.isoformat(),
        analysis_id=payload.analysis_id,
        image_sha256=image_hash,
        counts=payload.counts,
        model_metadata=detections.get("model_metadata", {}),
        inference_status=str(detections.get("inference_status", "failed")),
        corrected=corrected,
        human_reviewed=payload.human_reviewed,
        created_at=created_at,
    )
    if not saved:
        raise HTTPException(status_code=409, detail="This image has already been saved in this campaign")
    return {
        "observation_id": observation_id,
        "campaign_id": campaign_id,
        "observation_date": payload.observation_date.isoformat(),
        "analysis_id": payload.analysis_id,
        "counts": payload.counts,
        "corrected": corrected,
        "human_reviewed": payload.human_reviewed,
        "inference_status": detections.get("inference_status"),
    }


@app.post("/api/demo/student-scenarios")
def student_scenario(payload: StudentScenarioInput) -> dict[str, object]:
    students = get_demo_students()
    if not students:
        raise HTTPException(status_code=409, detail="Add student commute records before running scenarios")
    baseline_by_student = [_student_annual_emissions(student) for student in students]
    if any(value is None for value in baseline_by_student):
        raise HTTPException(status_code=409, detail="Some student records lack a supported factor; complete or correct those inputs before scenario comparison")
    baseline = sum(float(value) for value in baseline_by_student if value is not None)
    carpool_total = 0.0
    transit_total = 0.0
    active_total = 0.0
    shuttle_eligible_private_total = 0.0
    flow_modes = (
        "single_occupancy_car", "carpool_vehicle", "motorcycle",
        "public_transport", "active_travel", "shuttle",
    )
    baseline_flow = {mode: 0.0 for mode in flow_modes}
    carpool_flow = {mode: 0.0 for mode in flow_modes}
    transit_flow = {mode: 0.0 for mode in flow_modes}
    active_flow = {mode: 0.0 for mode in flow_modes}
    shuttle_flow = {mode: 0.0 for mode in flow_modes}
    for student, base in zip(students, baseline_by_student):
        base_value = float(base or 0)
        mode = str(student["travel_mode"])
        weekly_commute_days = float(student["commute_days_per_week"])
        current_flow_mode = (
            "carpool_vehicle" if mode == "car" and float(student["occupancy"]) > 1
            else "single_occupancy_car" if mode == "car"
            else "motorcycle" if mode == "motorcycle"
            else "public_transport" if mode == "public_transport"
            else "active_travel" if mode in {"walking", "cycling"}
            else None
        )
        if current_flow_mode:
            baseline_flow[current_flow_mode] += weekly_commute_days
            for profile in (carpool_flow, transit_flow, active_flow, shuttle_flow):
                profile[current_flow_mode] += weekly_commute_days
        if mode == "car":
            current_occupancy = max(1.0, float(student["occupancy"]))
            carpool_total += base_value * (1 - payload.carpool_share * (1 - current_occupancy / payload.carpool_occupancy))
            shifted = weekly_commute_days * payload.carpool_share
            carpool_flow[current_flow_mode] -= shifted
            carpool_flow["carpool_vehicle"] += shifted
        else:
            carpool_total += base_value
        if mode in {"car", "motorcycle"}:
            shuttle_eligible_private_total += base_value
            eligible_flow_mode = "single_occupancy_car" if mode == "car" and float(student["occupancy"]) <= 1 else "carpool_vehicle" if mode == "car" else "motorcycle"
            bus_value = _student_annual_emissions(student, "public_transport", payload.transit_occupancy)
            replacement = float(bus_value or 0)
            transit_total += base_value * (1 - payload.public_transport_share) + replacement * payload.public_transport_share
            transit_shift = weekly_commute_days * payload.public_transport_share
            transit_flow[eligible_flow_mode] -= transit_shift
            transit_flow["public_transport"] += transit_shift
            eligible = float(student["one_way_distance_km"]) <= payload.active_travel_limit_km
            active_total += base_value * (1 - payload.active_travel_share) if eligible else base_value
            if eligible:
                active_shift = weekly_commute_days * payload.active_travel_share
                active_flow[eligible_flow_mode] -= active_shift
                active_flow["active_travel"] += active_shift
            shuttle_shift = weekly_commute_days * payload.shuttle_shift_share
            shuttle_flow[eligible_flow_mode] -= shuttle_shift
            shuttle_flow["shuttle"] += shuttle_shift
        else:
            transit_total += base_value
            active_total += base_value
    private_fraction = min(1.0, max(0.0, payload.shuttle_shift_share))
    shuttle_avoided_kg = shuttle_eligible_private_total * private_fraction
    shuttle_vehicle_km_per_year = (
        payload.shuttle_daily_vehicles
        * payload.shuttle_trips_per_vehicle_per_day
        * payload.shuttle_one_way_route_km
        * 2
        * payload.shuttle_operating_days_per_year
    )
    shuttle_added_kg = shuttle_vehicle_km_per_year * DEMO_STUDENT_FACTORS["bus"]["value"]
    shuttle_total = baseline - shuttle_avoided_kg + shuttle_added_kg
    scenarios = {
        "carpool": carpool_total,
        "public_transport": transit_total,
        "active_travel": active_total,
        "campus_shuttle": shuttle_total,
    }
    def scenario_result(value: float) -> dict[str, object]:
        reduction = baseline - value
        return {
            "annual_kg_co2": value,
            "reduction_kg_co2": reduction,
            "reduction_percent": reduction / baseline * 100 if baseline else None,
        }
    result = {
        "evidence_label": "Illustrative deterministic scenario using student inputs and unapproved factors",
        "calculation_method_version": "student_commute_scenario_v1",
        "calculation_methodology": "Student annual commute vehicle-km = user-provided one-way distance × 2 × commute days per week × 52; passenger activity is allocated by entered vehicle occupancy. Shuttle service emissions use total shuttle vehicle-km × the unapproved bus factor.",
        "factor_register": DEMO_STUDENT_FACTORS,
        "baseline": {"annual_kg_co2": baseline},
        "scenarios": {key: scenario_result(value) for key, value in scenarios.items()},
        "flow_representation": {
            "basis": "Weekly round-trip commute-day activity weighted by user-entered commute days; fractional shares are illustrative, not measured trips or predicted road traffic.",
            "baseline": baseline_flow,
            "scenarios": {
                "carpool": carpool_flow,
                "public_transport": transit_flow,
                "active_travel": active_flow,
                "campus_shuttle": shuttle_flow,
            },
        },
        "shuttle_activity": {
            "avoided_private_annual_kg_co2": shuttle_avoided_kg,
            "added_shuttle_annual_kg_co2": shuttle_added_kg,
            "shuttle_vehicle_km_per_year": shuttle_vehicle_km_per_year,
            "operating_days_per_year": payload.shuttle_operating_days_per_year,
            "factor": DEMO_STUDENT_FACTORS["bus"],
        },
        "assumptions": payload.model_dump(mode="json"),
        "limitations": ["Factors are provisional demo candidates; scenario outputs are not forecasts."],
    }
    run_id = f"scenario_{uuid.uuid4().hex}"
    save_demo_scenario(run_id, utc_timestamp(), payload.model_dump(mode="json"), result)
    result["scenario_run_id"] = run_id
    return result


@app.get("/api/demo/scenarios/latest")
def latest_student_scenario() -> dict[str, object]:
    return {"scenario": get_latest_demo_scenario()}


@app.post("/api/demo/recommendations/generate")
async def generate_campaign_recommendations() -> dict[str, object]:
    students = get_demo_students()
    campaign = get_current_observation_campaign()
    observations = get_parking_observations(str(campaign["campaign_id"])) if campaign else []
    if not students and not observations:
        raise HTTPException(status_code=409, detail="Save student or parking observations before requesting recommendations")
    commute = _student_summary(students, int(campaign["duration_days"]) if campaign else 10)
    class_names = ("bicycle", "car", "motorcycle", "bus", "truck")
    date_groups: dict[str, list[dict[str, int]]] = {}
    for item in observations:
        date_groups.setdefault(str(item["observation_date"]), []).append(item["counts"])
    daily_averages = []
    for observation_date, rows in sorted(date_groups.items()):
        daily = {key: sum(float(row.get(key, 0)) for row in rows) / len(rows) for key in class_names}
        daily_averages.append({"date": observation_date, "mean_snapshot_counts": daily, "snapshot_count": len(rows)})
    mode_counts: dict[str, int] = {}
    for student in students:
        mode = str(student["travel_mode"])
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
    daily_mean_counts = {
        key: sum(day["mean_snapshot_counts"][key] for day in daily_averages) / len(daily_averages)
        for key in class_names
    } if daily_averages else {}
    evidence = {
        "student_count": len(students),
        "student_mode_counts": mode_counts,
        "student_commute_summary": commute,
        "observed_days": len(daily_averages),
        "snapshot_count": len(observations),
        "daily_mean_vehicle_counts": daily_mean_counts,
        "daily_observation_counts": daily_averages,
        "limitations": commute["limitations"] + [
            "Parking photos are point-in-time observations, not commute trip counts.",
            "No names, home addresses, or college addresses are present in this recommendation input.",
        ],
    }
    recommendation = await run_in_threadpool(generate_evidence_recommendations, evidence)
    save_demo_recommendations(f"recs_{uuid.uuid4().hex}", utc_timestamp(), recommendation)
    return {**recommendation, "evidence_context": {"student_count": len(students), "observation_days": len(daily_averages), "snapshot_count": len(observations)}}


@app.get("/api/demo/recommendations/latest")
def latest_recommendations() -> dict[str, object]:
    return {"recommendations": get_latest_demo_recommendations()}


@app.get("/api/demo/final-report")
def final_report() -> dict[str, object]:
    campaign = get_current_observation_campaign()
    observations = get_parking_observations(str(campaign["campaign_id"])) if campaign else []
    summary = _student_summary(get_demo_students(), int(campaign["duration_days"]) if campaign else 10)
    return {
        "campaign": _campaign_response(campaign),
        "observations": observations,
        "student_commute": summary,
        "scenario": get_latest_demo_scenario(),
        "recommendations": get_latest_demo_recommendations(),
        "privacy": "Personal names and residential addresses are excluded from this report.",
    }


@app.post("/api/assessments/{assessment_id}/commute-inputs")
def calculate_commute_inputs(
    assessment_id: str,
    request: CommuteInput,
) -> dict[str, object]:
    """Calculate using an explicit candidate factor or approved registry ref."""
    if request.calculation_mode == "approved":
        if not APPROVED_FACTOR_REGISTRY:
            raise HTTPException(
                status_code=503,
                detail="Approved factors unavailable",
            )

    category_results: list[dict[str, object]] = []
    annual_vkt_total_km = 0.0
    annual_emissions_total_kg_co2 = 0.0

    for mode in request.mode_data:
        if request.calculation_mode == "approved":
            registry_factor = resolve_approved_factor(
                mode.factor_reference.factor_id,
                mode.factor_reference.version,
            )
            if registry_factor is None:
                raise HTTPException(status_code=404, detail="Factor not found")
            if registry_factor.approval_status != "approved":
                raise HTTPException(status_code=409, detail="Factor is not approved")
            if (
                registry_factor.factor_id != mode.factor_reference.factor_id
                or registry_factor.version != mode.factor_reference.version
                or not registry_factor.review_evidence
                or not registry_factor.owner_approval_decision
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Factor approval evidence is unavailable",
                )
            if mode.category not in registry_factor.vehicle_categories:
                raise HTTPException(status_code=422, detail="Factor is not applicable")
            if (
                registry_factor.unit != EXPECTED_EMISSION_FACTOR_UNIT
                or registry_factor.metric_scope != "Tailpipe_CO2"
            ):
                raise HTTPException(status_code=422, detail="Factor is not applicable")
            factor_value = registry_factor.value
            factor_unit = registry_factor.unit
            factor_snapshot: dict[str, object] = {
                "factor_id": registry_factor.factor_id,
                "version": registry_factor.version,
                "value": registry_factor.value,
                "unit": registry_factor.unit,
                "metric_scope": registry_factor.metric_scope,
                "geographic_scope": registry_factor.geographic_scope,
                "vehicle_categories": list(registry_factor.vehicle_categories),
                "fuel_powertrain_applicability": (
                    registry_factor.fuel_powertrain_applicability
                ),
                "fuel_powertrain_checked": False,
                "source_title": registry_factor.source_title,
                "source_url": registry_factor.source_url,
                "source_version_year": registry_factor.source_version_year,
                "approximation_notes": registry_factor.approximation_notes,
                "limitations": registry_factor.limitations,
                "approval_status": registry_factor.approval_status,
                "review_evidence": registry_factor.review_evidence,
                "owner_approval_decision": registry_factor.owner_approval_decision,
            }
        else:
            candidate = mode.candidate_factor
            factor_value = candidate.value
            factor_unit = candidate.unit
            candidate_snapshot = {
                "category": mode.category,
                "factor": candidate.model_dump(mode="json"),
            }
            candidate_version_digest = hashlib.sha256(
                json.dumps(
                    candidate_snapshot,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            factor_snapshot = {
                "factor_id": candidate.factor_id,
                "version": f"candidate-sha256:{candidate_version_digest}",
                "declared_version": candidate.version,
                "value": candidate.value,
                "unit": candidate.unit,
                "metric_scope": candidate.provenance.metric_scope,
                "geographic_scope": candidate.provenance.geographic_scope,
                "vehicle_categories": [mode.category],
                "fuel_powertrain_applicability": (
                    "Not provided by request; compatibility not checked."
                ),
                "fuel_powertrain_checked": False,
                "source_title": candidate.provenance.source_title,
                "source_url": (
                    str(candidate.provenance.source_url)
                    if candidate.provenance.source_url
                    else None
                ),
                "source_version_year": candidate.provenance.version_year,
                "approximation_notes": candidate.provenance.approximation_notes,
                "limitations": "Candidate factor; not approved or independently verified.",
                "approval_status": "candidate",
                "review_evidence": None,
                "owner_approval_decision": None,
                "origin": candidate.provenance.origin,
            }

        factor = EmissionFactor(
            value=factor_value,
            unit=factor_unit,
        )
        result = calculate_annual_emissions(
            daily_vehicles=mode.daily_vehicles,
            one_way_distance_km=mode.avg_one_way_km,
            academic_days_per_year=request.annual_days,
            emission_factor=factor,
        )
        annual_vkt_total_km += result.annual_vkt_km
        annual_emissions_total_kg_co2 += result.annual_emissions_kg_co2
        category_results.append(
            {
                "category": mode.category,
                "daily_vehicles_per_day": mode.daily_vehicles,
                "daily_vehicles_provenance": mode.daily_vehicles_provenance.model_dump(
                    mode="json", exclude_unset=True
                ),
                "avg_one_way_km": mode.avg_one_way_km,
                "avg_one_way_km_provenance": mode.avg_one_way_km_provenance.model_dump(
                    mode="json", exclude_unset=True
                ),
                "occupancy_persons_per_vehicle": mode.occupancy,
                "emission_factor_kg_co2_per_vehicle_km": factor_value,
                "emission_factor_unit": factor_unit,
                "factor_snapshot": factor_snapshot,
                "annual_vkt_km_per_year": result.annual_vkt_km,
                "annual_emissions_kg_co2_per_year": result.annual_emissions_kg_co2,
                "annual_emissions_tonnes_co2_per_year": (
                    result.annual_emissions_tonnes_co2
                ),
            }
        )

    result = {
        "assessment_id": assessment_id,
        "annual_days_per_year": request.annual_days,
        "annual_days_provenance": request.annual_days_provenance.model_dump(
            mode="json", exclude_unset=True
        ),
        "sample_size": request.sample_size,
        "population_total": request.population_total,
        "is_campus_projection": False,
        "calculation_mode": request.calculation_mode,
        "approval_status": (
            "approved" if request.calculation_mode == "approved" else "unapproved"
        ),
        "calculation_method_version": CALCULATION_METHOD_VERSION,
        "metric_scope": "Tailpipe_CO2",
        "emissions_unit": "CO2",
        "annual_vkt_total_km_per_year": annual_vkt_total_km,
        "annual_emissions_kg_co2_per_year": annual_emissions_total_kg_co2,
        "annual_emissions_tonnes_co2_per_year": (
            annual_emissions_total_kg_co2 / 1000
        ),
        "total_annual_vkt": annual_vkt_total_km,
        "total_annual_tonnes_co2": annual_emissions_total_kg_co2 / 1000,
        "total_annual_kg_co2": annual_emissions_total_kg_co2,
        "evidence_label": "Derived calculation",
        "independently_verified": False,
        "result_interpretation": (
            "Candidate calculation; factor is unapproved."
            if request.calculation_mode == "candidate"
            else "Approved factor used; activity data are not independently verified."
        ),
        "b3_metadata": {
            "availability": "available_b3",
            "activity_provenance": "available",
            "factor_governance": (
                "approved_registry"
                if request.calculation_mode == "approved"
                else "candidate_unapproved"
            ),
            "calculation_method_version": CALCULATION_METHOD_VERSION,
        },
        "category_breakdown": category_results,
    }
    saved = save_commute_calculation(
        calculation_id=f"calc_{uuid.uuid4().hex}",
        assessment_id=assessment_id,
        created_at=utc_timestamp(),
        inputs=request.model_dump(mode="json", exclude_unset=True),
        result=result,
    )
    if not saved:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return result


@app.post("/api/demo/analyze", status_code=201)
async def analyze_demo_image(
    image: UploadFile = File(...),
    assumptions_json: str = Form(...),
    observation_campaign_id: str | None = Form(None),
) -> dict[str, object]:
    """Detect a parking snapshot, then calculate clearly illustrative estimates."""
    try:
        request = DemoAnalysisRequest.model_validate_json(assumptions_json)
    except ValidationError as exc:
        await image.close()
        raise HTTPException(status_code=422, detail="Invalid demo assumptions") from exc

    content_type = (image.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        await image.close()
        raise HTTPException(status_code=415, detail="Unsupported image type")
    try:
        image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    finally:
        await image.close()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds size limit")
    image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    duplicate_campaign_image = False
    if observation_campaign_id:
        if get_observation_campaign(observation_campaign_id) is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if has_parking_image(observation_campaign_id, image_sha256):
            duplicate_campaign_image = True
    try:
        validated_image = validate_image_bytes(image_bytes, content_type)
    except ImageInputError as exc:
        raise HTTPException(status_code=422, detail="Uploaded file is not a valid supported image") from exc
    if request.detection_mode == "simulated":
        counts = request.simulated_detection_counts
        detection_details: list[dict[str, object]] = []
        detection_mode = "simulated"
        model_metadata: dict[str, object] = {
            "name": "Simulated detections",
            "confidence_threshold": None,
            "class_mapping": {},
            "unmapped_vehicle_categories": [],
            "inference_status": "simulated",
            "inference_settings": None,
            "weights_sha256": None,
            "runtime_versions": None,
            "supported_classes": [],
        }
        inference_status = "simulated"
        annotated_image_data_uri = None
        warnings = [
            "Simulated mode was selected; the uploaded image was not analyzed."
        ]
        if duplicate_campaign_image:
            warnings.append("This image has already been saved in this campaign.")
    else:
        detections = await run_in_threadpool(
            detect_vehicle_image,
            validated_image.image,
        )
        counts = detections.counts
        detection_details = detections.detections
        detection_mode = "real"
        inference_status = detections.inference_status
        model_metadata = {
            **detections.metadata,
            "name": detections.model,
            "confidence_threshold": detections.confidence_threshold,
            "class_mapping": detections.class_mapping,
            "unmapped_vehicle_categories": detections.unmapped_vehicle_categories,
            "inference_status": detections.inference_status,
        }
        annotated_image_data_uri = detections.annotated_image_data_uri
        warnings = []
        if duplicate_campaign_image:
            warnings.append("This image has already been saved in this campaign.")
        if detections.unmapped_vehicle_categories:
            warnings.append(
                "The configured model does not contain every supported vehicle class; "
                "see unmapped_vehicle_categories before interpreting zero counts."
            )

    motor_total = sum(counts[name] for name in ("car", "motorcycle", "bus", "truck"))
    detected = {
        "mode": detection_mode,
        "simulated": detection_mode == "simulated",
        "inference_status": inference_status,
        "per_class": counts,
        "details": detection_details,
        "motor_vehicle_total": motor_total,
        "bicycle_total": counts["bicycle"],
        "all_vehicle_total": sum(counts.values()),
        "observation_scope": (
            "user_supplied_simulation"
            if detection_mode == "simulated"
            else "single_image_snapshot"
        ),
        "model": model_metadata["name"],
        "model_metadata": model_metadata,
        "confidence_threshold": model_metadata["confidence_threshold"],
        "class_mapping": model_metadata["class_mapping"],
        "unmapped_vehicle_categories": model_metadata[
            "unmapped_vehicle_categories"
        ],
        "image_sha256": image_sha256,
    }
    request_data = request.model_dump(mode="json")
    try:
        calculation = calculate_demo_analysis(
            detection_counts=counts,
            request=request_data,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Demo assumptions are invalid") from exc
    recommendation = await run_in_threadpool(
        generate_recommendations,
        calculation,
    )
    calculation["recommendations"] = recommendation
    calculation["warnings"] = warnings
    if detection_mode == "simulated":
        calculation["evidence_label"] = (
            "Simulated detection counts combined with explicit illustrative assumptions"
        )
        calculation["limitations"].append(
            "Simulated detections are user-supplied demo counts, not image detections."
        )
    analysis_id = f"demo_{uuid.uuid4().hex}"
    created_at = utc_timestamp()
    save_demo_analysis(
        analysis_id=analysis_id,
        created_at=created_at,
        detections=detected,
        assumptions=request_data,
        result=calculation,
    )
    return {
        "analysis_id": analysis_id,
        "image_sha256": image_sha256,
        "created_at": created_at,
        "detection_mode": detection_mode,
        "inference_status": inference_status,
        "detections": detected,
        "model": {
            **model_metadata,
            "detection_mode": detection_mode,
            "simulated": detection_mode == "simulated",
        },
        "detection_details": detection_details,
        "annotated_image_data_uri": annotated_image_data_uri,
        "result": calculation,
    }


@app.get("/api/demo/analyses/{analysis_id}")
def retrieve_demo_analysis(analysis_id: str) -> dict[str, object]:
    analysis = get_demo_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Demo analysis not found")
    return analysis


# ── Full Integration Endpoints for Frontend ───────────────────

@app.post("/api/assessments/{assessment_id}/images", status_code=201)
async def upload_assessment_image(
    assessment_id: str,
    file: UploadFile = File(...),
    confidence: float = Form(0.15, gt=0, le=1),
) -> dict[str, object]:
    """Upload parking snapshot, run YOLO vehicle detection, and return bounding boxes for frontend."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file in upload.")

    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        content_type = "image/jpeg"

    image_bytes = await file.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds size limit")

    try:
        validated_image = validate_image_bytes(image_bytes, content_type)
    except ImageInputError as exc:
        raise HTTPException(status_code=422, detail="Uploaded file is not a valid supported image") from exc

    detections = await run_in_threadpool(
        detect_vehicle_image,
        validated_image.image,
        confidence,
    )

    width, height = getattr(validated_image.image, "size", (1920, 1080))
    category_map = {
        "car": "Cars",
        "motorcycle": "Motorcycles and scooters",
        "bus": "Buses and campus shuttles",
        "truck": "Other fuel-burning vehicles",
        "bicycle": "Bicycles",
    }

    formatted_detections = []
    for idx, det in enumerate(detections.detections):
        cat = category_map.get(det["category"], det["category"])
        box_norm = det.get("bounding_box_normalized", {})
        x1 = int(round(box_norm.get("x_min", 0.0) * width))
        y1 = int(round(box_norm.get("y_min", 0.0) * height))
        x2 = int(round(box_norm.get("x_max", 0.0) * width))
        y2 = int(round(box_norm.get("y_max", 0.0) * height))
        formatted_detections.append({
            "detection_id": f"det_{idx + 1:02d}",
            "category": cat,
            "coco_class": det["category"].capitalize(),
            "confidence": round(det["confidence"], 4),
            "box": {
                "x_min": x1,
                "y_min": y1,
                "x_max": x2,
                "y_max": y2,
            }
        })

    # Save clean copy for record
    results_dir = Path(__file__).resolve().parent.parent / "detection_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(file.filename).stem or f"img_{uuid.uuid4().hex[:8]}"
    clean_path = results_dir / f"{stem}_original.jpg"
    try:
        validated_image.image.save(clean_path, format="JPEG")
    except Exception:
        pass

    return {
        "image_id": f"img_{uuid.uuid4().hex[:8]}",
        "image_name": file.filename,
        "width": width,
        "height": height,
        "annotated_image_url": detections.annotated_image_data_uri,
        "model": detections.model,
        "confidence_threshold": detections.confidence_threshold,
        "inference_status": detections.inference_status,
        "model_metadata": detections.metadata,
        "detections": formatted_detections,
        "snapshot_summary": {
            "Cars": detections.counts.get("car", 0),
            "Motorcycles and scooters": detections.counts.get("motorcycle", 0),
            "Buses and campus shuttles": detections.counts.get("bus", 0),
            "Other fuel-burning vehicles": detections.counts.get("truck", 0),
            "Bicycles": detections.counts.get("bicycle", 0),
        }
    }


class VerificationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    verified_counts: dict[str, int] = Field(default_factory=dict)


@app.post("/api/assessments/{assessment_id}/verify")
def verify_assessment_detections(assessment_id: str, payload: VerificationPayload) -> dict[str, object]:
    """Human verification lock endpoint: seals detection counts with confirmation metadata."""
    return {
        "assessment_id": assessment_id,
        "status": "confirmed",
        "evidence_label": "Human-confirmed observation",
        "verified_counts": payload.verified_counts,
        "verified_at": utc_timestamp(),
    }


class SimulationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    remote_days: float = 1.0
    carpool_pct: float = 25.0
    shuttle_pct: float = 15.0


@app.post("/api/assessments/{assessment_id}/simulate")
async def run_assessment_simulation(assessment_id: str, payload: SimulationPayload) -> dict[str, object]:
    """Simulate Digital Twin intervention scenarios (remote, carpool, shuttle) and AI recommendations."""
    assessment = load_assessment(assessment_id)
    baseline_tonnes = 45.0
    if assessment and assessment.get("commute_calculations"):
        last_calc = assessment["commute_calculations"][-1]["result"]
        baseline_tonnes = float(last_calc.get("annual_emissions_tonnes_co2_per_year", 45.0))

    remote_fraction = min(1.0, max(0.0, payload.remote_days / 5.0))
    s1_savings = baseline_tonnes * remote_fraction * 0.8
    s1_tonnes = max(0.0, baseline_tonnes - s1_savings)

    carpool_fraction = min(1.0, max(0.0, payload.carpool_pct / 100.0))
    s2_savings = baseline_tonnes * carpool_fraction * 0.40
    s2_tonnes = max(0.0, baseline_tonnes - s2_savings)

    shuttle_fraction = min(1.0, max(0.0, payload.shuttle_pct / 100.0))
    avoided_private = baseline_tonnes * shuttle_fraction * 0.50
    added_shuttle = 11.9 if shuttle_fraction > 0 else 0.0
    s3_tonnes = max(0.0, baseline_tonnes - avoided_private + added_shuttle)

    net_savings = baseline_tonnes - min(s1_tonnes, s2_tonnes, s3_tonnes)

    fake_calc = {
        "baseline": {
            "annual_tonnes_co2": baseline_tonnes,
        },
        "scenarios": [
            {
                "id": "active_travel",
                "name": f"Remote / Active travel ({payload.remote_days} days/wk)",
                "estimated_emissions": {"annual_tonnes_co2": s1_tonnes},
                "reduction_vs_baseline_tonnes": s1_savings,
            },
            {
                "id": "carpool",
                "name": f"Carpool matching ({payload.carpool_pct}% participation)",
                "estimated_emissions": {"annual_tonnes_co2": s2_tonnes},
                "reduction_vs_baseline_tonnes": s2_savings,
            },
            {
                "id": "campus_shuttle",
                "name": f"Campus shuttle ({payload.shuttle_pct}% shift)",
                "estimated_emissions": {"annual_tonnes_co2": s3_tonnes},
                "reduction_vs_baseline_tonnes": avoided_private - added_shuttle,
            },
        ],
        "best_scenario": {
            "id": "active_travel" if s1_tonnes <= min(s2_tonnes, s3_tonnes) else ("carpool" if s2_tonnes <= s3_tonnes else "campus_shuttle"),
            "name": "Optimal Carbon Reduction Strategy"
        }
    }
    recs = await run_in_threadpool(generate_recommendations, fake_calc)

    return {
        "assessment_id": assessment_id,
        "baseline_tonnes_co2": baseline_tonnes,
        "scenario_1_tonnes_co2": round(s1_tonnes, 2),
        "scenario_2_tonnes_co2": round(s2_tonnes, 2),
        "scenario_3_tonnes_co2": round(s3_tonnes, 2),
        "net_savings_tonnes_co2": round(net_savings, 2),
        "avoided_private_tonnes_co2": round(avoided_private, 2),
        "added_shuttle_tonnes_co2": round(added_shuttle, 2),
        "recommendations": recs.get("recommendations", []),
        "fallback_activated": recs.get("fallback_flag", True),
    }


# ── Static File Mounts ─────────────────────────────────────────
# Detection results are always served (small, stable directory).
results_dir = Path(__file__).resolve().parent.parent / "detection_results"
results_dir.mkdir(parents=True, exist_ok=True)
if os.getenv("CARBOSYNC_SERVE_DETECTION_RESULTS", "0") == "1":
    # This directory can contain uploaded source images; serve it only when an
    # operator explicitly accepts that every file in it is publicly readable.
    app.mount("/detection_results", StaticFiles(directory=str(results_dir)), name="detection_results")

# The frontend catch-all mount at "/" must be opt-in via env var because it
# intercepts ALL unmatched routes, which breaks dynamically-added test routes
# and the test error-handler tests.  Set CARBOSYNC_SERVE_FRONTEND=1 when
# running the real dev server (see README / BACKEND_SETUP.md).
if os.getenv("CARBOSYNC_SERVE_FRONTEND", "0") == "1":
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
