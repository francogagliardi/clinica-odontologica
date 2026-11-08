# Spec Delta

## Purpose

Ofrece a la clínica una lectura agregada y verificable de agenda, ausentismo, caja y liquidaciones para decidir con datos reales del consultorio, sin exportar ni duplicar cálculos en el cliente.

## ADDED Requirements

### Requirement: Reporte de agenda, ocupación y cancelaciones

`GET /reportes/agenda?desde&hasta` SHALL devolver, para el consultorio autenticado y en UTC-3, el total de turnos por estado, las cancelaciones, los agregados por profesional y sillón y la ocupación en minutos contra la agenda configurada. `profesional_id`, `sillon_id` y `estado` SHALL filtrar. Un rango mayor a 62 días, invertido o un parámetro no declarado SHALL responder 422.

**Trazabilidad**: US-041/CA-1 (`knowledge-base/06_funcionalidades.md:86–91`), RN-TU-01/RN-TU-02, RN-TU-07 (`knowledge-base/05_reglas_de_negocio.md:7–8,13`), `04_modelo_de_datos.md:46–50`, `agenda/turnos`.

#### Scenario: Totales por estado y por recurso

- **WHEN** un administrador consulta la agenda de un rango con 3 turnos `atendido`, 1 `cancelado` y 1 `ausente`, de dos profesionales y dos sillones
- **THEN** responde HTTP 200 con `total_turnos=5`, el mapa `por_estado` con esos conteos y un agregado por profesional y por sillón que suma 5

#### Scenario: Ocupación contra la agenda configurada

- **WHEN** un profesional con 8 horas diarias de agenda tiene 240 minutos de turnos activos en un día hábil del rango
- **THEN** `minutos_disponibles=480`, `minutos_ocupados=240` y `ocupacion_porcentaje=50.00` para ese profesional

#### Scenario: Rango por encima del máximo

- **WHEN** la consulta pide 63 días o envía `desde` posterior a `hasta`
- **THEN** el sistema responde HTTP 422 y no ejecuta la consulta

#### Scenario: Rango en el límite y zona horaria

- **WHEN** se consulta un rango de exactamente 62 días y un turno ocurre a las `2026-11-05T02:30:00Z`
- **THEN** el rango se acepta y el turno se cuenta en el día local 4 de noviembre (UTC-3)

#### Scenario: Profesional sin agenda o inexistente

- **WHEN** el profesional filtrado no tiene días de atención en el rango, o no existe o es de otro consultorio
- **THEN** el primer caso responde 200 con `minutos_disponibles=0`, `ocupacion_porcentaje=0.00` y `sin_agenda=true`, y el segundo 404

#### Scenario: Sobreturnos no inflan la ocupación

- **WHEN** el rango tiene un sobreturno marcado que se solapa con un turno normal
- **THEN** sus minutos se informan aparte en `minutos_sobreturno` y no se suman a `minutos_ocupados`

### Requirement: Reporte de ausentismo con tasas y detalle

`GET /reportes/ausentismo?desde&hasta` SHALL devolver atendidos, cancelados y ausentes, `tasa_ausentismo=(cancelados+ausentes)/(atendidos+cancelados+ausentes)` y `tasa_no_asistencia=ausentes/(atendidos+cancelados+ausentes)`, más el detalle de turnos cerrados y agregados por profesional. Los turnos activos SHALL informarse aparte y no SHALL entrar en las tasas. `profesional_id` SHALL filtrar; un rango inválido o parámetro no declarado SHALL responder 422.

**Trazabilidad**: US-041/CA-1 (`knowledge-base/06_funcionalidades.md:86–91`), RN-TU-03/RN-TU-04 (`knowledge-base/05_reglas_de_negocio.md:9–10`), `04_modelo_de_datos.md:46–50`, `agenda/turnos` §Máquina de estados.

#### Scenario: Tasas sobre turnos cerrados

- **WHEN** el rango tiene 6 `atendido`, 2 `cancelado` y 2 `ausente`
- **THEN** responde HTTP 200 con `tasa_ausentismo=0.40`, `tasa_no_asistencia=0.20` y los tres conteos

#### Scenario: Turnos activos fuera de la tasa

- **WHEN** el rango además tiene 5 turnos `reservado` o `confirmado`
- **THEN** `turnos_activos=5` y las tasas siguen calculadas solo sobre los 10 turnos cerrados

#### Scenario: Rango sin turnos cerrados

- **WHEN** el rango no tiene ningún turno `atendido`, `cancelado` o `ausente`
- **THEN** responde HTTP 200 con ambos conteos y tasas en `0.00`, `sin_cierres=true` y detalle vacío, sin dividir por cero

#### Scenario: Detalle con identidad y fecha local

- **WHEN** el rango incluye un turno `ausente` de un paciente y profesional concretos
- **THEN** el detalle incluye `turno_id`, `paciente_id`, `profesional_id`, `inicio` y `estado`, con la fecha en UTC-3

#### Scenario: Filtro por profesional propio y ajeno

- **WHEN** un odontólogo consulta el reporte sin filtro y luego con el `profesional_id` de otro profesional
- **THEN** la primera respuesta solo agrega su profesional y la segunda responde HTTP 403

#### Scenario: Rango inválido

- **WHEN** falta `desde`, falta `hasta` o el rango supera 62 días
- **THEN** el sistema responde HTTP 422

### Requirement: Reporte de caja, cobros y arqueos

`GET /reportes/caja?desde&hasta` SHALL agregar cobros por medio (`efectivo|mercadopago`) y estado, con `total_aprobado` como único monto de ingreso, y SHALL listar movimientos por tipo y las cajas del rango con su cierre. `medio` y `estado` SHALL filtrar. Una caja abierta SHALL informar cierre nulo y no SHALL recalcular el arqueo.

**Trazabilidad**: US-041/CA-1 (`knowledge-base/06_funcionalidades.md:86–91`), RN-AD-03 (`knowledge-base/05_reglas_de_negocio.md:27`), `caja/cobros`, `caja/arqueo`, `04_modelo_de_datos.md:77–79`.

#### Scenario: Totales por medio y estado

- **WHEN** el rango tiene 2 cobros aprobados en efectivo por 15000.00 y 1 aprobado por Mercado Pago por 8000.00
- **THEN** `total_aprobado=23000.00`, `total_efectivo=15000.00`, `total_mercadopago=8000.00` y el detalle por estado muestra 3 aprobados

#### Scenario: Cobros no aprobados no son ingreso

- **WHEN** el rango incluye cobros `pendiente`, `rechazado`, `reembolsado` y `perdido`
- **THEN** aparecen en `por_estado` pero no suman a `total_aprobado` ni a los totales por medio

#### Scenario: Movimientos y deudas separados del efectivo cobrado

- **WHEN** la caja del rango tiene un gasto de 3500.00 y una deuda de 12000.00 en efectivo
- **THEN** el reporte informa `total_gastos=3500.00` y `total_deudas=12000.00` sin restarlos de `total_aprobado`

#### Scenario: Arqueo cerrado y caja abierta

- **WHEN** el rango contiene una caja cerrada con diferencia 0.00 y una caja abierta
- **THEN** la cerrada devuelve `monto_sistema_efectivo`, `monto_contado` y `diferencia`, y la abierta devuelve esos tres campos nulos con `estado='abierta'`

#### Scenario: Filtro de medio inválido o no declarado

- **WHEN** se envía `medio='tarjeta'` o un parámetro fuera de `desde,hasta,medio,estado`
- **THEN** el sistema responde HTTP 422

#### Scenario: Consultorio sin cajas en el rango

- **WHEN** el rango no tiene cajas ni cobros
- **THEN** responde HTTP 200 con todos los totales en 0.00 y listas vacías, sin crear filas

### Requirement: Reporte de liquidaciones por obra social

`GET /reportes/liquidaciones?desde&hasta` SHALL incluir las liquidaciones cuyo período se cruza con el rango y devolver, por obra social y estado, `cantidad_liquidaciones`, `total_cobertura` y `cantidad_practicas`, más el detalle por prestación (`codigo`, `cantidad`, `cobertura`). `obra_social_id` y `estado` SHALL filtrar; una obra social inexistente o de otro consultorio SHALL responder 404.

**Trazabilidad**: US-041/CA-1 (`knowledge-base/06_funcionalidades.md:86–91`), RN-OS-03 (`knowledge-base/05_reglas_de_negocio.md:34`), `comercial/liquidaciones-obras-sociales`, `04_modelo_de_datos.md:74–79`.

#### Scenario: Agregado por obra social y estado

- **WHEN** existen una liquidación cerrada de 60000.00 con 3 prácticas y un borrador de 20000.00 con 1 práctica de "OS Demo"
- **THEN** el reporte devuelve dos filas por estado con sus totales y una fila agregada de la obra social con `cantidad_liquidaciones=2`, `total_cobertura=80000.00` y `cantidad_practicas=4`

#### Scenario: Cruce de período, no contención

- **WHEN** el rango consultado es noviembre y una liquidación va del 20 de octubre al 5 de noviembre
- **THEN** la liquidación se incluye porque su período se cruza con el rango

#### Scenario: Prácticas por prestación

- **WHEN** las liquidaciones incluidas tienen 2 ítems de `OBT` y 1 de `CONS`
- **THEN** el detalle por prestación devuelve `OBT` con `cantidad=2` y `CONS` con `cantidad=1`, y la cobertura sumada coincide con el total de las cabeceras

#### Scenario: Rango sin liquidaciones

- **WHEN** no hay liquidaciones que se crucen con el rango
- **THEN** responde HTTP 200 con `cantidad_liquidaciones=0`, totales en 0.00 y listas vacías

#### Scenario: Obra social de otro consultorio

- **WHEN** el filtro referencia una obra social inexistente, con baja lógica o de otro consultorio
- **THEN** el sistema responde HTTP 404 y no devuelve agregados

#### Scenario: Ítems dados de baja no cuentan

- **WHEN** una liquidación tiene un ítem con baja lógica
- **THEN** ese ítem no suma a `cantidad_practicas` ni al detalle por prestación

### Requirement: Rango, detalle acotado y metadatos del reporte

Todo reporte SHALL exigir `desde` y `hasta`, interpretarlos como fechas UTC-3 y calcular los totales en PostgreSQL sobre el rango completo. El detalle SHALL devolverse ordenado y acotado por `limite` (máximo 1000, default 500) con `total_detalle` y `detalle_truncado`; truncar el detalle no SHALL alterar los totales. La respuesta SHALL incluir `generado_en`, `desde`, `hasta` y `zona_horaria='UTC-3'`.

**Trazabilidad**: US-041/CA-1 (`knowledge-base/06_funcionalidades.md:86–91`), RN-SE-03 (`knowledge-base/05_reglas_de_negocio.md:46`), R-05/R-07 (`AGENTS.md`), `agenda/turnos` §Listado por rango.

#### Scenario: Detalle truncado con totales completos

- **WHEN** el reporte tiene 1200 filas de detalle y se consulta con `limite=500`
- **THEN** devuelve 500 filas ordenadas, `total_detalle=1200`, `detalle_truncado=true` y los totales calculados sobre las 1200

#### Scenario: Orden estable del detalle

- **WHEN** dos turnos comparten el mismo `inicio`
- **THEN** el detalle los ordena por `inicio` y luego por `id`, de forma reproducible entre consultas

#### Scenario: Límite fuera de rango

- **WHEN** se envía `limite=0`, `limite=1001` o un valor no entero
- **THEN** el sistema responde HTTP 422

#### Scenario: Fechas faltantes o invertidas

- **WHEN** falta `desde` o `hasta`, o `desde` es posterior a `hasta`
- **THEN** el reporte responde HTTP 422 y no consulta la base

#### Scenario: Metadatos de la consulta

- **WHEN** se consulta cualquier reporte válido
- **THEN** la respuesta incluye `generado_en` con zona horaria, `desde`, `hasta`, `zona_horaria='UTC-3'` y los filtros aplicados

#### Scenario: Totales calculados en el servidor

- **WHEN** se inspecciona la respuesta de cualquier reporte
- **THEN** cada total es un valor numérico ya agregado y no una lista de filas que el cliente deba sumar

### Requirement: Acceso a reportes por rol

El sistema SHALL aplicar la matriz de Reportes: administrador lee todo; odontólogo lee agenda, ausentismo y caja de su propio profesional y liquidaciones en lectura; recepción lee agenda, ausentismo y caja; auditor lee todo; asistente sin acceso. Un odontólogo que pide otro `profesional_id` SHALL recibir 403 y cualquier petición sin token 401. Los reportes SHALL ser solo lectura y no SHALL escribir ni auditar.

**Trazabilidad**: `knowledge-base/03_actores_y_roles.md:20–27` (§RBAC, fila Reportes), RN-SE-01 (`knowledge-base/05_reglas_de_negocio.md:44`), R-03 (`AGENTS.md`), `security/rbac-guards`.

#### Scenario: Administrador lee los cuatro reportes

- **WHEN** un administrador consulta agenda, ausentismo, caja y liquidaciones
- **THEN** las cuatro respuestas son HTTP 200 y respetan los filtros enviados

#### Scenario: Odontólogo solo sus agregados

- **WHEN** un odontólogo consulta agenda sin filtro y luego con el `profesional_id` de otro profesional
- **THEN** la primera respuesta solo incluye su profesional y la segunda responde HTTP 403

#### Scenario: Odontólogo lee liquidaciones

- **WHEN** un odontólogo consulta el reporte de liquidaciones
- **THEN** responde HTTP 200 con la lectura agregada y no puede solicitar exportaciones por ese permiso

#### Scenario: Recepción básica

- **WHEN** un recepcionista consulta agenda, ausentismo y caja, y luego liquidaciones
- **THEN** los tres primeros responden HTTP 200 y liquidaciones responde HTTP 403

#### Scenario: Auditor en lectura total

- **WHEN** un auditor consulta los cuatro reportes
- **THEN** todos responden HTTP 200 y ninguna petición crea, modifica o elimina filas

#### Scenario: Asistente sin acceso

- **WHEN** un asistente consulta cualquier reporte
- **THEN** el sistema responde HTTP 403

#### Scenario: Petición sin token y lectura sin efectos

- **WHEN** se consulta un reporte sin Bearer válido, o se compara la auditoría antes y después de una lectura autorizada
- **THEN** sin token responde HTTP 401 y una lectura autorizada no agrega filas a `registro_auditoria` ni modifica datos de dominio
