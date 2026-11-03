# Design

## Context

C-04 cerró la oferta de la agenda. C-05 abre la rama de **demanda** del GATE 3: pacientes y convenios de obra social. C-06 necesita un `paciente_id` válido para crear turnos; C-07 necesita identificar a quien reserva; C-11/C-12 necesitan la ficha y la cobertura declarada.

Constraints: R-01 (snake_case, hints, Pydantic v2 `extra='forbid'`), R-02 (routers + RORO, async, `deps.py`), R-03 (RBAC en API según `03_actores_y_roles.md`), R-04 (SQLAlchemy 2.x + Alembic), R-05 (índices justificados), R-07/R-08 (privacidad y datos ficticios), RN-OS-01/RN-OS-02, DD-11, governance **MEDIO**.

## Goals / Non-Goals

**Goals:**
- Registrar pacientes con DNI único por consultorio y teléfono WhatsApp obligatorio normalizado.
- Buscar por DNI, teléfono o prefijo de apellido sin volcar la tabla completa.
- Declarar cobertura (obra social + afiliado) de forma coherente.
- Administrar convenios con nomenclador y reglas locales de cobertura validadas.
- Seed demo idempotente con **OS Demo** y pacientes ficticios.

**Non-Goals:**
- Cálculo de cobertura/copago por ítem del presupuesto (RN-OS-02, C-12).
- Integración con nomencladores reales o validación externa (segunda iteración, DD-11).
- Historia clínica, odontograma y consentimientos (C-11).
- Turnos, reserva online y lista de espera (C-06/C-07/C-10).
- Deduplicación difusa de pacientes (fonética, apodo, fecha de nacimiento): v1 usa DNI exacto.

## Decisions

### D1 — Tablas, módulos y migración

Se agregan `pacientes` (módulo `app/models/pacientes.py`) y `obras_sociales` (extiende `app/models/comercial.py`, donde ya vive `Prestacion`). Ambas heredan `AuditMixin` con baja lógica y el CHECK `(deleted_at IS NULL) = is_active`.

La migración es `0005_pacientes_cobertura_base`, `down_revision = "0004_recursos_agendables"`. El roadmap decía «migración 003», pero el head real es `0004`; se corrige la numeración como se hizo en C-04.

### D2 — Identidad del paciente

- `dni` se guarda como string de 7–8 dígitos, sin puntos (`String(8)`), para no perder ceros a la izquierda.
- Es único por consultorio **entre pacientes activos**: índice único parcial `(consultorio_id, dni) WHERE deleted_at IS NULL`. Una baja lógica libera el DNI.
- No se usa el DNI como PK ni como identificador público: la API expone UUID.
- `consultorio_id` obligatorio para no bloquear multisucursal; v1 resuelve el consultorio demo.

### D3 — Normalización de DNI y teléfono como funciones puras

`app/domain/pacientes.py` concentra dos funciones sin I/O, reutilizables por C-07 y testeables por unidad:

1. `normalizar_dni(raw)`: quita puntos, espacios y guiones; exige exactamente 7 u 8 dígitos; devuelve solo dígitos. Cualquier otro formato lanza `ValueError` (el schema lo traduce a 422).
2. `normalizar_telefono(raw)`: quita todo lo que no sea dígito y aplica:
   - 10 dígitos → se interpreta como celular nacional (área + número) y se devuelve `+549{digitos}`;
   - 13 dígitos que empiezan con `549` → se devuelve `+{digitos}`;
   - 12 dígitos que empiezan con `54` (fijo sin `9`) → se rechaza porque el canal es WhatsApp móvil;
   - cualquier otra longitud o prefijo → se rechaza.

El valor canónico cumple `^\+549[0-9]{10}$`, que además es CHECK en PostgreSQL. El teléfono es obligatorio y no puede quedar vacío tras normalizar.

### D4 — Búsqueda acotada y con índice

`GET /pacientes` acepta exactamente `dni`, `telefono` y/o `apellido` (allow-list estricta, 422 ante cualquier otra clave), exige al menos uno y combina con AND:

- `dni`: normaliza y compara igualdad exacta.
- `telefono`: normaliza y compara igualdad exacta.
- `apellido`: prefijo sin distinguir mayúsculas (`lower(apellido) LIKE lower(:q) || '%'`), ordenado por `apellido, nombre`.

Se crea un índice de expresión `lower(apellido) text_pattern_ops` para que el prefijo use índice con la colación habitual de PostgreSQL, más `(consultorio_id, telefono)` y el único parcial `(consultorio_id, dni) WHERE deleted_at IS NULL`. La exigencia de criterio evita un endpoint que devuelva la tabla completa de datos personales.

### D5 — Alta, edición y baja

- `POST /pacientes` valida, normaliza, verifica DNI duplicado (409) y obra social activa (404).
- `PUT /pacientes/{id}` reemplaza los campos editables y repite las validaciones; el DNI puede cambiarse solo si no colisiona con otro activo.
- `DELETE /pacientes/{id}` es baja lógica (204); la ficha posterior responde 404 y la búsqueda no lo devuelve.
- `GET /pacientes/{id}` devuelve la ficha con `obra_social_id` y `nro_afiliado` planos. C-12 expandirá la cobertura calculada.

### D6 — Cobertura coherente

- `obra_social_id` es nullable (paciente particular).
- CHECK `obra_social_id IS NOT NULL OR nro_afiliado IS NULL`: un afiliado sin convenio es un dato incoherente.
- `nro_afiliado` puede ser nulo aunque haya obra social (el paciente puede no recordarlo al registrarse); RN-OS-01 lo exigirá cuando se intente validar cobertura.
- La obra social referenciada debe existir y estar activa; si no, 404 (no se crea el paciente).
- Quitar la cobertura exige limpiar también `nro_afiliado`; el schema lo valida y el CHECK lo respalda.

### D7 — Convenios: unicidad y reglas locales

`obras_sociales` guarda `nombre`, `nomenclador_ref` (nullable), `reglas_cobertura` JSONB (`{}` por defecto) y `validacion_externa`.

- Nombre único por consultorio entre activos, sin distinguir mayúsculas: índice único parcial sobre `lower(nombre)`.
- CHECK `btrim(nombre) <> ''` y `jsonb_typeof(reglas_cobertura) = 'object'`.
- CHECK `NOT validacion_externa`: en v1 no hay integración externa (DD-11/R-12); pedirla es 422, no un flag decorativo.
- La baja lógica libera el nombre.

### D8 — Reglas de cobertura tipadas

`ReglasCobertura` (Pydantic, `extra='forbid'`) admite solo:

| Campo | Tipo | Regla |
|---|---|---|
| `cobertura_porcentaje` | int 0–100, opcional | porcentaje cubierto por el convenio |
| `copago_porcentaje` | int 0–100, opcional | porcentaje a cargo del paciente |
| `prestaciones_cubiertas` | list[str], opcional | códigos en mayúsculas, sin duplicados, existentes en el catálogo activo |
| `requiere_autorizacion` | bool, default false | si la práctica necesita autorización previa |

Si ambos porcentajes están presentes, su suma no puede superar 100. Los códigos se normalizan a mayúsculas y se validan contra `prestaciones` activas al escribir (no al leer: un código puede quedar histórico si la prestación se da de baja). El cálculo efectivo por ítem es C-12.

### D9 — RBAC aplicado a la matriz

- **Pacientes** (no tiene columna propia en la matriz; se mapea al registro operativo de recepción):
  - lectura: `administrador`, `odontologo`, `recepcionista`, `asistente`, `auditor`;
  - alta y edición: `administrador`, `recepcionista`;
  - baja lógica: solo `administrador`.
- **Obras sociales** (columna literal de la matriz):
  - lectura: `administrador`, `odontologo`, `recepcionista`, `auditor`;
  - alta y baja: `administrador`;
  - edición: `administrador`, `recepcionista`;
  - `asistente`: sin acceso (403).

El mapeo de pacientes queda trazado a RN-SE-01 y justificado en la spec.

### D10 — Seed idempotente

Se extiende `app/seed.py` con inserciones `ON CONFLICT DO NOTHING` sin objetivo (cubren cualquier índice único, incluidos los de expresión):

- **OS Demo**: `nomenclador_ref = "DEMO-LOCAL"`, `validacion_externa = false`, reglas `{cobertura_porcentaje: 60, copago_porcentaje: 40, prestaciones_cubiertas: ["CONS","LIM","OBT"]}` (ficticias).
- **3 pacientes ficticios** (`Ana Demo`, `Bruno Demo`, `Carla Demo`) con DNI y teléfonos de prueba válidos: dos con OS Demo y afiliado ficticio, uno particular. No se usan datos de personas reales.

Reejecutar el seed no duplica ni reescribe datos existentes.

### D11 — Validación en dos capas

Pydantic valida el borde HTTP (422, `extra='forbid'`) y PostgreSQL respalda la integridad incluso por SQL directo: CHECK de baja lógica, DNI (`^[0-9]{7,8}$`), teléfono (`^\+549[0-9]{10}$`), coherencia de cobertura, nombre no vacío, tipo JSON de reglas y `validacion_externa = false`. Las reglas semánticas de cobertura (suma de porcentajes, códigos existentes) viven en Pydantic porque requieren consultar el catálogo.

## Risks / Trade-offs

- **Datos personales**: la búsqueda exige criterio y la demo solo usa datos ficticios; no se copian datos reales (R-08/R-12).
- **Teléfono estricto**: se rechazan fijos y formatos sin código 54; es deliberado porque el canal es WhatsApp móvil. Un paciente sin celular se registra cuando exista un canal alternativo.
- **Afiliado opcional**: RN-OS-01 fallará al validar cobertura sin número; se registra como deuda explícita para C-12.
- **Reglas JSONB**: se tipan solo las claves conocidas; una regla futura del nomenclador real requerirá migración de schema, aceptable en v1.
- **Deduplicación**: dos pacientes con el mismo DNI pero distinto consultorio se permiten (multi-tenant); dentro de un consultorio el índice lo impide.

## Migration Plan

1. `alembic upgrade head` aplica `0005`.
2. Reversión: `alembic downgrade 0004_recursos_agendables`.
3. Verificación: suite completa contra la base descartable del Compose, paridad ORM↔esquema en `test_migration.py` y upgrade/downgrade bidireccional.
