"""Base availability endpoint: slots, blocks and observable errors (C-04)."""

import uuid
from datetime import datetime, timedelta, timezone

from tests.integration.helpers import run
from tests.integration.recursos_helpers import (
    bearer,
    consultorio_demo_id,
    create_actor,
    create_profesional,
    create_sillon,
    seed_demo,
)

LUNES = "2026-11-02"
SABADO = "2026-11-07"
OFFSET = timezone(timedelta(hours=-3))


def _setup(session_factory) -> dict[str, object]:
    run(seed_demo(session_factory))
    consultorio_id = run(consultorio_demo_id(session_factory))
    actores = {
        rol: run(create_actor(session_factory, rol))
        for rol in ("administrador", "recepcionista")
    }
    profesional = run(
        create_profesional(
            session_factory,
            consultorio_id,
            "MP-DISP",
            hora_desde=datetime(2026, 1, 1, 9, 0).time(),
            hora_hasta=datetime(2026, 1, 1, 12, 0).time(),
        )
    )
    sillon = run(create_sillon(session_factory, consultorio_id, "Box Disp"))
    return {
        "actores": actores,
        "profesional": profesional,
        "sillon": sillon,
        "consultorio_id": consultorio_id,
    }


def _get(api_client, ctx, query: str = ""):
    return api_client.get(
        f"/profesionales/{ctx['profesional'].id}/disponibilidad?fecha={LUNES}{query}",
        headers=bearer(ctx["actores"]["recepcionista"]),
    )


def test_disponibilidad_con_duracion_base(api_client, session_factory) -> None:
    """Expected: three one-hour slots between 09:00 and 12:00."""
    ctx = _setup(session_factory)
    response = _get(api_client, ctx)
    assert response.status_code == 200, response.text
    slots = response.json()
    assert len(slots) == 3
    assert slots[0]["inicio"].startswith("2026-11-02T09:00:00")
    assert slots[-1]["fin"].startswith("2026-11-02T12:00:00")


def test_disponibilidad_usa_duracion_de_la_prestacion(
    api_client, session_factory
) -> None:
    """Expected: the service duration overrides the professional base (RN-TU-02)."""
    ctx = _setup(session_factory)
    prestaciones = api_client.get(
        "/prestaciones", headers=bearer(ctx["actores"]["recepcionista"])
    )
    cons = next(
        item for item in prestaciones.json() if item["codigo"] == "CONS"
    )
    response = _get(api_client, ctx, f"&prestacion_id={cons['id']}")
    assert response.status_code == 200, response.text
    assert len(response.json()) == 6  # 30-minute slots in a 3-hour window


def test_disponibilidad_de_profesional_inexistente_o_inactivo(
    api_client, session_factory
) -> None:
    """Business error: unknown or soft-deleted professionals return 404."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["recepcionista"])

    missing = api_client.get(
        f"/profesionales/{uuid.uuid4()}/disponibilidad?fecha={LUNES}",
        headers=headers,
    )
    assert missing.status_code == 404

    assert (
        api_client.delete(
            f"/profesionales/{ctx['profesional'].id}",
            headers=bearer(ctx["actores"]["administrador"]),
        ).status_code
        == 204
    )
    inactive = api_client.get(
        f"/profesionales/{ctx['profesional'].id}/disponibilidad?fecha={LUNES}",
        headers=headers,
    )
    assert inactive.status_code == 404


def test_disponibilidad_de_sillon_inexistente_o_inactivo(
    api_client, session_factory
) -> None:
    """Business error: a non-bookable chair returns 404."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["recepcionista"])

    missing = _get(api_client, ctx, f"&sillon_id={uuid.uuid4()}")
    assert missing.status_code == 404

    assert (
        api_client.delete(
            f"/sillones/{ctx['sillon'].id}",
            headers=bearer(ctx["actores"]["administrador"]),
        ).status_code
        == 204
    )
    inactive = _get(api_client, ctx, f"&sillon_id={ctx['sillon'].id}")
    assert inactive.status_code == 404


def test_dia_fuera_de_atencion_devuelve_lista_vacia(
    api_client, session_factory
) -> None:
    """Edge: a Saturday outside dias_atencion yields 200 with no slots."""
    ctx = _setup(session_factory)
    response = api_client.get(
        f"/profesionales/{ctx['profesional'].id}/disponibilidad?fecha={SABADO}",
        headers=bearer(ctx["actores"]["recepcionista"]),
    )
    assert response.status_code == 200
    assert response.json() == []


def test_fecha_invalida_o_parametros_extra(
    api_client, session_factory
) -> None:
    """Edge: bad date and unknown query params are rejected with 422."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["recepcionista"])

    assert (
        api_client.get(
            f"/profesionales/{ctx['profesional'].id}/disponibilidad?fecha=nope",
            headers=headers,
        ).status_code
        == 422
    )
    assert _get(api_client, ctx, "&extra=1").status_code == 422


def test_prestacion_inexistente_o_inactiva(
    api_client, session_factory
) -> None:
    """Business error: an unknown or soft-deleted service returns 404."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["recepcionista"])
    admin = bearer(ctx["actores"]["administrador"])

    assert _get(api_client, ctx, f"&prestacion_id={uuid.uuid4()}").status_code == 404

    prestaciones = api_client.get("/prestaciones", headers=headers)
    cons = next(
        item for item in prestaciones.json() if item["codigo"] == "CONS"
    )
    assert (
        api_client.delete(
            f"/prestaciones/{cons['id']}", headers=admin
        ).status_code
        == 204
    )
    assert _get(api_client, ctx, f"&prestacion_id={cons['id']}").status_code == 404


def _crear_bloqueo(api_client, ctx, payload: dict[str, object]) -> dict:
    response = api_client.post(
        "/bloqueos",
        json=payload,
        headers=bearer(ctx["actores"]["administrador"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_bloqueo_de_profesional_quita_slots_y_su_baja_los_restaura(
    api_client, session_factory
) -> None:
    """Expected/edge: a professional block removes slots; soft delete restores."""
    ctx = _setup(session_factory)
    desde = datetime(2026, 11, 2, 10, 0, tzinfo=OFFSET)
    bloqueo = _crear_bloqueo(
        api_client,
        ctx,
        {
            "profesional_id": str(ctx["profesional"].id),
            "sillon_id": None,
            "desde": desde.isoformat(),
            "hasta": (desde + timedelta(minutes=30)).isoformat(),
            "motivo": "Licencia",
        },
    )

    con_bloqueo = _get(api_client, ctx)
    assert con_bloqueo.status_code == 200
    assert [slot["inicio"][11:16] for slot in con_bloqueo.json()] == [
        "09:00",
        "11:00",
    ]

    assert (
        api_client.delete(
            f"/bloqueos/{bloqueo['id']}",
            headers=bearer(ctx["actores"]["administrador"]),
        ).status_code
        == 204
    )
    sin_bloqueo = _get(api_client, ctx)
    assert [slot["inicio"][11:16] for slot in sin_bloqueo.json()] == [
        "09:00",
        "10:00",
        "11:00",
    ]


def test_bloqueo_de_sillon_solo_afecta_la_consulta_con_sillon(
    api_client, session_factory
) -> None:
    """Expected: a chair block applies only when that chair is queried."""
    ctx = _setup(session_factory)
    desde = datetime(2026, 11, 2, 9, 0, tzinfo=OFFSET)
    _crear_bloqueo(
        api_client,
        ctx,
        {
            "profesional_id": None,
            "sillon_id": str(ctx["sillon"].id),
            "desde": desde.isoformat(),
            "hasta": (desde + timedelta(minutes=15)).isoformat(),
            "motivo": "Mantenimiento",
        },
    )

    con_sillon = _get(api_client, ctx, f"&sillon_id={ctx['sillon'].id}")
    assert [slot["inicio"][11:16] for slot in con_sillon.json()] == [
        "10:00",
        "11:00",
    ]

    sin_sillon = _get(api_client, ctx)
    assert [slot["inicio"][11:16] for slot in sin_sillon.json()] == [
        "09:00",
        "10:00",
        "11:00",
    ]


def test_bloqueo_de_otro_profesional_no_afecta(
    api_client, session_factory
) -> None:
    """Edge: the availability of B ignores blocks of professional A."""
    ctx = _setup(session_factory)
    otro = run(
        create_profesional(
            session_factory, ctx["consultorio_id"], "MP-OTRO-DISP"
        )
    )
    desde = datetime(2026, 11, 2, 9, 0, tzinfo=OFFSET)
    _crear_bloqueo(
        api_client,
        ctx,
        {
            "profesional_id": str(otro.id),
            "sillon_id": None,
            "desde": desde.isoformat(),
            "hasta": (desde + timedelta(hours=1)).isoformat(),
            "motivo": "Licencia",
        },
    )

    response = _get(api_client, ctx)
    assert response.status_code == 200
    assert [slot["inicio"][11:16] for slot in response.json()] == [
        "09:00",
        "10:00",
        "11:00",
    ]
