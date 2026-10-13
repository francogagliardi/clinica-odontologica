"""RED: env-only config with fail-fast on missing secrets.

Seam: app.core.settings.Settings / load_settings (public boundary).
"""

import pytest
from pydantic import ValidationError

from app.core.settings import Settings, load_settings

_REQUIRED = [
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "WHATSAPP_API_TOKEN",
    "WHATSAPP_PHONE_ID",
    "MP_ACCESS_TOKEN",
    "ARCA_CUIT",
    "ARCA_CERT",
    "ARCA_KEY",
    "APP_BASE_URL",
]


def _full_env() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "JWT_SECRET": "s" * 32,
        "JWT_ALGORITHM": "HS256",
        "JWT_EXPIRE_MINUTES": "60",
        "WHATSAPP_API_TOKEN": "tok",
        "WHATSAPP_PHONE_ID": "pid",
        "MP_ACCESS_TOKEN": "TEST-x",
        "ARCA_CUIT": "20000000001",
        "ARCA_CERT": "cert",
        "ARCA_KEY": "key",
        "APP_BASE_URL": "http://127.0.0.1:8080",
    }


def test_missing_jwt_secret_fails_naming_it(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)  # neutralize any local .env: pure process env
    for key in _REQUIRED:
        monkeypatch.delenv(key, raising=False)
    env = _full_env()
    for key, value in env.items():
        if key != "JWT_SECRET":
            monkeypatch.setenv(key, value)
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "jwt_secret" in str(exc_info.value).lower()


def test_missing_database_url_fails_naming_it(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)  # neutralize any local .env: pure process env
    for key in _REQUIRED:
        monkeypatch.delenv(key, raising=False)
    env = _full_env()
    for key, value in env.items():
        if key != "DATABASE_URL":
            monkeypatch.setenv(key, value)
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "database_url" in str(exc_info.value).lower()


def test_load_settings_names_missing_var_uppercase(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)  # neutralize any local .env: pure process env
    for key in _REQUIRED:
        monkeypatch.delenv(key, raising=False)
    env = _full_env()
    for key, value in env.items():
        if key != "JWT_SECRET":
            monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        load_settings()


def test_full_env_boots_with_typed_values(monkeypatch) -> None:
    for key, value in _full_env().items():
        monkeypatch.setenv(key, value)
    settings = load_settings()
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_expire_minutes == 60
    assert isinstance(settings.jwt_expire_minutes, int)
