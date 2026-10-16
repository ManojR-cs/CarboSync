"""Guarded OpenAI-compatible narrative recommendations with deterministic fallback."""

from __future__ import annotations

import json
import os
import re
from typing import Literal
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError


ScenarioId = Literal["carpool", "campus_shuttle", "active_travel"]
TIMEOUT_SECONDS = 4.0


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    priority: int = Field(ge=1, le=5)
    title: str = Field(min_length=3, max_length=120)
    why_it_may_help: str = Field(min_length=10, max_length=500)
    practical_tradeoffs: str = Field(min_length=5, max_length=500)
    related_scenario: ScenarioId


class RecommendationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str = Field(min_length=10, max_length=500)
    recommendations: list[Recommendation] = Field(min_length=1, max_length=5)
    best_scenario: ScenarioId


class EvidenceRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    priority: int = Field(ge=1, le=5)
    action: str = Field(min_length=3, max_length=160)
    relevance: str = Field(min_length=10, max_length=500)
    assumptions: str = Field(min_length=5, max_length=500)
    constraints: str = Field(min_length=5, max_length=500)
    estimated_reduction: Literal["Not calculated from current data"]


class EvidenceRecommendationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str = Field(min_length=10, max_length=500)
    recommendations: list[EvidenceRecommendation] = Field(min_length=1, max_length=5)


def _fallback(best: dict, llm_status: str = "unavailable") -> dict:
    return {
        "status": "fallback",
        "provider": None,
        "llm_status": llm_status,
        "fallback_flag": True,
        "label": "Rule-based plan (AI unavailable)",
        "summary": (
            "Use the scenario comparison as a discussion aid. Validate the supplied "
            "activity and factor assumptions before making campus decisions."
        ),
        "best_scenario": best,
        "recommendations": [
            {
                "priority": 1,
                "title": "Review the highest-performing illustrative scenario",
                "why_it_may_help": (
                    "The deterministic comparison identifies this option as lowest "
                    "under the assumptions submitted for this demo."
                ),
                "practical_tradeoffs": (
                    "The result is a simulation, not a measured or guaranteed outcome; "
                    "confirm feasibility and assumptions with campus stakeholders."
                ),
                "related_scenario": best["id"],
            },
            {
                "priority": 2,
                "title": "Collect representative commute evidence",
                "why_it_may_help": (
                    "Surveys or repeated observations can test whether the assumed "
                    "daily activity and distances resemble actual campus travel."
                ),
                "practical_tradeoffs": (
                    "Collection takes time and should use privacy-preserving aggregate data."
                ),
                "related_scenario": "carpool",
            },
        ],
    }


def _contains_untrusted_claims(draft: RecommendationDraft, computed_best: dict) -> bool:
    if draft.best_scenario != computed_best["id"]:
        return True
    prose = [draft.summary]
    for item in draft.recommendations:
        prose.extend(
            [
                item.title,
                item.why_it_may_help,
                item.practical_tradeoffs,
            ]
        )
    # Narrative must not invent numeric savings or source citations.
    forbidden_claim_markers = re.compile(
        r"\d|https?://|doi:|\bcitations?\b|\breferences?\b|\baccording to\b|"
        r"\bstudies?\b|\bresearch\b|\bproven\b|\bguaranteed?\b",
        re.IGNORECASE,
    )
    return any(forbidden_claim_markers.search(text) for text in prose)


def generate_recommendations(analysis: dict) -> dict:
    """Call an optional OpenAI-compatible provider; always fall back safely."""
    provider = os.getenv("CARBOSYNC_LLM_PROVIDER", "").strip().lower()
    api_key = os.getenv("CARBOSYNC_LLM_API_KEY", "").strip()
    base_url = os.getenv("CARBOSYNC_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("CARBOSYNC_LLM_MODEL", "gpt-4o-mini").strip()
    computed_best = analysis["best_scenario"]
    if not provider or not api_key:
        return _fallback(computed_best, "credentials_not_configured")
    if provider != "openai_compatible":
        return _fallback(computed_best, "unsupported_provider")
    if not model or not base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        return _fallback(computed_best, "provider_configuration_invalid")

    context = {
        "baseline": analysis["baseline"],
        "scenarios": [
            {
                "id": scenario["id"],
                "name": scenario["name"],
                "estimated_emissions": scenario["estimated_emissions"],
                "change_vs_baseline_tonnes": scenario["change_vs_baseline_tonnes"],
                "percentage_reduction_vs_baseline": scenario[
                    "percentage_reduction_vs_baseline"
                ],
                "assumptions": scenario["assumptions"],
                "limitations": scenario["limitations"],
            }
            for scenario in analysis["scenarios"]
        ],
        "assumptions": analysis["baseline_assumptions"],
        "limitations": analysis["limitations"],
        "computed_best_scenario": computed_best,
    }
    system_prompt = (
        "Provide concise campus transportation actions as JSON with fields summary, "
        "recommendations, best_scenario. Each recommendation requires priority, title, "
        "why_it_may_help, practical_tradeoffs, related_scenario. Use scenario IDs "
        "carpool, campus_shuttle, active_travel. Select best_scenario exactly from "
        "the supplied computed result. Explain qualitative tradeoffs. Do not calculate "
        "or restate emissions, invent savings, numbers, citations, factors, or source "
        "claims. All results are illustrative, unapproved estimates."
    )
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, allow_nan=False)},
        ],
    }
    req = Request(
        base_url + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            response_data = json.loads(response.read(1_000_000))
        content = response_data["choices"][0]["message"]["content"]
        draft = RecommendationDraft.model_validate_json(content)
        if _contains_untrusted_claims(draft, computed_best):
            return _fallback(computed_best, "response_rejected")
        return {
            "status": "llm",
            "provider": provider,
            "llm_status": "available",
            "fallback_flag": False,
            "label": "AI-assisted qualitative recommendations; estimates remain deterministic",
            **draft.model_dump(exclude={"best_scenario"}),
            "best_scenario": computed_best,
            "summary": (
                f"Under the submitted illustrative assumptions, {computed_best['name']} "
                "has the lowest modeled tailpipe estimate. This is not a verified forecast."
            ),
        }
    except (URLError, TimeoutError, OSError):
        return _fallback(computed_best, "provider_unavailable")
    except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError):
        return _fallback(computed_best, "invalid_provider_response")
    except Exception:
        # Provider libraries and response objects are outside our trust boundary.
        return _fallback(computed_best, "provider_error")


def generate_evidence_recommendations(evidence: dict) -> dict:
    """Recommend actions from aggregate, privacy-preserving demo evidence only."""
    provider = os.getenv("CARBOSYNC_LLM_PROVIDER", "").strip().lower()
    api_key = os.getenv("CARBOSYNC_LLM_API_KEY", "").strip()
    base_url = os.getenv("CARBOSYNC_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("CARBOSYNC_LLM_MODEL", "gpt-4o-mini").strip()
    modes = evidence.get("student_mode_counts", {})
    vehicle_counts = evidence.get("daily_mean_vehicle_counts", {})
    most_common_mode = max(modes, key=modes.get) if modes else None
    dominant_vehicle = max(vehicle_counts, key=vehicle_counts.get) if vehicle_counts else None
    fallback = {
        "status": "fallback",
        "provider": None,
        "llm_status": "credentials_not_configured",
        "fallback_flag": True,
        "label": "Rule-based recommendations (LLM unavailable)",
        "summary": "Recommendations are based on the saved aggregate demo data; no emissions savings are calculated here.",
        "recommendations": [
            {
                "priority": 1,
                "action": "Extend parking observations across additional campaign days",
                "relevance": f"The campaign currently contains {evidence.get('observed_days', 0)} observed days; more sessions can clarify day-to-day variation.",
                "assumptions": "Each uploaded image is one point-in-time snapshot; same-day images are kept separate.",
                "constraints": "Do not interpret a parking snapshot as daily trips or unique commuters.",
                "estimated_reduction": "Not calculated from current data",
            },
            {
                "priority": 2,
                "action": "Review commute options for the most represented travel group",
                "relevance": f"{most_common_mode or 'No student mode'} is currently the most represented saved commute mode.",
                "assumptions": "Student records and distances are user provided.",
                "constraints": "Validate routes, access, capacity, and costs before selecting an intervention.",
                "estimated_reduction": "Not calculated from current data",
            },
        ],
    }
    if not provider or not api_key:
        return fallback
    if provider != "openai_compatible" or not model or not base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        return {**fallback, "llm_status": "provider_configuration_invalid"}
    system_prompt = (
        "Recommend practical campus commute interventions using only supplied aggregate evidence. "
        "Return JSON with summary and recommendations. Each recommendation must include priority, action, "
        "relevance, assumptions, constraints, and estimated_reduction set exactly to 'Not calculated from current data'. "
        "Do not invent or estimate counts, emissions, savings, costs, routes, citations, or measured outcomes. "
        "Do not ask for or infer personal identities or addresses. Do not include numeric characters in prose."
    )
    request = Request(
        base_url + "/chat/completions",
        data=json.dumps({
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(evidence, allow_nan=False)},
            ],
        }).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            response_data = json.loads(response.read(1_000_000))
        draft = EvidenceRecommendationDraft.model_validate_json(
            response_data["choices"][0]["message"]["content"]
        )
        draft_json = draft.model_dump(mode="json")
        prose = " ".join(
            [draft.summary]
            + [
                f"{item.action} {item.relevance} {item.assumptions} {item.constraints}"
                for item in draft.recommendations
            ]
        )
        if re.search(r"\d|https?://|doi:|according to|studies|research|proven|guaranteed", prose, re.I):
            return {**fallback, "llm_status": "response_rejected"}
        return {
            "status": "llm",
            "provider": provider,
            "llm_status": "available",
            "fallback_flag": False,
            "label": "AI-assisted qualitative recommendations; no savings estimated",
            **draft_json,
        }
    except (URLError, TimeoutError, OSError):
        return {**fallback, "llm_status": "provider_unavailable"}
    except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError):
        return {**fallback, "llm_status": "invalid_provider_response"}
    except Exception:
        return {**fallback, "llm_status": "provider_error"}
