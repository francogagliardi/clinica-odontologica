# Spec Delta

## Purpose

Cierra la operación diaria del consultorio con una caja por fecha argentina y un arqueo que explica el efectivo esperado a partir de ingresos, gastos y deudas, sin permitir cerrar con diferencias.

## ADDED Requirements

### Requirement: Caja diaria única por fecha UTC-3

El sistema SHALL mantener una sola caja por consultorio y fecha, con la fecha calculada en UTC-3. `POST /caja/abrir` SHALL crearla con `monto_apertura >= 0` y estado `abierta`; una segunda apertura de la misma fecha SHALL responder 409. Un cobro en efectivo o un movimiento manual sin caja del día SHALL responder 409; al conciliar un cobro por Mercado Pago sin caja previa, SHALL crear la caja del día con apertura cero.

**Trazabilidad**: RN-AD-03, US-030/CA-3, `agenda/turnos` (UTC-3), Flujo 4 paso 1.

#### Scenario: Apertura con monto inicial
- **WHEN** un recepcionista abre la caja de hoy con `monto_apertura=10000.00`
- **THEN** responde HTTP 201 con `estado='abierta'`, la fecha local y el monto inicial

#### Scenario: Segunda apertura del mismo día
- **WHEN** se intenta abrir otra vez la caja de una fecha que ya existe
- **THEN** el sistema responde HTTP 409 y conserva la caja original

#### Scenario: Caja automática al conciliar Mercado Pago
- **WHEN** se aprueba por webhook un cobro de Mercado Pago y todavía no existe caja para esa fecha
- **THEN** el sistema crea la caja con `monto_apertura=0.00` y registra el ingreso por Mercado Pago

#### Scenario: Cobro en efectivo sin caja abierta
- **WHEN** se intenta cobrar en efectivo en una fecha sin caja abierta
- **THEN** el sistema responde HTTP 409 y no crea la caja de forma implícita

#### Scenario: Movimiento manual sin caja abierta
- **WHEN** se registra un gasto o una deuda en una fecha sin caja abierta
- **THEN** el sistema responde HTTP 409 y no crea la caja de forma implícita

#### Scenario: Movimiento de las 23:30 en UTC-3
- **WHEN** se concilia un cobro por Mercado Pago a las `2026-11-05T02:30:00Z`, que en Argentina es el 4 de noviembre a las 23:30
- **THEN** el movimiento pertenece a la caja del 4 de noviembre y no a la del 5

#### Scenario: Monto de apertura negativo
- **WHEN** el alta envía `monto_apertura=-1`
- **THEN** el sistema responde HTTP 422 y no crea la caja

#### Scenario: Fecha inválida o parámetro extra
- **WHEN** la fecha tiene formato inválido o se envía un campo no declarado
- **THEN** el sistema responde HTTP 422

### Requirement: Movimientos de ingreso, gasto y deuda

El sistema SHALL registrar movimientos de caja de tipo `ingreso`, `gasto` o `deuda` con concepto y monto mayor que cero en la caja abierta de la fecha. Un ingreso derivado de un cobro SHALL quedar vinculado a ese cobro y no SHALL duplicarse. Sobre una caja cerrada SHALL responder 409.

**Trazabilidad**: RN-AD-03, US-030/CA-3, RN-AD-04, Flujo 4 paso 1.

#### Scenario: Gasto del día
- **WHEN** un recepcionista registra un gasto de 3500.00 por insumos en la caja abierta
- **THEN** responde HTTP 201 con `tipo='gasto'` y el movimiento aparece en el arqueo del día

#### Scenario: Deuda registrada
- **WHEN** se registra una deuda de 12000.00 con un proveedor
- **THEN** responde HTTP 201 con `tipo='deuda'` y el total de deudas del arqueo sube a 12000.00

#### Scenario: Ingreso derivado de un cobro repetido
- **WHEN** se intenta registrar por segunda vez el ingreso del mismo cobro
- **THEN** el sistema responde HTTP 409 y no duplica el movimiento

#### Scenario: Monto no positivo
- **WHEN** el movimiento envía `monto=0` o negativo
- **THEN** el sistema responde HTTP 422 y no crea la fila

#### Scenario: Movimiento sobre una caja cerrada
- **WHEN** se registra un ingreso, gasto o deuda en una fecha cuya caja ya está cerrada
- **THEN** el sistema responde HTTP 409 y no modifica los totales

#### Scenario: Caja inexistente para la fecha consultada
- **WHEN** se listan movimientos de una fecha sin caja
- **THEN** el sistema responde HTTP 200 con lista vacía y totales en cero

### Requirement: Arqueo con efectivo esperado

`GET /caja/arqueo?fecha=` SHALL devolver `monto_apertura`, `ingresos_efectivo`, `gastos_efectivo`, `monto_sistema_efectivo`, `ingresos_mercadopago`, `deudas` y los movimientos del día. El efectivo esperado SHALL calcularse como `apertura + ingresos_efectivo - gastos_efectivo`; los cobros por Mercado Pago y las deudas SHALL informarse por separado y no alterar ese esperado.

**Trazabilidad**: RN-AD-03, US-030/CA-3, Flujo 4 paso 1, `04_modelo_de_datos.md` §Cobro.

#### Scenario: Arqueo con ingresos y gastos en efectivo
- **WHEN** la caja abrió con 10000.00, cobró 15000.00 en efectivo y pagó 3500.00
- **THEN** el arqueo devuelve `ingresos_efectivo=15000.00`, `gastos_efectivo=3500.00` y `monto_sistema_efectivo=21500.00`

#### Scenario: Cobro por Mercado Pago
- **WHEN** el día tiene un cobro aprobado por 8000.00 con medio `mercadopago`
- **THEN** `ingresos_mercadopago=8000.00` y `monto_sistema_efectivo` no cambia por ese cobro

#### Scenario: Deudas informadas aparte
- **WHEN** el día tiene una deuda de 12000.00 y ningún movimiento en efectivo
- **THEN** `deudas=12000.00` y `monto_sistema_efectivo` sigue igual al monto de apertura

#### Scenario: Fecha sin movimientos
- **WHEN** se consulta el arqueo de una caja abierta con `monto_apertura=10000.00` y sin movimientos
- **THEN** `ingresos_efectivo`, `gastos_efectivo`, `ingresos_mercadopago` y `deudas` son cero
- **AND** `monto_sistema_efectivo` es 10000.00 y la lista de movimientos está vacía

#### Scenario: Parámetro de fecha no declarado
- **WHEN** el arqueo recibe un filtro fuera de `fecha`
- **THEN** el sistema responde HTTP 422 por borde estricto

#### Scenario: Arqueo de una fecha sin caja
- **WHEN** se consulta el arqueo de una fecha que nunca fue abierta
- **THEN** responde HTTP 200 con `monto_apertura=0.00`, todos los totales en cero y sin movimientos
- **AND** no se crea una caja implícita

### Requirement: Cierre con diferencia cero

`POST /caja/cerrar` SHALL exigir `monto_contado` mayor o igual a cero y comparar contra `monto_sistema_efectivo`. Si la diferencia es distinta de cero SHALL responder 409 sin cerrar; si es cero SHALL dejar la caja `cerrada` con usuario, fecha/hora y observaciones opcionales. Una caja ya cerrada SHALL responder 409.

**Trazabilidad**: RN-AD-03, US-030/CA-3, Flujo 4 paso 1, R-11.

#### Scenario: Cierre cuadrado
- **WHEN** el sistema espera 21500.00 y se cuentan 21500.00
- **THEN** responde HTTP 200 con `estado='cerrada'`, `diferencia=0.00` y la caja deja de aceptar movimientos

#### Scenario: Cierre con faltante
- **WHEN** el sistema espera 21500.00 y se cuentan 21000.00
- **THEN** el sistema responde HTTP 409 con la diferencia y la caja sigue `abierta`

#### Scenario: Cierre con sobrante
- **WHEN** el sistema espera 21500.00 y se cuentan 22000.00
- **THEN** el sistema responde HTTP 409 con la diferencia y la caja sigue `abierta`

#### Scenario: Cierre repetido
- **WHEN** se intenta cerrar una caja que ya está `cerrada`
- **THEN** el sistema responde HTTP 409 y no recalcula el arqueo

#### Scenario: Monto contado inválido
- **WHEN** el cierre envía `monto_contado=-100`
- **THEN** el sistema responde HTTP 422 y la caja sigue abierta

#### Scenario: Cierre de una fecha sin caja
- **WHEN** se intenta cerrar una fecha que nunca fue abierta
- **THEN** el sistema responde HTTP 404 y no crea una caja implícita

### Requirement: Acceso y auditoría de caja

El sistema SHALL aplicar la matriz: administrador CRUD; recepcionista abrir, registrar movimientos, cerrar y leer; odontólogo sin acceso; asistente sin acceso; auditor lectura de caja y arqueo. Toda escritura SHALL dejar auditoría `caja.abrir`, `caja.movimiento` o `caja.cerrar` en la misma transacción.

**Trazabilidad**: `03_actores_y_roles.md` §Matriz (Caja/Cobros), RN-SE-01/RN-SE-02, R-03, R-11, `security/core-models`.

#### Scenario: Recepción opera la caja
- **WHEN** un recepcionista abre, registra un gasto y cierra la caja cuadrada
- **THEN** las tres operaciones responden 201, 201 y 200

#### Scenario: Odontólogo sin acceso a caja
- **WHEN** un odontólogo hace `GET /caja/arqueo`
- **THEN** el sistema responde HTTP 403

#### Scenario: Asistente sin acceso
- **WHEN** un asistente lista movimientos de caja
- **THEN** el sistema responde HTTP 403

#### Scenario: Auditor solo lee
- **WHEN** un auditor consulta la caja y el arqueo, y luego intenta abrir una caja
- **THEN** las lecturas responden HTTP 200 y la apertura HTTP 403

#### Scenario: Auditoría de apertura, movimiento y cierre
- **WHEN** se abre la caja, se registra un gasto y se cierra cuadrada
- **THEN** existen filas `caja.abrir`, `caja.movimiento` y `caja.cerrar` con el id de la caja, usuario, IP y dispositivo

#### Scenario: Escritura rechazada no deja auditoría
- **WHEN** un cierre descuadrado o un movimiento inválido es rechazado
- **THEN** la transacción se revierte y no queda auditoría de esa operación
