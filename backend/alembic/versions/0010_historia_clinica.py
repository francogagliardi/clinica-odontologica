"""Clinical record: history, evolutions, odontogram, attachments, consents (C-11).

Hand-written because Alembic autogenerate does not emit partial unique indexes,
FDI CHECK constraints or immutability triggers (design D2). The downgrade drops
triggers, functions and the six tables in reverse order and does not touch any
table created by C-01..C-10.

Revision ID: 0010_historia_clinica
Revises: 0009_lista_espera
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_historia_clinica"
down_revision: str | None = "0009_lista_espera"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_PIEZA_FDI_VALIDA = (
    "((pieza / 10 BETWEEN 1 AND 4 AND pieza % 10 BETWEEN 1 AND 8) "
    "OR (pieza / 10 BETWEEN 5 AND 8 AND pieza % 10 BETWEEN 1 AND 5))"
)
_CARAS_VALIDAS = (
    "'mesial','distal','vestibular','lingual','oclusal','incisal','completa'"
)
_ESTADOS_VALIDOS = (
    "'sano','caries','obturacion','endodoncia','corona','implante','ausente',"
    "'extraccion_indicada','fractura','sellante','protesis'"
)
_CIE10_FORMATO = "^[A-Z][0-9]{2}(\\.[0-9]{1,2})?$"
_MIMES_PERMITIDOS = "'image/jpeg','image/png','image/webp','application/pdf'"
_NOMBRE_SANEADO = (
    "btrim(nombre) <> '' AND nombre NOT LIKE '%..%' "
    "AND nombre !~ '[/\\\\]'"
)
_TIPOS_CONSENTIMIENTO = "'procedimiento_invasivo'"
_HASH_HEX = "^[0-9a-f]{64}$"
_FIRMA_REF = "^sha256:[0-9a-f]{64}$"
_MAX_ADJUNTO_BYTES = 5 * 1024 * 1024

_TABLAS_CLINICA = (
    "consentimientos",
    "adjuntos",
    "hallazgos_dentales",
    "odontogramas",
    "evoluciones",
    "historias_clinicas",
)

# Signed evolutions are immutable except for the false → true transition; a
# draft can still be edited, signed or discarded (design D4/D5).
_FUNCION_EVOLUCIONES = """
CREATE FUNCTION evoluciones_inmutabilidad() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.firmada THEN
            RAISE EXCEPTION
                'Una evolución firmada es inmutable (RN-CL-04): DELETE no permitido'
                USING ERRCODE = 'P0001';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.firmada THEN
        RAISE EXCEPTION
            'Una evolución firmada es inmutable (RN-CL-04): UPDATE no permitido'
            USING ERRCODE = 'P0001';
    END IF;

    IF NEW.firmada THEN
        IF NEW.historia_id IS DISTINCT FROM OLD.historia_id
           OR NEW.profesional_id IS DISTINCT FROM OLD.profesional_id
           OR NEW.creado_por IS DISTINCT FROM OLD.creado_por
           OR NEW.fecha IS DISTINCT FROM OLD.fecha
           OR NEW.texto IS DISTINCT FROM OLD.texto
           OR NEW.rectifica_a IS DISTINCT FROM OLD.rectifica_a THEN
            RAISE EXCEPTION
                'La firma no puede modificar el contenido (RN-CL-04)'
                USING ERRCODE = 'P0001';
        END IF;
        IF NEW.firmada_por IS NULL OR NEW.fecha_firma IS NULL THEN
            RAISE EXCEPTION
                'La firma exige firmada_por y fecha_firma (RN-CL-04)'
                USING ERRCODE = 'P0001';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.historia_id IS DISTINCT FROM OLD.historia_id
       OR NEW.profesional_id IS DISTINCT FROM OLD.profesional_id
       OR NEW.creado_por IS DISTINCT FROM OLD.creado_por
       OR NEW.fecha IS DISTINCT FROM OLD.fecha
       OR NEW.rectifica_a IS DISTINCT FROM OLD.rectifica_a THEN
        RAISE EXCEPTION
            'El borrador no puede cambiar historia, profesional, autor, '
            'fecha ni rectificación'
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# Snapshots and consents are append-only: every correction is a new act, so
# even a direct UPDATE/DELETE is rejected in PostgreSQL (design D3/D6/D10).
_FUNCION_APPEND_ONLY = """
CREATE FUNCTION {funcion}() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        '{tabla} es append-only (RN-CL-04): % no permitido', TG_OP
        USING ERRCODE = 'P0001';
END;
$$ LANGUAGE plpgsql;
"""

_TRIGGERS_APPEND_ONLY = (
    ("odontogramas", "odontogramas_append_only"),
    ("hallazgos_dentales", "hallazgos_dentales_append_only"),
    ("consentimientos", "consentimientos_append_only"),
)


def _audit_columns() -> list[sa.Column]:
    """Columns shared by business entities (mirrors AuditMixin)."""
    return [
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "historias_clinicas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("abierta_por", sa.Uuid(), nullable=False),
        sa.Column(
            "fecha_apertura",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_historias_clinicas_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["pacientes.id"],
            name="fk_historias_clinicas_paciente_id_pacientes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["abierta_por"],
            ["usuarios.id"],
            name="fk_historias_clinicas_abierta_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_historias_clinicas"),
    )
    op.create_index(
        "uq_historias_clinicas_paciente_activa",
        "historias_clinicas",
        ["paciente_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "evoluciones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("historia_id", sa.Uuid(), nullable=False),
        sa.Column("profesional_id", sa.Uuid(), nullable=False),
        sa.Column("creado_por", sa.Uuid(), nullable=False),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column(
            "firmada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("firmada_por", sa.Uuid(), nullable=True),
        sa.Column("fecha_firma", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rectifica_a", sa.Uuid(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            "firmada = (firmada_por IS NOT NULL AND fecha_firma IS NOT NULL)",
            name="firma_coherente",
        ),
        sa.CheckConstraint("btrim(texto) <> ''", name="texto_no_vacio"),
        sa.ForeignKeyConstraint(
            ["historia_id"],
            ["historias_clinicas.id"],
            name="fk_evoluciones_historia_id_historias_clinicas",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profesional_id"],
            ["profesionales.id"],
            name="fk_evoluciones_profesional_id_profesionales",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuarios.id"],
            name="fk_evoluciones_creado_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["firmada_por"],
            ["usuarios.id"],
            name="fk_evoluciones_firmada_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rectifica_a"],
            ["evoluciones.id"],
            name="fk_evoluciones_rectifica_a_evoluciones",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evoluciones"),
    )
    op.create_index(
        "uq_evoluciones_rectificacion_activa",
        "evoluciones",
        ["rectifica_a"],
        unique=True,
        postgresql_where=sa.text(
            "rectifica_a IS NOT NULL AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "ix_evoluciones_historia_fecha",
        "evoluciones",
        ["historia_id", "fecha"],
    )

    op.create_table(
        "odontogramas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("historia_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("version > 0", name="version_positiva"),
        sa.ForeignKeyConstraint(
            ["historia_id"],
            ["historias_clinicas.id"],
            name="fk_odontogramas_historia_id_historias_clinicas",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_odontogramas"),
        sa.UniqueConstraint(
            "historia_id",
            "version",
            name="uq_odontogramas_historia_version",
        ),
    )

    op.create_table(
        "hallazgos_dentales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("odontograma_id", sa.Uuid(), nullable=False),
        sa.Column("pieza", sa.Integer(), nullable=False),
        sa.Column("cara", sa.String(length=20), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("diagnostico", sa.Text(), nullable=True),
        sa.Column("cie10", sa.String(length=10), nullable=True),
        sa.Column(
            "fecha",
            sa.Date(),
            nullable=False,
            server_default=sa.func.current_date(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(_PIEZA_FDI_VALIDA, name="pieza_fdi_valida"),
        sa.CheckConstraint(f"cara IN ({_CARAS_VALIDAS})", name="cara_valida"),
        sa.CheckConstraint(
            f"estado IN ({_ESTADOS_VALIDOS})", name="estado_valido"
        ),
        sa.CheckConstraint(
            f"cie10 IS NULL OR cie10 ~ '{_CIE10_FORMATO}'",
            name="cie10_formato",
        ),
        sa.ForeignKeyConstraint(
            ["odontograma_id"],
            ["odontogramas.id"],
            name="fk_hallazgos_dentales_odontograma_id_odontogramas",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_hallazgos_dentales"),
        sa.UniqueConstraint(
            "odontograma_id",
            "pieza",
            "cara",
            name="uq_hallazgos_dentales_odontograma_pieza_cara",
        ),
    )

    op.create_table(
        "adjuntos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("historia_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=60), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column("subido_por", sa.Uuid(), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            f"mime IN ({_MIMES_PERMITIDOS})", name="mime_permitido"
        ),
        sa.CheckConstraint(
            f"tamano > 0 AND tamano <= {_MAX_ADJUNTO_BYTES}",
            name="tamano_valido",
        ),
        sa.CheckConstraint(
            "tamano = octet_length(contenido)", name="tamano_coherente"
        ),
        sa.CheckConstraint(_NOMBRE_SANEADO, name="nombre_saneado"),
        sa.ForeignKeyConstraint(
            ["historia_id"],
            ["historias_clinicas.id"],
            name="fk_adjuntos_historia_id_historias_clinicas",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subido_por"],
            ["usuarios.id"],
            name="fk_adjuntos_subido_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_adjuntos"),
    )
    op.create_index(
        "ix_adjuntos_historia", "adjuntos", ["historia_id", "created_at"]
    )

    op.create_table(
        "consentimientos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("texto_version", sa.String(length=20), nullable=False),
        sa.Column("texto_hash", sa.String(length=64), nullable=False),
        sa.Column("firma_ref", sa.String(length=80), nullable=False),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("registrado_por", sa.Uuid(), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            f"tipo IN ({_TIPOS_CONSENTIMIENTO})", name="tipo_valido"
        ),
        sa.CheckConstraint(
            f"texto_hash ~ '{_HASH_HEX}'", name="texto_hash_formato"
        ),
        sa.CheckConstraint(
            f"firma_ref ~ '{_FIRMA_REF}'", name="firma_ref_formato"
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_consentimientos_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["pacientes.id"],
            name="fk_consentimientos_paciente_id_pacientes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["registrado_por"],
            ["usuarios.id"],
            name="fk_consentimientos_registrado_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consentimientos"),
    )
    op.create_index(
        "ix_consentimientos_paciente_fecha",
        "consentimientos",
        ["consultorio_id", "paciente_id", "fecha"],
    )

    op.execute(_FUNCION_EVOLUCIONES)
    op.execute(
        """
        CREATE TRIGGER trg_evoluciones_inmutabilidad
        BEFORE UPDATE OR DELETE ON evoluciones
        FOR EACH ROW EXECUTE FUNCTION evoluciones_inmutabilidad();
        """
    )

    for tabla, funcion in _TRIGGERS_APPEND_ONLY:
        op.execute(
            _FUNCION_APPEND_ONLY.format(funcion=funcion, tabla=tabla)
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{tabla}_append_only
            BEFORE UPDATE OR DELETE ON {tabla}
            FOR EACH ROW EXECUTE FUNCTION {funcion}();
            """
        )


def downgrade() -> None:
    for tabla in _TABLAS_CLINICA:
        op.drop_table(tabla)
    op.execute("DROP FUNCTION IF EXISTS evoluciones_inmutabilidad();")
    for _tabla, funcion in _TRIGGERS_APPEND_ONLY:
        op.execute(f"DROP FUNCTION IF EXISTS {funcion}();")
