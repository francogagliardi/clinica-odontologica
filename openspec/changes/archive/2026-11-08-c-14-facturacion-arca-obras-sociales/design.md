# Design

## Context

Ver `proposal.md` para la motivación. El estado relevante del repo:

- C-13 dejó `Cobro` (`pendiente|aprobado|rechazado|reembolsado|perdido`) con hooks de aprobación en `application/cobros.crear_cobro` (efectivo) y `conciliar_pago` (webhook Mercado Pago). El head de migraciones es `0012_caja_cobros`.
- `Presupuesto`/`ItemPresupuesto` ya guardan `cobertura_calculada`, `copago`, `cobertura_item` y `copago_item` con aritmética cuantizada; `LocalCoberturaProvider` resuelve el convenio local de "OS Demo" (60 % y códigos `CONS`, `LIM`, `OBT`) y `calcular_item` calcula cobertura/copago.
- `Paciente` tiene nombre, apellido, DNI, teléfono obligatorio, email opcional, `obra_social_id` y `nro_afiliado`; no tiene condición fiscal ni domicilio.
- `platform/job-queues` fija `arca:emitir` y R-06 prohíbe que Redis sea fuente de verdad; `try_enqueue` es best-effort y no falla el request.
- `infrastructure/whatsapp.py` demuestra el patrón `Protocol` + `TestWhatsAppClient` sin red; `MensajeWhatsApp` exige turno o lista de espera y una lista cerrada de plantillas.
- `btree_gist` ya está habilitado por C-06, por lo que un `EXCLUDE USING gist` con `daterange` es viable sin extensión nueva.
- `AuditMixin`, `RegistroAuditoria` append-only, `UnitOfWork`/repositorios y `require_role` son los patrones vigentes (R-01..R-05, R-11).

## Goals / Non-Goals

**Goals:**

- Garantizar que todo cobro aprobado tenga exactamente un comprobante, con numeración interna gapless y respaldo verificable aunque ARCA esté caído.
- Emitir la factura fiscal en homologación mediante un proveedor sustituible, con CAE/QR deterministas e idempotencia demostrable por test.
- Procesar `arca:emitir` con claim atómico, reintentos exponenciales y barrido de pendientes, sin depender de Redis para no perder jobs.
- Validar cobertura de forma consultiva y liquidar por período con trazabilidad a presupuesto/ítem/cobro.
- Cubrir RBAC y auditoría sin cambiar los contratos de C-13 ni las specs archivadas.

**Non-Goals:**

- Certificados, CUIT/CERT/KEY reales, red hacia ARCA, notas de crédito o anulación fiscal.
- Topes, frecuencias y nomenclador real de obras sociales; PUCO u otra integración externa.
- Envío real de email o de WhatsApp por Meta; solo proveedor de prueba y registro persistido.
- UI fiscal, envío masivo, conciliación de pagos de obras sociales y reportes (C-15).
- Modificar `MensajeWhatsApp`, `whatsapp:send` o la lista cerrada de plantillas de C-09.

## Decisions

### D1 — Una sola tabla `comprobantes`, un registro por cobro

**Decisión**: `comprobantes` tiene `cobro_id` único y guarda en la misma fila el comprobante interno (número propio, QR interno, fecha de emisión interna) y, cuando existe, el fiscal (CAE, número fiscal, QR fiscal, fecha fiscal). El estado `pendiente|emitido|fallido` describe la situación fiscal.

**Por qué**: la invariante "todo cobro aprobado tiene un comprobante" se expresa como un único índice sobre `cobro_id`; no hace falta un arco exclusivo entre dos tablas ni un `LEFT JOIN` que pueda quedar inconsistente. La fila conserva la evidencia del comprobante interno aunque la emisión fiscal llegue después. La creación es idempotente: si ya existe un comprobante para el cobro, se devuelve sin una segunda numeración ni una segunda auditoría; el índice único resuelve la carrera.

**Alternativa descartada**: `ComprobanteInterno` + `ComprobanteARCA` separados. Obligaría a garantizar por trigger que un cobro tiene al menos uno de los dos, permitiría dos filas fiscales si falla la aplicación y duplicaría numeración/repositorios. La tabla única es más simple y auditable; el costo es que la fila mezcla dos momentos, resuelto con columnas separadas (`qr_interno`/`qr_fiscal`, `fecha_emision`/`fecha_emision_fiscal`).

**Alternativa descartada**: derivar el comprobante interno del cobro sin persistirlo. No habría numeración propia ni QR verificable, y "comprobante interno emitido" sería una promesa sin respaldo.

### D2 — Numeración interna y fiscal con secuencias por consultorio

**Decisión**: tabla `secuencias_comprobantes(consultorio_id, punto_venta, ultimo_interno, ultimo_fiscal)` con PK compuesta. La creación del comprobante hace `INSERT ... ON CONFLICT DO NOTHING` y luego `UPDATE ... SET ultimo_interno = ultimo_interno + 1 RETURNING ultimo_interno` dentro de la transacción del cobro. La emisión fiscal hace lo mismo con `ultimo_fiscal` en la transacción que persiste el CAE. `punto_venta` sale de `ARCA_PUNTO_VENTA` (default `1`) y es fijo en v1.

**Por qué**: un `UPDATE` bloquea la fila y serializa la numeración sin carreras; si la transacción se revierte, el número no se consume (gapless). La numeración fiscal se asigna recién al persistir el éxito, así que un fallo de persistencia no quema un número. `UNIQUE (consultorio_id, punto_venta, numero_interno)` y `UNIQUE (ambiente, punto_venta, numero_fiscal)` hacen la garantía visible en la base.

**Trade-off**: dos contadores en una fila implican que un `UPDATE` de emisión fiscal espera si hay una creación concurrente; la transacción es corta y el volumen de una clínica no lo hace problemático.

### D3 — `ArcaClient` con doble de prueba determinista

**Decisión**: `app/infrastructure/arca.py` define:

- `ResultadoEmision(cae: str, cae_vencimiento: date)`.
- `ArcaClient` (`Protocol`) con `emitir(*, clave_idempotencia: str, tipo: str, punto_venta: int, importe: Decimal, receptor: DatosReceptor) -> ResultadoEmision`.
- `TestArcaClient`: deriva un CAE de 14 dígitos con SHA-256 de `clave_idempotencia`, calcula vencimiento a 10 días, registra las llamadas en memoria y permite `simular_fallo(veces)`/`disponible=False`. No lee certificados ni abre sockets.
- `get_arca_client(settings)`: solo acepta `ARCA_PROVIDER='test'`; cualquier otro valor lanza `RuntimeError` explícito (R-12).

**Por qué**: el contrato es el mismo que el de WhatsApp/MP; el test puede probar determinismo, fallo inyectable y ausencia de red sin credenciales. La clave de idempotencia es el UUID del comprobante, estable entre reintentos.

**Alternativa descartada**: mockear el módulo en cada test. El doble real mantiene el contrato y permite tests de worker sin parchear imports.

### D4 — El comprobante es el job durable; la cola es un acelerador

**Decisión**: al crear el comprobante se hace `try_enqueue(redis, ARCA_EMITIR, str(comprobante.id))` best-effort. El worker, en cada tick, hace `BRPOP` de un id y además barre `comprobantes` con `estado='pendiente'` y `proximo_intento <= now()` (o nulo). El barrido no depende de la cola.

**Por qué**: R-06 exige que PostgreSQL sea la fuente de verdad. Si Redis se cae o el mensaje se pierde, el barrido retoma el trabajo; si el mensaje se duplica, el claim lo descarta. Encolar en el alta cumple el requisito explícito de "encolar en `arca:emitir`" sin convertir la cola en la única fuente.

**Claim atómico**: dos transacciones cortas separadas por la llamada al proveedor:

1. `UPDATE comprobantes SET claim_token = :token, reclamado_at = now() WHERE id = :id AND estado = 'pendiente' AND (proximo_intento IS NULL OR proximo_intento <= now()) AND (reclamado_at IS NULL OR reclamado_at < now() - interval '5 minutes') RETURNING id`. Si no devuelve fila, otro worker lo tomó o ya terminó: se omite.
2. Llamada al proveedor, fuera de la transacción de base.
3. `UPDATE ... WHERE id = :id AND claim_token = :token AND estado = 'pendiente'` para persistir `emitido|fallido` y limpiar `claim_token`/`reclamado_at`. Si no actualiza, el resultado se descarta; como la clave de idempotencia es estable, el próximo intento obtiene el mismo CAE.

**Por qué no `SELECT FOR UPDATE` durante la llamada**: mantener un lock de fila mientras se espera a un tercero alarga transacciones y bloquea el barrido. El claim con token y vencimiento es más robusto ante crashes y sigue siendo atómico.

### D5 — Idempotencia fiscal en PostgreSQL y en el proveedor

**Decisión**:

- `UNIQUE (cobro_id)` en `comprobantes`: un comprobante por cobro.
- `UNIQUE (ambiente, cae) WHERE cae IS NOT NULL`: un CAE no se reutiliza.
- `UNIQUE (ambiente, punto_venta, numero_fiscal) WHERE numero_fiscal IS NOT NULL`: numeración fiscal única.
- El worker nunca emite un comprobante `emitido`; si lo recibe, no llama al proveedor.
- El reintento manual sobre `fallido` resetea `intentos=0`, `proximo_intento=NULL`, `claim_token=NULL` y lo deja `pendiente` antes de encolar.
- `TestArcaClient` deriva el CAE de la clave de idempotencia, así que un reintento tras un fallo de persistencia devuelve el mismo CAE. El adaptador real (fuera de v1) deberá usar la misma clave o consultar el comprobante antes de reintentar; queda documentado como responsabilidad del adaptador.

**"CAE obtenido pero falla el persistir"**: la transacción de persistencia se revierte, la fila sigue `pendiente` y el claim vence a los 5 minutos. El reintento vuelve a llamar con la misma clave, obtiene el mismo CAE y persiste una sola fila. El `UNIQUE (ambiente, cae)` es la red de seguridad si un adaptador devolviera un CAE distinto y ya existiera.

**Alternativa descartada**: guardar el CAE en Redis antes de PostgreSQL. R-06 lo prohíbe y un Redis volátil perdería el CAE.

### D6 — Receptor mínimo v1: consumidor final con DNI

**Decisión**: el comprobante guarda un snapshot de `receptor_nombre` (`apellido, nombre`), `receptor_documento` (DNI), `receptor_tipo_documento='DNI'` y `condicion_fiscal_receptor='consumidor_final'`. El emisor se configura con `ARCA_CONDICION_EMISOR` (`responsable_inscripto` default → Factura B; `monotributista` → Factura C). El `tipo` se decide al crear el comprobante y no cambia.

**Por qué**: `Paciente` no tiene condición fiscal, domicilio ni tipo de documento, y agregarlos excede C-14. El snapshot evita que una edición posterior del paciente altere un comprobante ya emitido. La condición del emisor modela el único caso en que cambia B/C sin inventar datos del receptor.

**Faltantes documentados**: condición fiscal del paciente, domicilio, tipo de documento distinto de DNI, exenciones y percepción. Se registrarán como pregunta abierta para una iteración con datos fiscales reales.

### D7 — QR fiscal AFIP y QR interno verificable

**Decisión**:

- Fiscal: `https://www.afip.gob.ar/fe/qr/?p=<base64url(JSON)>` con `ver=1`, `fecha`, `cuit`, `ptoVta`, `tipoCmp` (6=B, 11=C), `nroCmp`, `importe`, `moneda='PES'`, `ctz=1`, `tipoDocRec=96`, `nroDocRec`, `tipoCodAut='E'`, `codAut=CAE`.
- Interno: `https://app.local/comprobantes/verificar?p=<base64url(JSON)>` con `tipo='INTERNO'`, `comprobante_id`, `numero_interno`, `importe`, `fecha`; no usa un CAE falso ni el dominio de AFIP.

Ambos se generan en `domain/fiscal.py` como funciones puras y se guardan como `Text`; no se resuelven por red. El QR fiscal solo existe cuando `estado='emitido'`.

**Por qué**: el formato AFIP es el que un verificador esperaría y permite un test de decodificación real; separar el interno evita confundir un comprobante no fiscal con uno autorizado.

### D8 — Validación de cobertura reutilizando `LocalCoberturaProvider`

**Decisión**: `application/cobertura.py` recibe el `CoberturaProvider` inyectado (`get_cobertura_provider()` de C-12) y devuelve:

- `None` del proveedor → `estado='pendiente_verificacion'`, `cobertura_porcentaje/monto` y `copago_monto` nulos.
- Paciente con obra social pero `nro_afiliado` nulo → `pendiente_verificacion` (afiliación no verificable, RN-OS-01), antes de consultar el proveedor.
- `CoberturaConvenio(0)` (paciente sin OS) → `no_cubierta`, 0 % y copago = precio base.
- `CoberturaConvenio` con porcentaje → `cubierta` si `cubre(codigo)`, si no `no_cubierta`; los montos salen de `calcular_item(precio_base, 1, porcentaje)`.

No escribe ni audita (es una lectura). El endpoint vive en un router con `prefix="/obras-sociales"` incluido antes del router de convenios, o declara `/cobertura` antes de `/{obra_social_id}`, para que FastAPI no lo interprete como un UUID.

**Por qué**: reutilizar el proveedor y `calcular_item` mantiene una sola definición de cobertura/copago (RN-OS-02) y permite que un test inyecte `CoberturaNoDisponible` para el estado pendiente. No se crea un servicio de cobertura paralelo. La validación es más estricta que C-12 en un punto: exige `nro_afiliado` para considerar cubierta una práctica, porque RN-OS-01 habla de afiliación; no modifica presupuestos ya calculados.

**Non-goal explícito**: topes, frecuencias y nomenclador real no se modelan; la respuesta no incluye esos campos y no hay llamada externa. Un convenio sin reglas utilizables es `pendiente_verificacion`, nunca una cobertura inventada.

### D9 — Liquidación desde ítems de presupuesto con cobro aprobado en el período

**Decisión**: `POST /obras-sociales/liquidaciones` recibe `obra_social_id`, `desde`, `hasta` y `observaciones?`. La selección:

1. Cobros `tipo='tratamiento'`, `estado='aprobado'`, `fecha_operacion BETWEEN desde AND hasta`, de pacientes con `obra_social_id` igual y mismo consultorio; se toma un cobro por presupuesto (el de menor `fecha_operacion`/id) como referencia.
2. Presupuestos en `aceptado|en_curso|finalizado` de esos cobros.
3. `ItemPresupuesto` activos con `cobertura_item > 0` que no estén en `items_liquidacion` vigentes.

Cada `items_liquidacion` guarda `item_presupuesto_id`, `presupuesto_id`, `cobro_id`, `prestacion_id`, `prestacion_codigo`, `pieza`, `cantidad` y `cobertura_item` (snapshot). `total_cobertura = SUM(cobertura_item)` y `cantidad_practicas = COUNT(*)`.

**Por qué**: el sistema no tiene un registro de "práctica realizada" por ítem (las evoluciones no se vinculan a ítems). El cobro de tratamiento aprobado es la señal más cercana de que el trabajo se facturó y tiene fecha real; el estado del presupuesto evita incluir borradores. La referencia al cobro es la trazabilidad que pide RN-OS-03.

**Duplicados**: `UNIQUE (item_presupuesto_id) WHERE deleted_at IS NULL` en `items_liquidacion` impide liquidar dos veces el mismo ítem, incluso entre períodos. Dos pagos parciales del mismo presupuesto no duplican ítems porque se agrupa por presupuesto.

**Período**: `desde <= hasta`, fechas locales (UTC-3) y `EXCLUDE USING gist (obra_social_id WITH =, daterange(desde, hasta, '[]') WITH &&) WHERE (deleted_at IS NULL)` en la cabecera. Un solapamiento da 409 en el servicio y `23P01` por SQL directo.

**Estados**: `borrador` → `cerrada`. Cerrar congela ítems/totales y exige administrador; repetir el cierre es no-op 200. `PUT` solo actualiza `observaciones` en borrador (admin/recepción). `DELETE` solo borra lógicamente un borrador (admin) y borra lógicamente sus ítems, liberando el período y los ítems; no hay anulación de cerradas (non-goal).

**Alternativas descartadas**: liquidar desde `Cobro` sin ítems (no hay detalle de prácticas ni cobertura por línea); liquidar desde turnos atendidos (no hay vínculo ítem-turno y una práctica puede abarcar varios turnos); liquidar desde `Presupuesto` completo (incluiría ítems no cubiertos y no tendría el período de cobro).

### D10 — Envío de factura simulado, sin tocar C-09

**Decisión**: tabla `comprobantes_envios` (`comprobante_id`, `canal`, `destino`, `estado registrado|fallido`, `proveedor_mensaje_id`, `error`, `creado_por`, timestamps) con `UNIQUE (comprobante_id, canal)`. `POST /comprobantes/{id}/enviar` acepta `{canal: 'whatsapp', destino?: string}`; si no hay destino usa `paciente.telefono`. Exige `estado='emitido'`; llama a `get_whatsapp_client(settings)` (`TestWhatsAppClient`) con plantilla `"factura"` y variables `{numero, cae, importe, qr}`; persiste el resultado. Repetir el envío devuelve 200 con la fila existente y no duplica la auditoría. `canal='email'` responde 422 en v1 (no hay proveedor de email y no se simula un envío real).

**Por qué**: `MensajeWhatsApp` tiene un CHECK que exige turno o lista de espera y una lista cerrada de plantillas; reutilizarlo obligaría a modificar C-09 en este change. El patrón de proveedor de WhatsApp ya existe y demuestra el envío sin red/costo (R-12). La deuda (historial de mensajes unificado) queda visible.

**Alternativa descartada**: encolar en `whatsapp:send` con un `MensajeWhatsApp` de factura. Requiere migrar el CHECK, la plantilla y el worker de C-09; es un change de comunicaciones, no de facturación.

### D11 — RBAC y auditoría

Matriz aplicada (de `03_actores_y_roles.md`):

| Recurso | Lectura | Escritura | Notas |
|---|---|---|---|
| `/comprobantes` | administrador, recepción, odontólogo, auditor | — | La creación es del sistema (hook del cobro) |
| `/comprobantes/{id}/reintentar`, `/enviar` | — | administrador, recepción | Asistente 403; odontólogo 403 |
| `/obras-sociales/cobertura` | administrador, recepción, odontólogo, auditor | — | Consultiva; asistente 403 |
| `/obras-sociales/liquidaciones` | administrador, recepción, odontólogo, auditor | crear/cerrar/borrar: administrador; observaciones: administrador/recepción | Ficha incluye ítems |

Acciones auditadas: `comprobante.crear`, `comprobante.emitir`, `comprobante.emitir_fallido`, `comprobante.reintentar`, `comprobante.enviar`, `liquidacion.crear`, `liquidacion.editar`, `liquidacion.cerrar`, `liquidacion.eliminar`. El worker y el webhook auditan con `usuario_id=None` (actor sistema). Las lecturas no auditan. Las repeticiones idempotentes (envío repetido, cierre repetido, reintento de un `emitido`) no duplican auditoría. Todas las filas se insertan con `infrastructure/audit.registrar` en la transacción del caso de uso; una escritura rechazada no deja fila.

### D12 — Esquema y migración `0013_facturacion_arca`

**`comprobantes`**:

- `id` UUID PK; `consultorio_id`, `cobro_id` (UNIQUE), `paciente_id` con FKs `RESTRICT`.
- `tipo` (`B|C`), `ambiente` (`homologacion`), `estado` (`pendiente|emitido|fallido`), `numero_interno BIGINT > 0`, `punto_venta INT > 0`, `numero_fiscal BIGINT?`, `cae VARCHAR(14)?`, `cae_vencimiento DATE?`, `qr_interno TEXT NOT NULL`, `qr_fiscal TEXT?`.
- Snapshot: `receptor_nombre`, `receptor_documento`, `receptor_tipo_documento`, `condicion_fiscal_receptor`, `condicion_fiscal_emisor`, `importe_total Numeric(12,2) > 0`.
- `fecha_emision DATE NOT NULL` (interna, UTC-3), `fecha_emision_fiscal TIMESTAMPTZ?`.
- Reintentos: `intentos INT >= 0`, `proximo_intento TIMESTAMPTZ?`, `ultimo_error TEXT?`, `claim_token UUID?`, `reclamado_at TIMESTAMPTZ?`.
- `payload_envio JSONB`, `respuesta_proveedor JSONB`, columnas de auditoría.
- CHECK de coherencia: `emitido` exige CAE, vencimiento, número fiscal, QR fiscal y fecha fiscal; `pendiente|fallido` los prohíben; `fallido` exige `ultimo_error`; `intentos >= 0`; tipo/ambiente válidos.
- Índices: `uq_comprobantes_cobro`, `uq_comprobantes_numero_interno (consultorio_id, punto_venta, numero_interno)`, `uq_comprobantes_cae (ambiente, cae) WHERE cae IS NOT NULL`, `uq_comprobantes_fiscal (ambiente, punto_venta, numero_fiscal) WHERE numero_fiscal IS NOT NULL`, `ix_comprobantes_estado_proximo (estado, proximo_intento)`, `ix_comprobantes_paciente`, `ix_comprobantes_fecha`.

**`comprobantes_envios`**: `id`, `comprobante_id`, `canal` (`whatsapp`), `destino`, `estado` (`registrado|fallido`), `proveedor_mensaje_id?`, `error?`, `creado_por?`, timestamps; `UNIQUE (comprobante_id, canal)`.

**`secuencias_comprobantes`**: `consultorio_id`, `punto_venta`, `ultimo_interno BIGINT`, `ultimo_fiscal BIGINT`, PK `(consultorio_id, punto_venta)`.

**`liquidaciones_obras_sociales`**: `id`, `consultorio_id`, `obra_social_id`, `creado_por`, `desde DATE`, `hasta DATE`, `estado` (`borrador|cerrada`), `total_cobertura Numeric(12,2) >= 0`, `cantidad_practicas INT >= 0`, `observaciones?`, `cerrada_por?`, `cerrada_at?`, auditoría; CHECK `desde <= hasta`, cierre coherente; exclusion constraint de período; índices por `(consultorio_id, obra_social_id, desde)` y `(estado)`.

**`items_liquidacion`**: `id`, `liquidacion_id`, `item_presupuesto_id`, `presupuesto_id`, `cobro_id`, `prestacion_id`, `prestacion_codigo`, `pieza?`, `cantidad > 0`, `cobertura_item >= 0`, auditoría; `UNIQUE (item_presupuesto_id) WHERE deleted_at IS NULL`; índices por liquidación, presupuesto y cobro.

**Downgrade**: `items_liquidacion` → `liquidaciones_obras_sociales` → `secuencias_comprobantes` → `comprobantes_envios` → `comprobantes`. No se alteran tablas existentes ni se backfillean cobros históricos de C-13 (quedan sin comprobante; el change no promete regularizar el pasado).

### D13 — API, bordes estrictos y configuración

- `GET /comprobantes?cobro_id&paciente_id&estado&desde&hasta&tipo` con `reject_unexpected_query_except`; `GET /comprobantes/{id}`; `POST /comprobantes/{id}/reintentar`; `POST /comprobantes/{id}/enviar` con `CobroEnvioCreate` (`canal`, `destino?`, `extra='forbid'`).
- `GET /obras-sociales/cobertura?paciente_id&prestacion_id`; `POST/GET /obras-sociales/liquidaciones`; `GET /obras-sociales/liquidaciones/{id}`; `PUT .../{id}` (`observaciones`); `POST .../{id}/cerrar`; `DELETE .../{id}`.
- Todos los cuerpos Pydantic v2 con `extra='forbid'`; respuestas sin secretos, sin rutas de certificados y sin payload crudo del proveedor.
- `Settings` suma `arca_provider: str = "test"`, `arca_punto_venta: int = 1`, `arca_condicion_emisor: str = "responsable_inscripto"`, `arca_max_intentos: int = 5`, `arca_worker_interval_seconds: int = 30`; valida el proveedor y la condición del emisor al construir el cliente.
- El worker suma el modo `arca` (`python -m app.workers arca [--once]`), sin cambiar los modos existentes.

### D14 — Estrategia de pruebas

- **Unitarias**: QR encode/decode (fiscal e interno), CAE determinista por clave, vencimiento, máquina de estados del comprobante, clasificación `cubierta|no_cubierta|pendiente`, totales de liquidación y backoff.
- **Integración con PostgreSQL real**: migración `0013`; CHECKs e índices únicos por SQL directo; hook de efectivo y de webhook MP; claim concurrente (dos workers, una emisión); reintento con backoff y tope; CAE obtenido + fallo de persistencia; barrido sin Redis; envío simulado; cobertura; liquidación (ítems, duplicados, solapamiento `23P01`, cierre, borrado); RBAC y auditoría.
- **Proveedor**: doble en memoria; un test verifica que no hay sockets ni lectura de certificados y que el fallo inyectado no emite.
- **Evidencia**: `docs/skills-mcp/evidencias/c-14/` con salidas de tests, `curl` del smoke y verificación de migración; `openspec validate --strict`.

## Risks / Trade-offs

- **Numeración y rollback** → el contador se incrementa dentro de la transacción; los tests cubren alta rechazada y concurrencia. Si un adaptador real quema números al autorizar, el diseño deberá separar la secuencia fiscal (documentado).
- **Claim con vencimiento y crash del worker** → a los 5 minutos otro worker retoma; la clave de idempotencia evita un segundo CAE.
- **Divergencia con ARCA real** (campos, códigos, QR) → el contrato está en el `Protocol` y el doble fija el formato; el adaptador real queda fuera de v1 y deberá normalizar.
- **"Cobro aprobado" como proxy de práctica realizada** → es la mejor señal disponible sin vínculo ítem-turno; queda como pregunta abierta y no cambia la API si luego se agrega un registro de práctica.
- **Cambio de obra social posterior al presupuesto** → ni `Presupuesto` ni `Cobro` snapshotean la obra social usada al calcular la cobertura, así que la liquidación usa la OS actual del paciente y podría reclamar a la OS equivocada si cambió. Se documenta como limitación v1; un change posterior puede agregar el snapshot al presupuesto.
- **Borrador de liquidación inmutable en su composición** → no hay endpoint para agregar ítems a un borrador; si aparecen prácticas nuevas hay que borrar el borrador y recrearlo. Es un trade-off consciente para no reabrir el cálculo de una liquidación ya mostrada.
- **Borrador que bloquea el período** → se puede borrar lógicamente un borrador; no hay anulación de cerradas, así que una liquidación cerrada errónea requiere un change posterior.
- **Envío no reutiliza C-09** → el historial de mensajes no muestra la factura; se documenta y se propone un change de comunicaciones para unificarlo.
- **Datos fiscales incompletos** → el snapshot usa consumidor final/DNI; agregar condición fiscal/domicilio es un change de pacientes/facturación.
- **Sin UI** → el flujo se valida por API; la pantalla fiscal queda para un change posterior.

## Migration Plan

1. `alembic upgrade head` aplica `0013_facturacion_arca`; solo crea tablas nuevas y reutiliza `btree_gist`.
2. Configurar `ARCA_PROVIDER=test`, `ARCA_PUNTO_VENTA=1`, `ARCA_CONDICION_EMISOR=responsable_inscripto` y `ARCA_MAX_INTENTOS`; no se requieren certificados.
3. Desplegar API + worker `arca`; el seed demo no cambia (los cobros previos no se backfillean).
4. Smoke: cobrar efectivo, ver comprobante pendiente, correr worker, ver CAE/QR, enviar por WhatsApp simulado, validar cobertura y crear/cerrar una liquidación.
5. Rollback: `alembic downgrade 0012_caja_cobros` elimina las cinco tablas nuevas; no hay pérdida de datos de C-13.

## Open Questions

- **Fuente de "práctica realizada"**: v1 usa un cobro de tratamiento aprobado dentro del período porque no hay vínculo ítem-turno/evolución. Si el usuario prefiere liquidar por turno atendido o por evolución firmada, cambia la consulta de D9 pero no la API ni el modelo de ítems; confirmar antes de implementar.
- **Nota de crédito**: un reembolso no genera nota de crédito en v1; confirmar si se acepta como non-goal.
- **Email**: v1 solo envía por WhatsApp simulado; confirmar si el email puede quedar como log/no-goal.
- **Condición fiscal del paciente**: v1 usa consumidor final/DNI; confirmar si se agregará en un change posterior.
- **Obra social del presupuesto**: la liquidación filtra por la OS actual del paciente porque `Presupuesto` no snapshotea la OS usada al calcular cobertura; confirmar si se acepta la limitación o se agrega el snapshot a C-12 antes de implementar.
