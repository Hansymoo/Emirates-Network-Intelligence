"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_VARS = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)  # never printed in repr/logs
    log_level: str = "INFO"
    log_dir: Path = PROJECT_ROOT / "logs"
    data_dir: Path = PROJECT_ROOT / "data"
    opensky_client_id: str = ""
    opensky_client_secret: str = field(default="", repr=False)

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from an env mapping.

    If ``env`` is None, load ``.env`` from the project root (if present) and use
    ``os.environ``. Passing an explicit mapping is intended for tests.
    """
    if env is None:
        load_dotenv(PROJECT_ROOT / ".env")
        env = os.environ

    missing = [name for name in REQUIRED_VARS if not env.get(name)]
    if missing:
        raise ConfigError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in."
        )

    try:
        port = int(env.get("POSTGRES_PORT", "5432"))
    except ValueError as exc:
        raise ConfigError("POSTGRES_PORT must be an integer.") from exc

    level = env.get("LOG_LEVEL", "INFO").upper()
    if level not in logging.getLevelNamesMapping():
        raise ConfigError(f"LOG_LEVEL '{level}' is not a valid logging level.")

    return Settings(
        db_host=env.get("POSTGRES_HOST", "localhost"),
        db_port=port,
        db_name=env["POSTGRES_DB"],
        db_user=env["POSTGRES_USER"],
        db_password=env["POSTGRES_PASSWORD"],
        log_level=level,
        log_dir=_resolve_path(env.get("LOG_DIR", "logs")),
        data_dir=_resolve_path(env.get("DATA_DIR", "data")),
        opensky_client_id=env.get("OPENSKY_CLIENT_ID", ""),
        opensky_client_secret=env.get("OPENSKY_CLIENT_SECRET", ""),
    )