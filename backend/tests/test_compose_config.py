"""Compose demo contract (C-16 task 10.1): eight services, tools profile, no secrets."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
BASE_SERVICES = {"api", "frontend", "db", "redis"}
WORKERS = {
    "worker-recordatorios",
    "worker-whatsapp",
    "worker-arca",
    "worker-reportes",
}


def _compose(*args: str) -> subprocess.CompletedProcess:
    if shutil.which("docker") is None:
        pytest.skip("Docker no está disponible para validar Compose")
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


def _config() -> dict:
    return json.loads(
        _compose(
            "--profile", "tools", "config", "--format", "json"
        ).stdout
    )


def test_ocho_servicios_por_defecto() -> None:
    """Expected: four base services plus four workers, no profile needed."""
    salida = _compose("config", "--services").stdout.split()
    assert set(salida) == BASE_SERVICES | WORKERS
    assert "backup" not in salida


def test_backup_solo_bajo_el_perfil_tools() -> None:
    """Business rule: the backup service never starts with the demo."""
    config = _config()
    backup = config["services"]["backup"]
    assert backup.get("profiles") == ["tools"]
    for servicio in BASE_SERVICES | WORKERS:
        assert not config["services"][servicio].get("profiles")


def test_workers_por_defecto_con_reinicio_y_gates() -> None:
    """Expected: workers restart and wait for healthy db/redis."""
    config = _config()
    for nombre in WORKERS:
        servicio = config["services"][nombre]
        assert servicio.get("restart") == "unless-stopped", nombre
        depends = servicio.get("depends_on", {})
        assert depends.get("db", {}).get("condition") == "service_healthy"
        assert depends.get("redis", {}).get("condition") == "service_healthy"


def test_healthchecks_y_volumenes() -> None:
    """Expected: named volumes and healthchecks on db/redis/api/frontend."""
    config = _config()
    services = config["services"]
    for nombre in ("db", "redis", "api", "frontend"):
        assert services[nombre].get("healthcheck"), nombre
    assert set(config.get("volumes", {})) >= {"pgdata", "redisdata"}


def test_sin_latest_ni_secretos_literales() -> None:
    """Business rule: pinned-enough tags, no literal tokens/passwords."""
    texto = COMPOSE.read_text(encoding="utf-8")
    assert ":latest" not in texto
    for prohibido in (
        "changeme",
        "TEST-",
        "password:",
        "POSTGRES_PASSWORD:",
        "JWT_SECRET:",
        "BACKUP_PASSPHRASE:",
    ):
        assert prohibido not in texto, prohibido
    config = _config()
    assert config["services"]["backup"].get("restart") == "unless-stopped"
