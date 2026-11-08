"""RED: env-only config with fail-fast on missing secrets.

Seam: app.core.settings.Settings / load_settings (public boundary).
"""

import pytest
from pydantic import ValidationError

from app.core.settings import Settings, load_settings
from app.infrastructure.arca import get_arca_client

_REQUIRED = [
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "WHATSAPP_API_TOKEN",
    "WHATSAPP_PHONE_ID",
    "WHATSAPP_APP_SECRET",
    "MP_ACCESS_TOKEN",
    "MP_WEBHOOK_SECRET",
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
        "WHATSAPP_APP_SECRET": "secret",
        "MP_ACCESS_TOKEN": "TEST-x",
        "MP_PROVIDER": "test",
        "MP_WEBHOOK_SECRET": "test-only-webhook-secret",
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


def test_gestion_token_ttl_default_and_override(monkeypatch) -> None:
    for key, value in _full_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GESTION_TOKEN_TTL_MINUTES", raising=False)
    assert load_settings().gestion_token_ttl_minutes == 10080

    monkeypatch.setenv("GESTION_TOKEN_TTL_MINUTES", "60")
    assert load_settings().gestion_token_ttl_minutes == 60


def test_missing_mp_webhook_secret_fails_naming_it(
    monkeypatch, tmp_path
) -> None:
    """C-13: the webhook secret has no default and stops the app if absent."""
    monkeypatch.chdir(tmp_path)  # neutralize any local .env: pure process env
    for key in _REQUIRED:
        monkeypatch.delenv(key, raising=False)
    env = _full_env()
    for key, value in env.items():
        if key != "MP_WEBHOOK_SECRET":
            monkeypatch.setenv(key, value)
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "mp_webhook_secret" in str(exc_info.value).lower()

    with pytest.raises(RuntimeError, match="MP_WEBHOOK_SECRET"):
        load_settings()


def test_mp_provider_defaults_to_test_and_is_overridable(monkeypatch) -> None:
    """C-13/R-12: v1 only allows the simulated provider, `test` by default."""
    for key, value in _full_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("MP_PROVIDER", raising=False)
    assert load_settings().mp_provider == "test"

    monkeypatch.setenv("MP_PROVIDER", "sandbox")
    assert load_settings().mp_provider == "sandbox"


def test_lista_espera_oferta_ttl_default_and_override(monkeypatch) -> None:
    """C-10: the offer TTL is configurable and defaults to 30 minutes."""
    for key, value in _full_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("LISTA_ESPERA_OFERTA_TTL_MINUTOS", raising=False)
    assert load_settings().lista_espera_oferta_ttl_minutos == 30

    monkeypatch.setenv("LISTA_ESPERA_OFERTA_TTL_MINUTOS", "15")
    assert load_settings().lista_espera_oferta_ttl_minutos == 15


_ARCA_ENV = (
    "ARCA_PROVIDER",
    "ARCA_PUNTO_VENTA",
    "ARCA_CONDICION_EMISOR",
    "ARCA_MAX_INTENTOS",
    "ARCA_WORKER_INTERVAL_SECONDS",
)


def test_arca_config_defaults_and_overrides(monkeypatch) -> None:
    """C-14/D13: billing defaults keep the trial provider and are overridable."""
    for key, value in _full_env().items():
        monkeypatch.setenv(key, value)
    for key in _ARCA_ENV:
        monkeypatch.delenv(key, raising=False)

    settings = load_settings()
    assert settings.arca_provider == "test"
    assert settings.arca_punto_venta == 1
    assert settings.arca_condicion_emisor == "responsable_inscripto"
    assert settings.arca_max_intentos == 5
    assert settings.arca_worker_interval_seconds == 30

    monkeypatch.setenv("ARCA_PUNTO_VENTA", "3")
    monkeypatch.setenv("ARCA_CONDICION_EMISOR", "monotributista")
    monkeypatch.setenv("ARCA_MAX_INTENTOS", "2")
    monkeypatch.setenv("ARCA_WORKER_INTERVAL_SECONDS", "5")
    cambiado = load_settings()
    assert cambiado.arca_punto_venta == 3
    assert cambiado.arca_condicion_emisor == "monotributista"
    assert cambiado.arca_max_intentos == 2
    assert cambiado.arca_worker_interval_seconds == 5


def test_arca_provider_invalido_falla_al_construir_el_cliente(
    monkeypatch,
) -> None:
    """C-14/D3: any provider other than `test` fails explicitly (R-12)."""
    for key, value in _full_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("ARCA_PROVIDER", "produccion")

    with pytest.raises(RuntimeError, match="ARCA_PROVIDER"):
        get_arca_client(load_settings())
