"""FastAPI endpoint for deterministic commute-emissions calculations."""

import hashlib
import json
import os
import uuid
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
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
from backend.recommendations import generate_recommendations
from backend.vehicle_detection import (
    DetectionUnavailable,
    ImageInputError,
    MAX_IMAGE_BYTES,
    detect_vehicle_image,
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
            "http://localhost:5500,http://127.0.0.1:5500",
        )
        if raw_origins is None
        else raw_origins
    )
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app = FastAPI(title="CarboSync Commute Emissions API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
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
    if exc.status_code == 503:
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


@app.exception_handler(Exception)
async def unexpected_error_handler(_, exc: Exception) -> JSONResponse:
    """Return a safe stable response without exposing exception details."""
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "An unexpected error occurred."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is responding; no optional subsystem is claimed."""
    return {"status": "healthy"}


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
        }
        annotated_image_data_uri = None
        warnings = [
            "Simulated mode was selected; the uploaded image was not analyzed."
        ]
    else:
        try:
            detections = await run_in_threadpool(
                detect_vehicle_image,
                validated_image.image,
            )
        except DetectionUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        counts = detections.counts
        detection_details = detections.detections
        detection_mode = "real"
        model_metadata = {
            "name": detections.model,
            "confidence_threshold": detections.confidence_threshold,
            "class_mapping": detections.class_mapping,
            "unmapped_vehicle_categories": detections.unmapped_vehicle_categories,
        }
        annotated_image_data_uri = detections.annotated_image_data_uri
        warnings = []
        if detections.unmapped_vehicle_categories:
            warnings.append(
                "The configured model does not contain every supported vehicle class; "
                "see unmapped_vehicle_categories before interpreting zero counts."
            )

    motor_total = sum(counts[name] for name in ("car", "motorcycle", "bus", "truck"))
    detected = {
        "mode": detection_mode,
        "simulated": detection_mode == "simulated",
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
        "confidence_threshold": model_metadata["confidence_threshold"],
        "class_mapping": model_metadata["class_mapping"],
        "unmapped_vehicle_categories": model_metadata[
            "unmapped_vehicle_categories"
        ],
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
        "created_at": created_at,
        "detection_mode": detection_mode,
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
