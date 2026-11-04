"""Public booking: catalogue, availability, reservation, token and actions (C-07)."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.api.deps import get_redis
from app.domain.agenda import ARGENTINA_OFFSET
from app.infrastructure.tokens import create_single_use_token, hash_token
from app.main import app
from app.models import Paciente, Turno
from tests.integration.helpers import run
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import (
    consultorio_demo_id,
    create_profesional,
    create_sillon,
    seed_demo,
)
from tests.integration.turnos_helpers import (
    insertar_turno_db,
    prestacion_id,
)


def _hora(hora: int, minuto: int = 0, dia: int = 9) -> datetime:
    return datetime(2026, 11, dia, hora, minuto, tzinfo=ARGENTINA_OFFSET)


class FakeRedis:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[tuple[str, str]] = []

    async def rpush(self, queue: str, payload: str) -> int:
        self.calls.append((queue, payload))
        if not self.ok:
            raise RuntimeError("redis caído")
        return 1


def _setup(session_factory) -> dict[str, object]:
    run(seed_demo(session_factory))
    consultorio_id = run(consultorio_demo_id(session_factory))
    profesional = run(
        create_profesional(session_factory, consultorio_id, "MP-PUB-1")
    )
    return {
        "consultorio_id": consultorio_id,
        "profesional": profesional,
        "cons": run(prestacion_id(session_factory, "CONS")),
        "endo": run(prestacion_id(session_factory, "ENDO")),
    }


def _payload(base, **overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "nombre": "Publico",
        "apellido": "Demo",
        "dni": "43000111",
        "telefono": "11 8888-9999",
        "email": "publico.demo@example.test",
        "profesional_id": str(base["profesional"].id),
        "prestacion_id": str(base["cons"]),
        "inicio": _hora(9).isoformat(),
    }
    payload.update(overrides)
    return payload


def _reservar(api_client, base, **overrides):
    return api_client.post("/reservar/demo/turnos", json=_payload(base, **overrides))


def _fake_redis(api_client, fake: FakeRedis) -> None:
    app.dependency_overrides[get_redis] = lambda: fake


def _clear_redis_override() -> None:
    app.dependency_overrides.pop(get_redis, None)


def _contar(session_factory, model) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(select(func.count()).select_from(model))

    return run(contar())


def _contar_dni(session_factory, dni: str) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count())
                .select_from(Paciente)
                .where(Paciente.dni == dni)
            )

    return run(contar())


# --- Catálogo ---------------------------------------------------------------


def test_catalogo_publico_sin_token(api_client, session_factory) -> None:
    """Expected: catalogue is public and exposes no PII or tokens."""
    _setup(session_factory)
    respuesta = api_client.get("/reservar/demo")
    assert respuesta.status_code == 200, respuesta.text
    body = respuesta.json()
    assert body["slug"] == "demo"
    assert body["plazo_cancelacion_horas"] == 24
    assert body["politica_sena"]
    assert body["profesionales"]
    assert {item["codigo"] for item in body["prestaciones"]} >= {"CONS", "ENDO"}
    texto = respuesta.text.lower()
    assert "email" not in texto
    assert "token" not in texto
    assert "password" not in texto


def test_catalogo_de_consultorio_inexistente(api_client, session_factory) -> None:
    """Business error: unknown slugs are 404."""
    _setup(session_factory)
    assert api_client.get("/reservar/no-existe").status_code == 404


def test_catalogo_excluye_recursos_inactivos(api_client, session_factory) -> None:
    """Edge: soft-deleted professionals disappear from the public catalogue."""
    base = _setup(session_factory)

    async def baja() -> None:
        from app.models import Profesional

        async with session_factory() as session, session.begin():
            row = await session.get(Profesional, base["profesional"].id)
            assert row is not None
            row.is_active = False
            row.deleted_at = datetime.now(timezone.utc)

    run(baja())
    body = api_client.get("/reservar/demo").json()
    assert base["profesional"].id not in [
        item["id"] for item in body["profesionales"]
    ]


# --- Disponibilidad ---------------------------------------------------------


def test_disponibilidad_publica(api_client, session_factory) -> None:
    """Expected: real slots without JWT."""
    base = _setup(session_factory)
    respuesta = api_client.get(
        "/reservar/demo/disponibilidad",
        params={
            "fecha": "2026-11-09",
            "profesional_id": str(base["profesional"].id),
            "prestacion_id": str(base["cons"]),
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    assert len(respuesta.json()) == 6  # 09:00–12:00 in 30-minute slots


@pytest.mark.parametrize("campo", ["profesional_id", "prestacion_id"])
def test_disponibilidad_con_recurso_inexistente(
    api_client, session_factory, campo: str
) -> None:
    """Business error: unknown resources are 404."""
    base = _setup(session_factory)
    params = {
        "fecha": "2026-11-09",
        "profesional_id": str(base["profesional"].id),
        "prestacion_id": str(base["cons"]),
    }
    params[campo] = str(uuid.uuid4())
    assert (
        api_client.get("/reservar/demo/disponibilidad", params=params).status_code
        == 404
    )


def test_disponibilidad_fecha_invalida_o_parametro_extra(
    api_client, session_factory
) -> None:
    """Edge: the public endpoint keeps the strict boundary."""
    base = _setup(session_factory)
    assert (
        api_client.get(
            "/reservar/demo/disponibilidad",
            params={
                "fecha": "09-11-2026",
                "profesional_id": str(base["profesional"].id),
            },
        ).status_code
        == 422
    )
    assert (
        api_client.get(
            "/reservar/demo/disponibilidad",
            params={
                "fecha": "2026-11-09",
                "profesional_id": str(base["profesional"].id),
                "sillon_id": str(uuid.uuid4()),
            },
        ).status_code
        == 422
    )


def test_disponibilidad_dia_sin_atencion(api_client, session_factory) -> None:
    """Edge: a non-working day yields []."""
    base = _setup(session_factory)
    respuesta = api_client.get(
        "/reservar/demo/disponibilidad",
        params={
            "fecha": "2026-11-14",  # Saturday
            "profesional_id": str(base["profesional"].id),
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == []


# --- Reserva ----------------------------------------------------------------


def test_reserva_publica_crea_paciente_y_turno(api_client, session_factory) -> None:
    """Expected: new patient, normalized identity and a reserved turn."""
    base = _setup(session_factory)
    respuesta = _reservar(api_client, base)
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["estado"] == "reservado"
    assert body["inicio"].endswith("-03:00")
    assert "gestion_url" in body
    assert "paciente" not in respuesta.text.lower()

    async def leer() -> Paciente:
        async with session_factory() as session:
            paciente = await session.scalar(
                select(Paciente).where(Paciente.dni == "43000111")
            )
            assert paciente is not None
            return paciente

    paciente = run(leer())
    assert paciente.telefono == "+5491188889999"


def test_reserva_reutiliza_paciente_con_mismo_telefono(
    api_client, session_factory
) -> None:
    """Expected: same DNI + same phone reuses the patient row."""
    base = _setup(session_factory)
    assert _reservar(api_client, base).status_code == 201
    respuesta = _reservar(api_client, base, inicio=_hora(10).isoformat())
    assert respuesta.status_code == 201
    assert _contar_dni(session_factory, "43000111") == 1


def test_reserva_con_dni_y_telefono_distinto_es_409(
    api_client, session_factory
) -> None:
    """Business error: identity mismatch is not silently overwritten."""
    base = _setup(session_factory)
    assert _reservar(api_client, base).status_code == 201
    respuesta = _reservar(
        api_client, base, telefono="11 7777-0000", inicio=_hora(10).isoformat()
    )
    assert respuesta.status_code == 409, respuesta.text
    assert _contar_dni(session_factory, "43000111") == 1


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("telefono", "123"),
        ("telefono", "541188889999"),
        ("dni", "123456"),
        ("dni", "4300011A"),
    ],
)
def test_reserva_invalida_no_deja_residuos(
    api_client, session_factory, campo: str, valor: str
) -> None:
    """Edge: 422 before writing anything."""
    base = _setup(session_factory)
    payload = _payload(base)
    payload[campo] = valor
    respuesta = api_client.post("/reservar/demo/turnos", json=payload)
    assert respuesta.status_code == 422, respuesta.text
    assert _contar_dni(session_factory, "43000111") == 0
    assert _contar(session_factory, Turno) == 0


def test_reserva_con_solape_o_bloqueo(api_client, session_factory) -> None:
    """Business error: the public flow reuses C-06 anti-overlap and blocks."""
    base = _setup(session_factory)
    assert _reservar(api_client, base).status_code == 201
    solape = _reservar(api_client, base, dni="43000222", inicio=_hora(9, 15).isoformat())
    assert solape.status_code == 409, solape.text

    bloqueo = api_client.post(
        "/bloqueos",
        json={
            "profesional_id": str(base["profesional"].id),
            "desde": _hora(10).isoformat(),
            "hasta": _hora(11).isoformat(),
            "motivo": "Bloqueo público",
        },
    )
    # /bloqueos requires JWT, so create it through the DB instead.
    assert bloqueo.status_code == 401
    run(_bloquear_db(session_factory, base))
    en_bloqueo = _reservar(
        api_client, base, dni="43000333", inicio=_hora(10).isoformat()
    )
    assert en_bloqueo.status_code == 409, en_bloqueo.text


def _bloquear_db(session_factory, base):
    async def insertar() -> None:
        from app.models import Bloqueo

        async with session_factory() as session, session.begin():
            session.add(
                Bloqueo(
                    id=uuid.uuid4(),
                    profesional_id=base["profesional"].id,
                    desde=_hora(10),
                    hasta=_hora(11),
                    motivo="Bloqueo público",
                )
            )

    return insertar()


def test_dos_reservas_publicas_concurrentes(api_client, session_factory) -> None:
    """Edge: exactly one wins the same slot."""
    base = _setup(session_factory)
    payload = _payload(base)

    def reservar() -> int:
        return api_client.post("/reservar/demo/turnos", json=payload).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        estados = list(pool.map(lambda _: reservar(), range(2)))
    assert sorted(estados) == [201, 409], estados
    assert _contar(session_factory, Turno) == 1


# --- Sillón -----------------------------------------------------------------


def test_sillon_ocupado_por_otro_profesional(api_client, session_factory) -> None:
    """Edge: the backend skips a busy chair and uses the free one."""
    base = _setup(session_factory)
    otro = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-PUB-2"
        )
    )
    sillones = run(_sillones(session_factory, base["consultorio_id"]))
    paciente = run(
        create_paciente(
            session_factory,
            base["consultorio_id"],
            nombre="Otro",
            apellido="Demo",
            dni="43000444",
            telefono="+5491100000000",
        )
    )
    run(
        insertar_turno_db(
            session_factory,
            consultorio_id=base["consultorio_id"],
            paciente_id=paciente.id,
            profesional_id=otro.id,
            sillon_id=sillones[0].id,
            inicio=_hora(9),
            fin=_hora(10),
        )
    )
    respuesta = _reservar(api_client, base)
    assert respuesta.status_code == 201, respuesta.text
    assert _turno_sillon(session_factory, respuesta.json()["turno_id"]) == sillones[1].id


async def _sillones(session_factory, consultorio_id):
    from app.models import Sillon

    async with session_factory() as session:
        return list(
            await session.scalars(
                select(Sillon)
                .where(Sillon.consultorio_id == consultorio_id)
                .order_by(Sillon.nombre)
            )
        )


def _turno_sillon(session_factory, turno_id: str):
    async def leer():
        async with session_factory() as session:
            turno = await session.get(Turno, uuid.UUID(turno_id))
            assert turno is not None
            return turno.sillon_id

    return run(leer())


def test_prefiere_sillones_habilitados(api_client, session_factory) -> None:
    """Edge: habilitation restricts the candidate chairs."""
    base = _setup(session_factory)
    sillones = run(_sillones(session_factory, base["consultorio_id"]))

    async def habilitar() -> None:
        from app.models import ProfesionalSillon

        async with session_factory() as session, session.begin():
            session.add(
                ProfesionalSillon(
                    profesional_id=base["profesional"].id,
                    sillon_id=sillones[1].id,
                )
            )

    run(habilitar())
    otro = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-PUB-3"
        )
    )
    paciente = run(
        create_paciente(
            session_factory,
            base["consultorio_id"],
            nombre="Otro",
            apellido="Demo",
            dni="43000555",
            telefono="+5491100000001",
        )
    )
    run(
        insertar_turno_db(
            session_factory,
            consultorio_id=base["consultorio_id"],
            paciente_id=paciente.id,
            profesional_id=otro.id,
            sillon_id=sillones[1].id,
            inicio=_hora(9),
            fin=_hora(10),
        )
    )
    respuesta = _reservar(api_client, base)
    assert respuesta.status_code == 409, respuesta.text


def test_sillon_id_no_permitido(api_client, session_factory) -> None:
    """Business error: the patient cannot impose a physical chair."""
    base = _setup(session_factory)
    respuesta = _reservar(
        api_client,
        base,
        sillon_id=str(uuid.uuid4()),
    )
    assert respuesta.status_code == 422


# --- Seña -------------------------------------------------------------------


def test_reserva_con_sena_pendiente(api_client, session_factory) -> None:
    """Expected: ENDO requires a deposit; state is pending."""
    base = _setup(session_factory)
    respuesta = _reservar(api_client, base, prestacion_id=str(base["endo"]))
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["sena"]["requiere"] is True
    assert body["sena"]["estado"] == "pendiente"
    assert body["sena"]["monto"] == "10000.00"
    assert body["politica_sena"]


def test_reserva_sin_sena(api_client, session_factory) -> None:
    """Edge: CONS has no deposit."""
    base = _setup(session_factory)
    body = _reservar(api_client, base).json()
    assert body["sena"] == {"requiere": False, "monto": None, "estado": "no_requiere"}


def test_reserva_con_prestacion_inexistente(api_client, session_factory) -> None:
    """Business error: unknown service is 404."""
    base = _setup(session_factory)
    respuesta = _reservar(api_client, base, prestacion_id=str(uuid.uuid4()))
    assert respuesta.status_code == 404, respuesta.text


# --- Token y acciones -------------------------------------------------------


def _token_de(body: dict[str, object]) -> str:
    return str(body["gestion_url"]).rsplit("/", 1)[-1]


def test_token_guardado_solo_como_hash(api_client, session_factory) -> None:
    """Expected: the raw token is returned once and never stored."""
    base = _setup(session_factory)
    body = _reservar(api_client, base).json()
    token = _token_de(body)

    async def leer() -> tuple[str, str]:
        from app.models import TokenUnSoloUso

        async with session_factory() as session:
            registro = await session.scalar(
                select(TokenUnSoloUso).where(
                    TokenUnSoloUso.token_hash == hash_token(token)
                )
            )
            assert registro is not None
            assert registro.token_hash != token
            return registro.tipo, registro.entidad_tipo

    assert run(leer()) == ("gestion_turno", "turno")


def test_get_gestion_no_consume(api_client, session_factory) -> None:
    """Edge: viewing the summary twice is safe."""
    base = _setup(session_factory)
    token = _token_de(_reservar(api_client, base).json())
    primero = api_client.get(f"/reservar/gestion/{token}")
    segundo = api_client.get(f"/reservar/gestion/{token}")
    assert primero.status_code == segundo.status_code == 200
    assert primero.json() == segundo.json()


def test_token_usado_vencido_o_ajeno(api_client, session_factory) -> None:
    """Business error: invalid management tokens are 410."""
    base = _setup(session_factory)
    body = _reservar(api_client, base).json()
    token = _token_de(body)
    assert api_client.post(f"/reservar/gestion/{token}/cancelar").status_code == 200
    assert api_client.get(f"/reservar/gestion/{token}").status_code == 410

    otro = _reservar(
        api_client, base, dni="43000666", inicio=_hora(10).isoformat()
    ).json()
    otro_token = _token_de(otro)

    async def vencer() -> None:
        from app.models import TokenUnSoloUso

        async with session_factory() as session, session.begin():
            registro = await session.scalar(
                select(TokenUnSoloUso).where(
                    TokenUnSoloUso.token_hash == hash_token(otro_token)
                )
            )
            assert registro is not None
            registro.expira_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    run(vencer())
    assert api_client.get(f"/reservar/gestion/{otro_token}").status_code == 410

    async def token_ajeno() -> str:
        async with session_factory() as session, session.begin():
            iss = await create_single_use_token(
                session,
                tipo="recordatorio",
                entidad_tipo="turno",
                entidad_id=str(uuid.uuid4()),
            )
            return iss.token

    assert (
        api_client.get(f"/reservar/gestion/{run(token_ajeno())}").status_code
        == 410
    )
    assert api_client.get("/reservar/gestion/no-existe").status_code == 410


def test_confirmar_desde_el_enlace(api_client, session_factory) -> None:
    """Expected: confirmation consumes the token and changes state."""
    base = _setup(session_factory)
    token = _token_de(_reservar(api_client, base).json())
    respuesta = api_client.post(f"/reservar/gestion/{token}/confirmar")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "confirmado"
    assert api_client.get(f"/reservar/gestion/{token}").status_code == 410


def test_confirmar_turno_invalido_no_consume(api_client, session_factory) -> None:
    """Business error: an invalid transition is 422 and keeps the token."""
    base = _setup(session_factory)
    body = _reservar(api_client, base).json()
    token = _token_de(body)

    async def cancelar_db() -> None:
        async with session_factory() as session, session.begin():
            turno = await session.get(Turno, uuid.UUID(body["turno_id"]))
            assert turno is not None
            turno.estado = "cancelado"

    run(cancelar_db())
    assert api_client.post(f"/reservar/gestion/{token}/confirmar").status_code == 422
    assert api_client.get(f"/reservar/gestion/{token}").status_code == 200


def test_cancelar_dentro_y_fuera_del_plazo(api_client, session_factory) -> None:
    """Expected: inside is free; outside marks the deposit as lost."""
    base = _setup(session_factory)
    body = _reservar(api_client, base).json()
    dentro = api_client.post(
        f"/reservar/gestion/{_token_de(body)}/cancelar"
    )
    assert dentro.status_code == 200, dentro.text
    assert dentro.json() == {"estado": "cancelado", "sena_perdida": False}

    con_sena = _reservar(
        api_client,
        base,
        dni="43000777",
        inicio=_hora(10).isoformat(),
        prestacion_id=str(base["endo"]),
    ).json()

    async def adelantar() -> None:
        async with session_factory() as session, session.begin():
            turno = await session.get(Turno, uuid.UUID(con_sena["turno_id"]))
            assert turno is not None
            turno.inicio = datetime.now(timezone.utc) + timedelta(hours=1)
            turno.fin = turno.inicio + timedelta(minutes=90)

    run(adelantar())
    fuera = api_client.post(
        f"/reservar/gestion/{_token_de(con_sena)}/cancelar"
    )
    assert fuera.status_code == 200, fuera.text
    assert fuera.json() == {"estado": "cancelado", "sena_perdida": True}


def test_cancelaciones_concurrentes_con_el_mismo_token(
    api_client, session_factory
) -> None:
    """Edge: the token is single-use even under concurrency."""
    base = _setup(session_factory)
    token = _token_de(_reservar(api_client, base).json())

    def cancelar() -> int:
        return api_client.post(
            f"/reservar/gestion/{token}/cancelar"
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        estados = list(pool.map(lambda _: cancelar(), range(2)))
    assert sorted(estados) == [200, 410], estados


# --- WhatsApp ---------------------------------------------------------------


def test_whatsapp_encolado(api_client, session_factory) -> None:
    """Expected: a successful RPUSH reports `encolada`."""
    base = _setup(session_factory)
    fake = FakeRedis(ok=True)
    _fake_redis(api_client, fake)
    try:
        respuesta = _reservar(api_client, base)
    finally:
        _clear_redis_override()
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["whatsapp_confirmacion"] == "encolada"
    assert fake.calls and fake.calls[0][0] == "whatsapp:send"
    assert respuesta.json()["turno_id"] in fake.calls[0][1]


def test_whatsapp_caido_no_rompe_la_reserva(api_client, session_factory) -> None:
    """Edge: Redis failure is reported without rollback."""
    base = _setup(session_factory)
    fake = FakeRedis(ok=False)
    _fake_redis(api_client, fake)
    try:
        respuesta = _reservar(api_client, base)
    finally:
        _clear_redis_override()
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["whatsapp_confirmacion"] == "pendiente_reintento"
    assert _contar(session_factory, Turno) == 1
