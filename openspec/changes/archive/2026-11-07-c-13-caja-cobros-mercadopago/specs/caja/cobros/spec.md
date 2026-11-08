# Spec Delta

## Purpose

Registra y concilia el dinero que entra por señas, tratamientos y otros conceptos, con efectivo o Mercado Pago sandbox, dejando trazabilidad entre el cobro, el turno y el presupuesto.

## ADDED Requirements

### Requirement: Alta de cobro en efectivo con conciliación inmediata

El sistema SHALL crear un cobro por `POST /cobros` con paciente, tipo, monto en ARS y medio. Con medio `efectivo` el cobro SHALL nacer `aprobado` en la misma transacción y registrar el ingreso correspondiente en la caja del día. El monto SHALL ser mayor que cero y el cuerpo SHALL rechazar campos no declarados.

**Trazabilidad**: US-030/CA-1, Flujo 4 paso 1, RN-AD-04, R-02.

#### Scenario: Cobro en efectivo aprobado
- **WHEN** un recepcionista autenticado hace `POST /cobros` con un paciente activo, `tipo='otro'`, `monto=15000.00` y `medio='efectivo'`
- **THEN** el sistema responde HTTP 201 con `estado='aprobado'`, la fecha de operación en UTC-3
- **AND** queda un movimiento de ingreso por 15000.00 en la caja abierta de ese día

#### Scenario: Monto no positivo
- **WHEN** el alta envía `monto=0` o un monto negativo
- **THEN** el sistema responde HTTP 422 y no crea cobro ni movimiento de caja

#### Scenario: Campo no declarado o moneda distinta de ARS
- **WHEN** el cuerpo incluye `moneda='USD'`, un `estado` o cualquier campo fuera del esquema
- **THEN** el sistema responde HTTP 422 y no persiste el cobro

#### Scenario: Paciente inexistente, inactivo o de otro consultorio
- **WHEN** el alta referencia un paciente que no existe, tiene baja lógica o pertenece a otro consultorio
- **THEN** el sistema responde HTTP 404 y no crea el cobro

#### Scenario: Cobro en efectivo sin caja abierta o con caja cerrada
- **WHEN** se intenta un cobro en efectivo cuando la caja de la fecha de operación no existe o ya está cerrada
- **THEN** el sistema responde HTTP 409 y no registra el cobro ni el movimiento

### Requirement: Seña solo para prestaciones que la requieren

Un cobro `tipo='sena'` SHALL exigir un turno activo del consultorio cuya prestación tenga `requiere_sena=true` y un monto exactamente igual al `monto_sena` vigente (RN-TU-08). Sin prestación o sin seña exigida SHALL responder 422. Al aprobarse, el turno SHALL quedar con `sena_estado='pagada'` (RN-AD-02).

**Trazabilidad**: RN-TU-08, RN-AD-02, US-030/CA-2, DD-10, Flujo 1 paso 4.

#### Scenario: Seña válida sobre una prestación que la exige
- **WHEN** un recepcionista registra una seña en efectivo para un turno cuya prestación tiene `requiere_sena=true` y `monto_sena=8000.00`
- **THEN** responde HTTP 201 con `tipo='sena'`, `monto=8000.00`, `estado='aprobado'`
- **AND** el turno pasa a `sena_estado='pagada'`

#### Scenario: Prestación sin seña exigida
- **WHEN** el turno referencia una prestación con `requiere_sena=false`
- **THEN** el sistema responde HTTP 422 y no crea el cobro

#### Scenario: Turno sin prestación
- **WHEN** el turno no tiene prestación asociada
- **THEN** el sistema responde HTTP 422 porque no hay seña exigible

#### Scenario: Monto distinto del monto de seña
- **WHEN** el alta envía un monto mayor o menor que el `monto_sena` vigente
- **THEN** el sistema responde HTTP 422 y el turno conserva su estado de seña

#### Scenario: Turno cancelado, ausente o de otro consultorio
- **WHEN** el turno está `cancelado`, `ausente`, no existe o pertenece a otro consultorio
- **THEN** el sistema responde HTTP 422 o 404 según corresponda y no crea el cobro

### Requirement: Una sola seña viva por turno

El sistema SHALL impedir más de un cobro de seña en estado `pendiente`, `aprobado` o `perdido` para el mismo turno, tanto en la aplicación como con un índice único parcial en PostgreSQL. Una seña `rechazado` o `reembolsado` SHALL permitir un nuevo intento.

**Trazabilidad**: RN-AD-02, RN-TU-04, US-030/CA-1, R-05.

#### Scenario: Segunda seña viva rechazada
- **WHEN** un turno ya tiene una seña `aprobado` y se intenta crear otra
- **THEN** el sistema responde HTTP 409 y no crea una fila nueva

#### Scenario: Reintento tras un rechazo
- **WHEN** la seña anterior quedó `rechazado` y se crea una nueva para el mismo turno
- **THEN** el sistema responde HTTP 201 con un cobro nuevo

#### Scenario: Dos altas concurrentes de seña
- **WHEN** dos peticiones simultáneas crean la seña del mismo turno
- **THEN** exactamente una responde HTTP 201 y la otra HTTP 409

#### Scenario: Seña duplicada por SQL directo
- **WHEN** se inserta por SQL un segundo cobro de seña vivo para el mismo turno
- **THEN** PostgreSQL rechaza la fila con SQLSTATE `23505`

#### Scenario: Seña perdida no se reemplaza
- **WHEN** el turno ya tiene una seña `perdido` y se intenta registrar otra
- **THEN** el sistema responde HTTP 409 porque la seña ya fue resuelta

### Requirement: Cobro de tratamiento contra presupuesto aceptado

Un cobro `tipo='tratamiento'` SHALL exigir un presupuesto del mismo paciente y consultorio en estado `aceptado` o `en_curso`. El monto SHALL ser mayor que cero y la suma de cobros de tratamiento aprobados no SHALL superar el `copago` del presupuesto; un exceso SHALL responder 409. Se permiten pagos parciales.

**Trazabilidad**: US-030/CA-1, RN-AD-04, DD-11 (copago calculado contra el convenio local), `comercial/presupuestos`, Flujo 4 paso 1.

#### Scenario: Pago parcial del copago
- **WHEN** un presupuesto aceptado tiene `copago=50000.00` y se cobran 20000.00
- **THEN** responde HTTP 201 con `tipo='tratamiento'` y el presupuesto conserva su estado
- **AND** el saldo pendiente informado es 30000.00

#### Scenario: Presupuesto en borrador o rechazado
- **WHEN** el presupuesto está `borrador`, `rechazado` o `finalizado`
- **THEN** el sistema responde HTTP 409 y no crea el cobro

#### Scenario: Cobro que excede el copago pendiente
- **WHEN** ya se cobraron 40000.00 de un copago de 50000.00 y se intenta cobrar 15000.00
- **THEN** el sistema responde HTTP 409 y no registra el excedente

#### Scenario: Presupuesto de otro paciente
- **WHEN** el `paciente_id` del cobro no coincide con el del presupuesto
- **THEN** el sistema responde HTTP 422 y no crea el cobro

#### Scenario: Presupuesto inexistente o de otro consultorio
- **WHEN** el presupuesto no existe o pertenece a otro consultorio
- **THEN** el sistema responde HTTP 404

### Requirement: Preferencia de pago Mercado Pago en sandbox

Con medio `mercadopago`, el sistema SHALL crear el cobro en estado `pendiente` y una preferencia de pago mediante el proveedor configurado, devolviendo un `link_pago` y un identificador de preferencia. Con `MP_PROVIDER=test` no SHALL llamarse a Mercado Pago ni generarse costos reales. Si el proveedor no está disponible, SHALL responder 503 sin persistir el cobro.

**Trazabilidad**: US-030/CA-1, Flujo 4 paso 1, R-12, DD-07c, `11_integraciones_argentinas.md` §Mercado Pago.

#### Scenario: Link de pago sandbox
- **WHEN** un recepcionista crea un cobro de seña con `medio='mercadopago'`
- **THEN** responde HTTP 201 con `estado='pendiente'`, `link_pago` y `proveedor_preferencia_id`
- **AND** no se realizó ninguna llamada de red a Mercado Pago

#### Scenario: Proveedor no disponible
- **WHEN** el proveedor de pagos lanza una indisponibilidad al crear la preferencia
- **THEN** el sistema responde HTTP 503 y no deja un cobro huérfano en `pendiente`

#### Scenario: Proveedor real deshabilitado en v1
- **WHEN** `MP_PROVIDER` tiene un valor distinto de `test`
- **THEN** el sistema falla de forma explícita y no intenta cobrar con credenciales reales

#### Scenario: Preferencia sin exponer secretos
- **WHEN** se devuelve la respuesta del alta
- **THEN** no incluye `MP_ACCESS_TOKEN`, el secreto del webhook ni datos internos del proveedor

### Requirement: Webhook de Mercado Pago firmado y público

`POST /webhooks/mercadopago` SHALL ser público y validar la firma HMAC del encabezado `x-signature` contra `MP_WEBHOOK_SECRET`, incluyendo una tolerancia de tiempo. Sin firma, con firma inválida o con `ts` vencido SHALL responder 401 sin modificar cobros ni caja.

**Trazabilidad**: Flujo 4, R-12 (webhooks idempotentes), `11_integraciones_argentinas.md` §Mercado Pago, R-03.

#### Scenario: Webhook con firma válida
- **WHEN** llega un webhook con `x-signature` y `ts` válidos para el secreto configurado
- **THEN** el sistema responde HTTP 200 y procesa el evento

#### Scenario: Firma inválida
- **WHEN** el `v1` de la firma no coincide con el HMAC calculado
- **THEN** el sistema responde HTTP 401 y ningún cobro cambia de estado

#### Scenario: Webhook sin firma
- **WHEN** la petición no incluye `x-signature`
- **THEN** el sistema responde HTTP 401 y no revela datos del cobro

#### Scenario: Timestamp fuera de tolerancia
- **WHEN** el `ts` de la firma está fuera de la ventana permitida
- **THEN** el sistema responde HTTP 401 aunque el HMAC sea correcto

#### Scenario: Webhook sin autenticación de backoffice
- **WHEN** la petición no envía token Bearer
- **THEN** el webhook sigue siendo accesible y solo la firma decide si se procesa

### Requirement: Conciliación idempotente del pago

El webhook SHALL resolver el pago con el proveedor y usar `external_reference` como cobro y el id de pago como clave de idempotencia. Un pago aprobado SHALL dejar el cobro `aprobado`, guardar `proveedor_pago_id`, registrar el ingreso y conciliar la seña del turno. Un pago rechazado SHALL dejar el cobro `rechazado` sin ingreso. Repetir el mismo pago SHALL responder 200 sin duplicar estado.

**Trazabilidad**: RN-AD-02, Flujo 4 (error: webhook duplicado/tardío), US-030/CA-1, R-12.

#### Scenario: Pago aprobado concilia el cobro y la seña
- **WHEN** llega un pago aprobado por 8000.00 para un cobro de seña pendiente
- **THEN** el cobro pasa a `aprobado` con `proveedor_pago_id`
- **AND** el turno pasa a `sena_estado='pagada'` y queda un ingreso en la caja del día

#### Scenario: Pago rechazado no cobra
- **WHEN** llega un pago rechazado para un cobro pendiente
- **THEN** el cobro pasa a `rechazado`, no se registra ingreso y el turno sigue `sena_estado='pendiente'`

#### Scenario: Webhook duplicado
- **WHEN** el mismo `proveedor_pago_id` se recibe dos veces
- **THEN** ambas respuestas son HTTP 200 y existe un solo cobro conciliado, sin segundo ingreso

#### Scenario: Webhook tardío sobre un cobro ya reembolsado o perdido
- **WHEN** llega un pago aprobado para un cobro que ya está `reembolsado` o `perdido`
- **THEN** responde HTTP 200 sin cambiar el estado ni duplicar el ingreso

#### Scenario: Monto o moneda no coinciden
- **WHEN** el pago aprobado informa un monto distinto del cobro o una moneda distinta de ARS
- **THEN** el sistema responde HTTP 409, no concilia y registra el intento en el log para revisión

#### Scenario: Referencia externa desconocida
- **WHEN** el pago referencia un cobro inexistente
- **THEN** el sistema responde HTTP 404 y no crea cobros

#### Scenario: Segundo pago aprobado para la misma seña
- **WHEN** llega un pago aprobado con otro `proveedor_pago_id` para una seña ya `aprobado`
- **THEN** el sistema responde HTTP 409, no crea otro cobro y registra el evento en el log para devolución manual

### Requirement: Pérdida de seña reflejada desde el turno

Cuando `Turno.sena_estado` pasa a `perdida` por cancelación tardía o ausentismo, el cobro de seña vivo del turno SHALL pasar a `perdido` en la misma transacción, sin crear otro cobro ni revertir el dinero ya ingresado. La regla de pérdida pertenece a agenda; caja solo refleja el estado.

**Trazabilidad**: RN-TU-04, RN-AD-02, US-030/CA-2, `agenda/turnos` §Pérdida de seña.

#### Scenario: Seña pagada que se pierde
- **WHEN** un turno con seña `pagada` pasa a `sena_estado='perdida'`
- **THEN** su cobro de seña pasa a `perdido` y el ingreso del día se conserva

#### Scenario: Seña pendiente que se pierde
- **WHEN** un turno con seña `pendiente` pasa a `perdida`
- **THEN** el cobro de seña pendiente pasa a `perdido` sin registrar ingreso

#### Scenario: Pérdida repetida
- **WHEN** el turno ya está en `perdida` y su cobro ya está `perdido`
- **THEN** la operación es idempotente, no duplica auditoría ni movimientos

#### Scenario: Turno sin seña exigida
- **WHEN** el turno tiene `sena_estado='no_requiere'`
- **THEN** no se crea ni modifica ningún cobro

### Requirement: Reembolso registrado sin devolución real

`POST /cobros/{id}/reembolsar` SHALL permitir reembolsar solo un cobro `aprobado`, dejándolo `reembolsado` con auditoría. En v1 no SHALL llamarse a Mercado Pago ni generarse un egreso automático de caja; el ajuste de efectivo, si corresponde, se registra como gasto manual. Repetir el reembolso SHALL ser idempotente.

**Trazabilidad**: US-030, R-11 (trazabilidad), R-12 (sin costo real), `04_modelo_de_datos.md` §Cobro.

#### Scenario: Reembolso de un cobro aprobado
- **WHEN** un administrador reembolsa un cobro `aprobado`
- **THEN** responde HTTP 200 con `estado='reembolsado'` y deja una fila `cobro.reembolsar`

#### Scenario: Reembolso de un cobro no aprobado
- **WHEN** se reembolsa un cobro `pendiente`, `rechazado` o `perdido`
- **THEN** el sistema responde HTTP 409 y no cambia el estado

#### Scenario: Reembolso repetido
- **WHEN** se repite el reembolso del mismo cobro
- **THEN** responde HTTP 200 sin una segunda auditoría ni un segundo movimiento

#### Scenario: Reembolso no llama al proveedor
- **WHEN** se reembolsa un cobro de Mercado Pago con `MP_PROVIDER=test`
- **THEN** no se realiza ninguna llamada de red ni se crea un gasto automático en la caja

#### Scenario: Cobro inexistente
- **WHEN** se reembolsa un id que no existe o de otro consultorio
- **THEN** el sistema responde HTTP 404

### Requirement: Acceso a cobros por rol

El sistema SHALL aplicar la matriz: administrador CRUD; recepcionista crear, leer y actualizar sin borrar; odontólogo leer solo los cobros cuyos turno o presupuesto sean de su profesional; asistente sin acceso; auditor lectura de todos. Sin token SHALL responder 401 y sin permiso 403.

**Trazabilidad**: `03_actores_y_roles.md` §Matriz (Caja/Cobros), RN-SE-01, R-03, `security/rbac-guards`.

#### Scenario: Administrador y recepción operan cobros
- **WHEN** un administrador crea, lista y reembolsa un cobro, y un recepcionista crea y lista otro
- **THEN** las escrituras responden 201/200 y las lecturas 200

#### Scenario: Recepción intenta borrar
- **WHEN** un recepcionista hace `DELETE /cobros/{id}`
- **THEN** el sistema responde HTTP 405 o 403 y no elimina el cobro

#### Scenario: Odontólogo lee solo los propios
- **WHEN** un odontólogo lista cobros de su profesional y de otro
- **THEN** ve solo los primeros y la ficha ajena responde HTTP 403

#### Scenario: Asistente sin acceso
- **WHEN** un asistente hace `GET /cobros`
- **THEN** el sistema responde HTTP 403

#### Scenario: Auditor solo lee
- **WHEN** un auditor lista y lee cobros, y luego intenta crear uno
- **THEN** las lecturas responden HTTP 200 y el alta HTTP 403

#### Scenario: Petición sin token
- **WHEN** cualquier endpoint de cobros se invoca sin Bearer válido
- **THEN** el sistema responde HTTP 401, salvo el webhook público

### Requirement: Auditoría de las escrituras de cobro

Toda escritura de cobro SHALL insertar en la misma transacción una fila de auditoría con usuario (o nulo para el sistema), acción `cobro.crear`, `cobro.conciliar`, `cobro.reembolsar` o `cobro.perder`, entidad `cobro`, identificador, IP y dispositivo. Una escritura rechazada no SHALL dejar auditoría y las filas SHALL seguir siendo inmutables.

**Trazabilidad**: RN-SE-02, R-11, `security/core-models` §Auditoría, `04_modelo_de_datos.md` §Auditoría.

#### Scenario: Auditoría del alta
- **WHEN** se crea un cobro desde `POST /cobros`
- **THEN** queda una fila `cobro.crear` con el id del cobro, usuario, IP y `User-Agent` truncado

#### Scenario: Auditoría de la conciliación
- **WHEN** el webhook aprueba un cobro
- **THEN** queda una fila `cobro.conciliar` con el id del cobro y usuario nulo (actor sistema)

#### Scenario: Auditoría de pérdida y reembolso
- **WHEN** una seña pasa a `perdido` y otro cobro se reembolsa
- **THEN** existen filas `cobro.perder` y `cobro.reembolsar` con sus identificadores

#### Scenario: Escritura rechazada no deja auditoría
- **WHEN** un alta falla por validación o un reembolso es inválido
- **THEN** la transacción se revierte y no queda auditoría de esa operación

#### Scenario: Auditoría append-only
- **WHEN** se intenta `UPDATE` o `DELETE` sobre una fila de auditoría de cobros
- **THEN** PostgreSQL responde SQLSTATE `P0001` y la fila permanece intacta
