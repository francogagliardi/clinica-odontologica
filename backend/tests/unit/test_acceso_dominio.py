"""Unit tests for the pure access-management helpers (C-16, task 2.1).

No database, no network: email normalization, the fixed five-role catalogue,
the stable audit action names, role-list validation and the viewer pagination.
"""

import pytest

from app.domain.acceso import (
    ACCIONES_AUDITORIA,
    LIMITE_DEFAULT,
    LIMITE_MAXIMO,
    ROLES_CATALOGO,
    calcular_paginacion,
    es_email_valido,
    normalizar_email,
    validar_paginacion,
    validar_roles,
)
from app.seed import ROLES as ROLES_SEMBRADOS


def test_normaliza_email_a_minusculas_y_sin_espacios() -> None:
    assert (
        normalizar_email("  Admin.Demo@Clinica.TEST ")
        == "admin.demo@clinica.test"
    )
    assert normalizar_email("ya@minuscula.test") == "ya@minuscula.test"
    # Idempotent: normalizing an already canonical address changes nothing.
    assert normalizar_email(normalizar_email(" MiXeD@Case.TEST ")) == (
        "mixed@case.test"
    )


@pytest.mark.parametrize(
    "email",
    [
        "admin@clinica.test",
        "nombre.apellido@sub.dominio.com.ar",
        "usuario+etiqueta@example.test",
    ],
)
def test_emails_validos(email: str) -> None:
    assert es_email_valido(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "",
        "sin-arroba",
        "a@b",
        "a b@clinica.test",
        "@clinica.test",
        "admin@",
        "admin@@clinica.test",
    ],
)
def test_emails_invalidos(email: str) -> None:
    assert es_email_valido(email) is False


def test_catalogo_fijo_de_cinco_roles() -> None:
    assert ROLES_CATALOGO == (
        "administrador",
        "odontologo",
        "recepcionista",
        "asistente",
        "auditor",
    )
    assert len(ROLES_CATALOGO) == 5
    assert ROLES_CATALOGO == tuple(ROLES_SEMBRADOS)


def test_nombres_de_accion_de_auditoria_estables() -> None:
    assert ACCIONES_AUDITORIA == {
        "usuario.crear",
        "usuario.editar",
        "usuario.password",
        "usuario.roles",
        "usuario.activar",
        "usuario.desactivar",
    }


def test_validar_roles_acepta_y_deduplica_en_orden_de_entrada() -> None:
    assert validar_roles(["odontologo", "asistente"]) == (
        "odontologo",
        "asistente",
    )
    assert validar_roles(
        ["odontologo", "odontologo", "asistente", "odontologo"]
    ) == ("odontologo", "asistente")


def test_validar_roles_rechaza_lista_vacia() -> None:
    with pytest.raises(ValueError):
        validar_roles([])


def test_validar_roles_rechaza_rol_desconocido() -> None:
    with pytest.raises(ValueError):
        validar_roles(["superadmin"])
    with pytest.raises(ValueError):
        validar_roles(["odontologo", "desconocido"])


def test_validar_roles_es_case_sensitive() -> None:
    # The catalogue names are exact: another casing is an unknown role (422).
    with pytest.raises(ValueError):
        validar_roles(["Administrador"])
    with pytest.raises(ValueError):
        validar_roles(["ODONTOLOGO"])


def test_paginacion_calcula_paginas_y_bordes() -> None:
    assert LIMITE_DEFAULT == 100
    assert LIMITE_MAXIMO == 500

    primera = calcular_paginacion(250)
    assert primera.total == 250
    assert primera.total_paginas == 3
    assert primera.pagina_actual == 1
    assert primera.hay_siguiente is True
    assert primera.hay_anterior is False

    ultima = calcular_paginacion(250, limite=100, offset=200)
    assert ultima.pagina_actual == 3
    assert ultima.hay_siguiente is False
    assert ultima.hay_anterior is True

    exacta = calcular_paginacion(100, limite=100, offset=0)
    assert exacta.total_paginas == 1
    assert exacta.hay_siguiente is False

    vacia = calcular_paginacion(0)
    assert vacia.total_paginas == 0
    assert vacia.pagina_actual == 1
    assert vacia.hay_siguiente is False
    assert vacia.hay_anterior is False


def test_paginacion_rechaza_limites_fuera_de_rango() -> None:
    with pytest.raises(ValueError):
        validar_paginacion(limite=0, offset=0)
    with pytest.raises(ValueError):
        validar_paginacion(limite=LIMITE_MAXIMO + 1, offset=0)
    with pytest.raises(ValueError):
        validar_paginacion(limite=100, offset=-1)
    # The boundaries themselves are accepted.
    validar_paginacion(limite=1, offset=0)
    validar_paginacion(limite=LIMITE_MAXIMO, offset=0)
