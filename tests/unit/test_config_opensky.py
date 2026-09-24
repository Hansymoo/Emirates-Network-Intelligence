from flightops.config import load_settings

BASE = {"POSTGRES_DB": "d", "POSTGRES_USER": "u", "POSTGRES_PASSWORD": "p"}


def test_opensky_credentials_default_to_empty():
    settings = load_settings(BASE)
    assert settings.opensky_client_id == ""
    assert settings.opensky_client_secret == ""


def test_opensky_secret_is_not_exposed_in_repr():
    env = {**BASE, "OPENSKY_CLIENT_ID": "abc", "OPENSKY_CLIENT_SECRET": "topsecret"}
    settings = load_settings(env)
    assert settings.opensky_client_id == "abc"
    assert "topsecret" not in repr(settings)