from datetime import UTC, datetime

from flightops.extract.probe import day_window, summarise


def test_day_window_covers_one_whole_utc_day():
    now = datetime(2026, 9, 25, 12, 30, tzinfo=UTC)
    begin, end = day_window(1, now=now)
    assert datetime.fromtimestamp(begin, UTC) == datetime(
        2026, 9, 24, 0, 0, tzinfo=UTC
    )
    assert end - begin == 86399


def test_summarise_counts_only_emirates_callsigns():
    rows = [
        {"icao24": "a", "callsign": "UAE201  ", "estDepartureAirport": "OMDB",
         "estArrivalAirport": None},
        {"icao24": "b", "callsign": "BAW107", "estDepartureAirport": "OMDB",
         "estArrivalAirport": "EGLL"},
    ]
    s = summarise(rows)
    assert s["total_rows"] == 2
    assert s["emirates_rows"] == 1
    assert s["missing_arrival_airport_share"] == 1.0


def test_summarise_handles_empty_response():
    assert summarise([])["emirates_rows"] == 0