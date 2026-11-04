"""Unit tests for the pure clinical domain (C-11, no database).

FDI, faces, states, CIE-10, attachment sanitisation/magic bytes and the
consent catalogue are pure functions: they can be exhaustively tested without
PostgreSQL, and the same predicates are mirrored by CHECKs in migration 0010.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.domain import clinica, consentimientos

PACIENTE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FECHA = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("pieza", [11, 18, 48, 51, 55, 85])
def test_pieza_fdi_valida(pieza: int) -> None:
    assert clinica.pieza_fdi_valida(pieza) is True


@pytest.mark.parametrize("pieza", [19, 20, 29, 49, 56, 86, 99, 0, 9])
def test_pieza_fdi_invalida(pieza: int) -> None:
    assert clinica.pieza_fdi_valida(pieza) is False


@pytest.mark.parametrize(
    "cara",
    [
        "mesial",
        "distal",
        "vestibular",
        "lingual",
        "oclusal",
        "incisal",
        "completa",
    ],
)
def test_cara_valida(cara: str) -> None:
    assert clinica.cara_valida(cara) is True


@pytest.mark.parametrize("cara", ["lateral", "superior", "", "MESIAL"])
def test_cara_invalida(cara: str) -> None:
    assert clinica.cara_valida(cara) is False


@pytest.mark.parametrize("estado", sorted(clinica.ESTADOS_VALIDOS))
def test_estado_valido(estado: str) -> None:
    assert clinica.estado_valido(estado) is True


@pytest.mark.parametrize("estado", ["desconocido", "", "CARIES", "sano "])
def test_estado_invalido(estado: str) -> None:
    assert clinica.estado_valido(estado) is False


@pytest.mark.parametrize(
    "cie10", ["K02.1", "A00", "K02", "K02.12", "M54.5"]
)
def test_cie10_valido(cie10: str) -> None:
    assert clinica.cie10_valido(cie10) is True


@pytest.mark.parametrize("cie10", ["caries", "k021", "K02.", "123", "", "K021"])
def test_cie10_invalido(cie10: str) -> None:
    assert clinica.cie10_valido(cie10) is False


def test_cie10_es_opcional() -> None:
    """Absent CIE-10 is valid (optional); a present value must match the format."""
    assert clinica.cie10_valido(None) is True
    assert clinica.cie10_valido("K02.1") is True


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("..\\..\\etc\\passwd", "passwd"),
        ("../../etc/passwd", "passwd"),
        ("/var/tmp/foto.png", "foto.png"),
        ("C:\\Users\\demo\\foto.PNG", "foto.PNG"),
        ("radiografia.pdf", "radiografia.pdf"),
    ],
)
def test_sanear_nombre_quita_rutas(nombre: str, esperado: str) -> None:
    assert clinica.sanear_nombre(nombre) == esperado


def test_sanear_nombre_acota_longitud_y_valores_vacios() -> None:
    assert len(clinica.sanear_nombre("a" * 400 + ".png")) == 255
    assert clinica.sanear_nombre("") == "adjunto"
    assert clinica.sanear_nombre("..") == "adjunto"


def test_sanear_nombre_quita_comillas_y_controles() -> None:
    """Header injection defence: quotes and newlines never reach the download."""
    assert clinica.sanear_nombre('informe"\r\n.png') == "informe.png"


@pytest.mark.parametrize(
    "mime",
    ["image/jpeg", "image/png", "image/webp", "application/pdf", "IMAGE/PNG"],
)
def test_mime_permitido(mime: str) -> None:
    assert clinica.mime_permitido(mime) is True


@pytest.mark.parametrize(
    "mime", ["application/x-msdownload", "text/html", "image/svg+xml", ""]
)
def test_mime_no_permitido(mime: str) -> None:
    assert clinica.mime_permitido(mime) is False


def test_limite_de_adjunto_es_cinco_megabytes() -> None:
    assert clinica.MAX_ADJUNTO_BYTES == 5 * 1024 * 1024


@pytest.mark.parametrize(
    ("mime", "contenido"),
    [
        ("image/jpeg", b"\xff\xd8\xff\xe0" + b"0" * 12),
        ("image/png", b"\x89PNG\r\n\x1a\n" + b"0" * 12),
        ("image/webp", b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"0"),
        ("application/pdf", b"%PDF-1.7\n"),
    ],
)
def test_firma_coincide_con_mime(mime: str, contenido: bytes) -> None:
    assert clinica.firma_coincide_con_mime(mime, contenido) is True


@pytest.mark.parametrize(
    ("mime", "contenido"),
    [
        ("image/png", b"%PDF-1.7\n"),
        ("image/jpeg", b"\x89PNG\r\n\x1a\n"),
        ("image/webp", b"RIFF\x00\x00\x00\x00JUNK"),
        ("application/pdf", b"PK\x03\x04"),
        ("image/png", b""),
        ("text/html", b"%PDF-1.7\n"),
    ],
)
def test_firma_no_coincide_con_mime(mime: str, contenido: bytes) -> None:
    assert clinica.firma_coincide_con_mime(mime, contenido) is False


def test_catalogo_de_consentimientos_versionado() -> None:
    assert consentimientos.VERSION_ACTUAL == "v1-2026-11"
    assert consentimientos.version_conocida("v1-2026-11") is True
    assert consentimientos.version_conocida("v0") is False
    assert "procedimiento" in consentimientos.texto_canonico(
        "v1-2026-11"
    ).lower()


def test_tipo_de_consentimiento_validado() -> None:
    assert consentimientos.tipo_valido("procedimiento_invasivo") is True
    assert consentimientos.tipo_valido("otro") is False


def test_hashes_de_consentimiento_son_deterministas() -> None:
    primero = consentimientos.calcular_hashes(
        version="v1-2026-11", paciente_id=PACIENTE_ID, fecha=FECHA
    )
    segundo = consentimientos.calcular_hashes(
        version="v1-2026-11", paciente_id=PACIENTE_ID, fecha=FECHA
    )
    assert primero == segundo
    texto_hash, firma_ref = primero
    assert len(texto_hash) == 64
    assert all(caracter in "0123456789abcdef" for caracter in texto_hash)
    assert firma_ref.startswith("sha256:")
    assert len(firma_ref) == len("sha256:") + 64


def test_hashes_cambian_con_paciente_o_fecha() -> None:
    base = consentimientos.calcular_hashes(
        version="v1-2026-11", paciente_id=PACIENTE_ID, fecha=FECHA
    )
    otro_paciente = consentimientos.calcular_hashes(
        version="v1-2026-11", paciente_id=uuid.uuid4(), fecha=FECHA
    )
    otra_fecha = consentimientos.calcular_hashes(
        version="v1-2026-11",
        paciente_id=PACIENTE_ID,
        fecha=datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc),
    )
    assert base[1] != otro_paciente[1]
    assert base[1] != otra_fecha[1]


def test_version_desconocida_no_tiene_texto() -> None:
    with pytest.raises(ValueError):
        consentimientos.texto_canonico("v0")
    with pytest.raises(ValueError):
        consentimientos.calcular_hashes(
            version="v0", paciente_id=PACIENTE_ID, fecha=FECHA
        )
