"""CLI: create (or update) the database schema from the numbered files in sql/.

Usage:
    python -m flightops.init_db
    python -m flightops.init_db --reset    # DROPS all project schemas first (asks first)
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from flightops.config import PROJECT_ROOT, ConfigError, load_settings
from flightops.db import get_engine
from flightops.logging_setup import setup_logging

SQL_DIR = PROJECT_ROOT / "sql"
SCHEMAS = ("raw", "staging", "core", "mart", "ops")
log = logging.getLogger("flightops.init_db")


def list_sql_files(sql_dir: Path = SQL_DIR) -> list[Path]:
    """Numbered SQL files (00_..., 01_...) in the order they must run."""
    return sorted(sql_dir.glob("[0-9][0-9]_*.sql"))


def apply_sql_files(engine: Engine, files: Iterable[Path]) -> None:
    """Run each file in its own transaction. Every file is safe to run repeatedly."""
    for path in files:
        log.info("Applying %s", path.name)
        sql = path.read_text(encoding="utf-8")
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)


def reset_schemas(engine: Engine) -> None:
    with engine.begin() as conn:
        for schema in SCHEMAS:
            conn.exec_driver_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def list_tables(engine: Engine) -> list[tuple[str, str]]:
    query = text(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_schema = ANY(:schemas) ORDER BY 1, 2"
    )
    with engine.connect() as conn:
        return [(row[0], row[1]) for row in conn.execute(query, {"schemas": list(SCHEMAS)})]


def confirm_reset(ask: Callable[[str], str] = input) -> bool:
    answer = ask(
        "This DROPS the raw, staging, core, mart and ops schemas and all their data. "
        "Type 'yes' to continue: "
    )
    return answer.strip().lower() == "yes"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the database schema from sql/*.sql")
    parser.add_argument("--reset", action="store_true", help="drop all project schemas first")
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    setup_logging(settings.log_level, settings.log_dir)
    files = list_sql_files()
    if not files:
        log.error("No SQL files found in %s", SQL_DIR)
        return 2

    engine = get_engine(settings)
    try:
        if args.reset:
            if not confirm_reset():
                log.info("Reset cancelled")
                return 0
            reset_schemas(engine)
            log.info("Dropped schemas: %s", ", ".join(SCHEMAS))
        apply_sql_files(engine, files)
        tables = list_tables(engine)
    except SQLAlchemyError as exc:
        log.error("Schema setup failed: %s", exc)
        return 1
    finally:
        engine.dispose()

    for schema, table in tables:
        log.info("  %s.%s", schema, table)
    log.info("Done: %s tables", len(tables))
    return 0


if __name__ == "__main__":
    sys.exit(main())