"""Public privacy policy endpoints (C-16, task 7.2).

`GET /privacidad` and `/privacidad/{version}` are anonymous, read-only and
contain only the versioned public text with its stable SHA-256. An unknown
version is 404 without leaking another version.
"""

import hashlib

import pytest

from app.domain.privacidad import VERSION_ACTUAL

URL = "/privacidad"


@pytest.mark.anyio
async def test_politica_vigente_sin_token(api_client) -> None:
    response = api_client.get(URL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == VERSION_ACTUAL
    assert body["alcance_legal_validado"] is False
    assert body["vigente_desde"]
    assert len(body["hash"]) == 64
    assert body["hash"] == hashlib.sha256(
        body["texto"].encode("utf-8")
    ).hexdigest()
    assert VERSION_ACTUAL in body["texto"]
    # Public content, not a session or a data dump.
    assert "access_token" not in body
    assert "@" not in body["texto"]


@pytest.mark.anyio
async def test_version_explicita_coincide_con_la_vigente(api_client) -> None:
    actual = api_client.get(URL).json()
    versionada = api_client.get(f"{URL}/{VERSION_ACTUAL}")
    assert versionada.status_code == 200, versionada.text
    assert versionada.json() == actual


@pytest.mark.anyio
async def test_version_desconocida_404_sin_filtrar_texto(api_client) -> None:
    vigente = api_client.get(URL).json()
    response = api_client.get(f"{URL}/v9999-01-01")
    assert response.status_code == 404, response.text
    assert vigente["texto"] not in response.text
    assert vigente["hash"] not in response.text


@pytest.mark.anyio
async def test_parametro_no_declarado_y_escritura(api_client) -> None:
    assert api_client.get(f"{URL}?version=x").status_code == 422
    assert api_client.post(URL, json={}).status_code == 405
