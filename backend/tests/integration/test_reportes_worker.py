"""C-15 `reportes` worker: claim, generation, retries, sweep and entrypoint."""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application import exportaciones
from app.application.exportaciones import (
    procesar_exportacion,
    run_once_reportes,
)
from app.workers.__main__ import main as worker_main
from tests.integration.clinica_helpers import auditorias
from tests.integration.comprobantes_helpers import FakeRedis
from tests.integration.exportaciones_helpers import (
    AHORA,
    config_exportacion,
    leer_exportacion,
    setup_exportacion_completa,
    unzip,
)
from tests.integration.helpers import run
from tests.integration.reportes_helpers import insertar_exportacion_db

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _setup(session_factory):
    return run(setup_exportacion_completa(session_factory))


def _crear(session_factory, data, **overrides):
    valores = {
        "solicitado_por": data["actores"]["administrador"].id,
        "alcance": "consultorio",
        **overrides,
    }
    return run(
        insertar_exportacion_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            **valores,
        )
    )


def _procesar(session_factory, exportacion_id, *, config=None, ahora=AHORA):
    return run(
        procesar_exportacion(
            session_factory,
            exportacion_id,
            config=config or config_exportacion(),
            ahora=ahora,
        )
    )


def test_worker_deja_lista_con_artefacto(session_factory) -> None:
    data = _setup(session_factory)
    exportacion_id = _crear(session_factory, data)

    procesados = run(
        run_once_reportes(
            SimpleNamespace(database_url="", redis_url=""),
            session_factory=session_factory,
            redis_client=FakeRedis(),
            config=config_exportacion(),
            ahora=AHORA,
        )
    )
    assert procesados == 1
    fila = run(leer_exportacion(session_factory, exportacion_id))
    assert fila is not None
    assert fila.estado == "lista"
    assert fila.contenido is not None
    assert fila.tamano_bytes == len(fila.contenido)
    assert fila.generada_at is not None
    assert unzip(fila.contenido)["exportacion.pdf"].startswith(b"%PDF-")
    generar = run(auditorias(session_factory, "exportacion.generar"))
    assert len(generar) == 1
    assert generar[0].usuario_id is None
    assert generar[0].entidad_id == str(exportacion_id)


def test_mismo_id_dos_veces_no_duplica_ni_retrocede(
    session_factory,
) -> None:
    data = _setup(session_factory)
    exportacion_id = _crear(session_factory, data)

    primero = _procesar(session_factory, exportacion_id)
    segundo = _procesar(
        session_factory, exportacion_id, ahora=AHORA + timedelta(minutes=1)
    )
    assert primero is not None and primero.estado == "lista"
    assert segundo is not None and segundo.estado == "lista"
    assert segundo.generada_at == primero.generada_at
    assert segundo.contenido == primero.contenido
    assert len(run(auditorias(session_factory, "exportacion.generar"))) == 1


def test_dos_workers_reclaman_y_solo_uno_genera(session_factory) -> None:
    data = _setup(session_factory)
    exportacion_id = _crear(session_factory, data)

    async def dos() -> list:
        return await asyncio.gather(
            procesar_exportacion(
                session_factory,
                exportacion_id,
                config=config_exportacion(),
                ahora=AHORA,
            ),
            procesar_exportacion(
                session_factory,
                exportacion_id,
                config=config_exportacion(),
                ahora=AHORA,
            ),
        )

    resultados = run(dos())
    assert any(
        resultado is not None and resultado.estado == "lista"
        for resultado in resultados
    )
    fila = run(leer_exportacion(session_factory, exportacion_id))
    assert fila is not None and fila.estado == "lista"
    assert len(run(auditorias(session_factory, "exportacion.generar"))) == 1


def test_fallo_transitorio_programa_backoff_y_se_recupera(
    session_factory, monkeypatch
) -> None:
    data = _setup(session_factory)
    exportacion_id = _crear(session_factory, data)
    original = exportaciones.generar_artefacto

    async def fallar(*args, **kwargs):
        raise RuntimeError("fallo transitorio simulado")

    monkeypatch.setattr(exportaciones, "generar_artefacto", fallar)
    fallida = _procesar(session_factory, exportacion_id)
    assert fallida is not None
    assert fallida.estado == "pendiente"
    assert fallida.intentos == 1
    assert fallida.proximo_intento == AHORA + timedelta(minutes=2)
    assert "fallo transitorio" in (fallida.ultimo_error or "")
    assert fallida.claim_token is None
    assert fallida.reclamado_at is None

    antes = _procesar(
        session_factory,
        exportacion_id,
        ahora=AHORA + timedelta(seconds=60),
    )
    assert antes is not None and antes.estado == "pendiente"

    monkeypatch.setattr(exportaciones, "generar_artefacto", original)
    recuperada = _procesar(
        session_factory,
        exportacion_id,
        ahora=AHORA + timedelta(minutes=3),
    )
    assert recuperada is not None
    assert recuperada.estado == "lista"
    assert recuperada.proximo_intento is None


def test_fallo_en_el_maximo_queda_fallida(
    session_factory, monkeypatch
) -> None:
    data = _setup(session_factory)
    exportacion_id = _crear(session_factory, data, intentos=2)

    async def fallar(*args, **kwargs):
        raise RuntimeError("fallo definitivo simulado")

    monkeypatch.setattr(exportaciones, "generar_artefacto", fallar)
    fallida = _procesar(
        session_factory,
        exportacion_id,
        config=config_exportacion(max_intentos=3),
    )
    assert fallida is not None
    assert fallida.estado == "fallida"
    assert fallida.intentos == 3
    assert "fallo definitivo" in (fallida.ultimo_error or "")
    assert fallida.contenido is None
    eventos = run(auditorias(session_factory, "exportacion.fallida"))
    assert len(eventos) == 1
    assert eventos[0].usuario_id is None


def test_barrido_procesa_pendientes_sin_redis(session_factory) -> None:
    data = _setup(session_factory)
    primera = _crear(session_factory, data)
    segunda = _crear(
        session_factory,
        data,
        solicitado_por=data["actores"]["odontologo"].id,
    )

    procesados = run(
        run_once_reportes(
            SimpleNamespace(database_url="", redis_url=""),
            session_factory=session_factory,
            redis_client=FakeRedis(brpop_error=True),
            config=config_exportacion(),
            ahora=AHORA,
        )
    )
    assert procesados == 2
    for exportacion_id in (primera, segunda):
        fila = run(leer_exportacion(session_factory, exportacion_id))
        assert fila is not None and fila.estado == "lista"


def test_entrypoint_reportes_once(monkeypatch) -> None:
    llamado: list[bool] = []

    async def fake_run_once(settings, *, timeout: int = 1) -> int:
        llamado.append(True)
        return 0

    import app.workers.__main__ as workers

    monkeypatch.setattr(workers, "load_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(workers, "run_once_reportes", fake_run_once)

    worker_main(["reportes", "--once"])
    assert llamado == [True]


def test_entrypoint_reportes_once_contra_la_base(
    migrated_database: str, session_factory
) -> None:
    data = _setup(session_factory)
    exportacion_id = _crear(session_factory, data)
    entorno = {
        **os.environ,
        "DATABASE_URL": migrated_database,
        "REDIS_URL": "redis://127.0.0.1:6399/0",
    }
    resultado = subprocess.run(
        [sys.executable, "-m", "app.workers", "reportes", "--once"],
        cwd=BACKEND_DIR,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert resultado.returncode == 0, resultado.stderr
    fila = run(leer_exportacion(session_factory, exportacion_id))
    assert fila is not None and fila.estado == "lista"
