# Proposal

## Why

US-021 es el tramo que falta entre la atención clínica (C-11) y el cobro (C-13): hoy el odontólogo no puede entregar al paciente un plan de tratamiento con cobertura y copago calculados antes de que decida. Sin eso, RN-CL-02 y RN-OS-02 no tienen contrato observable, y C-13/C-14 no tienen un presupuesto al que asociar cobros, comprobantes y liquidaciones.

## What Changes

- Nuevos modelos `Presupuesto` e `ItemPresupuesto` y migración `0011_presupuestos` (el head real es `0010_historia_clinica`; el "007" de `CHANGES.md` está desactualizado).
- Cálculo de cobertura y copago **por ítem** contra las reglas locales del convenio del paciente (OS Demo en v1, DD-11), con `Decimal`, redondeo half-up a dos decimales y totales derivados de los ítems. El cliente nunca envía precios, coberturas ni totales.
- Cobertura no calculable (regla ausente, convenio inactivo o proveedor de cobertura no disponible) → `cobertura_estado='pendiente_verificacion'` con cobertura 0 y copago igual al total, sin bloquear el alta ni la aceptación (RN-OS-02, Flujo 3 caso de error).
- Máquina de estados `borrador → aceptado|rechazado`, `aceptado → en_curso → finalizado`; `rechazado` y `finalizado` terminales; repetición idempotente; transición inválida 422. Edición, recálculo y baja lógica solo en `borrador`.
- Precio unitario como snapshot del `precio_base` del catálogo al crear o editar el borrador: un cambio posterior de precios no re-preciará un presupuesto existente.
- Endpoints `/presupuestos` (alta con ítems anidados, ficha, listado filtrable, edición de borrador, cambio de estado, recálculo y baja lógica) con RBAC de la matriz y auditoría en la misma transacción.
- Tests unitarios del cálculo (redondeo y sumas) y de integración contra PostgreSQL real para cobertura, estados, RBAC y auditoría.

**Fuera de alcance**: cobros, señas y conciliación Mercado Pago (C-13); facturación ARCA y liquidación de obras sociales (C-14); UI de presupuestos; envío del presupuesto por WhatsApp o PDF; firma digital certificada; integración con nomencladores reales; rutas públicas para que el paciente consulte su presupuesto (la matriz lo asigna al enlace público, que no existe para este recurso en v1).

## Capabilities

### New Capabilities

- `comercial/presupuestos`: alta, consulta, edición y ciclo de vida del presupuesto/plan de tratamiento, con cobertura y copago calculados por ítem contra el convenio local, snapshot de precios, estados, RBAC y auditoría.

### Modified Capabilities

Ninguna. C-12 consume los contratos ya existentes (`comercial/prestaciones` para el catálogo y `precio_base`, `comercial/obras-sociales` para `reglas_cobertura`, `pacientes/registro-pacientes` para la cobertura declarada, `agenda/turnos` para definir "paciente propio", `clinica/historia-clinica` para el consentimiento y `security/core-models` para auditoría). No cambia requisitos de esas capacidades ni agrega columnas a sus tablas.

## Impact

- **Backend**: `app/models/comercial.py` (dos modelos nuevos), `app/schemas/presupuestos.py`, `app/domain/presupuestos.py` (cálculo puro), `app/application/presupuestos.py` (autorización, servicio y proveedor de cobertura), `app/api/presupuestos.py`, `app/infrastructure/repositories.py`, `app/infrastructure/uow.py`, `app/main.py`, `alembic/versions/0011_presupuestos.py`.
- **Base de datos**: dos tablas nuevas (`presupuestos`, `items_presupuesto`), CHECKs de estado/cobertura/importes, FK a `pacientes`, `profesionales`, `prestaciones` y `consultorios`, e índices de listado. No se altera ninguna tabla de C-01–C-11.
- **API**: endpoints nuevos bajo `/presupuestos`; sin cambios breaking en endpoints existentes. C-13 podrá referenciar `presupuesto_id`.
- **Dependencias**: PostgreSQL, SQLAlchemy 2.x, Alembic, FastAPI. Sin servicios externos ni costos de terceros (R-12); el cálculo es local (DD-11).
- **Datos**: solo pacientes, prestaciones y OS Demo ficticias del seed; sin datos reales.
