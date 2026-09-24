import pytest

from flightops.config import PROJECT_ROOT, ConfigError, load_settings

VALID_ENV = {
    "POSTGRES_DB": "testdb",
    "POSTGRES_USER": "tester",
    "POSTGRES_PASSWORD": "secret",
}


def test_load_settings_with_defaults():
    settings = load_settings(VALID_ENV)
    assert settings.db_host == "localhost"
    assert settings.db_port == 5432
    assert settings.db_name == "testdb"
    assert settings.log_level == "INFO"
    assert settings.log_dir == PROJECT_ROOT / "logs"


def test_missing_required_variable_raises():
    env = {k: v for k, v in VALID_ENV.items() if k != "POSTGRES_PASSWORD"}
    with pytest.raises(ConfigError, match="POSTGRES_PASSWORD"):
        load_settings(env)


def test_invalid_port_raises():
    with pytest.raises(ConfigError, match="POSTGRES_PORT"):
        load_settings({**VALID_ENV, "POSTGRES_PORT": "abc"})


def test_invalid_log_level_raises():
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        load_settings({**VALID_ENV, "LOG_LEVEL": "LOUD"})


def test_log_level_is_normalised_to_uppercase():
    assert load_settings({**VALID_ENV, "LOG_LEVEL": "debug"}).log_level == "DEBUG"


def test_password_is_not_exposed_in_repr_or_url_string():
    settings = load_settings(VALID_ENV)
    assert "secret" not in repr(settings)
    assert "secret" not in str(settings.database_url)


def test_absolute_log_dir_is_respected(tmp_path):
    settings = load_settings({**VALID_ENV, "LOG_DIR": str(tmp_path)})
    assert settings.log_dir == tmp_path