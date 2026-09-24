import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from flightops.config import load_settings
from flightops.db import get_engine
from flightops.init_db import apply_sql_files, list_sql_files, list_tables

EXPECTED_TABLES = {
    ("ops", "pipeline_run"),
    ("ops", "ingestion_log"),
    ("ops", "dq_check_result"),
    ("raw", "opensky_flights"),
    ("raw", "aircraft_registry"),
    ("raw", "airports"),
    ("core", "dim_date"),
    ("core", "dim_airport"),
    ("core", "dim_aircraft"),
    ("core", "dim_route"),
    ("core", "fact_flight"),
}


@pytest.fixture(scope="module")
def engine():
    eng = get_engine(load_settings())
    apply_sql_files(eng, list_sql_files())
    yield eng
    eng.dispose()


def _count(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


@pytest.mark.integration
def test_expected_tables_exist(engine):
    assert EXPECTED_TABLES <= set(list_tables(engine))


@pytest.mark.integration
def test_applying_twice_is_idempotent(engine):
    tables = ["core.dim_date", "core.dim_airport", "core.dim_route"]
    before = [_count(engine, t) for t in tables]
    apply_sql_files(engine, list_sql_files())
    assert [_count(engine, t) for t in tables] == before


@pytest.mark.integration
def test_dim_date_covers_all_of_2026(engine):
    assert _count(engine, "core.dim_date") == 365
    with engine.connect() as conn:
        low, high = conn.execute(
            text("SELECT min(date_key), max(date_key) FROM core.dim_date")
        ).one()
    assert (low, high) == (20260101, 20261231)


@pytest.mark.integration
def test_unknown_members_exist(engine):
    with engine.connect() as conn:
        airport = conn.execute(
            text("SELECT icao_code FROM core.dim_airport WHERE airport_key = -1")
        ).scalar_one()
        route = conn.execute(
            text("SELECT route_label FROM core.dim_route WHERE route_key = -1")
        ).scalar_one()
    assert airport == "UNKNOWN"
    assert route == "Unknown route"


@pytest.mark.integration
def test_fact_flight_rejects_orphan_foreign_keys(engine):
    insert = text(
        "INSERT INTO core.fact_flight (icao24, first_seen_utc, last_seen_utc, date_key, "
        "aircraft_key, origin_airport_key, destination_airport_key, route_key, callsign, "
        "observed_duration_min, first_seen_hour_gst, is_origin_known, is_destination_known, "
        "is_same_origin_destination) "
        "VALUES ('zzzzzz', now(), now(), 99999999, 99999999, 99999999, 99999999, 99999999, "
        "'TEST', 0, 0, TRUE, TRUE, FALSE)"
    )
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert)