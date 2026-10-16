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
        raise ValueError(f"{DATABASE_PATH_ENV} must not be empty")
    return Path(raw_path).expanduser().resolve()


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
