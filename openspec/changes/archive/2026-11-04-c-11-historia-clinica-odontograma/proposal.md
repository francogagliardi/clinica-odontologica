# Proposal

## Why

La clínica ya agenda, registra pacientes y comunica turnos (C-01–C-10), pero no puede documentar la atención: sin historia clínica, evoluciones firmadas, odontograma FDI ni consentimientos, el flujo 3 de la KB queda incompleto y C-12 no tiene dónde apoyar el plan de tratamiento. Este change incorpora el registro clínico con las garantías contractuales de inmutabilidad, trazabilidad y RBAC (governance CRÍTICO).

## What Changes

- Nuevos modelos y migración `0010_historia_clinica` (el head real es `0009_lista_espera`; el "006" del roadmap está desactualizado): `HistoriaClinica`, `Evolucion`, `Odontograma`, `HallazgoDental`, `Adjunto` y `Consentimiento`.
- Una historia clínica por paciente y consultorio, abierta por un usuario autorizado y con odontograma versionado por snapshots completos e inmutables.
- Evoluciones con flujo mínimo borrador → firma: el borrador se edita; al firmar se congelan texto, fecha, autor y vínculo de rectificación. Una evolución firmada no se edita ni se borra por API y PostgreSQL rechaza el `UPDATE`/`DELETE` directo (RN-CL-04). La corrección se hace con una nueva evolución `rectifica_a` enlazada a la firmada, que también se firma.
- Odontograma FDI con piezas permanentes 11–18/21–28/31–38/41–48 y temporarias 51–55/61–65/71–75/81–85, caras válidas y estado/diagnóstico con CIE-10 opcional (RN-CL-01). Cada alta o corrección de hallazgo crea una versión nueva; las anteriores quedan de solo lectura y protegidas por trigger.
- Adjuntos clínicos (fotos/documentos) almacenados en PostgreSQL como `BYTEA` con límite de 5 MB, allow-list de MIME, verificación de firma de archivo y nombre saneado; se descargan solo autenticados.
- Consentimientos con texto versionado en código, tipo validado y `firma_ref` como digest SHA-256 del texto canónico + paciente + fecha; no se almacena firma gráfica.
- Endpoints REST RORO bajo `/historia-clinica` y `/odontograma`, con RBAC según la matriz (administrador y auditor leen todo; odontólogo escribe sobre pacientes propios; recepcionista y auditor leen; asistente actualiza lo asistido) y `RegistroAuditoria` append-only en toda escritura clínica (RN-SE-02).
- Tests de integración contra PostgreSQL real para inmutabilidad (403 + SQLSTATE `P0001`), rectificatoria, FDI inválida (422), adjunto sin historia (422), auditoría y RBAC.

**Fuera de alcance**: presupuestos/planes (C-12), UI de la ficha clínica (no hay change de frontend clínico en v1), firma digital certificada, almacenamiento en object storage, y cualquier borrado físico de registros clínicos.

## Capabilities

### New Capabilities

- `clinica/historia-clinica`: ciclo de vida de la historia clínica, evoluciones con firma e inmutabilidad, rectificatorias enlazadas, adjuntos clínicos y consentimientos informados versionados, con auditoría y RBAC.
- `clinica/odontograma`: odontograma FDI versionado por snapshots, validación de pieza/cara, hallazgos con estado y CIE-10 opcional, e inmutabilidad de versiones anteriores.

### Modified Capabilities

Ninguna. C-11 agrega comportamiento nuevo y no cambia requisitos de `security/core-models`, `agenda/turnos`, `pacientes/registro-pacientes` ni `comercial/prestaciones`; solo consume sus contratos (auditoría append-only, turnos para definir "propio", paciente y RBAC).

## Impact

- **Backend**: `app/models/clinica.py`, `app/schemas/clinica.py`, `app/domain/clinica.py`, `app/api/historia_clinica.py`, `app/api/odontograma.py`, `app/infrastructure/repositories.py`, `app/infrastructure/uow.py`, `app/main.py`, migración `alembic/versions/0010_historia_clinica.py`.
- **Base de datos**: seis tablas nuevas, índices únicos parciales, CHECKs de FDI/caras/MIME/tamaño, triggers de inmutabilidad de evolución firmada y de versiones de odontograma.
- **API**: endpoints nuevos de historia, evoluciones, odontograma, adjuntos y consentimientos; sin cambios breaking en endpoints existentes.
- **Dependencias**: PostgreSQL, SQLAlchemy 2.x, Alembic, FastAPI (multipart para adjuntos). No se agregan servicios externos ni costos de terceros.
- **Datos**: se usan pacientes y profesionales ficticios del seed demo; no se tocan datos reales.
