"""Resumable backfill of OpenSky flights for one airport over a date range.

Safe to stop and re-run at any time: ops.ingestion_log records every completed
partition (airport|direction|date), so a re-run skips finished days and continues
where the previous run's credits ran out.

Usage:
    python -m flightops.extract.backfill
    python -m flightops.extract.backfill --start 2026-03-01 --end 2026-09-24
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from flightops.config import ConfigError, load_settings
from flightops.db import get_engine
from flightops.extract.opensky_client import OpenSkyClient, OpenSkyError, OpenSkyRateLimited
from flightops.load.raw_loader import (
    finish_pipeline_run,
    insert_opensky_flights,
    is_partition_loaded,
    record_ingestion,
    start_pipeline_run,
)
from flightops.logging_setup import setup_logging

DXB_ICAO = "OMDB"
SOURCE_NAME = "opensky_flights"
CREDIT_COST_PER_CALL = 30  # confirmed empirically in Phase 2A probes
CALL_DELAY_S = 1
log = logging.getLogger("flightops.backfill")


def daterange(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end must not be before start")
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def day_window_for(day: date) -> tuple[int, int]:
    """Unix (begin, end) seconds covering one whole UTC calendar day."""
    start_dt = datetime(day.year, day.month, day.day, tzinfo=UTC)
    end_dt = start_dt + timedelta(days=1) - timedelta(seconds=1)
    return int(start_dt.timestamp()), int(end_dt.timestamp())


@dataclass
class BackfillSummary:
    partitions_attempted: int = 0
    partitions_loaded: int = 0
    partitions_skipped: int = 0
    rows_loaded: int = 0
    stopped_early: bool = False
    stop_reason: str | None = None


def run_backfill(
    client,
    dates: list[date],
    directions: list[str],
    is_loaded: Callable[[str, date], bool],
    save_response: Callable[[str, date, list, int, int | None], None],
    credit_cost: int = CREDIT_COST_PER_CALL,
    sleep_s: float = CALL_DELAY_S,
) -> BackfillSummary:
    """Pure orchestration logic. `client` only needs flights_by_airport(); this
    keeps the function unit-testable with a fake client and fake DB callables.
    """
    summary = BackfillSummary()
    last_remaining: int | None = None

    for day in dates:
        for direction in directions:
            if is_loaded(direction, day):
                summary.partitions_skipped += 1
                continue
            if last_remaining is not None and last_remaining < credit_cost:
                summary.stopped_early = True
                summary.stop_reason = (
                    f"Only {last_remaining} credits left; need {credit_cost} for the "
                    "next call. Stopping cleanly; re-run once credits refill."
                )
                return summary

            summary.partitions_attempted += 1
            begin, end = day_window_for(day)
            try:
                resp = client.flights_by_airport(direction, DXB_ICAO, begin, end)
            except OpenSkyRateLimited as exc:
                summary.stopped_early = True
                summary.stop_reason = f"Rate limited; retry after {exc.retry_after_s}s."
                return summary
            except OpenSkyError as exc:
                summary.stopped_early = True
                summary.stop_reason = f"OpenSky error: {exc}"
                return summary

            save_response(direction, day, resp.data, resp.status_code, resp.credits_remaining)
            summary.partitions_loaded += 1
            summary.rows_loaded += len(resp.data)
            last_remaining = resp.credits_remaining
            time.sleep(sleep_s)

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill OpenSky flights for OMDB.")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 3, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    parser.add_argument("--direction", choices=["departure", "arrival", "both"], default="both")
    args = parser.parse_args(argv)

    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    end = args.end or yesterday
    if end > yesterday:
        log.warning("End date %s is not yet available; clamping to %s", end, yesterday)
        end = yesterday

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if not (settings.opensky_client_id and settings.opensky_client_secret):
        print("Missing OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET in .env", file=sys.stderr)
        return 2

    setup_logging(settings.log_level, settings.log_dir)
    engine = get_engine(settings)
    client = OpenSkyClient(settings.opensky_client_id, settings.opensky_client_secret)
    directions = ["departure", "arrival"] if args.direction == "both" else [args.direction]
    dates = daterange(args.start, end)
    log.info(
        "Backfill range %s to %s (%s days), directions=%s", args.start, end, len(dates), directions
    )

    run_id = start_pipeline_run(engine)

    def is_loaded(direction: str, day: date) -> bool:
        key = f"{DXB_ICAO}|{direction}|{day.isoformat()}"
        return is_partition_loaded(engine, SOURCE_NAME, key)

    def save_response(direction, day, rows, http_status, credits_remaining):
        insert_opensky_flights(engine, rows, DXB_ICAO, direction, day, run_id)
        key = f"{DXB_ICAO}|{direction}|{day.isoformat()}"
        record_ingestion(engine, SOURCE_NAME, key, len(rows), http_status, credits_remaining, run_id)
        log.info(
            "%s %s | rows=%s | credits_remaining=%s", direction, day, len(rows), credits_remaining
        )

    try:
        summary = run_backfill(client, dates, directions, is_loaded, save_response)
    except Exception as exc:
        finish_pipeline_run(engine, run_id, "failed", 0, 0, str(exc))
        engine.dispose()
        raise

    status = "partial" if summary.stopped_early else "succeeded"
    finish_pipeline_run(engine, run_id, status, summary.rows_loaded, summary.rows_loaded)
    engine.dispose()

    log.info(
        "Backfill run finished: attempted=%s loaded=%s skipped=%s rows=%s status=%s",
        summary.partitions_attempted, summary.partitions_loaded,
        summary.partitions_skipped, summary.rows_loaded, status,
    )
    if summary.stopped_early:
        log.info("Stopped early: %s", summary.stop_reason)
        log.info("This is expected. Re-run this same command again tomorrow to continue.")
    else:
        log.info("Backfill complete: every partition in the requested range is loaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())