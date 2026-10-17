"""Small SQLite persistence layer for assessments and commute calculations."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterator


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "carbosync.db"
DATABASE_PATH_ENV = "CARBOSYNC_DATABASE_PATH"


def get_database_path() -> Path:
    """Return the configured SQLite path or the local development default."""
    raw_path = os.getenv(DATABASE_PATH_ENV)
    if raw_path is None:
        return DEFAULT_DATABASE_PATH
    if not raw_path.strip():
        raise ValueError(f"{DATABASE_PATH_ENV} must not be empty; set it to a writable SQLite file path")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = DEFAULT_DATABASE_PATH.parent / path
    return path.resolve()


@contextmanager
def database_connection() -> Iterator[sqlite3.Connection]:
    """Open an isolated connection, initialize schema, and always close it."""
    path = get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        initialize_schema(connection)
        yield connection
    finally:
        connection.close()


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Create B2 tables and the additive demo-analysis snapshot table."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS assessments (
            assessment_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS commute_calculations (
            calculation_id TEXT PRIMARY KEY,
            assessment_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            inputs_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_commute_calculations_assessment
        ON commute_calculations (assessment_id, created_at, calculation_id)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS demo_analyses (
            analysis_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            detections_json TEXT NOT NULL,
            assumptions_json TEXT NOT NULL,
            result_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS demo_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS demo_students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            residential_address TEXT NOT NULL,
            one_way_distance_km REAL NOT NULL,
            travel_mode TEXT NOT NULL,
            vehicle_type TEXT,
            fuel_type TEXT,
            commute_days_per_week REAL NOT NULL,
            occupancy REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS observation_campaigns (
            campaign_id TEXT PRIMARY KEY,
            start_date TEXT NOT NULL,
            duration_days INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS parking_observations (
            observation_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            observation_date TEXT NOT NULL,
            analysis_id TEXT NOT NULL,
            image_sha256 TEXT NOT NULL,
            counts_json TEXT NOT NULL,
            model_metadata_json TEXT NOT NULL,
            inference_status TEXT NOT NULL,
            corrected INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE (campaign_id, image_sha256),
            FOREIGN KEY (campaign_id) REFERENCES observation_campaigns (campaign_id)
                ON DELETE CASCADE,
            FOREIGN KEY (analysis_id) REFERENCES demo_analyses (analysis_id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_observations_campaign_date "
        "ON parking_observations (campaign_id, observation_date, created_at)"
    )
    observation_columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(parking_observations)")
    }
    if "human_reviewed" not in observation_columns:
        connection.execute(
            "ALTER TABLE parking_observations ADD COLUMN human_reviewed INTEGER"
        )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS demo_scenarios (
             scenario_run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
             inputs_json TEXT NOT NULL, result_json TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS demo_recommendations (
             recommendation_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
             result_json TEXT NOT NULL
           )"""
    )


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def encode_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"))


def create_assessment(assessment_id: str, created_at: str) -> None:
    with database_connection() as connection:
        with connection:
            connection.execute(
                "INSERT INTO assessments (assessment_id, created_at) VALUES (?, ?)",
                (assessment_id, created_at),
            )


def get_assessment(assessment_id: str) -> dict[str, object] | None:
    with database_connection() as connection:
        assessment = connection.execute(
            "SELECT assessment_id, created_at FROM assessments WHERE assessment_id = ?",
            (assessment_id,),
        ).fetchone()
        if assessment is None:
            return None

        rows = connection.execute(
            """
            SELECT calculation_id, created_at, inputs_json, result_json
            FROM commute_calculations
            WHERE assessment_id = ?
            ORDER BY created_at, calculation_id
            """,
            (assessment_id,),
        ).fetchall()

    calculations: list[dict[str, object]] = []
    for row in rows:
        inputs = json.loads(row["inputs_json"])
        result = json.loads(row["result_json"])
        if isinstance(result, dict) and "b3_metadata" not in result:
            # Response-layer compatibility only: never rewrite the stored B2
            # JSON or infer historical provenance, approval, or method version.
            result["b3_metadata"] = {
                "availability": "unavailable_legacy_b2",
                "activity_provenance": "unavailable",
                "factor_governance": "unavailable",
                "calculation_method_version": None,
            }
        calculations.append(
            {
                "calculation_id": row["calculation_id"],
                "created_at": row["created_at"],
                "inputs": inputs,
                "result": result,
            }
        )

    return {
        "assessment_id": assessment["assessment_id"],
        "created_at": assessment["created_at"],
        "commute_calculations": calculations,
    }


def save_commute_calculation(
    *,
    calculation_id: str,
    assessment_id: str,
    created_at: str,
    inputs: dict[str, object],
    result: dict[str, object],
) -> bool:
    """Atomically save one calculation; return False when its assessment is absent."""
    inputs_json = encode_json(inputs)
    result_json = encode_json(result)
    with database_connection() as connection:
        with connection:
            assessment = connection.execute(
                "SELECT 1 FROM assessments WHERE assessment_id = ?",
                (assessment_id,),
            ).fetchone()
            if assessment is None:
                return False
            connection.execute(
                """
                INSERT INTO commute_calculations
                    (calculation_id, assessment_id, created_at, inputs_json, result_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    calculation_id,
                    assessment_id,
                    created_at,
                    inputs_json,
                    result_json,
                ),
            )
    return True


def save_demo_analysis(
    *,
    analysis_id: str,
    created_at: str,
    detections: dict[str, object],
    assumptions: dict[str, object],
    result: dict[str, object],
) -> None:
    """Persist only structured counts, assumptions, and results, never images/secrets."""
    payloads = (
        encode_json(detections),
        encode_json(assumptions),
        encode_json(result),
    )
    with database_connection() as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO demo_analyses
                    (analysis_id, created_at, detections_json, assumptions_json, result_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (analysis_id, created_at, *payloads),
            )


def get_demo_analysis(analysis_id: str) -> dict[str, object] | None:
    with database_connection() as connection:
        row = connection.execute(
            """
            SELECT analysis_id, created_at, detections_json, assumptions_json, result_json
            FROM demo_analyses WHERE analysis_id = ?
            """,
            (analysis_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "analysis_id": row["analysis_id"],
        "created_at": row["created_at"],
        "detections": json.loads(row["detections_json"]),
        "assumptions": json.loads(row["assumptions_json"]),
        "result": json.loads(row["result_json"]),
    }


def set_campus_address(address: str, updated_at: str) -> None:
    with database_connection() as connection:
        with connection:
            connection.execute(
                """INSERT INTO demo_settings (setting_key, setting_value, updated_at)
                   VALUES ('campus_address', ?, ?)
                   ON CONFLICT(setting_key) DO UPDATE SET
                     setting_value=excluded.setting_value, updated_at=excluded.updated_at""",
                (address, updated_at),
            )


def get_campus_address() -> str:
    with database_connection() as connection:
        row = connection.execute(
            "SELECT setting_value FROM demo_settings WHERE setting_key='campus_address'"
        ).fetchone()
    return str(row["setting_value"]) if row else ""


def replace_demo_students(students: list[dict[str, object]], updated_at: str) -> None:
    with database_connection() as connection:
        with connection:
            connection.execute("DELETE FROM demo_students")
            connection.executemany(
                """INSERT INTO demo_students
                   (student_id, name, residential_address, one_way_distance_km,
                    travel_mode, vehicle_type, fuel_type, commute_days_per_week,
                    occupancy, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        row["student_id"], row["name"], row["residential_address"],
                        row["one_way_distance_km"], row["travel_mode"],
                        row.get("vehicle_type"), row.get("fuel_type"),
                        row["commute_days_per_week"], row["occupancy"], updated_at,
                    )
                    for row in students
                ],
            )


def get_demo_students() -> list[dict[str, object]]:
    with database_connection() as connection:
        rows = connection.execute(
            """SELECT student_id, name, residential_address, one_way_distance_km,
                      travel_mode, vehicle_type, fuel_type, commute_days_per_week,
                      occupancy, updated_at
               FROM demo_students ORDER BY student_id"""
        ).fetchall()
    return [dict(row) for row in rows]


def create_observation_campaign(
    campaign_id: str, start_date: str, duration_days: int, created_at: str
) -> None:
    with database_connection() as connection:
        with connection:
            connection.execute("UPDATE observation_campaigns SET is_active=0")
            connection.execute(
                """INSERT INTO observation_campaigns
                   (campaign_id, start_date, duration_days, created_at, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                (campaign_id, start_date, duration_days, created_at),
            )


def get_current_observation_campaign() -> dict[str, object] | None:
    with database_connection() as connection:
        row = connection.execute(
            """SELECT campaign_id, start_date, duration_days, created_at, is_active
               FROM observation_campaigns WHERE is_active=1
               ORDER BY created_at DESC LIMIT 1"""
        ).fetchone()
    return dict(row) if row else None


def get_observation_campaign(campaign_id: str) -> dict[str, object] | None:
    with database_connection() as connection:
        row = connection.execute(
            """SELECT campaign_id, start_date, duration_days, created_at, is_active
               FROM observation_campaigns WHERE campaign_id=?""",
            (campaign_id,),
        ).fetchone()
    return dict(row) if row else None


def save_parking_observation(
    *, observation_id: str, campaign_id: str, observation_date: str,
    analysis_id: str, image_sha256: str, counts: dict[str, int],
    model_metadata: dict[str, object], inference_status: str,
    corrected: bool, created_at: str, human_reviewed: bool = False,
) -> bool:
    with database_connection() as connection:
        with connection:
            existing = connection.execute(
                "SELECT 1 FROM parking_observations WHERE campaign_id=? AND image_sha256=?",
                (campaign_id, image_sha256),
            ).fetchone()
            if existing:
                return False
            connection.execute(
                """INSERT INTO parking_observations
                   (observation_id, campaign_id, observation_date, analysis_id,
                    image_sha256, counts_json, model_metadata_json, inference_status,
                    corrected, created_at, human_reviewed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (observation_id, campaign_id, observation_date, analysis_id,
                 image_sha256, encode_json(counts), encode_json(model_metadata),
                 inference_status, int(corrected), created_at, int(human_reviewed)),
            )
    return True


def get_parking_observations(campaign_id: str) -> list[dict[str, object]]:
    with database_connection() as connection:
        rows = connection.execute(
            """SELECT observation_id, campaign_id, observation_date, analysis_id,
                      image_sha256, counts_json, model_metadata_json, inference_status,
                      corrected, created_at, human_reviewed FROM parking_observations
               WHERE campaign_id=? ORDER BY observation_date, created_at""",
            (campaign_id,),
        ).fetchall()
    return [
        {
            **{key: row[key] for key in (
                "observation_id", "campaign_id", "observation_date", "analysis_id",
                "image_sha256", "inference_status", "corrected", "created_at",
            )},
            "human_reviewed": (
                None if row["human_reviewed"] is None else bool(row["human_reviewed"])
            ),
            "counts": json.loads(row["counts_json"]),
            "model_metadata": json.loads(row["model_metadata_json"]),
        }
        for row in rows
    ]


def has_parking_image(campaign_id: str, image_sha256: str) -> bool:
    with database_connection() as connection:
        return connection.execute(
            "SELECT 1 FROM parking_observations WHERE campaign_id=? AND image_sha256=?",
            (campaign_id, image_sha256),
        ).fetchone() is not None


def save_demo_scenario(run_id: str, created_at: str, inputs: dict[str, object], result: dict[str, object]) -> None:
    with database_connection() as connection:
        with connection:
            connection.execute(
                "INSERT INTO demo_scenarios VALUES (?, ?, ?, ?)",
                (run_id, created_at, encode_json(inputs), encode_json(result)),
            )


def get_latest_demo_scenario() -> dict[str, object] | None:
    with database_connection() as connection:
        row = connection.execute(
            "SELECT scenario_run_id, created_at, inputs_json, result_json FROM demo_scenarios ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {
        "scenario_run_id": row["scenario_run_id"],
        "created_at": row["created_at"],
        "inputs": json.loads(row["inputs_json"]),
        "result": json.loads(row["result_json"]),
    }


def save_demo_recommendations(recommendation_id: str, created_at: str, result: dict[str, object]) -> None:
    with database_connection() as connection:
        with connection:
            connection.execute(
                "INSERT INTO demo_recommendations VALUES (?, ?, ?)",
                (recommendation_id, created_at, encode_json(result)),
            )


def get_latest_demo_recommendations() -> dict[str, object] | None:
    with database_connection() as connection:
        row = connection.execute(
            "SELECT recommendation_id, created_at, result_json FROM demo_recommendations ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {
        "recommendation_id": row["recommendation_id"],
        "created_at": row["created_at"],
        **json.loads(row["result_json"]),
    }
