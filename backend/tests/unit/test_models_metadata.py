"""Unit tests for the security model contract (no database required)."""

from sqlalchemy import CheckConstraint, Uuid

from app.models import (
    Base,
    Bloqueo,
    Consultorio,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    RegistroAuditoria,
    Rol,
    Sillon,
    TokenUnSoloUso,
    Usuario,
    UsuarioRol,
)

EXPECTED_TABLES = {
    "consultorios",
    "roles",
    "usuarios",
    "usuario_roles",
    "registro_auditoria",
    "tokens_un_solo_uso",
    "profesionales",
    "sillones",
    "profesionales_sillones",
    "prestaciones",
    "bloqueos",
}


def test_tablas_de_seguridad_registradas() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_identificadores_son_uuid() -> None:
    for model in (Consultorio, Rol, Usuario):
        column = model.__table__.c.id
        assert isinstance(column.type, Uuid), model.__name__


def test_auditoria_no_expone_columnas_de_modificacion() -> None:
    columns = set(RegistroAuditoria.__table__.c.keys())
    assert "updated_at" not in columns
    assert "deleted_at" not in columns
    assert {"accion", "entidad", "entidad_id", "timestamp"} <= columns


def test_baja_logica_se_declara_en_entidades_de_negocio() -> None:
    for model in (
        Consultorio,
        Rol,
        Usuario,
        Profesional,
        Sillon,
        Prestacion,
        Bloqueo,
    ):
        columns = set(model.__table__.c.keys())
        assert {"is_active", "created_at", "updated_at", "deleted_at"} <= columns


def test_usuario_rol_tiene_pk_compuesta() -> None:
    primary_key = UsuarioRol.__table__.primary_key
    assert [column.name for column in primary_key.columns] == [
        "usuario_id",
        "rol_id",
    ]


def test_check_de_coherencia_de_baja_logica_declarado() -> None:
    for model in (
        Consultorio,
        Rol,
        Usuario,
        Profesional,
        Sillon,
        Prestacion,
        Bloqueo,
    ):
        checks = [
            constraint
            for constraint in model.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        ]
        assert any(
            "(deleted_at IS NULL) = is_active" in str(check.sqltext)
            for check in checks
        ), model.__name__


def test_unicidad_parcial_sobre_filas_activas() -> None:
    expected = {
        "uq_consultorios_slug_activo",
        "uq_roles_nombre_activo",
        "uq_usuarios_email_activo",
    }
    indexes = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    assert expected <= set(indexes)
    for name in expected:
        index = indexes[name]
        assert index.unique is True
        predicate = index.dialect_options["postgresql"].get("where")
        assert str(predicate) == "deleted_at IS NULL"


def test_tokens_publicos_guardan_solo_el_hash() -> None:
    columns = set(TokenUnSoloUso.__table__.c.keys())
    assert "token_hash" in columns
    assert "token" not in columns
    assert not TokenUnSoloUso.__table__.c.token_hash.nullable


def test_consumo_de_token_exige_coherencia() -> None:
    checks = [
        constraint
        for constraint in TokenUnSoloUso.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]
    assert any(
        "(usado) = (usado_at IS NOT NULL)" in str(check.sqltext)
        for check in checks
    )


def _checks(model) -> list[CheckConstraint]:
    return [
        constraint
        for constraint in model.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]


def test_unicidad_parcial_de_recursos_activos() -> None:
    expected = {
        "uq_profesionales_matricula_activo": "deleted_at IS NULL",
        "uq_profesionales_usuario_activo": (
            "usuario_id IS NOT NULL AND deleted_at IS NULL"
        ),
        "uq_sillones_nombre_activo": "deleted_at IS NULL",
        "uq_prestaciones_codigo_activo": "deleted_at IS NULL",
    }
    indexes = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    for name, predicate in expected.items():
        assert name in indexes
        assert indexes[name].unique is True
        where = indexes[name].dialect_options["postgresql"].get("where")
        assert str(where) == predicate


def test_bloqueo_exige_un_solo_recurso_y_rango_valido() -> None:
    sqltext = " ".join(str(check.sqltext) for check in _checks(Bloqueo))
    assert "(profesional_id IS NOT NULL) <> (sillon_id IS NOT NULL)" in sqltext
    assert "hasta > desde" in sqltext


def test_prestacion_exige_sena_coherente() -> None:
    sqltext = " ".join(str(check.sqltext) for check in _checks(Prestacion))
    assert "requiere_sena" in sqltext
    assert "monto_sena IS NOT NULL" in sqltext
    assert "monto_sena > 0" in sqltext


def test_profesional_valida_agenda_en_la_base() -> None:
    sqltext = " ".join(str(check.sqltext) for check in _checks(Profesional))
    assert "duracion_base_min > 0" in sqltext
    assert "hora_hasta > hora_desde" in sqltext
    assert "cardinality(dias_atencion) > 0" in sqltext
    assert "dias_atencion <@" in sqltext


def test_profesional_sillon_tiene_pk_compuesta() -> None:
    primary_key = ProfesionalSillon.__table__.primary_key
    assert [column.name for column in primary_key.columns] == [
        "profesional_id",
        "sillon_id",
    ]


def test_profesional_puede_no_tener_usuario_vinculado() -> None:
    assert Profesional.__table__.c.usuario_id.nullable is True
