"""Database engine creation and connectivity checks."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from flightops.config import Settings

logger = logging.getLogger(__name__)


def get_engine(settings: Settings) -> Engine:
    """Create a SQLAlchemy engine. pool_pre_ping drops stale connections."""
    return create_engine(settings.database_url, pool_pre_ping=True)


def check_connection(engine: Engine) -> str:
    """Run a trivial query and return the PostgreSQL version string."""
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar_one()
    logger.info("Connected to database")
    return version