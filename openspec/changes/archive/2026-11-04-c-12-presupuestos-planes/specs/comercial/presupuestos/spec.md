# Spec Delta

## Purpose

Convierte la indicación clínica en una oferta comercial verificable: ítems con precio congelado, cobertura y copago calculados por ítem contra el convenio local del paciente y un ciclo de vida auditable hasta el plan en curso.

## ADDED Requirements

### Requirement: Alta de presupuesto con ítems y precios del servidor

El sistema SHALL crear presupuestos en estado `borrador` para un paciente y un profesional activos del consultorio, con ítems anidados de prestación, pieza FDI opcional y cantidad. El cliente SHALL enviar solo referencias y cantidades: precios, coberturas y totales los calcula el servidor, y todo importe enviado SHALL rechazarse con 422. La respuesta SHALL devolver los ítems calculados y los totales.

**Trazabilidad**: RN-CL-02, US-021/CA-1, `04_modelo_de_datos.md` (`:70-72`), R-02.

#### Scenario: Alta de un presupuesto con dos ítems
- **WHEN** un odontólogo autenticado hace `POST /presupuestos` con un paciente propio activo, su profesional y dos ítems (`CONS` sin pieza, cantidad 1; `OBT` con pieza 16, cantidad 2)
- **THEN** el sistema responde HTTP 201 con `estado='borrador'`, `cobertura_estado='calculada'`
- **AND** cada ítem devuelve `precio_unitario` igual al `precio_base` vigente del catálogo, su `cobertura_item` y su `copago_item`
- **AND** la respuesta devuelve `subtotal`, `cobertura_calculada` y `copago`

#### Scenario: El cliente intenta fijar precios o totales
- **WHEN** el cuerpo del alta incluye `precio_unitario`, `cobertura_item`, `copago_item`, `subtotal` o `copago`
- **THEN** el sistema responde HTTP 422 por campo no permitido y no persiste el presupuesto ni sus ítems

#### Scenario: Presupuesto sin ítems
- **WHEN** se intenta crear un presupuesto con la lista `items` vacía o ausente
- **THEN** el sistema responde HTTP 422 y no crea el presupuesto

#### Scenario: Paciente inexistente, dado de baja o de otro consultorio
- **WHEN** el alta referencia un paciente que no existe, tiene baja lógica o pertenece a otro consultorio
- **THEN** el sistema responde HTTP 404 y no crea el presupuesto

#### Scenario: Profesional inactivo o de otro consultorio
- **WHEN** el alta referencia un profesional que no existe, está inactivo o pertenece a otro consultorio
- **THEN** el sistema responde HTTP 404 y no crea el presupuesto

#### Scenario: Prestación inexistente o dada de baja
- **WHEN** el alta referencia una prestación fuera del catálogo activo
- **THEN** el sistema responde HTTP 404 y no crea el presupuesto

#### Scenario: Cantidad no positiva
- **WHEN** un ítem envía `cantidad` igual a 0 o negativa
- **THEN** el sistema responde HTTP 422 y el CHECK de PostgreSQL rechaza la misma fila por SQL directo con SQLSTATE `23514`

#### Scenario: Pieza FDI inválida informada
- **WHEN** un ítem envía `pieza=19`, `pieza=49` o `pieza=86`, y otro ítem válido informa `pieza=48`
- **THEN** las piezas inválidas responden HTTP 422 sin crear el presupuesto
- **AND** la pieza 48 se acepta y se devuelve tal cual

### Requirement: Cálculo de cobertura y copago por ítem (RN-OS-02)

El sistema SHALL calcular por ítem `cobertura_item = precio_unitario * cantidad * cobertura_porcentaje / 100`, redondeado a dos decimales, y `copago_item = total_item - cobertura_item`. Sin obra social o con la prestación fuera de `prestaciones_cubiertas`, la cobertura SHALL ser 0 y el copago igual al total. Los totales SHALL ser la suma de los ítems y `subtotal = cobertura_calculada + copago`.

**Trazabilidad**: RN-OS-02, US-021/CA-1, DD-11, `05_reglas_de_negocio.md` (`:33`).

#### Scenario: Cobertura parcial con el convenio OS Demo
- **WHEN** un paciente afiliado a OS Demo (cobertura 60 %) suma un ítem `CONS` de precio 10.000,00 con cantidad 2
- **THEN** el ítem devuelve `cobertura_item=12000.00` y `copago_item=8000.00`
- **AND** el presupuesto devuelve `subtotal=20000.00`, `cobertura_calculada=12000.00` y `copago=8000.00`

#### Scenario: Prestación fuera del convenio
- **WHEN** el mismo paciente agrega un ítem `EXO` que no está en `prestaciones_cubiertas`
- **THEN** el ítem devuelve `cobertura_item=0.00` y `copago_item` igual al total del ítem
- **AND** `cobertura_estado` sigue siendo `calculada` porque el 0 es conocido

#### Scenario: Paciente sin obra social
- **WHEN** se arma un presupuesto para un paciente sin `obra_social_id`
- **THEN** todos los ítems tienen cobertura 0 y copago igual a su total
- **AND** `cobertura_calculada=0.00` y `copago=subtotal`

#### Scenario: Redondeo half-up sin centavos perdidos
- **WHEN** un ítem de precio 33,33 con cantidad 1 tiene cobertura del 60 % (19,998 exacto)
- **THEN** `cobertura_item=20.00` y `copago_item=13.33`
- **AND** `cobertura_item + copago_item` iguala exactamente `precio_unitario * cantidad`

#### Scenario: Totales iguales a la suma de los ítems
- **WHEN** un presupuesto tiene tres ítems con coberturas distintas y se lee con `GET /presupuestos/{id}`
- **THEN** `subtotal`, `cobertura_calculada` y `copago` igualan la suma de los valores de los ítems
- **AND** la fila de PostgreSQL cumple `subtotal = cobertura_calculada + copago`

#### Scenario: Cobertura extrema del 100 % y del 0 %
- **WHEN** el convenio cubre el 100 % de una prestación y el 0 % de otra
- **THEN** la primera tiene `copago_item=0.00` y la segunda `cobertura_item=0.00` con copago igual al total

#### Scenario: CHECK de coherencia por ítem
- **WHEN** se ejecuta por SQL directo un `UPDATE items_presupuesto SET cobertura_item = 1` que rompe `cobertura_item + copago_item = precio_unitario * cantidad`
- **THEN** PostgreSQL rechaza la fila con SQLSTATE `23514`

### Requirement: Cobertura no verificable no bloquea el presupuesto

Si la cobertura no puede calcularse (porcentaje ausente, convenio inactivo o proveedor no disponible), el sistema SHALL guardar el presupuesto con `cobertura_estado='pendiente_verificacion'`, cobertura 0 y copago igual al total, y SHALL responder 201 sin bloquear alta ni aceptación. Con porcentaje definido y prestación fuera de la lista, la cobertura SHALL ser 0 conocido y el estado `calculada`.

**Trazabilidad**: RN-OS-02, Flujo 3 (caso de error), DD-11, US-021/CA-1.

#### Scenario: Convenio sin porcentaje de cobertura
- **WHEN** el paciente tiene una obra social cuyas `reglas_cobertura` no definen `cobertura_porcentaje`
- **THEN** el alta responde HTTP 201 con `cobertura_estado='pendiente_verificacion'` y cobertura 0
- **AND** los ítems quedan con copago igual a su total

#### Scenario: Obra social del paciente dada de baja
- **WHEN** el paciente conserva `obra_social_id` pero ese convenio tiene baja lógica
- **THEN** el alta responde HTTP 201 con `cobertura_estado='pendiente_verificacion'` y no responde 500

#### Scenario: Proveedor de cobertura no disponible
- **WHEN** el proveedor de cobertura inyectado lanza una indisponibilidad al calcular
- **THEN** el alta responde HTTP 201 con `cobertura_estado='pendiente_verificacion'` y cobertura 0
- **AND** el presupuesto y sus ítems quedan persistidos para verificarlos después

#### Scenario: Porcentaje definido con prestación no cubierta
- **WHEN** el convenio define 60 % pero la prestación no figura en `prestaciones_cubiertas`
- **THEN** el presupuesto queda `calculada` con cobertura 0, sin pasar a pendiente

#### Scenario: Aceptación con cobertura pendiente
- **WHEN** se acepta un presupuesto en `pendiente_verificacion`
- **THEN** el sistema responde HTTP 200 con `estado='aceptado'` y conserva `pendiente_verificacion` y la cobertura 0
- **AND** el paciente puede decidir con el copago informado, sin que la aceptación se bloquee

### Requirement: Máquina de estados del presupuesto

El sistema SHALL permitir solo `borrador → aceptado`, `borrador → rechazado`, `aceptado → en_curso` y `en_curso → finalizado`. `rechazado` y `finalizado` SHALL ser terminales, `borrador` no SHALL ser destino y repetir el estado actual SHALL responder 200 sin nueva auditoría. Cualquier otra transición SHALL responder 422 sin modificar el presupuesto.

**Trazabilidad**: US-021/CA-2, RN-CL-02, `04_modelo_de_datos.md` (`:71`).

#### Scenario: Camino completo de estados
- **WHEN** un presupuesto en borrador se pasa a `aceptado`, luego a `en_curso` y luego a `finalizado`
- **THEN** cada llamada a `PATCH /presupuestos/{id}/estado` responde HTTP 200 con el estado nuevo
- **AND** cada transición deja su fila de auditoría con el identificador del presupuesto

#### Scenario: Salto inválido desde borrador
- **WHEN** se intenta pasar un `borrador` directamente a `en_curso` o a `finalizado`
- **THEN** el sistema responde HTTP 422 y el presupuesto sigue en `borrador`

#### Scenario: Aceptado no se rechaza
- **WHEN** se intenta pasar un presupuesto `aceptado` a `rechazado`
- **THEN** el sistema responde HTTP 422 y no cambia el estado

#### Scenario: Estados terminales
- **WHEN** se intenta cualquier transición desde `rechazado` o desde `finalizado`
- **THEN** el sistema responde HTTP 422 y el estado terminal se conserva

#### Scenario: Repetición del estado actual
- **WHEN** se envía `aceptado` a un presupuesto que ya está `aceptado`
- **THEN** el sistema responde HTTP 200 sin modificar el presupuesto y sin insertar una segunda auditoría de aceptación

#### Scenario: Destino inexistente o borrador
- **WHEN** el cuerpo envía `estado='borrador'` o un valor fuera del catálogo
- **THEN** el sistema responde HTTP 422 y no modifica el presupuesto

### Requirement: Edición y recálculo solo en borrador

El sistema SHALL aceptar `PUT /presupuestos/{id}` solo en `borrador`, reemplazando ítems y recalculando precios, cobertura y totales; en otro estado SHALL responder 409. `POST /presupuestos/{id}/recalcular` SHALL recalcular la cobertura del borrador sin cambiar ítems, y `DELETE /presupuestos/{id}` SHALL dar de baja lógica solo un borrador (204); ambos SHALL responder 409 fuera de `borrador`.

**Trazabilidad**: RN-CL-02, RN-OS-02, US-021/CA-1, R-02.

#### Scenario: Edición de borrador recalcula
- **WHEN** un borrador con dos ítems se reemplaza por tres ítems mediante `PUT /presupuestos/{id}`
- **THEN** el sistema responde HTTP 200 con los tres ítems, sus coberturas y los totales recalculados
- **AND** ya no queda ningún ítem de la versión anterior

#### Scenario: Edición fuera de borrador
- **WHEN** se hace `PUT /presupuestos/{id}` sobre un presupuesto `aceptado`, `en_curso`, `finalizado` o `rechazado`
- **THEN** el sistema responde HTTP 409 y el presupuesto, sus ítems y sus totales no cambian

#### Scenario: Edición con importes del cliente
- **WHEN** el `PUT` incluye `precio_unitario`, `cobertura_item`, `copago_item` o totales
- **THEN** el sistema responde HTTP 422 y no modifica el borrador

#### Scenario: Recálculo tras corregir las reglas del convenio
- **WHEN** un presupuesto pendiente pertenece a un convenio al que un administrador le define `cobertura_porcentaje=60` y luego se llama a `POST /presupuestos/{id}/recalcular`
- **THEN** el sistema responde HTTP 200 con `cobertura_estado='calculada'`
- **AND** los ítems cubiertos pasan a tener cobertura mayor a 0 y los totales se actualizan
- **AND** los `precio_unitario` de los ítems no cambian

#### Scenario: Recálculo con cuerpo inesperado
- **WHEN** el cuerpo del recálculo incluye `cobertura_item`, `precio_unitario` o un total
- **THEN** el sistema responde HTTP 422 y el borrador no se modifica

#### Scenario: Recálculo fuera de borrador
- **WHEN** se llama a `POST /presupuestos/{id}/recalcular` sobre un presupuesto que ya salió de `borrador`
- **THEN** el sistema responde HTTP 409 y conserva precios, coberturas y totales

#### Scenario: Edición que cambia el paciente
- **WHEN** un `PUT` de borrador cambia `paciente_id` por otro paciente con otra obra social
- **THEN** el sistema responde HTTP 200 y recalcula la cobertura contra el convenio del paciente nuevo

#### Scenario: Baja lógica de un borrador
- **WHEN** se hace `DELETE /presupuestos/{id}` sobre un borrador
- **THEN** el sistema responde HTTP 204 y el presupuesto deja de aparecer en el listado
- **AND** el mismo `DELETE` sobre un presupuesto aceptado responde HTTP 409

### Requirement: Precio unitario congelado por ítem

El sistema SHALL guardar `precio_unitario` como copia del `precio_base` del catálogo al crear o editar el borrador y no SHALL recalcularlo cuando el catálogo cambie. Un presupuesto que salió de `borrador` SHALL conservar precios, cobertura y totales aunque la prestación cambie de precio o se dé de baja; solo una edición del borrador SHALL tomar el precio vigente.

**Trazabilidad**: US-021/CA-1, `04_modelo_de_datos.md` (`:72`), DD-11.

#### Scenario: Cambio de precio del catálogo no altera el presupuesto
- **WHEN** un administrador modifica el `precio_base` de `CONS` y luego se lee un presupuesto existente que lo incluye
- **THEN** el ítem conserva el `precio_unitario` original y los totales no cambian

#### Scenario: Edición del borrador toma el precio vigente
- **WHEN** tras el cambio de precio del catálogo se edita el borrador conservando la misma prestación
- **THEN** el ítem recalculado toma el `precio_base` nuevo y los totales se actualizan

#### Scenario: Presupuesto aceptado inmune al catálogo
- **WHEN** un presupuesto aceptado incluye `OBT` y luego cambia su precio de catálogo
- **THEN** `GET /presupuestos/{id}` sigue devolviendo el precio congelado y la cobertura original

#### Scenario: Prestación dada de baja después de aceptar
- **WHEN** la prestación de un presupuesto aceptado recibe baja lógica
- **THEN** la ficha del presupuesto sigue respondiendo HTTP 200 con el snapshot del ítem
- **AND** un presupuesto nuevo que intente usar esa prestación responde HTTP 404

#### Scenario: Dos ítems de la misma prestación tras un cambio de precio
- **WHEN** se agrega un ítem, cambia el precio del catálogo y se edita el borrador agregando otro ítem de la misma prestación
- **THEN** el `PUT` re-cotiza todo el borrador: ambos ítems toman el precio vigente en ese momento y los totales cuadran con la suma

### Requirement: Acceso a presupuestos por rol

El sistema SHALL aplicar la matriz: administrador CRUD sobre todo el consultorio; odontólogo CRUD solo sobre los de su profesional, y al crear, el paciente SHALL tener turno vigente con él; recepcionista, asistente y auditor solo lectura. Sin token SHALL responder 401 y sin permiso 403. Un odontólogo sin fila en `profesionales` SHALL recibir 403.

**Trazabilidad**: `03_actores_y_roles.md` (Presupuestos, `:20-27`), RN-SE-01, R-03, `clinica/historia-clinica` ("propio").

#### Scenario: Administrador opera cualquier presupuesto
- **WHEN** un administrador crea un presupuesto, lee y edita otro, acepta uno y da de baja lógica un borrador de distintos profesionales
- **THEN** las operaciones responden 201, 200, 200, 200 y 204 respectivamente

#### Scenario: Odontólogo opera pacientes propios y ajenos
- **WHEN** un odontólogo crea un presupuesto para un paciente con turno vigente de su profesional y luego intenta lo mismo con un paciente solo vinculado a otro profesional
- **THEN** el paciente propio responde HTTP 201 y el ajeno HTTP 403, sin crear filas para el ajeno

#### Scenario: Odontólogo sin profesional vinculado
- **WHEN** un usuario con rol odontólogo pero sin fila en `profesionales` intenta listar o crear presupuestos
- **THEN** el sistema responde HTTP 403 y no expone ni crea presupuestos

#### Scenario: Odontólogo no puede asignar otro profesional
- **WHEN** un odontólogo envía en el alta el `profesional_id` de otro profesional del consultorio
- **THEN** el sistema responde HTTP 403 y no crea el presupuesto

#### Scenario: Recepción lee y no escribe
- **WHEN** un recepcionista lista y lee presupuestos, y luego intenta crear o editar uno
- **THEN** las lecturas responden HTTP 200 y las escrituras HTTP 403

#### Scenario: Asistente y auditor solo leen
- **WHEN** un asistente o un auditor consulta presupuestos y luego intenta cambiar un estado o darlo de baja
- **THEN** las lecturas responden HTTP 200 y las escrituras HTTP 403

#### Scenario: Paciente sin turno vigente
- **WHEN** el único turno entre el paciente y el profesional del odontólogo está `cancelado` o `ausente`
- **THEN** el alta responde HTTP 403 porque no hay vínculo clínico vigente

#### Scenario: Presupuesto de otro odontólogo
- **WHEN** un odontólogo intenta leer, editar o cambiar el estado de un presupuesto de otro profesional
- **THEN** el sistema responde HTTP 403 y no modifica nada

#### Scenario: Petición sin token
- **WHEN** cualquier endpoint de presupuestos se invoca sin encabezado Bearer válido
- **THEN** el sistema responde HTTP 401 y no expone datos del presupuesto

### Requirement: Auditoría de las escrituras de presupuesto

Toda escritura (alta, edición, recálculo, baja lógica y cambio de estado) SHALL insertar en la misma transacción una fila de `RegistroAuditoria` con usuario, acción `presupuesto.*`, entidad `presupuesto`, identificador, IP y dispositivo. Una escritura rechazada no SHALL dejar auditoría y las filas SHALL seguir siendo inmutables por el trigger existente.

**Trazabilidad**: RN-SE-02, `04_modelo_de_datos.md` (`:87`), R-11, `security/core-models`.

#### Scenario: Auditoría del alta
- **WHEN** se crea un presupuesto desde `POST /presupuestos`
- **THEN** queda una fila con `accion='presupuesto.crear'`, `entidad='presupuesto'`, el `entidad_id` del presupuesto, el usuario autenticado, la IP y el `User-Agent` truncado

#### Scenario: Auditoría de cada transición
- **WHEN** un presupuesto recorre borrador, aceptado, en_curso y finalizado, y otro borrador se rechaza
- **THEN** existen filas `presupuesto.aceptar`, `presupuesto.en_curso`, `presupuesto.finalizar` y `presupuesto.rechazar` con el identificador del presupuesto

#### Scenario: Auditoría de edición, recálculo y baja
- **WHEN** se edita, se recalcula y se da de baja lógica un borrador
- **THEN** existen filas `presupuesto.editar`, `presupuesto.recalcular` y `presupuesto.eliminar` con el identificador del presupuesto

#### Scenario: Escritura rechazada no deja auditoría
- **WHEN** un alta falla por validación o un cambio de estado es inválido, o un odontólogo intenta editar un presupuesto ajeno
- **THEN** la transacción se revierte y no queda ninguna fila de auditoría de esa operación

#### Scenario: Auditoría de presupuestos append-only
- **WHEN** se intenta `UPDATE` o `DELETE` sobre una fila de auditoría generada por una escritura de presupuesto
- **THEN** PostgreSQL responde SQLSTATE `P0001` y la fila permanece intacta

### Requirement: Consulta y listado de presupuestos

El sistema SHALL exponer la ficha `GET /presupuestos/{id}` con ítems y totales, y el listado `GET /presupuestos` filtrable por `paciente_id`, `profesional_id` y `estado`, ordenado del más reciente al más antiguo. Un parámetro no declarado SHALL responder 422; un presupuesto inexistente o de otro consultorio, 404; el odontólogo SHALL listar solo los de su profesional.

**Trazabilidad**: US-021/CA-1, `03_actores_y_roles.md` (Presupuestos), RN-SE-01, R-02.

#### Scenario: Ficha con ítems y totales
- **WHEN** se consulta `GET /presupuestos/{id}` de un presupuesto calculado
- **THEN** la respuesta incluye `estado`, `cobertura_estado`, cada ítem con prestación, pieza, cantidad, precio, cobertura y copago, y los tres totales

#### Scenario: Listado por paciente
- **WHEN** un paciente tiene dos presupuestos y se consulta `GET /presupuestos?paciente_id={id}`
- **THEN** el sistema responde HTTP 200 con ambos, del más reciente al más antiguo, sin presupuestos de otros pacientes

#### Scenario: Filtro no declarado
- **WHEN** el listado recibe un parámetro fuera de `paciente_id`, `profesional_id` y `estado`
- **THEN** el sistema responde HTTP 422 por borde estricto

#### Scenario: Presupuesto inexistente o de otro consultorio
- **WHEN** se consulta la ficha de un identificador inexistente o de un presupuesto de otro consultorio
- **THEN** el sistema responde HTTP 404 y no expone ítems ni importes

#### Scenario: Odontólogo lista solo los propios
- **WHEN** existen presupuestos de dos profesionales y un odontólogo consulta `GET /presupuestos`
- **THEN** la respuesta HTTP 200 contiene solo los de su profesional

### Requirement: Aceptación sin bloqueo por consentimiento (RN-CL-03)

El sistema SHALL aceptar un presupuesto sin exigir consentimiento informado ni historia clínica abierta, porque el consentimiento es un acto clínico de C-11 y la práctica invasiva se registra fuera del presupuesto. La aceptación SHALL completarse con 200 y el consentimiento SHALL poder registrarse antes o después con `POST /pacientes/{id}/consentimientos`.

**Trazabilidad**: RN-CL-03, US-021/CA-3, `05_reglas_de_negocio.md` (`:20`), design D8.

#### Scenario: Aceptación de un plan con práctica invasiva sin consentimiento
- **WHEN** un presupuesto que incluye `EXO` (práctica invasiva) se pasa a `aceptado` sin ningún consentimiento registrado
- **THEN** el sistema responde HTTP 200 con `estado='aceptado'`
- **AND** no se crea ni se modifica ningún consentimiento

#### Scenario: Consentimiento registrado después de aceptar
- **WHEN** tras la aceptación se registra un consentimiento `procedimiento_invasivo` con `POST /pacientes/{id}/consentimientos`
- **THEN** el alta responde HTTP 201 con sus hashes y el presupuesto conserva `estado='aceptado'` y sus importes

#### Scenario: Aceptación sin historia clínica
- **WHEN** se acepta un presupuesto de un paciente que todavía no tiene historia clínica abierta
- **THEN** el sistema responde HTTP 200 y no intenta abrir ni exigir la historia

#### Scenario: Cuerpo de aceptación con datos clínicos
- **WHEN** el cuerpo del cambio de estado incluye `consentimiento`, `texto_version` o `firma_ref`
- **THEN** el sistema responde HTTP 422 por campo no permitido y el presupuesto no cambia de estado
