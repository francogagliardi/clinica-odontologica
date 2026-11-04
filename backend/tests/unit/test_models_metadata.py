"""Unit tests for the security model contract (no database required)."""

from sqlalchemy import CheckConstraint, Uuid
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.schema import AddConstraint

from app.models import (
    Base,
    Bloqueo,
    Consultorio,
    EntradaListaEspera,
    MensajeWhatsApp,
    ObraSocial,
    Paciente,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    Recordatorio,
    RegistroAuditoria,
    Rol,
    Sillon,
    TokenUnSoloUso,
    Turno,
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
    "pacientes",
    "obras_sociales",
    "turnos",
    "recordatorios",
    "mensajes_whatsapp",
    "entradas_lista_espera",
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
        Paciente,
        ObraSocial,
        Turno,
        EntradaListaEspera,
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
        Paciente,
        ObraSocial,
        Turno,
        EntradaListaEspera,
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


def test_paciente_valida_dni_telefono_y_cobertura() -> None:
    sqltext = " ".join(str(check.sqltext) for check in _checks(Paciente))
    assert "^[0-9]{7,8}$" in sqltext
    assert "^\\+549[0-9]{10}$" in sqltext
    assert "obra_social_id IS NOT NULL" in sqltext
    assert "nro_afiliado IS NULL" in sqltext


def test_paciente_guarda_dni_y_telefono_canonicos() -> None:
    assert not Paciente.__table__.c.dni.nullable
    assert Paciente.__table__.c.dni.type.length == 8
    assert not Paciente.__table__.c.telefono.nullable
    assert Paciente.__table__.c.fecha_nacimiento.nullable is True
    assert Paciente.__table__.c.obra_social_id.nullable is True
    assert Paciente.__table__.c.nro_afiliado.nullable is True


def test_obra_social_valida_reglas_y_deshabilita_validacion_externa() -> None:
    sqltext = " ".join(str(check.sqltext) for check in _checks(ObraSocial))
    assert "jsonb_typeof(reglas_cobertura)" in sqltext
    assert "validacion_externa" in sqltext
    assert "btrim(nombre)" in sqltext


def test_unicidad_de_pacientes_y_obras_sociales() -> None:
    indexes = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    expected = {
        "uq_pacientes_dni_activo": "deleted_at IS NULL",
        "uq_obras_sociales_nombre_activo": "deleted_at IS NULL",
    }
    for name, predicate in expected.items():
        assert name in indexes
        assert indexes[name].unique is True
        where = indexes[name].dialect_options["postgresql"].get("where")
        assert str(where) == predicate


def test_indices_de_busqueda_de_pacientes() -> None:
    indexes = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    assert "ix_pacientes_telefono" in indexes
    assert [column.name for column in indexes["ix_pacientes_telefono"].columns] == [
        "consultorio_id",
        "telefono",
    ]
    apellido = indexes["ix_pacientes_apellido_lower"]
    assert "lower" in str(apellido.expressions[0]).lower()


def test_obra_social_referencia_el_consultorio() -> None:
    foreign_keys = {
        constraint.columns[0].name: constraint
        for constraint in ObraSocial.__table__.foreign_key_constraints
    }
    assert "consultorio_id" in foreign_keys
    assert foreign_keys["consultorio_id"].referred_table.name == "consultorios"


def test_turno_valida_rango_estados_origenes_y_sobreturno() -> None:
    sqltext = " ".join(str(check.sqltext) for check in _checks(Turno))
    assert "fin > inicio" in sqltext
    assert "reservado" in sqltext and "ausente" in sqltext
    assert "recepcion" in sqltext and "whatsapp" in sqltext
    assert "es_sobreturno = (color_sobreturno IS NOT NULL)" in sqltext
    assert "^#[0-9A-Fa-f]{6}$" in sqltext


def test_turno_declara_exclusion_por_profesional_y_sillon() -> None:
    excludes = {
        constraint.name: constraint
        for constraint in Turno.__table__.constraints
        if isinstance(constraint, ExcludeConstraint)
    }
    assert set(excludes) == {"ex_turnos_profesional", "ex_turnos_sillon"}
    for constraint in excludes.values():
        where = str(constraint.where) if constraint.where is not None else ""
        assert "NOT es_sobreturno" in where
        assert "reservado" in where
        assert "deleted_at IS NULL" in where


def test_turno_declara_indices_de_agenda_y_token() -> None:
    indexes = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    expected = {
        "ix_turnos_profesional_inicio",
        "ix_turnos_sillon_inicio",
        "ix_turnos_estado",
        "uq_turnos_token_publico",
    }
    assert expected <= set(indexes)
    assert [
        column.name
        for column in indexes["ix_turnos_profesional_inicio"].columns
    ] == ["profesional_id", "inicio"]
    assert [
        column.name
        for column in indexes["ix_turnos_sillon_inicio"].columns
    ] == ["sillon_id", "inicio"]
    token = indexes["uq_turnos_token_publico"]
    assert token.unique is True
    where = token.dialect_options["postgresql"].get("where")
    assert str(where) == "token_publico IS NOT NULL"


def test_consultorio_configura_el_plazo_de_cancelacion() -> None:
    sqltext = " ".join(str(check.sqltext) for check in _checks(Consultorio))
    assert "plazo_cancelacion_horas" in sqltext
    columna = Consultorio.__table__.c.plazo_cancelacion_horas
    assert columna.nullable is False
    assert str(columna.server_default.arg) == "24"


def test_turno_guarda_el_estado_de_la_sena() -> None:
    sqltext = " ".join(str(check.sqltext) for check in _checks(Turno))
    assert "sena_estado IN" in sqltext
    columna = Turno.__table__.c.sena_estado
    assert columna.nullable is False
    assert columna.default.arg == "no_requiere"
    assert str(columna.server_default.arg) == "'no_requiere'"


def test_recordatorio_valida_ventana_y_estado() -> None:
    sqltext = " ".join(str(check.sqltext) for check in _checks(Recordatorio))
    assert "ventana IN ('48h','24h')" in sqltext
    assert "pendiente" in sqltext and "cancelado" in sqltext
    indexes = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    assert indexes["uq_recordatorios_turno_ventana"].unique is True
    assert [
        column.name
        for column in indexes["uq_recordatorios_turno_ventana"].columns
    ] == ["turno_id", "ventana"]


def test_mensaje_whatsapp_valida_estados_y_proveedor_unico() -> None:
    sqltext = " ".join(
        str(check.sqltext) for check in _checks(MensajeWhatsApp)
    )
    assert "recordatorio" in sqltext and "oferta_hueco" in sqltext
    assert "pendiente" in sqltext and "fallido" in sqltext
    assert "ninguna" in sqltext and "derivado" in sqltext
    indexes = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    proveedor = indexes["uq_mensajes_whatsapp_proveedor"]
    assert proveedor.unique is True
    where = proveedor.dialect_options["postgresql"].get("where")
    assert str(where) == "proveedor_mensaje_id IS NOT NULL"


def test_entrada_lista_espera_declara_retencion_y_fifo() -> None:
    """Contract of the waiting-list entry: FIFO order and retention columns."""
    columns = EntradaListaEspera.__table__.c
    for name in (
        "consultorio_id",
        "paciente_id",
        "prestacion_id",
        "profesional_id",
        "orden",
        "estado",
        "oferta_profesional_id",
        "oferta_sillon_id",
        "oferta_inicio",
        "oferta_fin",
        "oferta_expira_en",
        "turno_id",
    ):
        assert name in columns, name

    assert columns.profesional_id.nullable is True
    for opcional in (
        "oferta_profesional_id",
        "oferta_sillon_id",
        "oferta_inicio",
        "oferta_fin",
        "oferta_expira_en",
        "turno_id",
    ):
        assert columns[opcional].nullable is True, opcional

    assert columns.orden.identity is not None
    assert columns.orden.nullable is False
    assert columns.estado.nullable is False
    assert columns.estado.default.arg == "pendiente"
    assert str(columns.estado.server_default.arg) == "'pendiente'"


def test_entrada_lista_espera_valida_coherencia_de_estados() -> None:
    """CHECKs: offer completeness, conversion, and retention only when offered."""
    sqltext = " ".join(
        str(check.sqltext) for check in _checks(EntradaListaEspera)
    )
    assert "estado IN ('pendiente','ofrecido','convertido','vencido')" in sqltext
    assert "oferta_fin > oferta_inicio" in sqltext
    assert "oferta_profesional_id IS NOT NULL" in sqltext
    assert "oferta_sillon_id IS NOT NULL" in sqltext
    assert "oferta_expira_en IS NOT NULL" in sqltext
    assert "estado <> 'convertido' OR turno_id IS NOT NULL" in sqltext
    assert "estado = 'ofrecido'" in sqltext
    assert "oferta_inicio IS NULL" in sqltext
    assert "(deleted_at IS NULL) = is_active" in sqltext


def test_entrada_lista_espera_declara_exclusion_de_retencion() -> None:
    """Two partial GiST constraints make overlapping offers impossible."""
    excludes = {
        constraint.name: constraint
        for constraint in EntradaListaEspera.__table__.constraints
        if isinstance(constraint, ExcludeConstraint)
    }
    assert set(excludes) == {
        "ex_lista_espera_profesional",
        "ex_lista_espera_sillon",
    }
    for constraint in excludes.values():
        where = str(constraint.where) if constraint.where is not None else ""
        assert "estado = 'ofrecido'" in where
        assert "deleted_at IS NULL" in where
        ddl = str(
            AddConstraint(constraint).compile(
                dialect=postgresql.dialect()
            )
        )
        assert "tstzrange(oferta_inicio, oferta_fin" in ddl
        assert "WITH &&" in ddl
        assert "USING gist" in ddl


def test_entrada_lista_espera_declara_indices_de_cola_y_vencimiento() -> None:
    """Queue, expiry sweep, retention lookups and the partial unique indexes."""
    indexes = {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    expected = {
        "ix_entradas_lista_espera_cola",
        "ix_entradas_lista_espera_prestacion",
        "ix_entradas_lista_espera_vencimiento",
        "ix_entradas_lista_espera_retencion_profesional",
        "ix_entradas_lista_espera_retencion_sillon",
        "uq_entradas_lista_espera_pendiente",
        "uq_entradas_lista_espera_turno",
    }
    assert expected <= set(indexes)

    assert [
        column.name for column in indexes["ix_entradas_lista_espera_cola"].columns
    ] == ["consultorio_id", "estado", "orden"]
    assert [
        column.name
        for column in indexes["ix_entradas_lista_espera_vencimiento"].columns
    ] == ["estado", "oferta_expira_en"]

    pendiente = indexes["uq_entradas_lista_espera_pendiente"]
    assert pendiente.unique is True
    where = pendiente.dialect_options["postgresql"].get("where")
    assert str(where) == "estado = 'pendiente' AND deleted_at IS NULL"
    expresiones = " ".join(
        str(expression) for expression in pendiente.expressions
    )
    assert "paciente_id" in expresiones
    assert "prestacion_id" in expresiones
    assert "coalesce" in expresiones.lower()

    turno = indexes["uq_entradas_lista_espera_turno"]
    assert turno.unique is True
    where_turno = turno.dialect_options["postgresql"].get("where")
    assert str(where_turno) == "turno_id IS NOT NULL"


def test_mensaje_whatsapp_admite_oferta_sin_turno() -> None:
    """An offer message has no turn yet: nullable turn plus waiting-list link."""
    columns = MensajeWhatsApp.__table__.c
    assert columns.turno_id.nullable is True
    assert "lista_espera_id" in columns
    assert columns.lista_espera_id.nullable is True

    foreign_keys = {
        constraint.columns[0].name: constraint
        for constraint in MensajeWhatsApp.__table__.foreign_key_constraints
    }
    assert (
        foreign_keys["lista_espera_id"].referred_table.name
        == "entradas_lista_espera"
    )

    sqltext = " ".join(
        str(check.sqltext) for check in _checks(MensajeWhatsApp)
    )
    assert "aceptado" in sqltext and "rechazado" in sqltext
    assert "turno_id IS NOT NULL OR lista_espera_id IS NOT NULL" in sqltext
