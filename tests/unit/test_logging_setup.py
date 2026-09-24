import logging

import pytest

from flightops.logging_setup import LOGGER_NAME, setup_logging


@pytest.fixture(autouse=True)
def _cleanup_handlers():
    yield
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()  # releases the file (important on Windows)


def test_setup_is_idempotent(tmp_path):
    setup_logging("INFO", tmp_path)
    setup_logging("INFO", tmp_path)
    logger = logging.getLogger(LOGGER_NAME)
    assert len(logger.handlers) == 2  # one console + one file, no duplicates


def test_log_file_is_written(tmp_path):
    setup_logging("INFO", tmp_path)
    logging.getLogger(f"{LOGGER_NAME}.test").info("hello from test")
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()
    content = (tmp_path / "flightops.log").read_text(encoding="utf-8")
    assert "hello from test" in content


def test_invalid_level_raises(tmp_path):
    with pytest.raises(ValueError):
        setup_logging("LOUD", tmp_path)