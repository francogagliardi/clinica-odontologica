# Spec Delta

## Purpose

Valida en forma preventiva la cobertura de una práctica contra el convenio local y liquida por período las prácticas cubiertas de una obra social, con trazabilidad a presupuesto, ítem y cobro, para que la clínica pueda reclamar sin doble carga ni pérdida de respaldo.

## ADDED Requirements

### Requirement: Validación preventiva de cobertura

`GET /obras-sociales/cobertura?paciente_id&prestacion_id` SHALL devolver `estado cubierta|no_cubierta|pendiente_verificacion`, `cobertura_porcentaje`, `cobertura_monto` y `copago_monto`, calculados con el convenio local vigente y el precio base. Si el paciente tiene obra social pero no `nro_afiliado`, la respuesta SHALL ser `pendiente_verificacion`. La consulta no SHALL escribir ni bloquear turnos, presupuestos o atenciones; paciente o prestación inexistente SHALL responder 404.

**Trazabilidad**: RN-OS-01, RN-OS-02, US-031/CA-2, DD-11, Flujo 3, `04_modelo_de_datos.md` §ObraSocial/Convenio.

#### Scenario: Práctica cubierta por el convenio
- **WHEN** un paciente de "OS Demo" con cobertura 60 % consulta una prestación cubierta de precio 10000.00
- **THEN** responde HTTP 200 con `estado='cubierta'`, `cobertura_porcentaje=60`, `cobertura_monto=6000.00` y `copago_monto=4000.00`

#### Scenario: Paciente sin obra social
- **WHEN** el paciente no tiene obra social asignada
- **THEN** responde HTTP 200 con `estado='no_cubierta'`, cobertura 0 y copago igual al precio base

#### Scenario: Práctica fuera del convenio
- **WHEN** el convenio existe pero la prestación no está en `prestaciones_cubiertas`
- **THEN** responde HTTP 200 con `estado='no_cubierta'` y no inventa una cobertura parcial

#### Scenario: Cobertura no determinable
- **WHEN** el convenio del paciente está inactivo o sus reglas no permiten calcular el porcentaje
- **THEN** responde HTTP 200 con `estado='pendiente_verificacion'`, montos nulos y sin bloquear la atención

#### Scenario: Paciente con obra social sin número de afiliado
- **WHEN** el paciente tiene una obra social activa pero `nro_afiliado` nulo
- **THEN** responde HTTP 200 con `estado='pendiente_verificacion'` y montos nulos

#### Scenario: Paciente o prestación inexistente
- **WHEN** el `paciente_id` o el `prestacion_id` no existe, está inactivo o es de otro consultorio
- **THEN** el sistema responde HTTP 404

#### Scenario: La validación no escribe
- **WHEN** se valida cobertura de un paciente con turnos y presupuestos existentes
- **THEN** no se crea ni modifica ningún turno, presupuesto, cobro o liquidación

### Requirement: Cobertura solo local en v1

La validación SHALL usar exclusivamente `reglas_cobertura` locales del convenio; topes, frecuencias y nomenclador real no SHALL modelarse en v1. Sin reglas utilizables la respuesta SHALL ser `pendiente_verificacion` con montos nulos, nunca una cobertura inventada.

**Trazabilidad**: RN-OS-01, DD-11, R-12, SU-03, `11_integraciones_argentinas.md` §Verificación de cobertura.

#### Scenario: Convenio sin porcentaje utilizable
- **WHEN** el convenio tiene reglas vacías o un porcentaje inválido
- **THEN** la validación responde `pendiente_verificacion` y no calcula montos

#### Scenario: Sin topes ni frecuencias en la respuesta
- **WHEN** se consulta la cobertura de cualquier práctica
- **THEN** la respuesta no incluye topes, frecuencias ni códigos de nomenclador externo

#### Scenario: Sin llamadas externas
- **WHEN** se valida cobertura con el proveedor local
- **THEN** no se realiza ninguna llamada de red a PUCO ni a otra obra social

### Requirement: Liquidación por período con trazabilidad

`POST /obras-sociales/liquidaciones` SHALL crear una liquidación `borrador` para una obra social y un período `desde/hasta` en UTC-3, incluyendo una sola vez cada ítem activo cubierto (`cobertura_item > 0`) de presupuestos `aceptado|en_curso|finalizado` con un cobro de tratamiento `aprobado` en el período. Cada ítem SHALL guardar referencias a presupuesto, ítem y cobro, y el snapshot de prestación, cantidad y cobertura.

**Trazabilidad**: RN-OS-03, US-031/CA-3, DD-11, `04_modelo_de_datos.md` §Cobro/ComprobanteARCA y §Presupuesto.

#### Scenario: Liquidación con prácticas cubiertas
- **WHEN** un presupuesto de un paciente de la obra social tiene un ítem cubierto y un cobro de tratamiento aprobado dentro del período
- **THEN** responde HTTP 201 con una liquidación `borrador`, un ítem trazable a presupuesto/ítem/cobro y `total_cobertura` igual a la suma de las coberturas

#### Scenario: Sin prácticas liquidables
- **WHEN** el período no tiene cobros de tratamiento aprobados con ítems cubiertos
- **THEN** el sistema responde HTTP 422 y no crea la cabecera

#### Scenario: Pagos parciales no duplican la práctica
- **WHEN** un mismo presupuesto tiene dos cobros de tratamiento aprobados dentro del período
- **THEN** sus ítems aparecen una sola vez en la liquidación

#### Scenario: Ítem ya liquidado
- **WHEN** un ítem de presupuesto ya pertenece a otra liquidación vigente
- **THEN** no se incluye otra vez y el total no lo cuenta dos veces

#### Scenario: Ítems sin cobertura o de otra obra social
- **WHEN** el presupuesto tiene ítems con `cobertura_item=0` o el paciente pertenece a otra obra social
- **THEN** esos ítems no se incluyen en la liquidación

#### Scenario: Presupuesto sin cobro aprobado en el período
- **WHEN** el presupuesto tiene ítems cubiertos pero ningún cobro de tratamiento aprobado dentro del período
- **THEN** el ítem no se incluye en esa liquidación

### Requirement: Período coherente y no solapado

El período SHALL cumplir `desde <= hasta` y no SHALL solaparse con otra liquidación vigente de la misma obra social. Un solapamiento SHALL responder HTTP 409 y el intento por SQL directo SHALL fallar con SQLSTATE `23P01`; fechas invertidas SHALL responder 422 y una obra social inexistente o inactiva 404.

**Trazabilidad**: RN-OS-03, R-04, R-05, `04_modelo_de_datos.md` §ObraSocial/Convenio.

#### Scenario: Período válido de un solo día
- **WHEN** se crea una liquidación con `desde=hasta`
- **THEN** responde HTTP 201 y el período se considera válido

#### Scenario: Fechas invertidas
- **WHEN** el alta envía `desde` posterior a `hasta`
- **THEN** el sistema responde HTTP 422 y no crea la liquidación

#### Scenario: Solapamiento entre liquidaciones
- **WHEN** ya existe una liquidación vigente de la misma obra social que se cruza con el período pedido
- **THEN** el sistema responde HTTP 409 y no crea una segunda cabecera

#### Scenario: Solapamiento por SQL directo
- **WHEN** se inserta por SQL un período que se cruza con otro vigente de la misma obra social
- **THEN** PostgreSQL rechaza la fila con SQLSTATE `23P01`

#### Scenario: Períodos contiguos
- **WHEN** una liquidación termina el 31 de enero y otra empieza el 1 de febrero
- **THEN** ambas se aceptan porque no se solapan

#### Scenario: Obra social inexistente o inactiva
- **WHEN** el alta referencia una obra social que no existe, tiene baja lógica o es de otro consultorio
- **THEN** el sistema responde HTTP 404

### Requirement: Estados, cierre y borrado de borrador

La liquidación SHALL nacer `borrador` y pasar a `cerrada` solo por administrador; cerrar SHALL congelar ítems y totales, y repetir el cierre SHALL ser idempotente. Una liquidación `cerrada` no SHALL aceptar edición ni borrado. Solo un `borrador` SHALL poder borrarse lógicamente por administrador, liberando su período.

**Trazabilidad**: RN-OS-03, R-11, `03_actores_y_roles.md` §Matriz (Obras sociales), `04_modelo_de_datos.md` §ObraSocial/Convenio.

#### Scenario: Cierre de una liquidación
- **WHEN** un administrador cierra una liquidación `borrador`
- **THEN** responde HTTP 200 con `estado='cerrada'`, `cerrada_por`, `cerrada_at` y los totales congelados

#### Scenario: Cierre repetido
- **WHEN** se repite el cierre de una liquidación ya `cerrada`
- **THEN** responde HTTP 200 sin cambiar totales ni duplicar auditoría

#### Scenario: Edición de una liquidación cerrada
- **WHEN** se intenta editar observaciones o borrar una liquidación `cerrada`
- **THEN** el sistema responde HTTP 409 y no modifica nada

#### Scenario: Borrado de un borrador libera el período
- **WHEN** un administrador borra lógicamente una liquidación `borrador`
- **THEN** responde HTTP 204 y se puede crear otra liquidación que cubra el mismo período

#### Scenario: Recepción no cierra
- **WHEN** un recepcionista intenta cerrar o borrar una liquidación
- **THEN** el sistema responde HTTP 403

### Requirement: Consulta y RBAC de liquidaciones

`GET /obras-sociales/liquidaciones` y su ficha SHALL listar y consultar por obra social, estado y período, incluyendo ítems y totales. Administrador, recepción, odontólogo y auditor SHALL leer; solo administrador SHALL crear, cerrar y borrar; recepción SHALL editar observaciones de un borrador; el asistente SHALL recibir 403. La validación de cobertura SHALL seguir la misma matriz de lectura.

**Trazabilidad**: RN-SE-01, `03_actores_y_roles.md` §Matriz (Obras sociales y Caja/Cobros), R-03, `security/rbac-guards`.

#### Scenario: Lectura por los roles habilitados
- **WHEN** administrador, recepción, odontólogo y auditor listan liquidaciones
- **THEN** todos reciben HTTP 200 y la ficha incluye ítems y totales

#### Scenario: Recepción edita observaciones
- **WHEN** un recepcionista actualiza las observaciones de una liquidación `borrador`
- **THEN** responde HTTP 200 y el resto de la liquidación no cambia

#### Scenario: Odontólogo intenta crear
- **WHEN** un odontólogo intenta crear, cerrar o borrar una liquidación
- **THEN** el sistema responde HTTP 403

#### Scenario: Asistente sin acceso
- **WHEN** un asistente consulta cualquier endpoint de liquidaciones o de cobertura
- **THEN** el sistema responde HTTP 403

#### Scenario: Filtro no declarado
- **WHEN** el listado recibe un parámetro de filtro no declarado
- **THEN** el sistema responde HTTP 422

#### Scenario: Petición sin token
- **WHEN** cualquier endpoint de liquidaciones o de cobertura se invoca sin Bearer válido
- **THEN** el sistema responde HTTP 401

### Requirement: Auditoría de liquidaciones

Crear, editar, cerrar y borrar una liquidación SHALL insertar en la misma transacción una fila de auditoría `liquidacion.crear`, `liquidacion.editar`, `liquidacion.cerrar` o `liquidacion.eliminar` con usuario, IP y dispositivo. Una escritura rechazada no SHALL dejar auditoría y las filas SHALL seguir siendo inmutables.

**Trazabilidad**: RN-SE-02, R-11, `security/core-models` §Auditoría, `04_modelo_de_datos.md` §Usuario/Rol/RegistroAuditoria.

#### Scenario: Auditoría del alta y del cierre
- **WHEN** un administrador crea y luego cierra una liquidación
- **THEN** quedan filas `liquidacion.crear` y `liquidacion.cerrar` con usuario, IP y dispositivo

#### Scenario: Auditoría de edición y borrado
- **WHEN** un recepcionista edita observaciones y un administrador borra el borrador
- **THEN** quedan filas `liquidacion.editar` y `liquidacion.eliminar` con sus identificadores

#### Scenario: Escritura rechazada no deja auditoría
- **WHEN** un alta falla por período solapado o sin prácticas liquidables
- **THEN** la transacción se revierte y no queda auditoría de esa operación

#### Scenario: Auditoría append-only
- **WHEN** se intenta `UPDATE` o `DELETE` sobre una fila de auditoría de liquidaciones
- **THEN** PostgreSQL responde SQLSTATE `P0001` y la fila permanece intacta
