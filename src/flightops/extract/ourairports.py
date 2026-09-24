"""Download the OurAirports global airport reference (public domain, no auth).

Source: https://ourairports.com/data/ (mirrored on GitHub, updated daily).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
DEFAULT_TIMEOUT_S = 60

# Columns we actually need for dim_airport; OurAirports has more than this.
REQUIRED_COLUMNS = [
    "ident",
    "type",
    "name",
    "latitude_deg",
    "longitude_deg",
    "iso_country",
    "municipality",
    "icao_code",
    "iata_code",
]


def download_airports(dest_path: Path, timeout: int = DEFAULT_TIMEOUT_S) -> Path:
    """Download the raw airports.csv to dest_path. Returns the path written."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading OurAirports data from %s", AIRPORTS_URL)
    resp = requests.get(AIRPORTS_URL, timeout=timeout)
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)
    logger.info("Saved %s bytes to %s", len(resp.content), dest_path)
    return dest_path


def load_airports(csv_path: Path) -> pd.DataFrame:
    """Load a previously-downloaded airports.csv and keep only the columns we need."""
    df = pd.read_csv(csv_path, low_memory=False)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"airports.csv is missing expected columns: {missing}. "
            "OurAirports may have changed its schema."
        )
    return df[REQUIRED_COLUMNS].copy()


def profile_airports(df: pd.DataFrame) -> dict:
    """Small profile used by the verification script and tests."""
    omdb = df[df["icao_code"] == "OMDB"]
    return {
        "total_rows": len(df),
        "distinct_countries": int(df["iso_country"].nunique()),
        "rows_missing_coordinates": int(
            df["latitude_deg"].isna().sum() + df["longitude_deg"].isna().sum()
        ),
        "omdb_found": not omdb.empty,
        "omdb_row": omdb.iloc[0].to_dict() if not omdb.empty else None,
    }