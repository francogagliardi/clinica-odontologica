"""Unit tests for the security model contract (no database required)."""

from sqlalchemy import CheckConstraint, Uuid

from app.models import (
    Base,
    Consultorio,
    RegistroAuditoria,
    Rol,
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
    for model in (Consultorio, Rol, Usuario):
        columns = set(model.__table__.c.keys())
        assert {"is_active", "created_at", "updated_at", "deleted_at"} <= columns


def test_usuario_rol_tiene_pk_compuesta() -> None:
    primary_key = UsuarioRol.__table__.primary_key
    assert [column.name for column in primary_key.columns] == [
        "usuario_id",
        "rol_id",
    ]


def test_check_de_coherencia_de_baja_logica_declarado() -> None:
    for model in (Consultorio, Rol, Usuario):
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
