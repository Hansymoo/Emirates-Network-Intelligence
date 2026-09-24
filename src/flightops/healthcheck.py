"""CLI: verify configuration and database connectivity.

Usage:  python -m flightops.healthcheck
Exit codes: 0 = OK, 1 = database unreachable, 2 = configuration error.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy.exc import SQLAlchemyError

from flightops.config import ConfigError, load_settings
from flightops.db import check_connection, get_engine
from flightops.logging_setup import setup_logging


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    setup_logging(settings.log_level, settings.log_dir)
    log = logging.getLogger("flightops.healthcheck")
    log.info(
        "Checking database %s at %s:%s as user %s",
        settings.db_name, settings.db_host, settings.db_port, settings.db_user,
    )

    engine = get_engine(settings)
    try:
        version = check_connection(engine)
    except SQLAlchemyError as exc:
        log.error("Database connection failed: %s", exc)
        return 1
    finally:
        engine.dispose()

    log.info("OK: %s", version)
    return 0


if __name__ == "__main__":
    sys.exit(main())