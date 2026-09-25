import json

import pandas as pd
import pytest
from sqlalchemy import text

from flightops.config import load_settings
from flightops.db import get_engine
from flightops.init_db import apply_sql_files, list_sql_files
from flightops.load.raw_loader import (
    finish_pipeline_run,
    insert_opensky_flights,
    is_partition_loaded,
    record_ingestion,
    replace_aircraft_registry,
    replace_airports,
    start_pipeline_run,
)


@pytest.fixture(scope="module")
def engine():
    eng = get_engine(load_settings())
    apply_sql_files(eng, list_sql_files())
    yield eng
    eng.dispose()


@pytest.mark.integration
def test_pipeline_run_lifecycle(engine):
    run_id = start_pipeline_run(engine)
    finish_pipeline_run(engine, run_id, "succeeded", rows_extracted=10, rows_loaded=10)
    with engine.connect() as conn:
        status, rows = conn.execute(
            text("SELECT status, rows_loaded FROM ops.pipeline_run WHERE run_id = :id"),
            {"id": run_id},
        ).one()
    assert (status, rows) == ("succeeded", 10)


@pytest.mark.integration
def test_ingestion_log_dedupes_on_source_and_partition(engine):
    run_id = start_pipeline_run(engine)
    key = "OMDB|departure|2099-01-01"  # far-future date avoids clashing with real data
    record_ingestion(engine, "opensky_flights", key, 5, 200, 3970, run_id)
    assert is_partition_loaded(engine, "opensky_flights", key) is True
    record_ingestion(engine, "opensky_flights", key, 7, 200, 3940, run_id)  # update, not duplicate
    with engine.connect() as conn:
        count, row_count = conn.execute(
            text(
                "SELECT count(*), max(row_count) FROM ops.ingestion_log "
                "WHERE source_name = 'opensky_flights' AND partition_key = :k"
            ),
            {"k": key},
        ).one()
    assert (count, row_count) == (1, 7)


@pytest.mark.integration
def test_insert_opensky_flights_round_trips_jsonb(engine):
    run_id = start_pipeline_run(engine)
    rows = [{"icao24": "896184", "callsign": "UAE384  ", "estArrivalAirport": None}]
    count = insert_opensky_flights(engine, rows, "OMDB", "departure", "2099-01-02", run_id)
    assert count == 1
    with engine.connect() as conn:
        payload = conn.execute(
            text(
                "SELECT payload FROM raw.opensky_flights "
                "WHERE query_date = '2099-01-02' ORDER BY raw_id DESC LIMIT 1"
            )
        ).scalar_one()
    stored = payload if isinstance(payload, dict) else json.loads(payload)
    assert stored["icao24"] == "896184"


@pytest.mark.integration
def test_insert_opensky_flights_handles_empty_list(engine):
    run_id = start_pipeline_run(engine)
    assert insert_opensky_flights(engine, [], "OMDB", "arrival", "2099-01-03", run_id) == 0


@pytest.mark.integration
def test_replace_aircraft_registry_truncates_before_reload(engine):
    run_id = start_pipeline_run(engine)
    df = pd.DataFrame(
        [{"icao24": "896184", "registration": "A6-EEE", "manufacturericao": "AIRBUS",
          "manufacturername": "Airbus", "model": "A380 861", "typecode": "A388",
          "operator": None, "operatoricao": "UAE", "built": None, "engines": None}]
    )
    count = replace_aircraft_registry(engine, df, run_id)
    assert count == 1
    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM raw.aircraft_registry")).scalar_one()
    assert total == 1  # proves the prior TRUNCATE ran, not just an append


@pytest.mark.integration
def test_replace_airports_truncates_before_reload(engine):
    run_id = start_pipeline_run(engine)
    df = pd.DataFrame(
        [{"ident": "OMDB", "type": "large_airport", "name": "Dubai International Airport",
          "latitude_deg": 25.25, "longitude_deg": 55.37, "iso_country": "AE",
          "municipality": "Dubai", "icao_code": "OMDB", "iata_code": "DXB"}]
    )
    count = replace_airports(engine, df, run_id)
    assert count == 1
    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM raw.airports")).scalar_one()
    assert total == 1