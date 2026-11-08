# Spec Delta

## Purpose

Emite un comprobante por cada cobro aprobado, lo fiscaliza contra ARCA en homologación cuando el proveedor está disponible y conserva un comprobante interno verificable cuando no lo está, para que ningún cobro quede sin respaldo ni se duplique un CAE.

## ADDED Requirements

### Requirement: Comprobante único por cobro aprobado

Al aprobarse un cobro (efectivo al crear o Mercado Pago al conciliar), el sistema SHALL crear en la misma transacción exactamente un comprobante con numeración interna única y sin huecos por consultorio y punto de venta, `tipo B|C`, `ambiente='homologacion'` y estado `pendiente`. Un cobro que nunca llegó a `aprobado` no SHALL tener comprobante.

**Trazabilidad**: RN-AD-01, US-031/CA-1, DD-09, Flujo 4 paso 1, `04_modelo_de_datos.md` §Cobro/ComprobanteARCA.

#### Scenario: Cobro en efectivo aprobado emite comprobante
- **WHEN** un recepcionista registra un cobro en efectivo que queda `aprobado`
- **THEN** responde HTTP 201 y existe un comprobante `pendiente` con `numero_interno` consecutivo, `tipo='B'`, `ambiente='homologacion'`, importe igual al cobro y QR interno
- **AND** el comprobante referencia exactamente ese cobro

#### Scenario: Cobro pendiente o rechazado no emite comprobante
- **WHEN** se crea un cobro Mercado Pago que queda `pendiente`, o un webhook lo deja `rechazado`
- **THEN** el sistema no crea ningún comprobante para ese cobro

#### Scenario: Aprobación concurrente o webhook repetido
- **WHEN** dos peticiones aprueban el mismo cobro o el mismo webhook se recibe dos veces
- **THEN** existe un solo comprobante, sin una segunda numeración interna ni un segundo CAE

#### Scenario: Alta rechazada no consume numeración
- **WHEN** el alta del cobro falla después de reservar un número interno
- **THEN** la transacción se revierte y el siguiente comprobante recibe el número que habría correspondido, sin huecos

### Requirement: Emisión fiscal con CAE y QR

Cuando el proveedor ARCA confirma la emisión, el comprobante SHALL pasar a `emitido` con CAE de 14 dígitos, vencimiento de CAE, punto de venta, número fiscal y QR. El `tipo` SHALL ser B para emisor Responsable Inscripto con receptor consumidor final, o C si el emisor configurado es monotributista. El QR SHALL ser una URL AFIP base64url decodificable con CAE e importe.

**Trazabilidad**: RN-AD-01, US-031/CA-1, DD-09, R-11, `11_integraciones_argentinas.md` §Facturación ARCA.

#### Scenario: Emisión confirmada por el proveedor
- **WHEN** el worker procesa un comprobante `pendiente` y el proveedor confirma
- **THEN** el comprobante queda `emitido` con `cae`, `cae_vencimiento`, `punto_venta`, `numero_fiscal` y `qr` fiscal
- **AND** la fecha de emisión fiscal queda registrada en UTC

#### Scenario: Proveedor rechaza la emisión
- **WHEN** el proveedor responde un rechazo explícito
- **THEN** el comprobante queda `fallido`, conserva su comprobante interno y no expone un CAE

#### Scenario: Reemisión de un comprobante ya emitido
- **WHEN** se intenta emitir otra vez un comprobante `emitido`
- **THEN** el sistema devuelve el mismo CAE y no crea otro comprobante ni otro número fiscal

#### Scenario: QR fiscal verificable
- **WHEN** se decodifica el `qr` de un comprobante `emitido`
- **THEN** el JSON contiene `codAut` igual al CAE, el punto de venta, el número y el importe del comprobante

### Requirement: Proveedor ARCA simulado sin red ni certificados

La emisión SHALL resolverse mediante `ArcaClient`; con `ARCA_PROVIDER=test` SHALL usarse un cliente simulado que deriva el CAE de una clave de idempotencia, permite inyectar fallos y no SHALL hacer llamadas de red ni leer certificados. Cualquier otro valor SHALL fallar de forma explícita sin emitir.

**Trazabilidad**: R-12, DD-09, `11_integraciones_argentinas.md` §Facturación ARCA, `08_arquitectura_propuesta.md` §Variables de entorno.

#### Scenario: CAE simulado determinista
- **WHEN** se emite el mismo comprobante dos veces con `ARCA_PROVIDER=test`
- **THEN** ambas respuestas traen el mismo CAE y no hubo ninguna llamada de red

#### Scenario: Fallo inyectable del proveedor
- **WHEN** el test configura una indisponibilidad del proveedor
- **THEN** la emisión falla con un error explícito y el comprobante no pasa a `emitido`

#### Scenario: Proveedor real deshabilitado en v1
- **WHEN** `ARCA_PROVIDER` tiene un valor distinto de `test`
- **THEN** el sistema falla de forma explícita y no intenta emitir con certificados reales

#### Scenario: Certificados ausentes no rompen el alta
- **WHEN** el entorno de test no define certificado ni clave de ARCA
- **THEN** la emisión simulada funciona igual y no se lee ningún archivo de certificado

### Requirement: Fallback interno cuando ARCA no está disponible

Si la emisión fiscal falla o el proveedor no está disponible, el comprobante SHALL conservar su numeración interna y quedar en estado fiscal `pendiente` (o `fallido` al agotar intentos), mientras el cobro y su comprobante interno se conservan y la factura fiscal queda para el worker de `arca:emitir`. La respuesta del cobro no SHALL fallar por ARCA.

**Trazabilidad**: RN-AD-01, Flujo 4 degradado, DD-07c, R-06, R-12, `11_integraciones_argentinas.md` §Facturación ARCA.

#### Scenario: ARCA caído no pierde el cobro
- **WHEN** se cobra en efectivo mientras el proveedor ARCA está caído
- **THEN** el cobro responde HTTP 201, el comprobante queda en estado fiscal `pendiente` con su QR interno y el id del comprobante queda encolado en `arca:emitir`

#### Scenario: Aprobación de Mercado Pago con ARCA caído
- **WHEN** un webhook aprueba un cobro y la emisión fiscal falla
- **THEN** el cobro queda `aprobado`, el comprobante interno se conserva y el webhook responde HTTP 200

#### Scenario: Redis caído no pierde el job
- **WHEN** ARCA y Redis están caídos al aprobar un cobro
- **THEN** el comprobante queda `pendiente` con `proximo_intento` y el barrido del worker lo retoma sin depender de la cola

#### Scenario: Reintento posterior emite la factura
- **WHEN** el worker vuelve a procesar un comprobante `pendiente` cuando ARCA se recupera
- **THEN** el comprobante pasa a `emitido` sin crear otro comprobante para el cobro

### Requirement: Worker `arca:emitir` con reintentos e idempotencia

El worker de `arca:emitir` SHALL reclamar comprobantes `pendiente` de forma atómica, emitir y persistir `emitido|fallido`; un job duplicado o concurrente SHALL procesar cada comprobante una sola vez. Los fallos SHALL reintentarse con backoff exponencial hasta un máximo configurable y luego quedar `fallido` con el último error. Un `emitido` no SHALL volver a llamar al proveedor.

**Trazabilidad**: RN-AD-01, R-06, DD-07c, US-031/CA-1, `platform/job-queues`.

#### Scenario: Procesamiento de un job encolado
- **WHEN** el worker toma un id de `arca:emitir` y el comprobante sigue `pendiente`
- **THEN** llama al proveedor una vez y persiste el resultado `emitido`

#### Scenario: Reintento con backoff
- **WHEN** el proveedor falla en el primer intento
- **THEN** el comprobante sigue `pendiente`, incrementa `intentos` y `proximo_intento` crece exponencialmente

#### Scenario: Tope de intentos
- **WHEN** el proveedor falla hasta alcanzar el máximo configurado
- **THEN** el comprobante queda `fallido` con el último error y deja de reintentarse automáticamente

#### Scenario: Job duplicado
- **WHEN** el mismo id de comprobante aparece dos veces en `arca:emitir`
- **THEN** se realiza una sola emisión y existe un solo CAE

#### Scenario: Dos workers concurrentes
- **WHEN** dos workers intentan reclamar el mismo comprobante a la vez
- **THEN** solo uno lo procesa y el otro lo omite sin llamar al proveedor

#### Scenario: CAE obtenido pero falla la persistencia
- **WHEN** el proveedor devuelve un CAE y la escritura en PostgreSQL falla
- **THEN** la transacción se revierte y el reintento obtiene el mismo CAE, sin una segunda emisión fiscal

### Requirement: Idempotencia fiscal garantizada por PostgreSQL

PostgreSQL SHALL garantizar un comprobante por cobro, un CAE único por ambiente y una numeración fiscal única por punto de venta mediante índices únicos. Un segundo intento de emisión para el mismo cobro SHALL devolver el comprobante existente sin crear otra fila ni otro CAE.

**Trazabilidad**: RN-AD-01, R-05, DD-09, `platform/persistence-patterns`.

#### Scenario: Segundo comprobante para el mismo cobro
- **WHEN** se inserta por SQL un segundo comprobante para un cobro que ya tiene uno
- **THEN** PostgreSQL rechaza la fila con SQLSTATE `23505`

#### Scenario: CAE duplicado en el mismo ambiente
- **WHEN** se intenta persistir dos comprobantes con el mismo CAE y ambiente
- **THEN** PostgreSQL rechaza la segunda fila con SQLSTATE `23505`

#### Scenario: Repetición del pedido de emisión
- **WHEN** se repite la emisión de un cobro ya emitido
- **THEN** la respuesta devuelve el comprobante y CAE existentes sin insertar una fila nueva

### Requirement: Consulta y envío del comprobante

`GET /comprobantes` y `GET /comprobantes/{id}` SHALL permitir consultar por cobro, paciente, estado y fecha. `POST /comprobantes/{id}/enviar` SHALL registrar el envío por WhatsApp del comprobante `emitido` con el proveedor de prueba, persistiendo canal, destino y estado; sin destino válido SHALL responder 422, sobre `pendiente|fallido` 409 y repetir el envío SHALL devolver el registro existente.

**Trazabilidad**: US-031/CA-1, R-12, DD-03, `03_actores_y_roles.md` §Matriz (Facturación ARCA).

#### Scenario: Consulta por cobro
- **WHEN** un recepcionista consulta `GET /comprobantes?cobro_id=<id>`
- **THEN** responde HTTP 200 con el comprobante del cobro, su estado, CAE y QR cuando corresponde

#### Scenario: Envío simulado por WhatsApp
- **WHEN** se envía un comprobante `emitido` de un paciente con teléfono
- **THEN** responde HTTP 201 con `canal='whatsapp'`, `destino` igual al teléfono, `estado='registrado'` y un id de proveedor de prueba
- **AND** no se realizó ninguna llamada de red

#### Scenario: Comprobante sin destino válido
- **WHEN** el envío no recibe un destino válido y el paciente tampoco aporta uno
- **THEN** el envío responde HTTP 422 y no crea un registro de envío

#### Scenario: Envío de un comprobante no emitido
- **WHEN** se intenta enviar un comprobante `pendiente` o `fallido`
- **THEN** el sistema responde HTTP 409 porque todavía no hay factura fiscal

#### Scenario: Envío repetido
- **WHEN** se repite el envío por el mismo canal del mismo comprobante
- **THEN** responde HTTP 200 con el registro existente, sin duplicar el envío

### Requirement: Reintento manual de emisión

`POST /comprobantes/{id}/reintentar` SHALL habilitar un nuevo intento de emisión sobre un comprobante `pendiente|fallido`, reiniciando `proximo_intento` y encolando el job; sobre `emitido` SHALL ser un no-op 200 y sobre inexistente 404. El reintento SHALL respetar la idempotencia fiscal.

**Trazabilidad**: RN-AD-01, US-031/CA-1, R-11, DD-09.

#### Scenario: Reintento de un comprobante fallido
- **WHEN** un administrador reintenta un comprobante `fallido`
- **THEN** responde HTTP 200, el comprobante vuelve a `pendiente` con `proximo_intento` nulo y el job queda encolado

#### Scenario: Reintento de un comprobante ya emitido
- **WHEN** se reintenta un comprobante `emitido`
- **THEN** responde HTTP 200 sin cambiar el CAE ni encolar un job

#### Scenario: Reintento de un comprobante inexistente
- **WHEN** se reintenta un id que no existe o de otro consultorio
- **THEN** el sistema responde HTTP 404

### Requirement: RBAC y auditoría de comprobantes

La lectura de comprobantes SHALL estar disponible para administrador, recepción, odontólogo y auditor; el reintento y el envío para administrador y recepción; el asistente SHALL recibir 403. La creación, emisión, reintento y envío SHALL auditarse con usuario o actor sistema, IP y dispositivo, y las filas de auditoría SHALL ser inmutables.

**Trazabilidad**: RN-SE-01, RN-SE-02, `03_actores_y_roles.md` §Matriz (Facturación ARCA), R-03, R-11, `security/core-models` §Auditoría.

#### Scenario: Matriz de lectura y escritura
- **WHEN** administrador, recepción, odontólogo y auditor consultan comprobantes
- **THEN** todos reciben HTTP 200; administrador y recepción además pueden reintentar y enviar

#### Scenario: Asistente sin acceso
- **WHEN** un asistente hace `GET /comprobantes` o intenta un reintento
- **THEN** el sistema responde HTTP 403

#### Scenario: Odontólogo no escribe
- **WHEN** un odontólogo intenta `POST /comprobantes/{id}/reintentar` o `/enviar`
- **THEN** el sistema responde HTTP 403 y no modifica el comprobante

#### Scenario: Petición sin token
- **WHEN** cualquier endpoint de comprobantes se invoca sin Bearer válido
- **THEN** el sistema responde HTTP 401

#### Scenario: Auditoría de emisión y envío
- **WHEN** se crea, emite, reintenta y envía un comprobante
- **THEN** quedan filas `comprobante.crear`, `comprobante.emitir`, `comprobante.reintentar` y `comprobante.enviar` con usuario o actor sistema, IP y dispositivo

#### Scenario: Auditoría append-only
- **WHEN** se intenta `UPDATE` o `DELETE` sobre una fila de auditoría de comprobantes
- **THEN** PostgreSQL responde SQLSTATE `P0001` y la fila permanece intacta
