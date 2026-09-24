import pandas as pd
import pytest

from flightops.extract.aircraft_registry import (
    REQUIRED_COLUMNS,
    load_aircraft_db,
    profile_aircraft,
)


@pytest.fixture
def sample_csv(tmp_path):
    df = pd.DataFrame(
        {
            "icao24": ["896184", "8963E9"],  # mixed case on purpose
            "registration": ["A6-EOA", "A6-EOB"],
            "manufacturericao": ["AIRBUS", "AIRBUS"],
            "manufacturername": ["Airbus", "Airbus"],
            "model": ["A380-861", "A380-861"],
            "typecode": ["A388", "A388"],
            "operator": ["Emirates", "Emirates"],
            "operatoricao": ["UAE", "UAE"],
            "built": ["2015-01-01", "2016-01-01"],
            "engines": ["4 Engine Jet", "4 Engine Jet"],
        }
    )
    path = tmp_path / "aircraftDatabase.csv"
    df.to_csv(path, index=False)
    return path


def test_load_aircraft_db_lowercases_icao24(sample_csv):
    df = load_aircraft_db(sample_csv)
    assert list(df.columns) == REQUIRED_COLUMNS
    assert set(df["icao24"]) == {"896184", "8963e9"}


def test_load_aircraft_db_raises_on_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"icao24": ["896184"]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing expected columns"):
        load_aircraft_db(path)


def test_profile_matches_known_icao24s(sample_csv):
    df = load_aircraft_db(sample_csv)
    profile = profile_aircraft(df, sample_icao24=["896184", "8963e9", "ffffff"])
    assert profile["sample_size"] == 3
    assert profile["sample_matched"] == 2
    assert profile["sample_match_rate"] == pytest.approx(0.667, abs=0.01)
    assert profile["matched_operators"] == ["Emirates"]


def test_profile_handles_empty_sample(sample_csv):
    df = load_aircraft_db(sample_csv)
    profile = profile_aircraft(df, sample_icao24=[])
    assert profile["sample_match_rate"] is None