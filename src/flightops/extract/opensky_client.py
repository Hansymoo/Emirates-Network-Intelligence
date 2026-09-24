"""Minimal OpenSky REST client using the OAuth2 client-credentials flow.

Only the /flights/departure and /flights/arrival endpoints are wrapped for now.
Docs: https://openskynetwork.github.io/opensky-api/rest.html
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/"
    "protocol/openid-connect/token"
)
API_ROOT = "https://opensky-network.org/api"
REFRESH_MARGIN_S = 30
DEFAULT_TIMEOUT_S = 60
MAX_SPAN_S = 2 * 24 * 3600  # OpenSky: airport flight queries must not exceed 2 days


class OpenSkyError(RuntimeError):
    """Any failure talking to OpenSky."""


class OpenSkyRateLimited(OpenSkyError):
    """HTTP 429: credits exhausted."""

    def __init__(self, retry_after_s: int | None):
        super().__init__(f"Rate limited by OpenSky; retry after {retry_after_s} seconds.")
        self.retry_after_s = retry_after_s


@dataclass(frozen=True)
class ApiResponse:
    data: list
    status_code: int
    credits_remaining: int | None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


class OpenSkyClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        session: requests.Session | None = None,
        timeout: int = DEFAULT_TIMEOUT_S,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = session or requests.Session()
        self._timeout = timeout
        self._token: str | None = None
        self._expires_at = 0.0

    def _get_token(self) -> str:
        if self._token and time.monotonic() < self._expires_at:
            return self._token
        try:
            resp = self._session.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise OpenSkyError(f"Network error while requesting a token: {exc}") from exc
        if resp.status_code != 200:
            raise OpenSkyError(
                f"Token request failed with HTTP {resp.status_code}. "
                "Check OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET in .env."
            )
        payload = resp.json()
        self._token = payload["access_token"]
        lifetime = int(payload.get("expires_in", 1800)) - REFRESH_MARGIN_S
        self._expires_at = time.monotonic() + max(lifetime, 0)
        logger.info("Obtained OpenSky access token")
        return self._token

    def _get(self, path: str, params: dict) -> ApiResponse:
        url = f"{API_ROOT}{path}"
        resp = None
        for attempt in range(2):
            headers = {"Authorization": f"Bearer {self._get_token()}"}
            try:
                resp = self._session.get(
                    url, params=params, headers=headers, timeout=self._timeout
                )
            except requests.RequestException as exc:
                raise OpenSkyError(f"Network error calling {path}: {exc}") from exc
            if resp.status_code == 401 and attempt == 0:
                logger.info("Token rejected (401); requesting a new one")
                self._token = None
                continue
            break

        remaining = _to_int(resp.headers.get("X-Rate-Limit-Remaining"))
        if resp.status_code == 404:  # OpenSky uses 404 for "no flights in this period"
            return ApiResponse([], 404, remaining)
        if resp.status_code == 429:
            raise OpenSkyRateLimited(_to_int(resp.headers.get("X-Rate-Limit-Retry-After-Seconds")))
        if resp.status_code != 200:
            raise OpenSkyError(f"HTTP {resp.status_code} from {path}: {resp.text[:200]}")
        return ApiResponse(resp.json(), 200, remaining)

    def flights_by_airport(
        self, direction: str, airport: str, begin: int, end: int
    ) -> ApiResponse:
        """Flights departing from or arriving at an airport (ICAO code) in [begin, end]."""
        if direction not in ("departure", "arrival"):
            raise ValueError("direction must be 'departure' or 'arrival'")
        if end <= begin:
            raise ValueError("end must be after begin")
        if end - begin > MAX_SPAN_S:
            raise ValueError("time window must not exceed 2 days")
        return self._get(
            f"/flights/{direction}", {"airport": airport, "begin": begin, "end": end}
        )