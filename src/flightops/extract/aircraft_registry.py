"""Download OpenSky's aircraft metadata database (public, no auth, no credits).

This replaces national aircraft registries (e.g. the FAA's, which only covers
US-registered N-number aircraft) because it is keyed on icao24 and covers any
aircraft OpenSky has seen, regardless of country of registration.
Source: https://opensky-network.org/data (aircraft database CSV export).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

AIRCRAFT_DB_URL = "https://s3.opensky-network.org/data-samples/metadata/aircraftDatabase.csv"
DEFAULT_TIMEOUT_S = 120  # this file is larger than airports.csv

REQUIRED_COLUMNS = [
    "icao24",
    "registration",
    "manufacturericao",
    "manufacturername",
    "model",
    "typecode",
    "operator",
    "operatoricao",
    "built",
    "engines",
]


def download_aircraft_db(dest_path: Path, timeout: int = DEFAULT_TIMEOUT_S) -> Path:
    """Download the raw aircraft database CSV to dest_path. Returns the path written."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading OpenSky aircraft database from %s", AIRCRAFT_DB_URL)
    resp = requests.get(AIRCRAFT_DB_URL, timeout=timeout)
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)
    logger.info("Saved %s bytes to %s", len(resp.content), dest_path)
    return dest_path


def load_aircraft_db(csv_path: Path) -> pd.DataFrame:
    """Load a previously-downloaded aircraft database CSV, keeping needed columns."""
    df = pd.read_csv(csv_path, low_memory=False, dtype={"icao24": str})
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"aircraftDatabase.csv is missing expected columns: {missing}. "
            "OpenSky may have changed its schema."
        )
    df["icao24"] = df["icao24"].str.lower().str.strip()
    return df[REQUIRED_COLUMNS].copy()


def profile_aircraft(df: pd.DataFrame, sample_icao24: list[str]) -> dict:
    """Small profile: overall size plus a match-rate check against real icao24s we saw."""
    sample = {code.lower() for code in sample_icao24}
    matched = df[df["icao24"].isin(sample)]
    return {
        "total_rows": len(df),
        "sample_size": len(sample),
        "sample_matched": len(matched),
        "sample_match_rate": round(len(matched) / len(sample), 3) if sample else None,
        "matched_operators": sorted(matched["operator"].dropna().unique().tolist())[:5],
    }