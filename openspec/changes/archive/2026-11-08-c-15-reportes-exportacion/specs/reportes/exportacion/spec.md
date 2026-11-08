# Spec Delta

## Purpose

Garantiza que el paciente o el consultorio puedan sacar todos sus datos en todo momento, en formato legible (PDF) y estructurado (JSON y CSV), mediante una exportación durable, auditada y sin cargos ni ventanas de retención.

## ADDED Requirements

### Requirement: Exportación total de un paciente

`POST /exportaciones` con `alcance='paciente'` SHALL aceptar un `paciente_id` del consultorio y responder 202 con una exportación `pendiente`; un paciente inexistente, inactivo o de otro consultorio SHALL responder 404, y un alcance o campo no declarado 422. La exportación SHALL incluir todas las entidades vinculadas al paciente y sus adjuntos binarios, aunque el paciente no tenga datos clínicos.

**Trazabilidad**: US-041/CA-2 (`knowledge-base/06_funcionalidades.md:86–91`), RN-SE-03 (`knowledge-base/05_reglas_de_negocio.md:46`), DD-05 (`knowledge-base/09_decisiones_y_supuestos.md:28–31`), CHANGES.md §C-15.

#### Scenario: Solicitud de exportación de un paciente

- **WHEN** un administrador solicita exportar un paciente activo del consultorio
- **THEN** responde HTTP 202 con `id`, `alcance='paciente'`, `paciente_id` y `estado='pendiente'`

#### Scenario: Paciente inexistente, inactivo o ajeno

- **WHEN** el `paciente_id` no existe, tiene baja lógica o pertenece a otro consultorio
- **THEN** el sistema responde HTTP 404 y no crea una exportación

#### Scenario: Alcance o campo no declarado

- **WHEN** el cuerpo envía `alcance='historias'`, un `formato` distinto de `zip` o un campo extra
- **THEN** el sistema responde HTTP 422 y no encola trabajo

#### Scenario: Paciente sin datos clínicos

- **WHEN** se exporta un paciente que solo tiene datos de registro
- **THEN** la exportación termina `lista` con las secciones clínicas vacías, sin fallar

#### Scenario: Adjuntos del paciente incluidos

- **WHEN** el paciente tiene un adjunto clínico de 2 MB
- **THEN** el ZIP incluye el binario del adjunto y su fila de metadatos en el estructurado

### Requirement: Exportación total del consultorio

`POST /exportaciones` con `alcance='consultorio'` SHALL exportar todos los pacientes y entidades del consultorio autenticado sin exigir rango y responder 202. `paciente_id` SHALL rechazarse en este alcance con 422. La exportación de consultorio SHALL incluir el directorio mínimo de usuarios (id, nombre, email y roles activos), sin `hash_password`.

**Trazabilidad**: US-041/CA-2 (`knowledge-base/06_funcionalidades.md:86–91`), RN-SE-03 (`knowledge-base/05_reglas_de_negocio.md:46`), DD-05 (`knowledge-base/09_decisiones_y_supuestos.md:28–31`), `04_modelo_de_datos.md:13–28`.

#### Scenario: Exportación de todo el consultorio

- **WHEN** un administrador solicita exportar el consultorio
- **THEN** responde HTTP 202 con `alcance='consultorio'` y `paciente_id=null`

#### Scenario: Paciente declarado en alcance consultorio

- **WHEN** el cuerpo combina `alcance='consultorio'` con un `paciente_id`
- **THEN** el sistema responde HTTP 422 y no crea la exportación

#### Scenario: Todos los pacientes, ningún otro tenant

- **WHEN** el consultorio tiene 3 pacientes y otro consultorio tiene 2
- **THEN** `manifiesto.json` informa 3 pacientes y el ZIP no contiene ningún id del otro consultorio

#### Scenario: Directorio de usuarios sin credenciales

- **WHEN** se exporta el consultorio con usuarios y roles
- **THEN** el estructurado incluye id, nombre, email y roles de cada usuario, y no incluye `hash_password`

### Requirement: Contenido del ZIP y exclusiones de secretos

El ZIP SHALL contener `exportacion.pdf`, `datos.json` (con `version`, `alcance`, `generado_en` y una clave por entidad), `manifiesto.json` (conteos por entidad) y un CSV por entidad. SHALL incluir las entidades del ERD y excluir `hash_password`, tokens públicos o de un solo uso, secretos de webhook, `claim_token`, `link_pago` y payloads de proveedores. El PDF SHALL ser un resumen legible con totales por sección, no la única fuente de datos.

**Trazabilidad**: US-041/CA-2 (`knowledge-base/06_funcionalidades.md:86–91`), RN-SE-03/RN-SE-04 (`knowledge-base/05_reglas_de_negocio.md:46–47`), DD-05, `04_modelo_de_datos.md:13–28`, R-11 (`AGENTS.md`).

#### Scenario: Entradas obligatorias del ZIP

- **WHEN** una exportación termina `lista` y se descarga
- **THEN** el ZIP contiene `exportacion.pdf`, `datos.json`, `manifiesto.json` y al menos un archivo `csv/` por entidad con filas

#### Scenario: Conteos coherentes

- **WHEN** `manifiesto.json` informa 4 turnos y 2 cobros
- **THEN** `datos.json` y los CSV correspondientes tienen exactamente esas cantidades

#### Scenario: Secretos y credenciales ausentes

- **WHEN** se inspeccionan todos los archivos del ZIP de un consultorio con usuarios y turnos con token público
- **THEN** no aparecen `hash_password`, valores de `token_publico`, tokens de un solo uso, `claim_token`, `link_pago`, secretos de webhook ni payloads crudos de proveedores

#### Scenario: PDF legible y no vacío

- **WHEN** se abre `exportacion.pdf`
- **THEN** comienza con la firma `%PDF-`, tiene al menos una página e incluye los totales por sección y la fecha de generación en UTC-3

#### Scenario: Auditoría y comunicaciones incluidas

- **WHEN** el paciente tiene recordatorios, mensajes, liquidaciones y filas de auditoría
- **THEN** esas entidades aparecen en `datos.json`, en sus CSV y en el manifiesto con sus conteos

#### Scenario: Volumen por encima del límite

- **WHEN** una entidad supera `EXPORTACION_MAX_FILAS` o el artefacto supera `EXPORTACION_MAX_BYTES`
- **THEN** la exportación termina `fallida` con un error que nombra el límite, no deja un ZIP parcial y permite solicitar una nueva

### Requirement: Generación asincrónica y durable

La generación SHALL ejecutarse fuera del request: el 202 no SHALL esperar al PDF/ZIP y una exportación SHALL quedar `lista` solo cuando el worker `reportes` persistió el artefacto. El estado SHALL seguir `pendiente→generando→lista|fallida`; un fallo SHALL incrementar `intentos` y reintentar con backoff hasta el máximo. Si Redis está caído, el barrido de pendientes SHALL recuperar el trabajo sin perderlo.

**Trazabilidad**: DD-07c (`knowledge-base/09_decisiones_y_supuestos.md:55–58`), CHANGES.md §C-15 ("reportes pesados como jobs"), R-06 (`AGENTS.md`), `platform/job-queues`.

#### Scenario: El request no espera la generación

- **WHEN** se solicita una exportación de consultorio y el worker no está corriendo
- **THEN** el POST responde 202 en el mismo request y `GET /exportaciones/{id}` informa `pendiente` sin artefacto

#### Scenario: El worker deja la exportación lista

- **WHEN** el worker `reportes` procesa una exportación `pendiente`
- **THEN** la fila pasa a `generando` y luego a `lista`, con `tamano_bytes`, `generada_at` y el ZIP descargable

#### Scenario: Job duplicado no duplica artefacto

- **WHEN** el mismo id aparece dos veces en `reportes:generar` o el worker lo reprocesa
- **THEN** se genera un solo artefacto y la exportación no retrocede de `lista` a `generando`

#### Scenario: Fallo transitorio con backoff

- **WHEN** falla la generación antes del máximo de intentos
- **THEN** `intentos` aumenta, `proximo_intento` se calcula con backoff y la exportación vuelve a `pendiente` para reintento

#### Scenario: Fallo definitivo

- **WHEN** se alcanza `EXPORTACION_MAX_INTENTOS`
- **THEN** la exportación queda `fallida` con `ultimo_error`, sin ZIP parcial y sin bloquear nuevas solicitudes

#### Scenario: Redis caído no pierde la exportación

- **WHEN** `reportes:generar` está vacío o Redis no responde y existen exportaciones `pendiente` vencidas
- **THEN** el worker las encuentra por barrido en PostgreSQL y las procesa igual

#### Scenario: Estado de otro consultorio

- **WHEN** un usuario consulta el estado de una exportación de otro consultorio
- **THEN** el sistema responde HTTP 404 y no revela su alcance ni su contenido

### Requirement: Descarga, idempotencia y disponibilidad sin cargo

`GET /exportaciones/{id}/archivo` SHALL responder 200 `application/zip` solo con estado `lista`; `pendiente|generando` SHALL responder 409 y `fallida` 409 con el error. Repetir `POST /exportaciones` con el mismo alcance y paciente mientras exista una exportación en curso SHALL devolver la misma exportación (202), sin duplicar jobs. Una exportación `fallida` o `lista` SHALL permitir solicitar una nueva sin cargo ni ventana; no SHALL existir borrado automático punitivo.

**Trazabilidad**: RN-SE-03 (`knowledge-base/05_reglas_de_negocio.md:46`), DD-05 (`knowledge-base/09_decisiones_y_supuestos.md:28–31`), US-041/CA-2, CHANGES.md §C-15.

#### Scenario: Descarga de una exportación lista

- **WHEN** se descarga una exportación `lista`
- **THEN** responde HTTP 200 con `Content-Type: application/zip` y un ZIP válido con las entradas obligatorias

#### Scenario: Descarga antes de tiempo

- **WHEN** se descarga una exportación `pendiente` o `generando`
- **THEN** el sistema responde HTTP 409 y no entrega un artefacto incompleto

#### Scenario: Descarga de una exportación fallida

- **WHEN** se descarga una exportación `fallida`
- **THEN** el sistema responde HTTP 409 con `ultimo_error` y no inventa un archivo

#### Scenario: Solicitud repetida en curso

- **WHEN** se repite el mismo `POST /exportaciones` mientras la primera sigue `pendiente` o `generando`
- **THEN** responde 202 con el mismo `id` y no se encola un segundo trabajo

#### Scenario: Nueva exportación tras un fallo

- **WHEN** una exportación quedó `fallida` y se solicita otra del mismo alcance
- **THEN** se crea una exportación nueva sin cobro, sin ventana de espera y sin borrar el historial anterior

#### Scenario: Sin cargos ni límites comerciales

- **WHEN** un administrador exporta el mismo paciente diez veces
- **THEN** las diez solicitudes se aceptan o reutilizan el job en curso, sin respuesta de pago, cuota o bloqueo temporal

### Requirement: Acceso a exportaciones por rol

Exportar un paciente SHALL permitir al administrador y al odontólogo solo si el paciente tiene un turno o presupuesto de su profesional; exportar el consultorio SHALL ser exclusivo del administrador. Recepción, asistente y auditor SHALL recibir 403 y sin token 401. El listado, el estado y el archivo SHALL respetar el mismo alcance sin filtrar datos de otra exportación.

**Trazabilidad**: `knowledge-base/03_actores_y_roles.md:20–27` (§RBAC, Reportes y Ficha clínica), RN-SE-01 (`knowledge-base/05_reglas_de_negocio.md:44`), RN-SE-04 (`:47`), R-03 (`AGENTS.md`).

#### Scenario: Administrador exporta ambos alcances

- **WHEN** un administrador exporta un paciente y luego el consultorio
- **THEN** ambas solicitudes responden HTTP 202

#### Scenario: Odontólogo exporta un paciente propio

- **WHEN** un odontólogo exporta un paciente con un turno de su profesional
- **THEN** el sistema responde HTTP 202 y el ZIP no incluye datos de otros pacientes

#### Scenario: Odontólogo exporta un paciente ajeno

- **WHEN** un odontólogo exporta un paciente sin turnos ni presupuestos de su profesional
- **THEN** el sistema responde HTTP 403 y no crea la exportación

#### Scenario: Odontólogo intenta exportar el consultorio

- **WHEN** un odontólogo solicita `alcance='consultorio'`
- **THEN** el sistema responde HTTP 403

#### Scenario: Roles sin exportación

- **WHEN** recepción, asistente o auditor solicitan cualquier exportación
- **THEN** el sistema responde HTTP 403, y sin token responde HTTP 401

#### Scenario: Acceso a una exportación ajena

- **WHEN** un odontólogo consulta el estado o descarga una exportación de consultorio creada por el administrador
- **THEN** el sistema responde HTTP 404 o 403 sin revelar el contenido

### Requirement: Auditoría de la exportación

`exportacion.solicitar`, `exportacion.generar`, `exportacion.fallida` y `exportacion.descargar` SHALL insertarse en `registro_auditoria` con usuario (o nulo para el worker), exportación, alcance, IP y dispositivo. Una solicitud rechazada no SHALL dejar auditoría y el sondeo de estado no SHALL duplicar filas.

**Trazabilidad**: RN-SE-02 (`knowledge-base/05_reglas_de_negocio.md:45`), R-11 (`AGENTS.md`), `security/core-models` §Auditoría, `04_modelo_de_datos.md:85–88`.

#### Scenario: Auditoría de la solicitud

- **WHEN** un administrador solicita una exportación con IP y `User-Agent` conocidos
- **THEN** existe una fila `exportacion.solicitar` con el id de la exportación, usuario, alcance, IP y dispositivo truncado

#### Scenario: Auditoría de la generación por el worker

- **WHEN** el worker genera el artefacto
- **THEN** queda una fila `exportacion.generar` con `usuario_id=null` (actor sistema) y el id de la exportación

#### Scenario: Auditoría de la descarga

- **WHEN** se descarga el ZIP
- **THEN** queda una fila `exportacion.descargar` con usuario, IP y dispositivo

#### Scenario: Solicitud rechazada sin auditoría

- **WHEN** una exportación se rechaza por 403, 404 o 422
- **THEN** la transacción no deja fila de auditoría de esa solicitud

#### Scenario: Sondeo sin auditoría repetida

- **WHEN** el cliente consulta `GET /exportaciones/{id}` diez veces mientras está `generando`
- **THEN** no se agrega ninguna fila de auditoría por esas lecturas

#### Scenario: Auditoría de exportación inmutable

- **WHEN** se intenta `UPDATE` o `DELETE` sobre una fila de auditoría de exportación
- **THEN** PostgreSQL responde SQLSTATE `P0001` y la fila permanece intacta
