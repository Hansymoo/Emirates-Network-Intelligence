"""One-off loader: download and load the aircraft registry and OurAirports CSVs.

Usage:
    python -m flightops.extract.load_reference_data
"""

from __future__ import annotations

import logging
import sys

from flightops.config import ConfigError, load_settings
from flightops.db import get_engine
from flightops.extract.aircraft_registry import download_aircraft_db, load_aircraft_db
from flightops.extract.ourairports import download_airports, load_airports
from flightops.load.raw_loader import (
    finish_pipeline_run,
    replace_aircraft_registry,
    replace_airports,
    start_pipeline_run,
)
from flightops.logging_setup import setup_logging

log = logging.getLogger("flightops.load_reference_data")


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    setup_logging(settings.log_level, settings.log_dir)
    engine = get_engine(settings)
    run_id = start_pipeline_run(engine)

    try:
        aircraft_path = download_aircraft_db(settings.data_dir / "raw" / "aircraftDatabase.csv")
        aircraft_df = load_aircraft_db(aircraft_path)
        aircraft_count = replace_aircraft_registry(engine, aircraft_df, run_id)
        log.info("Loaded %s aircraft registry rows", aircraft_count)

        airports_path = download_airports(settings.data_dir / "raw" / "airports.csv")
        airports_df = load_airports(airports_path)
        airports_count = replace_airports(engine, airports_df, run_id)
        log.info("Loaded %s airport rows", airports_count)
    except Exception as exc:
        finish_pipeline_run(engine, run_id, "failed", 0, 0, str(exc))
        engine.dispose()
        raise

    total = aircraft_count + airports_count
    finish_pipeline_run(engine, run_id, "succeeded", total, total)
    engine.dispose()
    log.info("Reference data load complete: %s total rows", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())