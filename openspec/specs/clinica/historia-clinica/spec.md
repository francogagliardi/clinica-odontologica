# clinica/historia-clinica Specification

## Purpose
Registra y protege la ficha clínica del paciente —historia, evoluciones firmadas, adjuntos y consentimientos— para que la atención quede documentada con trazabilidad total, corrección por rectificatoria y acceso restringido por rol.

## Requirements

### Requirement: Historia clínica única por paciente

El sistema SHALL crear una historia clínica por paciente y consultorio, registrando quién la abre y cuándo, y SHALL permitir leerla por paciente o por identificador. Un paciente inexistente o dado de baja SHALL responder 404; una segunda historia activa para el mismo paciente SHALL responder 409, respaldada por un índice único en PostgreSQL.

**Trazabilidad**: `04_modelo_de_datos.md` §HistoriaClinica / Evolucion (`:59-61`), US-020/CA-1, RN-SE-02, R-04.

#### Scenario: Apertura de la historia de un paciente existente
- **WHEN** un odontólogo autenticado y vinculado al profesional del paciente hace `POST /historia-clinica` con el `paciente_id`
- **THEN** el sistema responde HTTP 201 con la historia creada, `abierta_por` igual al usuario autenticado y `fecha_apertura` no nula
- **AND** `GET /historia-clinica/{id}` y `GET /pacientes/{paciente_id}/historia-clinica` devuelven HTTP 200 con la misma historia

#### Scenario: Segunda historia activa para el mismo paciente
- **WHEN** se intenta abrir otra historia para un paciente que ya tiene una activa
- **THEN** el sistema responde HTTP 409 y no crea una fila nueva
- **AND** un `INSERT` directo duplicado es rechazado por PostgreSQL con SQLSTATE `23505`

#### Scenario: Paciente inexistente o dado de baja
- **WHEN** se intenta abrir una historia para un `paciente_id` que no existe, pertenece a otro consultorio o tiene baja lógica
- **THEN** el sistema responde HTTP 404 y no crea la historia ni deja auditoría de apertura

#### Scenario: Lectura de un paciente sin historia
- **WHEN** se consulta `GET /pacientes/{paciente_id}/historia-clinica` para un paciente activo que todavía no tiene historia
- **THEN** el sistema responde HTTP 404 con detalle "Historia clínica no encontrada"

#### Scenario: Historia de un paciente de otro consultorio
- **WHEN** se consulta `GET /historia-clinica/{id}` con el identificador de una historia de otro consultorio
- **THEN** el sistema responde HTTP 404 y no expone datos clínicos

### Requirement: Evolución borrador y firma inmutable

El sistema SHALL crear evoluciones como borrador (`firmada=false`) con historia, profesional y texto. El autor odontólogo o un asistente habilitado sobre el paciente en sala SHALL poder editar o descartar el borrador. La firma SHALL fijar `firmada=true`, `firmada_por` y `fecha_firma` y congelar historia, profesional, fecha, texto y `rectifica_a`. Una evolución firmada SHALL rechazar edición o borrado por API con 403 y por trigger con `P0001`; desfirmar no SHALL ser posible.

**Trazabilidad**: RN-CL-04 (`05_reglas_de_negocio.md:21`), RN-SE-02 (`:45`), US-020/CA-2, `04_modelo_de_datos.md` §Evolucion (`:61`), R-11.

#### Scenario: Alta de una evolución en borrador
- **WHEN** un odontólogo hace `POST /historia-clinica/{id}/evoluciones` con `texto` no vacío
- **THEN** el sistema responde HTTP 201 con `firmada=false`, `firmada_por` nulo y `fecha_firma` nula
- **AND** la respuesta incluye el `profesional_id` vinculado al usuario

#### Scenario: Edición del borrador por su autor
- **WHEN** el odontólogo autor actualiza el `texto` de una evolución no firmada
- **THEN** el sistema responde HTTP 200 con el texto nuevo y la evolución sigue con `firmada=false`

#### Scenario: Firma de la evolución
- **WHEN** el odontólogo autor hace `POST /historia-clinica/{id}/evoluciones/{evolucion_id}/firmar`
- **THEN** el sistema responde HTTP 200 con `firmada=true`, `firmada_por` igual al usuario y `fecha_firma` no nula
- **AND** queda una fila de auditoría `evolucion.firmar` con el usuario, IP y dispositivo de la petición

#### Scenario: Edición de una evolución firmada
- **WHEN** se intenta `PUT /historia-clinica/{id}/evoluciones/{evolucion_id}` sobre una evolución firmada
- **THEN** el sistema responde HTTP 403 y el texto firmado no cambia

#### Scenario: UPDATE directo sobre una evolución firmada
- **WHEN** se ejecuta `UPDATE evoluciones SET texto = 'adulterado'` por SQL directo sobre una fila firmada
- **THEN** PostgreSQL aborta la operación con SQLSTATE `P0001` y el texto original permanece intacto

#### Scenario: Borrado de una evolución firmada
- **WHEN** se intenta `DELETE /historia-clinica/{id}/evoluciones/{evolucion_id}` sobre una evolución firmada, o un `DELETE` directo por SQL
- **THEN** la API responde HTTP 403 y PostgreSQL rechaza el borrado directo con SQLSTATE `P0001`; la evolución sigue consultable

#### Scenario: Firma repetida es idempotente
- **WHEN** se vuelve a firmar una evolución ya firmada
- **THEN** el sistema responde HTTP 200 sin modificar `fecha_firma`, `firmada_por` ni el texto, y no duplica la auditoría de firma

#### Scenario: Firma con cuerpo inesperado
- **WHEN** la petición de firma envía un cuerpo con campos distintos de ninguno (por ejemplo `fecha_firma` o `texto`)
- **THEN** el sistema responde HTTP 422 y la evolución sigue en borrador

### Requirement: Rectificatoria enlazada a la evolución firmada

La corrección de una evolución firmada SHALL hacerse con una nueva evolución cuyo `rectifica_a` apunte a una evolución firmada de la misma historia. La rectificatoria SHALL seguir el flujo borrador→firma y no SHALL modificar la original. Una referencia a un borrador o a otra historia SHALL responder 422; una referencia inexistente, 404; una segunda rectificatoria activa de la misma original SHALL responder 409 y el índice único parcial SHALL impedirla también por SQL.

**Trazabilidad**: RN-CL-04 (`05_reglas_de_negocio.md:21`), RN-SE-02 (`:45`), US-020/CA-2, R-11.

#### Scenario: Alta de la rectificatoria
- **WHEN** un odontólogo crea una evolución con `rectifica_a` igual al identificador de una evolución firmada de la misma historia
- **THEN** el sistema responde HTTP 201 con `rectifica_a` informado y `firmada=false`
- **AND** la evolución original conserva su texto, `firmada=true` y `fecha_firma`

#### Scenario: Firma de la rectificatoria y enlace visible
- **WHEN** se firma la rectificatoria y luego se lee la evolución original
- **THEN** la original expone `rectificada_por` con el identificador de la rectificatoria firmada y su texto no cambió

#### Scenario: Rectificar un borrador
- **WHEN** se envía `rectifica_a` apuntando a una evolución con `firmada=false`
- **THEN** el sistema responde HTTP 422 porque solo se rectifica lo firmado

#### Scenario: Rectificar una evolución de otra historia
- **WHEN** se envía `rectifica_a` apuntando a una evolución firmada de otra historia clínica
- **THEN** el sistema responde HTTP 422 y no crea la evolución

#### Scenario: Segunda rectificatoria de la misma original
- **WHEN** ya existe una rectificatoria activa para una evolución firmada y se intenta crear otra sobre la misma original
- **THEN** el sistema responde HTTP 409 y un `INSERT` directo es rechazado con SQLSTATE `23505`

#### Scenario: Rectificar una rectificatoria
- **WHEN** se crea una nueva evolución con `rectifica_a` apuntando a una rectificatoria ya firmada
- **THEN** el sistema responde HTTP 201 y la cadena de correcciones queda navegable sin alterar ningún eslabón anterior

### Requirement: Adjuntos clínicos con contenido validado

El sistema SHALL aceptar adjuntos de una historia existente en `multipart/form-data` con nombre saneado, MIME permitido (JPEG, PNG, WebP, PDF), tamaño máximo 5 MB y bytes persistidos en PostgreSQL. SHALL verificar que la firma del archivo corresponda al MIME declarado y SHALL rechazar ejecutables o nombres con rutas. La descarga SHALL exigir autenticación y devolver el archivo con su MIME sin exponer rutas del servidor.

**Trazabilidad**: US-020/CA-3, `04_modelo_de_datos.md` §Clínica (`:7`), R-04 (persistencia en PostgreSQL), R-08 (sin rutas ni ejecutables), RN-SE-02.

#### Scenario: Subida válida de una imagen
- **WHEN** un odontólogo sube por `POST /adjuntos` un PNG real de 200 KB con `historia_id` de un paciente propio
- **THEN** el sistema responde HTTP 201 con `nombre`, `mime`, `tamano`, `subido_por` y la referencia del adjunto
- **AND** los bytes almacenados en PostgreSQL coinciden exactamente con los enviados

#### Scenario: Descarga autenticada del adjunto
- **WHEN** un usuario con permiso de lectura hace `GET /adjuntos/{id}`
- **THEN** el sistema responde HTTP 200 con `Content-Type` igual al MIME original y un `Content-Disposition` con el nombre saneado
- **AND** el cuerpo descargado es byte a byte igual al archivo subido

#### Scenario: Adjunto sin historia
- **WHEN** se envía el multipart sin el campo `historia_id` o con un valor que no es UUID
- **THEN** el sistema responde HTTP 422 y no persiste el archivo

#### Scenario: Historia inexistente
- **WHEN** el `historia_id` enviado no existe o tiene baja lógica
- **THEN** el sistema responde HTTP 404 y no persiste el archivo

#### Scenario: MIME no permitido
- **WHEN** se sube un archivo declarado como `application/x-msdownload`, `text/html` o con extensión `.exe`
- **THEN** el sistema responde HTTP 422 y no persiste el adjunto

#### Scenario: Archivo mayor a 5 MB
- **WHEN** se sube un archivo cuyo contenido supera 5 MB
- **THEN** el sistema responde HTTP 422, no persiste el adjunto y el CHECK de tamaño de PostgreSQL también rechaza un `INSERT` directo

#### Scenario: Contenido que no coincide con el MIME declarado
- **WHEN** se declara `image/png` pero los primeros bytes corresponden a un PDF, un ZIP o un ejecutable
- **THEN** el sistema responde HTTP 422 porque la firma del archivo no coincide con el MIME

#### Scenario: Nombre con intento de path traversal
- **WHEN** se sube un archivo con nombre `..\..\etc\passwd` o `../../etc/passwd`
- **THEN** el sistema responde HTTP 201 con `nombre` saneado a `passwd`, y la descarga no incluye `..` ni separadores de ruta en `Content-Disposition`

#### Scenario: Descarga sin token o de un adjunto inexistente
- **WHEN** se hace `GET /adjuntos/{id}` sin encabezado Bearer válido, o con un identificador inexistente
- **THEN** el sistema responde HTTP 401 en el primer caso y HTTP 404 en el segundo, sin exponer el archivo

### Requirement: Consentimiento informado versionado

El sistema SHALL registrar consentimientos por paciente con tipo válido, `texto_version` existente en el catálogo del servidor, `texto_hash` y `firma_ref` calculados por el servidor como digest SHA-256 del texto canónico, el paciente y la fecha. El cliente no SHALL enviar el texto ni una firma gráfica. Un tipo o versión no soportada SHALL responder 422; un paciente inexistente o de baja, 404.

**Trazabilidad**: RN-CL-03 (`05_reglas_de_negocio.md:20`), `04_modelo_de_datos.md` §Consentimiento (`:89-90`), US-021/CA-3 (consumo por C-12), R-11.

#### Scenario: Registro de un consentimiento válido
- **WHEN** un odontólogo registra un consentimiento para un paciente propio con `tipo=procedimiento_invasivo` y `texto_version=v1-2026-11`
- **THEN** el sistema responde HTTP 201 con `texto_hash` y `firma_ref` con prefijo `sha256:`
- **AND** el `texto_hash` coincide con el SHA-256 del texto canónico de esa versión y no se almacena ninguna imagen de firma

#### Scenario: Tipo de consentimiento inválido
- **WHEN** se envía un `tipo` fuera del catálogo permitido
- **THEN** el sistema responde HTTP 422 y no registra el consentimiento

#### Scenario: Versión de texto desconocida
- **WHEN** se envía una `texto_version` que no existe en el catálogo del servidor
- **THEN** el sistema responde HTTP 422 y no registra el consentimiento

#### Scenario: Cliente intenta enviar el texto o la firma
- **WHEN** el cuerpo incluye `texto`, `texto_hash` o `firma_ref` además de los campos declarados
- **THEN** el sistema responde HTTP 422 por campo extra no permitido y no registra nada

#### Scenario: Paciente inexistente o dado de baja
- **WHEN** se registra un consentimiento para un paciente que no existe, es de otro consultorio o tiene baja lógica
- **THEN** el sistema responde HTTP 404 y no registra el consentimiento

#### Scenario: Dos consentimientos del mismo tipo y versión
- **WHEN** se registran dos consentimientos del mismo tipo y versión para el mismo paciente en fechas distintas
- **THEN** ambos quedan persistidos como actos independientes y el listado los devuelve del más reciente al más antiguo

### Requirement: Auditoría de toda escritura clínica

Toda escritura clínica (apertura de historia, alta, edición, firma y rectificación de evolución, versión de odontograma, subida de adjunto y alta de consentimiento) SHALL insertar en la misma transacción una fila de `RegistroAuditoria` con usuario, acción, entidad, identificador afectado, IP y dispositivo. Si la operación falla, no SHALL quedar auditoría; las filas SHALL ser inmutables por trigger.

**Trazabilidad**: RN-SE-02 (`05_reglas_de_negocio.md:45`), `security/core-models` §Auditoría append-only, `04_modelo_de_datos.md` §RegistroAuditoria (`:87`), R-11.

#### Scenario: Auditoría de la apertura de historia
- **WHEN** se abre una historia clínica desde `POST /historia-clinica`
- **THEN** queda una fila con `accion='historia_clinica.crear'`, `entidad='historia_clinica'`, el `entidad_id` de la historia, el usuario autenticado, la IP y el `User-Agent` truncado

#### Scenario: Auditoría de firma y de rectificatoria
- **WHEN** se firma una evolución y se crea una rectificatoria firmada
- **THEN** existen filas `evolucion.firmar` y `evolucion.rectificar` con el usuario y el identificador de la evolución nueva

#### Scenario: Auditoría de adjunto y consentimiento
- **WHEN** se sube un adjunto y se registra un consentimiento
- **THEN** existen filas `adjunto.crear` y `consentimiento.registrar` con el identificador del recurso creado

#### Scenario: Escritura rechazada no deja auditoría
- **WHEN** una escritura clínica falla por validación (por ejemplo, un `tipo` de consentimiento inválido o un adjunto de MIME no permitido)
- **THEN** la transacción se revierte y no queda fila de auditoría de esa escritura

#### Scenario: Auditoría clínica append-only
- **WHEN** se intenta `UPDATE` o `DELETE` sobre una fila de auditoría generada por una escritura clínica
- **THEN** PostgreSQL responde SQLSTATE `P0001` y la fila permanece intacta

### Requirement: Control de acceso a la ficha clínica

El sistema SHALL aplicar la matriz de `03_actores_y_roles.md`: administrador, recepcionista y auditor leen toda la ficha; odontólogo lee y escribe solo pacientes propios; asistente lee y actualiza solo pacientes con turno `en_sala`; nadie más escribe. «Propio» SHALL significar que existe un turno no cancelado del paciente con el profesional vinculado al usuario por `profesionales.usuario_id`. Sin token SHALL responder 401 y sin permiso, 403.

**Trazabilidad**: `03_actores_y_roles.md` §Matriz (Ficha clínica / Odontograma, `:20-27`), RN-SE-01, R-03, `agenda/turnos` §Acceso por rol (mismo criterio de «propio»).

#### Scenario: Administrador lee todo pero no escribe la ficha
- **WHEN** un administrador consulta la historia, evoluciones y odontograma de cualquier paciente, y luego intenta `POST` una evolución
- **THEN** las lecturas responden HTTP 200 y la escritura responde HTTP 403 porque su permiso es solo lectura

#### Scenario: Odontólogo opera solo pacientes propios
- **WHEN** un odontólogo vinculado a un profesional escribe una evolución de un paciente con turno de ese profesional y luego intenta lo mismo con un paciente de otro profesional
- **THEN** el paciente propio responde HTTP 201 y el ajeno HTTP 403, sin crear filas para el ajeno

#### Scenario: Turno cancelado no otorga propiedad
- **WHEN** el único turno entre el paciente y el profesional del odontólogo está `cancelado` o `ausente`
- **THEN** la escritura del odontólogo responde HTTP 403 porque el vínculo clínico no está vigente

#### Scenario: Odontólogo sin profesional vinculado
- **WHEN** un usuario con rol odontólogo pero sin fila en `profesionales` intenta leer o escribir una ficha
- **THEN** el sistema responde HTTP 403 y no expone datos clínicos

#### Scenario: Recepción y auditoría solo leen
- **WHEN** un recepcionista o un auditor consultan la ficha y luego intentan crear una evolución o un consentimiento
- **THEN** las lecturas responden HTTP 200 y las escrituras HTTP 403

#### Scenario: Asistente actualiza solo al paciente en sala
- **WHEN** un asistente edita el texto de una evolución en borrador de un paciente con turno `en_sala`, y luego intenta hacerlo con un paciente `confirmado` o crear/firmar una evolución
- **THEN** el paciente en sala responde HTTP 200; el otro paciente, la creación y la firma responden HTTP 403

#### Scenario: Petición sin token
- **WHEN** cualquier endpoint de la ficha clínica se invoca sin encabezado Bearer válido
- **THEN** el sistema responde HTTP 401 y no expone datos clínicos
