"""C-14 group 7: receipt API, simulated delivery and manual retry."""

import uuid
from datetime import timedelta

from app.api.deps import get_redis, get_whatsapp_client
from app.application.comprobantes import procesar_comprobante
from app.infrastructure.arca import TestArcaClient
from app.infrastructure.whatsapp import TestWhatsAppClient
from app.main import app
from tests.integration.clinica_helpers import auditorias
from tests.integration.comprobantes_helpers import (
    FakeRedis,
    comprobante_de_cobro,
    crear_comprobante_pendiente,
    envios_de,
    fiscal_config,
    hoy,
    paciente_db,
    post_efectivo,
    setup_comprobantes,
)
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_comprobantes(session_factory))


def _emitir(session_factory, comprobante_id):
    return run(
        procesar_comprobante(
            session_factory,
            TestArcaClient(),
            comprobante_id,
            config=fiscal_config(),
        )
    )


def test_get_lista_por_cobro_paciente_estado_tipo_y_fechas(
    api_client, session_factory
) -> None:
    """Expected: every declared filter narrows the consultorio list."""
    data = _setup(session_factory)
    body = post_efectivo(api_client, data)

    async def leer():
        return await comprobante_de_cobro(
            session_factory, uuid.UUID(body["id"])
        )

    comprobante = run(leer())
    assert comprobante is not None
    headers = bearer(data["actores"]["auditor"])
    base = "/comprobantes"

    def get(**params):
        return api_client.get(base, params=params, headers=headers)

    assert [fila["id"] for fila in get().json()] == [str(comprobante.id)]
    assert [
        fila["id"]
        for fila in get(cobro_id=body["id"]).json()
    ] == [str(comprobante.id)]
    assert [
        fila["id"]
        for fila in get(
            paciente_id=str(paciente_db(data).id)
        ).json()
    ] == [str(comprobante.id)]
    assert [
        fila["id"] for fila in get(estado="pendiente").json()
    ] == [str(comprobante.id)]
    assert get(estado="emitido").json() == []
    assert [
        fila["id"] for fila in get(tipo="B").json()
    ] == [str(comprobante.id)]
    assert get(tipo="C").json() == []
    assert [
        fila["id"]
        for fila in get(
            desde=hoy().isoformat(), hasta=hoy().isoformat()
        ).json()
    ] == [str(comprobante.id)]
    assert get(desde=(hoy() + timedelta(days=1)).isoformat()).json() == []


def test_filtro_no_declarado_devuelve_422(
    api_client, session_factory
) -> None:
    """Business error: an undeclared query parameter is rejected, not ignored."""
    data = _setup(session_factory)
    respuesta = api_client.get(
        "/comprobantes",
        params={"inventado": "1"},
        headers=bearer(data["actores"]["administrador"]),
    )
    assert respuesta.status_code == 422, respuesta.text


def test_detalle_incluye_cae_y_qr_cuando_esta_emitido(
    api_client, session_factory
) -> None:
    """Expected: detail exposes fiscal data only after emission."""
    data = _setup(session_factory)
    body = post_efectivo(api_client, data)

    async def leer():
        return await comprobante_de_cobro(
            session_factory, uuid.UUID(body["id"])
        )

    comprobante = run(leer())
    assert comprobante is not None
    _emitir(session_factory, comprobante.id)

    respuesta = api_client.get(
        f"/comprobantes/{comprobante.id}",
        headers=bearer(data["actores"]["odontologo"]),
    )
    assert respuesta.status_code == 200, respuesta.text
    detalle = respuesta.json()
    assert detalle["estado"] == "emitido"
    assert len(detalle["cae"]) == 14
    assert detalle["numero_fiscal"] == 1
    assert detalle["qr_fiscal"].startswith(
        "https://www.afip.gob.ar/fe/qr/?p="
    )
    assert detalle["fecha_emision_fiscal"] is not None


def test_detalle_inexistente_devuelve_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = api_client.get(
        f"/comprobantes/{uuid.uuid4()}",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert respuesta.status_code == 404, respuesta.text


def test_envio_whatsapp_simulado(
    api_client, session_factory
) -> None:
    """Expected: 201, persisted delivery and the `factura` template, no network."""
    data = _setup(session_factory)
    body = post_efectivo(api_client, data)
    comprobante_id = run(
        comprobante_de_cobro(session_factory, uuid.UUID(body["id"]))
    ).id
    _emitir(session_factory, comprobante_id)

    cliente = TestWhatsAppClient()
    app.dependency_overrides[get_whatsapp_client] = lambda: cliente
    try:
        respuesta = api_client.post(
            f"/comprobantes/{comprobante_id}/enviar",
            json={"canal": "whatsapp"},
            headers=bearer(data["actores"]["recepcionista"]),
        )
    finally:
        app.dependency_overrides.pop(get_whatsapp_client, None)

    assert respuesta.status_code == 201, respuesta.text
    envio = respuesta.json()
    assert envio["canal"] == "whatsapp"
    assert envio["destino"] == paciente_db(data).telefono
    assert envio["estado"] == "registrado"
    assert envio["proveedor_mensaje_id"].startswith("test-")

    assert len(cliente.enviados) == 1
    assert cliente.enviados[0]["plantilla"] == "factura"
    variables = cliente.enviados[0]["variables"]
    assert variables["numero"] == 1
    assert len(variables["cae"]) == 14
    assert variables["qr"].startswith("https://www.afip.gob.ar/fe/qr/?p=")

    assert len(run(envios_de(session_factory, comprobante_id))) == 1


def test_envio_repetido_devuelve_200_sin_duplicar(
    api_client, session_factory
) -> None:
    """Edge: repeating the delivery returns the existing row and one audit."""
    data = _setup(session_factory)
    body = post_efectivo(api_client, data)
    comprobante_id = run(
        comprobante_de_cobro(session_factory, uuid.UUID(body["id"]))
    ).id
    _emitir(session_factory, comprobante_id)
    headers = bearer(data["actores"]["recepcionista"])

    primera = api_client.post(
        f"/comprobantes/{comprobante_id}/enviar",
        json={"canal": "whatsapp"},
        headers=headers,
    )
    segunda = api_client.post(
        f"/comprobantes/{comprobante_id}/enviar",
        json={"canal": "whatsapp"},
        headers=headers,
    )
    assert primera.status_code == 201, primera.text
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["id"] == primera.json()["id"]
    assert len(run(envios_de(session_factory, comprobante_id))) == 1
    assert len(run(auditorias(session_factory, "comprobante.enviar"))) == 1


def test_envio_de_comprobante_no_emitido_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: there is no fiscal invoice to send while pending."""
    data = _setup(session_factory)
    body = post_efectivo(api_client, data)
    comprobante_id = run(
        comprobante_de_cobro(session_factory, uuid.UUID(body["id"]))
    ).id
    respuesta = api_client.post(
        f"/comprobantes/{comprobante_id}/enviar",
        json={"canal": "whatsapp"},
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert respuesta.status_code == 409, respuesta.text
    assert run(envios_de(session_factory, comprobante_id)) == []


def test_envio_de_comprobante_fallido_devuelve_409(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(
            session_factory, data, numero_interno=1, estado="fallido"
        )
    )
    respuesta = api_client.post(
        f"/comprobantes/{comprobante_id}/enviar",
        json={"canal": "whatsapp"},
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert respuesta.status_code == 409, respuesta.text


def test_envio_con_destino_invalido_o_canal_no_soportado_es_422(
    api_client, session_factory
) -> None:
    """Business error: bad destination or email channel leaves no row."""
    data = _setup(session_factory)
    body = post_efectivo(api_client, data)
    comprobante_id = run(
        comprobante_de_cobro(session_factory, uuid.UUID(body["id"]))
    ).id
    _emitir(session_factory, comprobante_id)
    headers = bearer(data["actores"]["recepcionista"])

    for payload in (
        {"canal": "whatsapp", "destino": "no-es-telefono"},
        {"canal": "whatsapp", "destino": "   "},
        {"canal": "email"},
    ):
        respuesta = api_client.post(
            f"/comprobantes/{comprobante_id}/enviar",
            json=payload,
            headers=headers,
        )
        assert respuesta.status_code == 422, respuesta.text
    assert run(envios_de(session_factory, comprobante_id)) == []


def test_reintento_de_fallido_vuelve_a_pendiente_y_encola(
    api_client, session_factory
) -> None:
    """Expected: reset retries, stay pending and enqueue the job."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(
            session_factory,
            data,
            numero_interno=1,
            estado="fallido",
            intentos=5,
        )
    )
    fake = FakeRedis()
    app.dependency_overrides[get_redis] = lambda: fake
    try:
        respuesta = api_client.post(
            f"/comprobantes/{comprobante_id}/reintentar",
            headers=bearer(data["actores"]["administrador"]),
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["intentos"] == 0
    assert cuerpo["proximo_intento"] is None
    assert cuerpo["ultimo_error"] is None
    assert ("arca:emitir", str(comprobante_id)) in fake.items
    assert len(run(auditorias(session_factory, "comprobante.reintentar"))) == 1


def test_reintento_de_emitido_es_no_op(
    api_client, session_factory
) -> None:
    """Edge: an emitted receipt keeps its CAE and queues nothing."""
    data = _setup(session_factory)
    body = post_efectivo(api_client, data)
    comprobante_id = run(
        comprobante_de_cobro(session_factory, uuid.UUID(body["id"]))
    ).id
    emitido = _emitir(session_factory, comprobante_id)
    fake = FakeRedis()
    app.dependency_overrides[get_redis] = lambda: fake
    try:
        respuesta = api_client.post(
            f"/comprobantes/{comprobante_id}/reintentar",
            headers=bearer(data["actores"]["administrador"]),
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "emitido"
    assert respuesta.json()["cae"] == emitido.cae
    assert fake.items == []
    assert run(auditorias(session_factory, "comprobante.reintentar")) == []


def test_reintento_de_inexistente_devuelve_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = api_client.post(
        f"/comprobantes/{uuid.uuid4()}/reintentar",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert respuesta.status_code == 404, respuesta.text
