"""Insert/track functions for the raw schema and ops (pipeline monitoring) tables."""

from __future__ import annotations

import json
import logging
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def start_pipeline_run(engine: Engine) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text("INSERT INTO ops.pipeline_run DEFAULT VALUES RETURNING run_id")
        ).scalar_one()


def finish_pipeline_run(
    engine: Engine,
    run_id: int,
    status: str,
    rows_extracted: int,
    rows_loaded: int,
    error_message: str | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE ops.pipeline_run SET finished_at = now(), status = :status, "
                "rows_extracted = :rows_extracted, rows_loaded = :rows_loaded, "
                "error_message = :error_message WHERE run_id = :run_id"
            ),
            {
                "status": status,
                "rows_extracted": rows_extracted,
                "rows_loaded": rows_loaded,
                "error_message": error_message,
                "run_id": run_id,
            },
        )


def is_partition_loaded(engine: Engine, source_name: str, partition_key: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT 1 FROM ops.ingestion_log "
                "WHERE source_name = :s AND partition_key = :p"
            ),
            {"s": source_name, "p": partition_key},
        ).first()
    return row is not None


def record_ingestion(
    engine: Engine,
    source_name: str,
    partition_key: str,
    row_count: int,
    http_status: int | None,
    credits_remaining: int | None,
    run_id: int,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ops.ingestion_log "
                "(source_name, partition_key, row_count, http_status, credits_remaining, run_id) "
                "VALUES (:source_name, :partition_key, :row_count, :http_status, "
                ":credits_remaining, :run_id) "
                "ON CONFLICT (source_name, partition_key) DO UPDATE SET "
                "row_count = EXCLUDED.row_count, http_status = EXCLUDED.http_status, "
                "credits_remaining = EXCLUDED.credits_remaining, run_id = EXCLUDED.run_id, "
                "loaded_at = now()"
            ),
            {
                "source_name": source_name,
                "partition_key": partition_key,
                "row_count": row_count,
                "http_status": http_status,
                "credits_remaining": credits_remaining,
                "run_id": run_id,
            },
        )


def insert_opensky_flights(
    engine: Engine,
    rows: list[dict],
    query_airport: str,
    query_direction: str,
    query_date: date,
    run_id: int,
) -> int:
    """Insert one row per flight object, storing the raw payload as JSONB."""
    if not rows:
        return 0
    with engine.begin() as conn:
        for row in rows:
            conn.execute(
                text(
                    "INSERT INTO raw.opensky_flights "
                    "(query_airport, query_direction, query_date, payload, run_id) "
                    "VALUES (:airport, :direction, :date, CAST(:payload AS JSONB), :run_id)"
                ),
                {
                    "airport": query_airport,
                    "direction": query_direction,
                    "date": query_date,
                    "payload": json.dumps(row, default=str),
                    "run_id": run_id,
                },
            )
    return len(rows)


def replace_aircraft_registry(engine: Engine, df: pd.DataFrame, run_id: int) -> int:
    """Full-refresh load: this is a reference snapshot, not partitioned data."""
    df = df.copy()
    df["run_id"] = run_id
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE raw.aircraft_registry"))
        df.to_sql("aircraft_registry", conn, schema="raw", if_exists="append", index=False)
    return len(df)


def replace_airports(engine: Engine, df: pd.DataFrame, run_id: int) -> int:
    """Full-refresh load: this is a reference snapshot, not partitioned data."""
    df = df.copy()
    df["run_id"] = run_id
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE raw.airports"))
        df.to_sql("airports", conn, schema="raw", if_exists="append", index=False)
    return len(df)