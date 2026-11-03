# Proposal

## Why

C-03 dejó cerrada la identidad y el acceso (login, JWT, RBAC, tokens públicos), pero la agenda todavía no tiene **oferta**: no existen profesionales, sillones, prestaciones ni bloqueos. Sin esos recursos, C-06 (`turnos-anti-solapamiento`) no puede validar disponibilidad ni aplicar RN-TU-01/RN-TU-02/RN-TU-07, y C-11/C-12 tampoco tienen catálogo de prestaciones para presupuestar.

C-04 es la rama A del GATE 3 y corre en paralelo con C-05 (demanda). Cierra el lado de la oferta y expone la disponibilidad base que C-06 y C-07 reutilizan.

## What Changes

- Agrega modelos SQLAlchemy 2.x y migración `0004`:
  - `Profesional`: consultorio, usuario opcional, matrícula, especialidades y agenda base (`duracion_base_min`, `dias_atencion`, `hora_desde`, `hora_hasta`).
  - `Sillon`: consultorio y nombre, con baja lógica.
  - `ProfesionalSillon`: habilitación *──* idempotente.
  - `Prestacion`: código, nombre, duración, precio base, especialidad y seña opcional (`requiere_sena`, `monto_sena`).
  - `Bloqueo`: por profesional **o** por sillón (exactamente uno), desde/hasta y motivo.
- Expone endpoints con RBAC (RN-SE-01):
  - `/profesionales` + `/sillones`: lectura para roles de agenda, escritura solo administrador.
  - `POST/DELETE /profesionales/{id}/sillones/{sillon_id}`: habilitación idempotente (administrador).
  - `GET /profesionales/{id}/disponibilidad`: slots base desde `agenda_config`, descontando bloqueos.
  - `/prestaciones`: lectura para roles de agenda, escritura solo administrador.
  - `/bloqueos`: lectura para roles de agenda; escritura administrador/recepcionista, y odontólogo solo para su propio profesional.
- Valida en el borde (Pydantic v2 `extra='forbid'` + CHECKs en PostgreSQL):
  - duraciones positivas, precios no negativos, rango horario coherente, días 0–6 no vacíos;
  - `requiere_sena=true` exige `monto_sena` no nulo y no negativo (RN-TU-08);
  - bloqueo con exactamente un recurso y `hasta > desde`.
- Extiende el seed demo de forma idempotente: 2 sillones del consultorio demo y 5 prestaciones ficticias (consulta, limpieza, obturación, endodoncia, extracción), una con seña.
- Agrega suite unitaria (validadores, cálculo de disponibilidad) e integración (CRUD por rol, 403/409/422, disponibilidad y bloqueos).

## Capabilities

### New Capabilities
- `agenda/recursos-agendables`: profesionales, sillones, habilitación y disponibilidad base.
- `comercial/prestaciones`: catálogo de prestaciones y seña opcional por prestación.
- `agenda/bloqueos`: bloqueos por profesional/sillón y su efecto en la disponibilidad.

### Modified Capabilities
- Ninguna: C-02/C-03 no definieron recursos de agenda ni catálogo comercial.

## Impact

- **Backend**:
  - `app/models/agenda.py`, `app/models/comercial.py` (o un módulo por dominio) y `app/models/__init__.py`.
  - `app/infrastructure/repositories.py` y `app/infrastructure/uow.py` (nuevos repositorios).
  - `app/schemas/recursos.py`, `app/api/{profesionales,sillones,prestaciones,bloqueos}.py`, `app/main.py`.
  - `app/domain/agenda.py` (cálculo puro de disponibilidad).
  - `app/seed.py` (sillones + prestaciones).
  - Migración `backend/alembic/versions/0004_recursos_agendables.py`.
  - Tests unitarios e integración; actualización de los tests que asumen el head `0003` y las tablas de C-02/C-03.
- **API Surface**: `/profesionales`, `/sillones`, `/prestaciones`, `/bloqueos` y `GET /profesionales/{id}/disponibilidad`.
- **Riesgos y mitigaciones**:
  - Solapamiento de turnos: se resuelve en C-06; C-04 solo calcula disponibilidad base.
  - Zona horaria: v1 usa offset fijo `UTC-3` (Argentina sin DST); la zona por consultorio queda para C-06.
  - Multi-tenant: v1 opera con el consultorio demo; `Profesional`/`Sillon` ya llevan `consultorio_id` para no bloquear el salto a multisucursal.
