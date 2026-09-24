"""CLI probe: measure what a standard OpenSky account can retrieve for Dubai (OMDB).

Usage:
    python -m flightops.extract.probe
    python -m flightops.extract.probe --days-ago 30 90 180 --direction departure

Raw responses are saved under data/probe/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime, timedelta

import pandas as pd

from flightops.config import ConfigError, load_settings
from flightops.extract.opensky_client import OpenSkyClient, OpenSkyError
from flightops.logging_setup import setup_logging

DXB_ICAO = "OMDB"
EMIRATES_PREFIX = "UAE"
log = logging.getLogger("flightops.probe")


def day_window(days_ago: int, now: datetime | None = None) -> tuple[int, int]:
    """Return (begin, end) Unix seconds covering one whole UTC calendar day."""
    now = now or datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight - timedelta(days=days_ago)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return int(start.timestamp()), int(end.timestamp())


def summarise(rows: list[dict]) -> dict:
    """Profile one API response, focusing on rows with an Emirates callsign."""
    summary = {
        "total_rows": len(rows),
        "emirates_rows": 0,
        "emirates_unique_aircraft": 0,
        "missing_departure_airport_share": None,
        "missing_arrival_airport_share": None,
        "columns": [],
        "sample": [],
    }
    df = pd.DataFrame(rows)
    if df.empty or "callsign" not in df.columns:
        return summary

    summary["columns"] = list(df.columns)
    callsign = df["callsign"].fillna("").str.strip()
    emirates = df[callsign.str.startswith(EMIRATES_PREFIX)]
    summary["emirates_rows"] = len(emirates)
    if emirates.empty:
        return summary

    if "icao24" in emirates.columns:
        summary["emirates_unique_aircraft"] = int(emirates["icao24"].nunique())
    for key, col in (
        ("missing_departure_airport_share", "estDepartureAirport"),
        ("missing_arrival_airport_share", "estArrivalAirport"),
    ):
        if col in emirates.columns:
            summary[key] = round(float(emirates[col].isna().mean()), 3)
    summary["sample"] = emirates.head(3).to_dict("records")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe OpenSky access for Emirates flights.")
    parser.add_argument("--days-ago", type=int, nargs="+", default=[3])
    parser.add_argument(
        "--direction", choices=["departure", "arrival", "both"], default="both"
    )
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if not (settings.opensky_client_id and settings.opensky_client_secret):
        print(
            "Missing OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET in .env", file=sys.stderr
        )
        return 2

    setup_logging(settings.log_level, settings.log_dir)
    out_dir = settings.data_dir / "probe"
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OpenSkyClient(settings.opensky_client_id, settings.opensky_client_secret)
    directions = ["departure", "arrival"] if args.direction == "both" else [args.direction]
    previous_remaining = None

    for days_ago in args.days_ago:
        begin, end = day_window(days_ago)
        day = datetime.fromtimestamp(begin, UTC).date()
        for direction in directions:
            try:
                resp = client.flights_by_airport(direction, DXB_ICAO, begin, end)
            except OpenSkyError as exc:
                log.error("%s %s (%s days ago) failed: %s", DXB_ICAO, direction, days_ago, exc)
                return 1

            cost = None
            if previous_remaining is not None and resp.credits_remaining is not None:
                cost = previous_remaining - resp.credits_remaining
            previous_remaining = resp.credits_remaining

            (out_dir / f"{DXB_ICAO}_{direction}_{day}.json").write_text(
                json.dumps(resp.data), encoding="utf-8"
            )
            s = summarise(resp.data)
            log.info(
                "%s %s %s | HTTP %s | rows=%s emirates=%s aircraft=%s | "
                "missing dep=%s arr=%s | credits_remaining=%s cost_of_this_call=%s",
                DXB_ICAO, direction, day, resp.status_code, s["total_rows"],
                s["emirates_rows"], s["emirates_unique_aircraft"],
                s["missing_departure_airport_share"], s["missing_arrival_airport_share"],
                resp.credits_remaining, cost,
            )
            if s["columns"]:
                log.info("Columns returned: %s", s["columns"])
            if s["sample"]:
                log.info("Sample Emirates rows: %s", json.dumps(s["sample"], default=str))
            time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())