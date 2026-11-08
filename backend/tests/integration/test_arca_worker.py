"""C-14 group 6: `arca:emitir` worker, retries, idempotency and sweep."""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.application.comprobantes import procesar_comprobante
from app.core.settings import load_settings
from app.domain.fiscal import decodificar_qr
from app.infrastructure.arca import ResultadoEmision, TestArcaClient
from app.infrastructure.repositories import SecuenciaComprobanteRepository
from app.workers.__main__ import run_once_arca
from tests.integration.clinica_helpers import auditorias
from tests.integration.comprobantes_helpers import (
    FakeRedis,
    contar_comprobantes,
    crear_comprobante_pendiente,
    fiscal_config,
    leer_comprobante,
    setup_comprobantes,
)
from tests.integration.helpers import run

BACKEND_DIR = Path(__file__).resolve().parents[2]
AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


class ClienteGrabador:
    """Wrap the trial client to keep every authorization result for asserts."""

    def __init__(self) -> None:
        self.real = TestArcaClient()
        self.resultados: list[ResultadoEmision] = []

    async def emitir(self, **kwargs: object) -> ResultadoEmision:
        resultado = await self.real.emitir(**kwargs)  # type: ignore[arg-type]
        self.resultados.append(resultado)
        return resultado


def _setup(session_factory) -> dict[str, object]:
    return run(setup_comprobantes(session_factory))


def _procesar(session_factory, cliente, comprobante_id, **overrides):
    return run(
        procesar_comprobante(
            session_factory,
            cliente,
            comprobante_id,
            config=overrides.pop("config", fiscal_config()),
            ahora=overrides.pop("ahora", AHORA),
            **overrides,
        )
    )


def test_procesa_pendiente_y_persiste_cae_y_qr(
    session_factory,
) -> None:
    """Expected: one provider call persists CAE, fiscal number, QR and date."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    cliente = TestArcaClient()

    emitido = _procesar(session_factory, cliente, comprobante_id)
    assert emitido is not None
    assert emitido.estado == "emitido"
    assert len(emitido.cae or "") == 14
    assert (emitido.cae or "").isdigit()
    assert emitido.cae_vencimiento is not None
    assert emitido.numero_fiscal == 1
    assert emitido.fecha_emision_fiscal is not None
    assert emitido.claim_token is None
    assert emitido.reclamado_at is None
    assert emitido.proximo_intento is None
    assert len(cliente.llamadas) == 1

    datos = decodificar_qr(emitido.qr_fiscal or "")
    assert datos["codAut"] == emitido.cae
    assert datos["ptoVta"] == 1
    assert datos["nroCmp"] == 1
    assert Decimal(str(datos["importe"])) == Decimal("15000.00")

    emitir = run(auditorias(session_factory, "comprobante.emitir"))
    assert len(emitir) == 1
    assert emitir[0].usuario_id is None
    assert emitir[0].entidad_id == str(comprobante_id)


def test_emitido_no_vuelve_a_llamar_al_proveedor(session_factory) -> None:
    """Edge: an emitted receipt is terminal; a second job is a no-op."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    cliente = TestArcaClient()
    primero = _procesar(session_factory, cliente, comprobante_id)
    segundo = _procesar(
        session_factory,
        cliente,
        comprobante_id,
        ahora=AHORA + timedelta(minutes=1),
    )
    assert primero is not None and primero.cae == segundo.cae
    assert len(cliente.llamadas) == 1
    assert len(run(auditorias(session_factory, "comprobante.emitir"))) == 1


def test_fallo_incrementa_intentos_y_programa_backoff(
    session_factory,
) -> None:
    """Business error: a provider failure stays pending with exponential wait."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    cliente = TestArcaClient()
    cliente.simular_fallo(1)

    fallido = _procesar(session_factory, cliente, comprobante_id)
    assert fallido is not None
    assert fallido.estado == "pendiente"
    assert fallido.intentos == 1
    assert fallido.proximo_intento == AHORA + timedelta(seconds=60)
    assert "simulado" in (fallido.ultimo_error or "")
    assert fallido.claim_token is None
    assert len(cliente.llamadas) == 1

    # Before the backoff elapses the sweep cannot claim it.
    assert (
        _procesar(
            session_factory,
            cliente,
            comprobante_id,
            ahora=AHORA + timedelta(seconds=30),
        )
        is None
    )
    assert len(cliente.llamadas) == 1

    recuperado = _procesar(
        session_factory,
        cliente,
        comprobante_id,
        ahora=AHORA + timedelta(seconds=61),
    )
    assert recuperado is not None
    assert recuperado.estado == "emitido"
    assert recuperado.proximo_intento is None
    assert (
        len(run(auditorias(session_factory, "comprobante.emitir_fallido")))
        == 1
    )


def test_tope_de_intentos_deja_el_comprobante_fallido(
    session_factory,
) -> None:
    """Business error: the maximum number of attempts marks it failed."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    cliente = TestArcaClient()
    cliente.simular_fallo(5)
    config = fiscal_config(max_intentos=2)

    primero = _procesar(
        session_factory, cliente, comprobante_id, config=config
    )
    assert primero is not None and primero.estado == "pendiente"
    segundo = _procesar(
        session_factory,
        cliente,
        comprobante_id,
        config=config,
        ahora=AHORA + timedelta(seconds=61),
    )
    assert segundo is not None
    assert segundo.estado == "fallido"
    assert segundo.intentos == 2
    assert "simulado" in (segundo.ultimo_error or "")

    assert (
        _procesar(
            session_factory,
            cliente,
            comprobante_id,
            config=config,
            ahora=AHORA + timedelta(minutes=60),
        )
        is None
    )
    assert len(cliente.llamadas) == 2
    assert (
        len(run(auditorias(session_factory, "comprobante.emitir_fallido")))
        == 2
    )


def test_dos_workers_concurrentes_solo_uno_emite(session_factory) -> None:
    """Edge: the claim token serializes two simultaneous workers (D4)."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    cliente = TestArcaClient()

    async def scenario() -> list[Comprobante | None]:
        return list(
            await asyncio.gather(
                procesar_comprobante(
                    session_factory,
                    cliente,
                    comprobante_id,
                    config=fiscal_config(),
                    ahora=AHORA,
                ),
                procesar_comprobante(
                    session_factory,
                    cliente,
                    comprobante_id,
                    config=fiscal_config(),
                    ahora=AHORA,
                ),
            )
        )

    resultados = run(scenario())
    emitidos = [r for r in resultados if r is not None]
    assert emitidos
    assert len(cliente.llamadas) == 1
    assert len(run(auditorias(session_factory, "comprobante.emitir"))) == 1
    final = run(leer_comprobante(session_factory, comprobante_id))
    assert final is not None and final.estado == "emitido"


def test_job_duplicado_en_la_cola_emite_una_sola_vez(
    session_factory,
) -> None:
    """Edge: the same id twice in `arca:emitir` yields one CAE."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    cliente = TestArcaClient()
    fake = FakeRedis()
    fake.items = [
        ("arca:emitir", str(comprobante_id)),
        ("arca:emitir", str(comprobante_id)),
    ]
    settings = load_settings()

    primero = run(
        run_once_arca(
            settings,
            cliente=cliente,
            session_factory=session_factory,
            redis_client=fake,
            timeout=0,
            ahora=AHORA,
        )
    )
    segundo = run(
        run_once_arca(
            settings,
            cliente=cliente,
            session_factory=session_factory,
            redis_client=fake,
            timeout=0,
            ahora=AHORA + timedelta(seconds=1),
        )
    )
    assert primero == 1
    assert segundo == 1  # the duplicate job is a no-op, not a second CAE
    assert len(cliente.llamadas) == 1
    assert len(run(auditorias(session_factory, "comprobante.emitir"))) == 1


def test_cae_obtenido_y_fallo_de_persistencia_reintenta_el_mismo_cae(
    session_factory, monkeypatch
) -> None:
    """Edge: the idempotency key makes the retry return the same CAE (D5)."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    cliente = ClienteGrabador()

    async def falla(self, consultorio_id, punto_venta):
        raise RuntimeError("persistencia caída")

    with monkeypatch.context() as parche:
        parche.setattr(
            SecuenciaComprobanteRepository, "siguiente_fiscal", falla
        )
        with pytest.raises(RuntimeError):
            _procesar(session_factory, cliente, comprobante_id)

    assert len(cliente.resultados) == 1
    pendiente = run(leer_comprobante(session_factory, comprobante_id))
    assert pendiente is not None
    assert pendiente.estado == "pendiente"
    assert pendiente.numero_fiscal is None

    # The claim expires after five minutes and the retry gets the same CAE.
    reintentado = _procesar(
        session_factory,
        cliente,
        comprobante_id,
        ahora=AHORA + timedelta(minutes=6),
    )
    assert reintentado is not None
    assert reintentado.estado == "emitido"
    assert len(cliente.resultados) == 2
    assert cliente.resultados[0].cae == cliente.resultados[1].cae
    assert reintentado.cae == cliente.resultados[0].cae
    assert run(contar_comprobantes(session_factory)) == 1


def test_barrido_sin_cola_procesa_los_pendientes_vencidos(
    session_factory,
) -> None:
    """Edge: an empty Redis still processes due receipts (D4/R-06)."""
    data = _setup(session_factory)
    vencido = run(
        crear_comprobante_pendiente(
            session_factory, data, numero_interno=1
        )
    )
    futuro = run(
        crear_comprobante_pendiente(
            session_factory,
            data,
            numero_interno=2,
            proximo_intento=AHORA + timedelta(minutes=10),
        )
    )
    cliente = TestArcaClient()

    procesados = run(
        run_once_arca(
            load_settings(),
            cliente=cliente,
            session_factory=session_factory,
            redis_client=FakeRedis(),
            timeout=0,
            ahora=AHORA,
        )
    )
    assert procesados == 1
    emitido = run(leer_comprobante(session_factory, vencido))
    assert emitido is not None and emitido.estado == "emitido"
    pendiente = run(leer_comprobante(session_factory, futuro))
    assert pendiente is not None and pendiente.estado == "pendiente"


def test_barrido_tolera_un_brpop_roto(session_factory) -> None:
    """Edge: a Redis error during BRPOP must not lose the sweep."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    fake = FakeRedis(brpop_error=True)

    procesados = run(
        run_once_arca(
            load_settings(),
            cliente=TestArcaClient(),
            session_factory=session_factory,
            redis_client=fake,
            timeout=0,
            ahora=AHORA,
        )
    )
    assert procesados == 1
    assert fake.brpops == 1
    emitido = run(leer_comprobante(session_factory, comprobante_id))
    assert emitido is not None and emitido.estado == "emitido"


def test_run_once_arca_procesa_el_job_encolado(session_factory) -> None:
    """Expected: the worker pops one id, emits it and empties the queue."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    cliente = TestArcaClient()
    fake = FakeRedis()
    fake.items = [("arca:emitir", str(comprobante_id))]

    procesados = run(
        run_once_arca(
            load_settings(),
            cliente=cliente,
            session_factory=session_factory,
            redis_client=fake,
            timeout=0,
            ahora=AHORA,
        )
    )
    assert procesados == 1
    assert fake.items == []
    assert len(cliente.llamadas) == 1
    emitido = run(leer_comprobante(session_factory, comprobante_id))
    assert emitido is not None and emitido.estado == "emitido"


def test_entrypoint_arca_once_contra_la_base_de_test(
    migrated_database: str, session_factory
) -> None:
    """Expected: `python -m app.workers arca --once` exits 0 and emits."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    env = {
        **os.environ,
        "DATABASE_URL": migrated_database,
        # A dead Redis proves the sweep does not depend on the queue.
        "REDIS_URL": "redis://127.0.0.1:1/0",
        "ARCA_PROVIDER": "test",
    }
    resultado = subprocess.run(
        [sys.executable, "-m", "app.workers", "arca", "--once"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert resultado.returncode == 0, resultado.stderr
    emitido = run(leer_comprobante(session_factory, comprobante_id))
    assert emitido is not None
    assert emitido.estado == "emitido"
