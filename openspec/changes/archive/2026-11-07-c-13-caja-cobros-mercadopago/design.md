# Design

## Context

Ver `proposal.md` para la motivación. El estado relevante del repo:

- `Turno.sena_estado` (`no_requiere|pendiente|pagada|perdida`) ya existe desde C-06; C-07 lo marca `perdida` al cancelar fuera de plazo en la ruta pública.
- `Prestacion.requiere_sena/monto_sena` (RN-TU-08) y `Presupuesto.copago` (C-12) son la fuente de los importes; el cliente nunca fija precios.
- `AuditMixin`, `RegistroAuditoria` append-only, `UnitOfWork`/repositorios y `require_role` son los patrones vigentes (R-01..R-04, R-11).
- `platform/job-queues` fija tres nombres y R-06 prohíbe usar Redis como fuente de verdad; el head de migraciones es `0011_presupuestos`.
- `Settings` ya exige `MP_ACCESS_TOKEN`; el proveedor de WhatsApp demuestra el patrón `Protocol` + cliente `test` sin llamadas reales (R-12).

## Goals / Non-Goals

**Goals:**

- Persistir el hecho económico (`Cobro`) y conciliarlo con turno/presupuesto en una sola transacción.
- Cerrar el día con un arqueo que explique el efectivo y detecte diferencias antes de cerrar.
- Integrar Mercado Pago sandbox con un proveedor sustituible, firma de webhook e idempotencia demostrable.
- Mantener la pérdida de seña en agenda y reflejarla en caja sin dos fuentes de verdad.

**Non-Goals:**

- Emisión fiscal, CAE/QR y obras sociales (C-14).
- Devoluciones reales a Mercado Pago, liquidaciones y comisiones.
- UI de caja/cobros (la superficie de pago es el checkout hospedado de MP).
- Cobros con credenciales o costos reales; cualquier llamada de red a MP en v1.

## Decisions

### D1 — Caja con `CajaDiaria` + `MovimientoCaja`, no derivada de `Cobro`

**Decisión**: crear dos tablas además de `cobros`.

- `CajaDiaria`: `consultorio_id`, `fecha` (date, UTC-3), `estado abierta|cerrada`, `monto_apertura`, `monto_sistema_efectivo` (snapshot al cerrar), `monto_contado`, `diferencia`, `cerrada_por`, `cerrada_at`, `observaciones`, columnas de auditoría. Único `(consultorio_id, fecha)`.
- `MovimientoCaja`: `caja_id`, `tipo ingreso|gasto|deuda`, `concepto`, `monto > 0`, `medio efectivo|mercadopago`, `cobro_id` opcional único, `creado_por`, auditoría.

**Por qué**: RN-AD-03 exige ingresos, **gastos y deudas**. `Cobro` solo representa entradas; sin movimientos no hay arqueo real ni forma de explicar un faltante. Derivar todo de `Cobro` obligaría a modelar gastos como cobros negativos, rompiendo la semántica de estados y auditoría.

**Alternativa descartada**: un único `MovimientoCaja` polimórfico que también guarde el cobro; se descartó porque `Cobro` necesita estados de proveedor, idempotencia y relación con turno/presupuesto, y mezclarlo con gastos manuales vuelve ilegible el arqueo.

### D2 — Webhook sincrónico e idempotente, sin cuarta cola Redis

**Decisión**: `POST /webhooks/mercadopago` valida la firma, consulta el pago al proveedor y concilia en una transacción corta; responde 200 al terminar. Si la DB falla, responde 5xx para que MP reintente. No se agrega `pagos:conciliar`.

**Por qué**: R-06 fija los nombres reservados y `platform/job-queues` declara que no se crean otras colas; agregar una cuarta exigiría modificar una regla dura y una capability de plataforma fuera del alcance de C-13. La conciliación es una escritura puntual (marcar cobro, movimiento, seña) y la idempotencia se garantiza con índices únicos, no con una cola. Si en el futuro la conciliación incluye llamadas lentas (p. ej. ARCA), ese trabajo ya tiene su cola `arca:emitir` en C-14.

**Trade-off**: un pico de webhooks golpea la API en lugar de desacoplarse. Mitigación: transacción mínima, índices únicos y reintentos de MP; si el volumen lo exige, se propone `pagos:conciliar` en un change que modifique explícitamente `platform/job-queues` y R-06.

### D3 — Proveedor de pagos abstraído con doble de prueba

**Decisión**: `app/infrastructure/mercadopago.py` define `MercadoPagoClient` (`Protocol`) con:

- `crear_preferencia(cobro_id, monto, descripcion) -> PreferenciaPago(preferencia_id, link_pago)`.
- `consultar_pago(pago_id) -> PagoNormalizado | None` (`proveedor_pago_id`, `cobro_id`, `estado aprobado|rechazado|pendiente`, `monto`, `moneda`, `fecha`).
- `TestMercadoPagoClient` registra preferencias en memoria, devuelve `test-pref-<uuid>` y un link sandbox ficticio, y resuelve pagos desde un diccionario que los tests pueblan con `simular_pago(...)`. `get_mercadopago_client` falla si `MP_PROVIDER != "test"`.

**Por qué**: R-12 exige sandbox sin costo; el patrón es idéntico al de `infrastructure/whatsapp.py`. El webhook no confía en el cuerpo: la verdad del pago la da `consultar_pago`, y el cuerpo solo aporta el id. Eso evita manipulación de montos/estados.

### D4 — La pérdida de seña sigue viviendo en agenda

**Decisión**: `Turno.sena_estado` es la única fuente de verdad. C-13 agrega un hook `sincronizar_sena_perdida(uow, turno, ...)` que, si el turno quedó `perdida`, busca el cobro de seña vivo (`pendiente|aprobado`) y lo pasa a `perdido`, auditando `cobro.perder`. Se llama en la misma transacción desde:

1. `PATCH /turnos/{id}/estado` cuando el nuevo estado es `ausente`, o `cancelado` fuera del plazo (paridad con la ruta pública, delta de `agenda/turnos`).
2. La cancelación pública existente de C-07, después de marcar `Turno.sena_estado='perdida'`.

**Por qué**: evita dos implementaciones de RN-TU-04. Caja no decide si la seña se pierde; solo refleja la decisión de agenda. El dinero ya ingresado no se revierte: el cobro cambia de estado y el ingreso del día se conserva.

### D5 — Reembolso: solo estado y auditoría en v1

**Decisión**: `POST /cobros/{id}/reembolsar` pasa un cobro `aprobado` a `reembolsado` y audita. No llama a MP (el doble de prueba no implementa devolución real) ni crea un egreso automático. Si el reembolso es en efectivo, el ajuste se registra como `gasto` manual en la caja abierta.

**Por qué**: no hay integración real de devolución y un egreso automático podría descuadrar el arqueo sin que el dinero haya salido físicamente. Repetir el reembolso es idempotente (200, sin segunda auditoría).

### D6 — Fecha operativa y zona horaria

**Decisión**: todo cálculo de "día" usa `TZ_ARGENTINA` (`UTC-3`, ya definido en `app/domain/turnos.py`).

- `Cobro.fecha_operacion`: fecha local de creación (para listados).
- `Cobro.fecha_conciliacion`: timestamp UTC en que se aprueba/rechaza; el movimiento de caja se imputa a `fecha_conciliacion.astimezone(TZ_ARGENTINA).date()`.
- `CajaDiaria.fecha`: date local; único por consultorio.
- `MovimientoCaja` no guarda fecha propia: hereda la de su caja.

**Por qué**: un pago confirmado a las 23:30 de Argentina no debe caer en el día siguiente por estar en UTC. Imputar el ingreso a la fecha de conciliación (no a la de creación de la preferencia) refleja cuándo entró realmente el dinero.

### D7 — Idempotencia y unicidad en PostgreSQL

**Decisión**:

- Índice único parcial `uq_cobros_proveedor_pago` sobre `proveedor_pago_id` (no nulo).
- Índice único parcial `uq_cobros_sena_turno` sobre `turno_id` donde `tipo='sena' AND estado IN ('pendiente','aprobado','perdido')`.
- Índice único parcial `uq_movimientos_caja_cobro` sobre `cobro_id` (no nulo).
- El webhook atrapa `IntegrityError` (`23505`), recarga el cobro y responde 200 si el mismo pago ya fue procesado; 409 si es un segundo pago distinto para una seña ya aprobada.

**Por qué**: la aplicación valida para dar mensajes claros, pero la carrera concurrente la resuelve la base. Es el patrón ya usado por las constraints de exclusión de C-06.

### D8 — RBAC y auditoría

Matriz aplicada (de `03_actores_y_roles.md`):

| Recurso | Lectura | Escritura | Notas |
|---|---|---|---|
| `/cobros` | administrador, recepcionista, auditor, odontólogo | administrador, recepcionista | Odontólogo filtra por `turno.profesional_id` o `presupuesto.profesional_id`; ficha ajena 403 |
| `/caja`, `/caja/arqueo` | administrador, recepcionista, auditor | administrador, recepcionista | Odontólogo y asistente 403 |
| `/webhooks/mercadopago` | público | — | Solo la firma autoriza |

Acciones auditadas: `cobro.crear`, `cobro.conciliar`, `cobro.reembolsar`, `cobro.perder`, `caja.abrir`, `caja.movimiento`, `caja.cerrar`. El webhook audita con `usuario_id=None` (actor sistema). Todas las filas se insertan con `infrastructure/audit.registrar` en la transacción del caso de uso.

### D9 — Esquema y migración `0012_caja_cobros`

`cobros`:

- `id` UUID PK; `consultorio_id`, `paciente_id`, `turno_id?`, `presupuesto_id?`, `creado_por?` (nulo para sistema) con FKs `RESTRICT`.
- `tipo` (`sena|tratamiento|otro`), `medio` (`efectivo|mercadopago`), `estado` (`pendiente|aprobado|rechazado|reembolsado|perdido`).
- `monto Numeric(12,2) > 0`; `proveedor_pago_id varchar(100)?`; `proveedor_preferencia_id varchar(100)?`; `link_pago text?`.
- `fecha_operacion date NOT NULL`; `fecha_conciliacion timestamptz?`; columnas de auditoría.
- CHECKs: combinación tipo/referencias (`sena` exige turno y prohíbe presupuesto; `tratamiento` al revés; `otro` sin ambos), `monto > 0`, `medio='efectivo'` no puede estar `pendiente`, `proveedor_pago_id` solo con `mercadopago`, baja lógica coherente.
- Índices: `ix_cobros_paciente_fecha`, `ix_cobros_turno`, `ix_cobros_presupuesto`, `ix_cobros_estado`, más los únicos parciales de D7.

`cajas_diarias`:

- `id`, `consultorio_id`, `fecha date`, `estado abierta|cerrada`, `monto_apertura >= 0`, `monto_sistema_efectivo?`, `monto_contado?`, `diferencia?`, `cerrada_por?`, `cerrada_at?`, `observaciones varchar(500)?`, auditoría.
- Único `(consultorio_id, fecha)`; CHECK de coherencia: `cerrada` exige snapshot, contado, diferencia, usuario y fecha de cierre; `abierta` los prohíbe; `diferencia = monto_contado - monto_sistema_efectivo`.

`movimientos_caja`:

- `id`, `caja_id`, `tipo ingreso|gasto|deuda`, `concepto varchar(200)`, `monto > 0`, `medio efectivo|mercadopago`, `cobro_id?`, `creado_por?`, auditoría.
- Índice `ix_movimientos_caja_caja`; único parcial de `cobro_id`; CHECK de baja lógica.

Downgrade: `movimientos_caja` → `cajas_diarias` → `cobros` (respetando FKs). No se altera ninguna tabla existente ni se backfillean datos; las señas históricas de C-07 no tienen `Cobro` y quedan como están.

### D10 — API y flujo de casos de uso

`/cobros`:

- `POST /cobros` → valida según `tipo`, crea cobro y, si corresponde, preferencia, movimiento y conciliación de seña. Devuelve 201 con `link_pago` (MP) y `saldo_pendiente` (tratamiento).
- `GET /cobros?paciente_id&turno_id&presupuesto_id&estado&medio&fecha_desde&fecha_hasta` y `GET /cobros/{id}`.
- `POST /cobros/{id}/reembolsar`.

`/caja`:

- `POST /caja/abrir` (`monto_apertura`, `fecha?`), `GET /caja?fecha` (ficha), `POST /caja/movimientos`, `GET /caja/movimientos?fecha`, `GET /caja/arqueo?fecha`, `POST /caja/cerrar` (`monto_contado`, `observaciones?`).

`POST /webhooks/mercadopago` (público): firma → `consultar_pago` → conciliación → 200. Errores: 401 firma, 404 referencia desconocida, 409 monto/moneda o segundo pago, 5xx para reintento.

**Caja automática**: un cobro en efectivo o un movimiento manual exige caja abierta de la fecha (409 si no existe o está cerrada). La conciliación de un cobro por Mercado Pago crea la caja del día con apertura 0 si no existe, porque ese dinero no afecta el efectivo del cajón. Para evitar carreras, se apoya en el único `(consultorio_id, fecha)` y reintenta la lectura tras `IntegrityError`. El cierre bloquea la fila de la caja (`SELECT ... FOR UPDATE`) para que no entren movimientos concurrentes.

**Validación de tratamiento**: se suman los cobros `tratamiento` en `aprobado` del presupuesto y se compara contra `copago`; el servicio devuelve el saldo. El exceso se rechaza con 409. El cobro no cambia el estado del presupuesto (eso es C-12).

### D11 — Esquema Pydantic y borde estricto

Todos los cuerpos usan `extra='forbid'` (R-01). Excepción documentada: el cuerpo del webhook de MP declara solo `type`, `action` y `data.id` con `extra='ignore'`, porque el proveedor agrega campos y el límite de confianza real es la firma + `consultar_pago`, no el esquema. No se aceptan montos ni estados enviados por el cliente en ningún alta.

### D12 — Estrategia de pruebas

- **Unitarias**: totales de arqueo, cálculo de fecha UTC-3, HMAC de firma, máquina de estados de cobro, reglas de seña/tratamiento puras.
- **Integración con PostgreSQL real**: migración `0012`, CHECKs e índices únicos por SQL directo, alta efectivo/MP, webhook duplicado/tardío/firma inválida, pérdida de seña por cancelación tardía y ausentismo, cierre descuadrado, RBAC y auditoría.
- **Proveedor**: doble en memoria; un test verifica que no hay llamadas de red y que el link es ficticio.
- **Evidencia**: `docs/skills-mcp/evidencias/c-13/` con salidas de tests, `curl` de smoke y verificación de migración.

## Risks / Trade-offs

- **Webhook sincrónico bajo carga** → transacción mínima + índices únicos; si el volumen crece, se evalúa `pagos:conciliar` con cambio explícito de `platform/job-queues`/R-06.
- **Divergencia con el sandbox real de MP** (firma, forma del payload, estados) → el proveedor normaliza; el doble de prueba fija el contrato y los tests cubren firma inválida y estados.
- **Caja cerrada con pagos pendientes** → el ingreso se imputa a la fecha de conciliación; si el día ya cerró, la conciliación responde 409 y requiere intervención, en lugar de reescribir un arqueo cerrado.
- **Segundo pago real para una seña ya aprobada** → 409 + auditoría para devolución manual; no se crea un segundo cobro ni se pierde el registro del evento.
- **Pérdida de seña en efectivo** → el cobro pasa a `perdido` pero el ingreso se conserva (la clínica retiene el dinero); no se genera un movimiento de reversión.
- **Zona horaria** → un único helper `fecha_local()` evita que cada servicio reimplemente el cálculo; los tests cubren el cruce 02:30 UTC.
- **Sin UI** → el flujo se valida por API y checkout hospedado; la pantalla de caja queda para un change posterior, lo que reduce el alcance de C-13 pero deja una deuda visible.

## Migration Plan

1. `alembic upgrade head` aplica `0012_caja_cobros`; solo crea tablas nuevas, sin tocar datos existentes.
2. Desplegar API y workers con `MP_PROVIDER=test` y `MP_WEBHOOK_SECRET` configurado; el seed demo no cambia.
3. Smoke: abrir caja, cobrar efectivo, crear seña MP, simular webhook aprobado, consultar arqueo y cerrar cuadrado.
4. Rollback: `alembic downgrade 0011_presupuestos` elimina las tres tablas nuevas; no hay pérdida de datos de changes anteriores.

## Open Questions

- Ninguna que cambie el alcance de C-13. La comisión real de MP, las devoluciones efectivas y la conciliación de liquidaciones quedan para C-14/C-15 y no afectan este diseño.
