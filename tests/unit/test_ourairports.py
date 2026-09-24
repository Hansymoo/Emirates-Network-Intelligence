import pandas as pd
import pytest

from flightops.extract.ourairports import REQUIRED_COLUMNS, load_airports, profile_airports


@pytest.fixture
def sample_csv(tmp_path):
    df = pd.DataFrame(
        {
            "ident": ["OMDB", "EGLL"],
            "type": ["large_airport", "large_airport"],
            "name": ["Dubai International Airport", "London Heathrow Airport"],
            "latitude_deg": [25.2528, 51.4706],
            "longitude_deg": [55.3644, -0.4619],
            "iso_country": ["AE", "GB"],
            "municipality": ["Dubai", "London"],
            "icao_code": ["OMDB", "EGLL"],
            "iata_code": ["DXB", "LHR"],
            "extra_column_we_dont_need": ["x", "y"],
        }
    )
    path = tmp_path / "airports.csv"
    df.to_csv(path, index=False)
    return path


def test_load_airports_keeps_only_required_columns(sample_csv):
    df = load_airports(sample_csv)
    assert list(df.columns) == REQUIRED_COLUMNS
    assert len(df) == 2


def test_load_airports_raises_on_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"ident": ["OMDB"]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing expected columns"):
        load_airports(path)


def test_profile_finds_omdb(sample_csv):
    df = load_airports(sample_csv)
    profile = profile_airports(df)
    assert profile["total_rows"] == 2
    assert profile["omdb_found"] is True
    assert profile["omdb_row"]["name"] == "Dubai International Airport"


def test_profile_reports_no_omdb_when_absent(sample_csv):
    df = load_airports(sample_csv)
    df = df[df["icao_code"] != "OMDB"]
    profile = profile_airports(df)
    assert profile["omdb_found"] is False
    assert profile["omdb_row"] is None