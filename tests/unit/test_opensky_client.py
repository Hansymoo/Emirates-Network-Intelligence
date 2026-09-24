import pytest

from flightops.extract.opensky_client import (
    OpenSkyClient,
    OpenSkyError,
    OpenSkyRateLimited,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = ""

    def json(self):
        return self._payload


class FakeSession:
    """Stands in for requests.Session so tests never touch the network."""

    def __init__(self, get_responses):
        self.get_responses = list(get_responses)
        self.post_calls = 0

    def post(self, url, data=None, timeout=None):
        self.post_calls += 1
        return FakeResponse(200, {"access_token": f"tok{self.post_calls}", "expires_in": 1800})

    def get(self, url, params=None, headers=None, timeout=None):
        return self.get_responses.pop(0)


def make_client(responses):
    session = FakeSession(responses)
    return OpenSkyClient("id", "secret", session=session), session


def test_returns_flights_and_remaining_credits():
    client, _ = make_client(
        [FakeResponse(200, [{"callsign": "UAE1"}], {"X-Rate-Limit-Remaining": "3970"})]
    )
    resp = client.flights_by_airport("departure", "OMDB", 0, 3600)
    assert resp.data == [{"callsign": "UAE1"}]
    assert resp.credits_remaining == 3970


def test_404_means_no_flights():
    client, _ = make_client([FakeResponse(404)])
    resp = client.flights_by_airport("arrival", "OMDB", 0, 3600)
    assert resp.data == []
    assert resp.status_code == 404


def test_429_raises_rate_limited():
    client, _ = make_client(
        [FakeResponse(429, headers={"X-Rate-Limit-Retry-After-Seconds": "120"})]
    )
    with pytest.raises(OpenSkyRateLimited) as info:
        client.flights_by_airport("departure", "OMDB", 0, 3600)
    assert info.value.retry_after_s == 120


def test_401_triggers_one_token_refresh_then_succeeds():
    client, session = make_client([FakeResponse(401), FakeResponse(200, [])])
    client.flights_by_airport("departure", "OMDB", 0, 3600)
    assert session.post_calls == 2


def test_token_is_cached_between_calls():
    client, session = make_client([FakeResponse(200, []), FakeResponse(200, [])])
    client.flights_by_airport("departure", "OMDB", 0, 3600)
    client.flights_by_airport("arrival", "OMDB", 0, 3600)
    assert session.post_calls == 1


def test_window_longer_than_two_days_is_rejected():
    client, _ = make_client([])
    with pytest.raises(ValueError):
        client.flights_by_airport("departure", "OMDB", 0, 3 * 24 * 3600)


def test_invalid_direction_is_rejected():
    client, _ = make_client([])
    with pytest.raises(ValueError):
        client.flights_by_airport("sideways", "OMDB", 0, 3600)


def test_server_error_raises_opensky_error():
    client, _ = make_client([FakeResponse(500)])
    with pytest.raises(OpenSkyError):
        client.flights_by_airport("departure", "OMDB", 0, 3600)