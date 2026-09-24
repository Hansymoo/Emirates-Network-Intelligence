import pytest

from flightops.config import load_settings
from flightops.db import check_connection, get_engine


@pytest.mark.integration
def test_database_connection():
    engine = get_engine(load_settings())
    try:
        assert check_connection(engine).startswith("PostgreSQL")
    finally:
        engine.dispose()