"""Service catalogue: duration, price and optional deposit (C-04, RN-TU-08)."""

import pytest

from tests.integration.helpers import run
from tests.integration.recursos_helpers import (
    bearer,
    create_actor,
    seed_demo,
)


def _payload(codigo: str = "PRUEBA") -> dict[str, object]:
    return {
        "codigo": codigo,
        "nombre": "Prestación de prueba",
        "duracion_min": 45,
        "precio_base": "15000.00",
        "especialidad": "general",
        "requiere_sena": False,
        "monto_sena": None,
    }


def _setup(session_factory) -> dict[str, object]:
    run(seed_demo(session_factory))
    return {
        rol: run(create_actor(session_factory, rol))
        for rol in (
            "administrador",
            "odontologo",
            "recepcionista",
            "asistente",
            "auditor",
        )
    }


def test_alta_de_prestacion_y_lectura(api_client, session_factory) -> None:
    """Expected: admin creates and reception reads the catalogue (201/200)."""
    actores = _setup(session_factory)
    created = api_client.post(
        "/prestaciones",
        json=_payload("CONS2"),
        headers=bearer(actores["administrador"]),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["codigo"] == "CONS2"
    assert body["duracion_min"] == 45
    assert float(body["precio_base"]) == 15000.0

    listed = api_client.get(
        "/prestaciones", headers=bearer(actores["recepcionista"])
    )
    assert listed.status_code == 200, listed.text
    assert "CONS2" in {item["codigo"] for item in listed.json()}


def test_codigo_duplicado_devuelve_409(api_client, session_factory) -> None:
    """Business error: active codes are unique, case-insensitively normalized."""
    actores = _setup(session_factory)
    headers = bearer(actores["administrador"])
    assert (
        api_client.post(
            "/prestaciones", json=_payload("DUP"), headers=headers
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            "/prestaciones", json=_payload("dup"), headers=headers
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "rol", ["odontologo", "recepcionista", "asistente", "auditor"]
)
def test_escritura_por_rol_no_administrador(
    api_client, session_factory, rol: str
) -> None:
    """Business error: only admin writes the catalogue."""
    actores = _setup(session_factory)
    headers = bearer(actores[rol])
    created = api_client.get(
        "/prestaciones", headers=bearer(actores["administrador"])
    )
    prestacion_id = next(
        item["id"] for item in created.json() if item["codigo"] == "CONS"
    )

    assert (
        api_client.post(
            "/prestaciones", json=_payload("ROL"), headers=headers
        ).status_code
        == 403
    )
    assert (
        api_client.put(
            f"/prestaciones/{prestacion_id}",
            json=_payload("CONS"),
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        api_client.delete(
            f"/prestaciones/{prestacion_id}", headers=headers
        ).status_code
        == 403
    )


def test_baja_logica_libera_el_codigo(api_client, session_factory) -> None:
    """Edge: a soft-deleted code can be reused and leaves the catalogue."""
    actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    created = api_client.post(
        "/prestaciones", json=_payload("LIBRE"), headers=headers
    )
    assert created.status_code == 201
    prestacion_id = created.json()["id"]
    assert (
        api_client.delete(
            f"/prestaciones/{prestacion_id}", headers=headers
        ).status_code
        == 204
    )

    again = api_client.post(
        "/prestaciones", json=_payload("LIBRE"), headers=headers
    )
    assert again.status_code == 201, again.text
    assert again.json()["id"] != prestacion_id

    listed = api_client.get("/prestaciones", headers=headers)
    ids = {item["id"] for item in listed.json()}
    assert prestacion_id not in ids
    assert again.json()["id"] in ids


@pytest.mark.parametrize(
    "cambio",
    [
        {"duracion_min": 0},
        {"duracion_min": -5},
        {"precio_base": "-0.01"},
    ],
)
def test_duracion_o_precio_fuera_de_rango(
    api_client, session_factory, cambio: dict[str, object]
) -> None:
    """Edge: duration must be positive and price non-negative."""
    actores = _setup(session_factory)
    payload = {**_payload("RANGO"), **cambio}
    response = api_client.post(
        "/prestaciones",
        json=payload,
        headers=bearer(actores["administrador"]),
    )
    assert response.status_code == 422, response.text


def test_prestacion_con_sena_y_monto_visible(
    api_client, session_factory
) -> None:
    """Expected: a required deposit exposes its amount (RN-TU-08)."""
    actores = _setup(session_factory)
    payload = {
        **_payload("SENA"),
        "requiere_sena": True,
        "monto_sena": "5000.00",
    }
    created = api_client.post(
        "/prestaciones",
        json=payload,
        headers=bearer(actores["administrador"]),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["requiere_sena"] is True
    assert float(body["monto_sena"]) == 5000.0


def test_sena_exigida_sin_monto_devuelve_422(
    api_client, session_factory
) -> None:
    """Business error: requires_sena=true without amount violates RN-TU-08."""
    actores = _setup(session_factory)
    payload = {
        **_payload("SENA-SIN"),
        "requiere_sena": True,
        "monto_sena": None,
    }
    response = api_client.post(
        "/prestaciones",
        json=payload,
        headers=bearer(actores["administrador"]),
    )
    assert response.status_code == 422, response.text


def test_monto_sin_seña_exigida_devuelve_422(
    api_client, session_factory
) -> None:
    """Edge: an amount without a required deposit is incoherent."""
    actores = _setup(session_factory)
    payload = {
        **_payload("SENA-NO"),
        "requiere_sena": False,
        "monto_sena": "5000.00",
    }
    response = api_client.post(
        "/prestaciones",
        json=payload,
        headers=bearer(actores["administrador"]),
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("monto", ["0", "-1.00"])
def test_monto_de_sena_no_positivo_devuelve_422(
    api_client, session_factory, monto: str
) -> None:
    """Edge: a deposit must be strictly positive."""
    actores = _setup(session_factory)
    payload = {
        **_payload("SENA-CERO"),
        "requiere_sena": True,
        "monto_sena": monto,
    }
    response = api_client.post(
        "/prestaciones",
        json=payload,
        headers=bearer(actores["administrador"]),
    )
    assert response.status_code == 422, response.text


def test_quitar_la_sena_persiste_monto_nulo(
    api_client, session_factory
) -> None:
    """Edge: switching to no deposit clears the stored amount."""
    actores = _setup(session_factory)
    headers = bearer(actores["administrador"])
    created = api_client.post(
        "/prestaciones",
        json={
            **_payload("SENA-OFF"),
            "requiere_sena": True,
            "monto_sena": "5000.00",
        },
        headers=headers,
    )
    assert created.status_code == 201
    prestacion_id = created.json()["id"]

    updated = api_client.put(
        f"/prestaciones/{prestacion_id}",
        json=_payload("SENA-OFF"),
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["requiere_sena"] is False
    assert updated.json()["monto_sena"] is None
