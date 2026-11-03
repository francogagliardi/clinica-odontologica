# Proposal

## Why

C-04 cerró la **oferta** de la agenda (profesionales, sillones, prestaciones y bloqueos), pero el sistema todavía no tiene **demanda**: no existe ningún paciente ni convenio de obra social. Sin `Paciente`, C-06 (`turnos-anti-solapamiento`) no puede crear un `Turno`, C-07 no puede identificar a quien reserva online y C-11/C-12 no tienen a quién asociar historia clínica, presupuesto ni cobertura.

C-05 es la rama B del GATE 3 y corre en paralelo con C-04. Cierra el lado de la demanda con el registro mínimo de pacientes y los convenios base contra los que después se calculará cobertura/copago (RN-OS-02).

## What Changes

- Agrega modelos SQLAlchemy 2.x y migración `0005_pacientes_cobertura_base`:
  - `Paciente`: consultorio, nombre, apellido, DNI, fecha de nacimiento opcional, teléfono WhatsApp obligatorio, email opcional, obra social y número de afiliado opcionales, notas y baja lógica.
  - `ObraSocial`: consultorio, nombre, referencia de nomenclador, reglas de cobertura locales (JSONB) y bandera de validación externa.
- Expone endpoints con RBAC (RN-SE-01):
  - `POST/GET/PUT/DELETE /pacientes` y `GET /pacientes/{id}` (ficha), con búsqueda obligatoria por al menos un criterio (`dni`, `telefono` o `apellido`).
  - `GET/POST/PUT/DELETE /obras-sociales` (convenios), con lectura para los roles que presupuestan y escritura según la matriz.
- Valida en el borde (Pydantic v2 `extra='forbid'`) y en PostgreSQL (CHECK + índices únicos parciales):
  - DNI argentino de 7–8 dígitos, normalizado sin puntos, único por consultorio entre pacientes activos.
  - Teléfono argentino normalizado a formato internacional (`+549…`): 10 dígitos nacionales o 12–13 con código país; ausente o inválido bloquea el alta (canal WhatsApp requerido).
  - `nro_afiliado` solo puede existir si hay obra social; una obra social inexistente o dada de baja responde 404.
  - Reglas de cobertura con porcentajes 0–100, cobertura + copago ≤ 100 y códigos de prestación existentes en el catálogo activo.
- Extiende el seed demo de forma idempotente: convenio ficticio **OS Demo** (DD-11, reglas locales, `validacion_externa=false`) y 3 pacientes ficticios con DNI/teléfono de prueba.
- Agrega suite unitaria (normalización de DNI/teléfono, reglas de cobertura) e integración (CRUD por rol, 401/403/404/409/422, búsqueda y filtros).

## Capabilities

### New Capabilities
- `pacientes/registro-pacientes`: alta, ficha, edición, baja lógica y búsqueda de pacientes con datos de contacto y cobertura.
- `comercial/obras-sociales`: convenios de obra social con nomenclador y reglas locales de cobertura.

### Modified Capabilities
- Ninguna: C-02/C-03/C-04 no definieron pacientes ni convenios.

## Impact

- **Backend**:
  - `app/models/pacientes.py` (o un módulo por dominio), `app/models/comercial.py` y `app/models/__init__.py`.
  - `app/domain/pacientes.py` (normalización pura de DNI/teléfono) y validadores de reglas de cobertura.
  - `app/infrastructure/repositories.py` y `app/infrastructure/uow.py` (repositorios de pacientes y obras sociales).
  - `app/schemas/pacientes.py`, `app/api/pacientes.py`, `app/api/obras_sociales.py`, `app/main.py`.
  - `app/seed.py` (OS Demo + pacientes ficticios).
  - Migración `backend/alembic/versions/0005_pacientes_cobertura_base.py`.
  - Tests unitarios e integración; actualización de los tests que asumen el head `0004` y el inventario de tablas.
- **API Surface**: `/pacientes`, `/pacientes/{id}` y `/obras-sociales`.
- **Riesgos y mitigaciones**:
  - Datos personales: solo datos ficticios en demo y base descartable; no se copian datos reales (R-08/R-12). La búsqueda exige criterio para evitar volcados completos.
  - Validación de cobertura real: v1 valida contra reglas locales de **OS Demo** (DD-11); la integración con nomencladores reales queda para la segunda iteración.
  - Multi-tenant: v1 opera con el consultorio demo, pero ambas tablas llevan `consultorio_id` para no bloquear multisucursal.
  - El cálculo de cobertura/copago por ítem (RN-OS-02) se implementa en C-12; C-05 solo persiste el convenio y sus reglas.
