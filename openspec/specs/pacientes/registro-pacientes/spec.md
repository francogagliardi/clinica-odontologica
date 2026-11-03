# pacientes/registro-pacientes Specification

## Purpose
Registra la **demanda** de la clínica: pacientes con sus datos personales, contacto WhatsApp obligatorio y cobertura declarada, para que C-06 pueda crear turnos, C-07 identifique a quien reserva online y C-11/C-12 asocien historia clínica y presupuestos.

Nota de alcance: C-05 no calcula cobertura ni copago por ítem (RN-OS-02, C-12), no crea turnos (C-06) y no administra historia clínica (C-11). La validación de cobertura es contra reglas locales del convenio (DD-11).

## Requirements

### Requirement: Registro y ficha de pacientes

El sistema SHALL permitir alta, lectura de ficha, edición y baja lógica de pacientes del consultorio. Nombre, apellido, DNI y teléfono WhatsApp SHALL ser obligatorios. El DNI SHALL normalizarse sin puntos y ser único por consultorio entre pacientes activos; la baja lógica libera el DNI. El teléfono SHALL normalizarse a formato internacional argentino.

**Trazabilidad**: `04_modelo_de_datos.md` §Paciente (DNI único por consultorio, teléfono requerido, índices dni/telefono/apellido), RN-TU-01 (el turno referencia un paciente existente), DD-11.

#### Scenario: Alta exitosa con DNI y teléfono normalizados
- **WHEN** un administrador autenticado hace `POST /pacientes` con nombre, apellido, DNI `30.111.222` y teléfono `+54 9 11 5555-1234`
- **THEN** el sistema responde HTTP 201 con el paciente creado, `dni` igual a `30111222` y `telefono` igual a `+5491155551234`
- **AND** `GET /pacientes/{id}` devuelve HTTP 200 con la misma ficha y los datos de cobertura en `null`

#### Scenario: DNI duplicado entre pacientes activos
- **WHEN** se intenta dar de alta un segundo paciente activo del mismo consultorio con un DNI que ya existe, incluso escrito con puntos
- **THEN** el sistema responde HTTP 409 y no crea una fila nueva
- **AND** el índice único parcial `uq_pacientes_dni_activo` impide también el duplicado por SQL directo

#### Scenario: Baja lógica libera el DNI
- **WHEN** un administrador da de baja un paciente y luego crea otro activo con el mismo DNI
- **THEN** el alta responde HTTP 201 y el paciente anterior conserva `deleted_at` no nulo
- **AND** `GET /pacientes/{id}` del paciente dado de baja responde HTTP 404

#### Scenario: Teléfono ausente o vacío bloquea el alta
- **WHEN** el alta omite el teléfono, lo envía vacío o solo con separadores
- **THEN** el sistema responde HTTP 422 y no persiste el paciente porque WhatsApp es el canal de la clínica

#### Scenario: DNI o teléfono con formato inválido
- **WHEN** el alta envía un DNI con letras o fuera de 7–8 dígitos, o un teléfono que no tiene 10 dígitos nacionales ni código país 54
- **THEN** el sistema responde HTTP 422 y no persiste el paciente

#### Scenario: Edición de la ficha
- **WHEN** un administrador o recepcionista actualiza nombre, apellido, email o notas de un paciente activo
- **THEN** el sistema responde HTTP 200 con los datos actualizados y conserva DNI, teléfono y baja lógica intactos
- **AND** editar un paciente inexistente o dado de baja responde HTTP 404

### Requirement: Búsqueda de pacientes con criterio obligatorio

El sistema SHALL exponer `GET /pacientes` para buscar pacientes activos por DNI exacto normalizado, teléfono exacto normalizado o prefijo de apellido sin distinguir mayúsculas. Los filtros SHALL combinarse con AND y la consulta SHALL exigir al menos uno; los parámetros no declarados SHALL rechazarse con 422.

**Trazabilidad**: `04_modelo_de_datos.md` §Paciente (índices dni/telefono/apellido), RN-SE-01 (los datos solo se consultan autenticado), R-07 (privacidad: no hay volcado completo de pacientes).

#### Scenario: Búsqueda por apellido sin distinguir mayúsculas
- **WHEN** un recepcionista consulta `GET /pacientes?apellido=gos`
- **THEN** el sistema responde HTTP 200 con los pacientes activos cuyo apellido empieza con `gos`, ordenados por apellido y nombre
- **AND** buscar `GOS` o `gos` produce el mismo resultado

#### Scenario: Búsqueda por DNI o teléfono formateados
- **WHEN** la consulta usa `dni=30.111.222` o `telefono=+54 9 11 5555-1234`
- **THEN** el sistema normaliza el criterio y responde HTTP 200 con el paciente que coincide exactamente

#### Scenario: Filtros combinados con AND
- **WHEN** la consulta envía `apellido=gos&dni=30111222`
- **THEN** el sistema responde HTTP 200 solo si el paciente cumple ambos criterios; si no, devuelve lista vacía

#### Scenario: Consulta sin ningún criterio
- **WHEN** se llama `GET /pacientes` sin `dni`, `telefono` ni `apellido`
- **THEN** el sistema responde HTTP 422 con detalle que exige al menos un criterio de búsqueda y no devuelve pacientes

#### Scenario: Parámetro de búsqueda no declarado
- **WHEN** la consulta incluye un parámetro distinto de `dni`, `telefono` o `apellido` (por ejemplo `nombre`)
- **THEN** el sistema responde HTTP 422 en lugar de ignorarlo

#### Scenario: Búsqueda sin coincidencias
- **WHEN** el criterio no coincide con ningún paciente activo del consultorio
- **THEN** el sistema responde HTTP 200 con lista vacía

#### Scenario: Pacientes dados de baja excluidos de la búsqueda
- **WHEN** un paciente con DNI coincidente fue dado de baja lógica
- **THEN** la búsqueda por ese DNI responde HTTP 200 con lista vacía y no expone la ficha

### Requirement: Cobertura declarada del paciente

El sistema SHALL permitir asociar a un paciente una obra social activa del consultorio y un número de afiliado opcional. El número de afiliado SHALL ser nulo cuando no hay obra social. La obra social referenciada SHALL existir y estar activa. Quitar la cobertura SHALL limpiar también el número de afiliado.

**Trazabilidad**: `04_modelo_de_datos.md` §Paciente y §ObraSocial/Convenio, RN-OS-01 (validación preventiva de cobertura), DD-11.

#### Scenario: Alta con obra social y número de afiliado
- **WHEN** el alta referencia una obra social activa y envía un número de afiliado
- **THEN** el sistema responde HTTP 201 y la ficha devuelve `obra_social_id` y `nro_afiliado` informados

#### Scenario: Obra social inexistente o dada de baja
- **WHEN** el alta o la edición referencia una obra social que no existe o tiene baja lógica
- **THEN** el sistema responde HTTP 404 y no modifica el paciente

#### Scenario: Número de afiliado sin obra social
- **WHEN** el alta o la edición envía `nro_afiliado` con `obra_social_id` nulo
- **THEN** el sistema responde HTTP 422 porque el afiliado no tiene convenio asociado

#### Scenario: Quitar la cobertura limpia el afiliado
- **WHEN** la edición envía `obra_social_id` nulo y también `nro_afiliado` nulo
- **THEN** el sistema responde HTTP 200 y la ficha queda sin cobertura
- **AND** si se envía `obra_social_id` nulo conservando `nro_afiliado`, responde HTTP 422

#### Scenario: Cambio de obra social conservando afiliado
- **WHEN** la edición cambia `obra_social_id` a otra obra social activa y mantiene `nro_afiliado`
- **THEN** el sistema responde HTTP 200 con el nuevo convenio y el afiliado sin cambios

### Requirement: Control de acceso al registro de pacientes

El alta y la edición de pacientes SHALL exigir rol administrador o recepcionista. La baja lógica SHALL exigir administrador. Odontólogo, asistente y auditor SHALL poder leer pero no escribir. Toda petición sin token válido SHALL responder 401.

**Trazabilidad**: RN-SE-01, `03_actores_y_roles.md` §Matriz de permisos (recepción opera el registro; odontólogo y asistente leen para atender; auditor solo lee).

#### Scenario: Recepción crea y edita pacientes
- **WHEN** un recepcionista autenticado hace `POST /pacientes` y luego `PUT /pacientes/{id}`
- **THEN** el sistema responde HTTP 201 y HTTP 200 respectivamente

#### Scenario: Roles clínicos y de auditoría no escriben
- **WHEN** un odontólogo, asistente o auditor intenta `POST`, `PUT` o `DELETE /pacientes`
- **THEN** el sistema responde HTTP 403 con detalle "Permisos insuficientes"

#### Scenario: Solo administrador da de baja
- **WHEN** un recepcionista intenta `DELETE /pacientes/{id}`
- **THEN** el sistema responde HTTP 403 y el paciente sigue activo
- **AND** un administrador sobre el mismo paciente recibe HTTP 204

#### Scenario: Petición sin token
- **WHEN** cualquier endpoint de pacientes se invoca sin encabezado Bearer válido
- **THEN** el sistema responde HTTP 401 y no expone datos del paciente
