from datetime import date

import pytest

from flightops.extract.backfill import BackfillSummary, daterange, day_window_for, run_backfill
from flightops.extract.opensky_client import ApiResponse, OpenSkyError, OpenSkyRateLimited


class StubClient:
    """Duck-types OpenSkyClient.flights_by_airport; no network, no real auth."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def flights_by_airport(self, direction, airport, begin, end):
        self.calls.append((direction, airport, begin, end))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_daterange_is_inclusive():
    days = daterange(date(2026, 3, 1), date(2026, 3, 3))
    assert days == [date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)]


def test_daterange_rejects_end_before_start():
    with pytest.raises(ValueError):
        daterange(date(2026, 3, 3), date(2026, 3, 1))


def test_day_window_covers_whole_utc_day():
    begin, end = day_window_for(date(2026, 3, 1))
    assert end - begin == 86399


def _recorder():
    saved = []
    return saved, lambda direction, day, rows, status, remaining: saved.append(
        (direction, day, rows, status, remaining)
    )


def test_skips_already_loaded_partitions():
    client = StubClient([])
    saved, save = _recorder()
    summary = run_backfill(
        client, [date(2026, 3, 1)], ["departure"],
        is_loaded=lambda d, day: True, save_response=save, sleep_s=0,
    )
    assert summary.partitions_skipped == 1
    assert summary.partitions_attempted == 0
    assert saved == []


def test_loads_new_partition_and_records_it():
    client = StubClient([ApiResponse([{"callsign": "UAE1"}], 200, 3970)])
    saved, save = _recorder()
    summary = run_backfill(
        client, [date(2026, 3, 1)], ["departure"],
        is_loaded=lambda d, day: False, save_response=save, sleep_s=0,
    )
    assert summary.partitions_loaded == 1
    assert summary.rows_loaded == 1
    assert saved[0][0] == "departure"


def test_stops_before_a_call_it_cannot_afford():
    client = StubClient([ApiResponse([], 200, 20)])  # only 20 credits left after this call
    _, save = _recorder()
    summary = run_backfill(
        client, [date(2026, 3, 1), date(2026, 3, 2)], ["departure"],
        is_loaded=lambda d, day: False, save_response=save, credit_cost=30, sleep_s=0,
    )
    assert summary.partitions_loaded == 1
    assert summary.stopped_early is True
    assert "credits" in summary.stop_reason.lower()


def test_stops_cleanly_on_rate_limit_error():
    client = StubClient([OpenSkyRateLimited(120)])
    _, save = _recorder()
    summary = run_backfill(
        client, [date(2026, 3, 1)], ["departure"],
        is_loaded=lambda d, day: False, save_response=save, sleep_s=0,
    )
    assert summary.stopped_early is True
    assert "rate limited" in summary.stop_reason.lower()


def test_stops_cleanly_on_other_opensky_error():
    client = StubClient([OpenSkyError("boom")])
    _, save = _recorder()
    summary = run_backfill(
        client, [date(2026, 3, 1)], ["departure"],
        is_loaded=lambda d, day: False, save_response=save, sleep_s=0,
    )
    assert summary.stopped_early is True
    assert "boom" in summary.stop_reason


def test_processes_both_directions_per_day():
    client = StubClient(
        [ApiResponse([], 200, 3970), ApiResponse([], 200, 3940)]
    )
    _, save = _recorder()
    summary = run_backfill(
        client, [date(2026, 3, 1)], ["departure", "arrival"],
        is_loaded=lambda d, day: False, save_response=save, sleep_s=0,
    )
    assert summary.partitions_attempted == 2
    assert [c[0] for c in client.calls] == ["departure", "arrival"]


def test_summary_defaults_are_zero():
    s = BackfillSummary()
    assert (s.partitions_attempted, s.partitions_loaded, s.rows_loaded) == (0, 0, 0)
    assert s.stopped_early is False