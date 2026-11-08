"""C-14 group 8: preventive local coverage, read-only and non-blocking."""

import uuid

from app.api.deps import get_cobertura_provider
from app.application.presupuestos import LocalCoberturaProvider
from app.main import app
from tests.integration.clinica_helpers import auditorias
from tests.integration.helpers import run
from tests.integration.liquidaciones_helpers import (
    contar_tablas_mutables,
    crear_paciente_os,
    get_cobertura,
    setup_liquidaciones,
)
from tests.integration.presupuestos_helpers import crear_convenio

_CLAVES = {
    "paciente_id",
    "prestacion_id",
    "estado",
    "cobertura_porcentaje",
    "cobertura_monto",
    "copago_monto",
}


class ProviderEspia:
    """Local provider double that records it was consulted (no network)."""

    def __init__(self) -> None:
        self.llamadas = 0
        self.real = LocalCoberturaProvider()

    async def resolver(self, uow, paciente):
        self.llamadas += 1
        return await self.real.resolver(uow, paciente)


def _setup(session_factory) -> dict[str, object]:
    return run(setup_liquidaciones(session_factory))


def test_practica_cubierta_60_40_con_montos(
    api_client, session_factory
) -> None:
    """Expected: OS Demo pays 60 % of a covered 10000.00 service."""
    data = _setup(session_factory)
    respuesta = get_cobertura(
        api_client,
        data,
        paciente_id=data["paciente_os_demo"].id,
        prestacion_id=data["prestaciones"]["CONS"].id,
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "cubierta"
    assert cuerpo["cobertura_porcentaje"] == "60"
    assert cuerpo["cobertura_monto"] == "6000.00"
    assert cuerpo["copago_monto"] == "4000.00"


def test_paciente_sin_obra_social_no_esta_cubierto(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    paciente = data["paciente_propio"]
    respuesta = get_cobertura(
        api_client,
        data,
        paciente_id=paciente.id,
        prestacion_id=data["prestaciones"]["CONS"].id,
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "no_cubierta"
    assert cuerpo["cobertura_porcentaje"] == "0"
    assert cuerpo["cobertura_monto"] == "0.00"
    assert cuerpo["copago_monto"] == "10000.00"


def test_practica_fuera_del_convenio_no_inventa_cobertura(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = get_cobertura(
        api_client,
        data,
        paciente_id=data["paciente_os_demo"].id,
        prestacion_id=data["prestaciones"]["EXO"].id,
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "no_cubierta"
    assert cuerpo["cobertura_porcentaje"] == "0"
    assert cuerpo["cobertura_monto"] == "0.00"
    assert cuerpo["copago_monto"] == "30000.00"


def test_convenio_inactivo_queda_pendiente_sin_montos(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = get_cobertura(
        api_client,
        data,
        paciente_id=data["paciente_convenio_inactivo"].id,
        prestacion_id=data["prestaciones"]["CONS"].id,
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "pendiente_verificacion"
    assert cuerpo["cobertura_porcentaje"] is None
    assert cuerpo["cobertura_monto"] is None
    assert cuerpo["copago_monto"] is None


def test_convenio_sin_reglas_utilizables_queda_pendiente(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    obra = run(
        crear_convenio(
            session_factory,
            data["consultorio_id"],
            nombre=f"OS Sin Reglas {uuid.uuid4().hex[:5]}",
            reglas_cobertura={},
        )
    )
    paciente = run(
        crear_paciente_os(
            session_factory, data, obra_social_id=obra.id
        )
    )
    respuesta = get_cobertura(
        api_client,
        data,
        paciente_id=paciente.id,
        prestacion_id=data["prestaciones"]["CONS"].id,
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "pendiente_verificacion"
    assert cuerpo["cobertura_porcentaje"] is None
    assert cuerpo["cobertura_monto"] is None


def test_paciente_con_obra_social_sin_afiliado_queda_pendiente(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    paciente = run(
        crear_paciente_os(session_factory, data, nro_afiliado=None)
    )
    respuesta = get_cobertura(
        api_client,
        data,
        paciente_id=paciente.id,
        prestacion_id=data["prestaciones"]["CONS"].id,
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "pendiente_verificacion"
    assert cuerpo["cobertura_monto"] is None


def test_paciente_o_prestacion_inexistente_devuelve_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    inexistente = get_cobertura(
        api_client,
        data,
        paciente_id=uuid.uuid4(),
        prestacion_id=data["prestaciones"]["CONS"].id,
    )
    assert inexistente.status_code == 404, inexistente.text

    sin_prestacion = get_cobertura(
        api_client,
        data,
        paciente_id=data["paciente_os_demo"].id,
        prestacion_id=uuid.uuid4(),
    )
    assert sin_prestacion.status_code == 404, sin_prestacion.text


def test_la_validacion_no_escribe(api_client, session_factory) -> None:
    """Business rule: a read-only consultation leaves every table untouched."""
    data = _setup(session_factory)
    run(
        _crear_escenario(
            session_factory, data
        )
    )
    antes = run(contar_tablas_mutables(session_factory))
    auditorias_antes = len(run(auditorias(session_factory)))

    assert (
        get_cobertura(
            api_client,
            data,
            paciente_id=data["paciente_os_demo"].id,
            prestacion_id=data["prestaciones"]["CONS"].id,
        ).status_code
        == 200
    )
    despues = run(contar_tablas_mutables(session_factory))
    assert despues == antes
    assert len(run(auditorias(session_factory))) == auditorias_antes


def test_solo_local_sin_campos_de_nomenclador(
    api_client, session_factory
) -> None:
    """Business rule: no caps, frequencies or external nomenclature (8.3)."""
    data = _setup(session_factory)
    espia = ProviderEspia()
    app.dependency_overrides[get_cobertura_provider] = lambda: espia
    try:
        respuesta = get_cobertura(
            api_client,
            data,
            paciente_id=data["paciente_os_demo"].id,
            prestacion_id=data["prestaciones"]["CONS"].id,
        )
    finally:
        app.dependency_overrides.pop(get_cobertura_provider, None)

    assert respuesta.status_code == 200, respuesta.text
    assert espia.llamadas == 1
    cuerpo = respuesta.json()
    assert set(cuerpo) == _CLAVES
    for prohibido in ("topes", "frecuencias", "nomenclador", "copago_porcentaje"):
        assert prohibido not in cuerpo


async def _crear_escenario(session_factory, data):
    from tests.integration.liquidaciones_helpers import crear_escenario

    return await crear_escenario(session_factory, data)
