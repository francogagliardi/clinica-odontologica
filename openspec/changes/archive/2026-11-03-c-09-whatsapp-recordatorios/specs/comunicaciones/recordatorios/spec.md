# Spec Delta

## Purpose

Programa y envía recordatorios 48/24 h por WhatsApp con estado persistido en PostgreSQL, colas Redis y reintentos, para que el paciente gestione su turno sin llamar y la clínica no dependa del teléfono.

## ADDED Requirements

### Requirement: Programación automática de recordatorios al crear un turno

Al crear un turno activo, el sistema SHALL programar recordatorios a 48 h y 24 h antes del inicio cuando el turno esté a más de esas ventanas. Cada recordatorio SHALL persistirse en PostgreSQL con estado `pendiente`, ventana (`48h`/`24h`) y `programado_para`, y SHALL ser idempotente ante reintentos del alta.

**Trazabilidad**: RN-NO-01 (`05_reglas_de_negocio.md:38`), US-010/CA-1, Flujo 2 paso 1, `04_modelo_de_datos.md` §Recordatorio.

#### Scenario: Turno con más de 48 horas
- **WHEN** se crea un turno que empieza en 72 horas
- **THEN** se crean dos recordatorios `pendiente`, uno a 48 h y otro a 24 h del inicio

#### Scenario: Turno entre 24 y 48 horas
- **WHEN** el turno empieza en 30 horas
- **THEN** se crea solo el recordatorio de 24 h; el de 48 h no se crea ni queda vencido

#### Scenario: Turno con menos de 24 horas
- **WHEN** el turno empieza en 10 horas
- **THEN** no se crea ningún recordatorio automático

#### Scenario: Reintento del alta no duplica
- **WHEN** la creación del turno se reintenta para el mismo turno
- **THEN** no se duplican recordatorios para la misma ventana

#### Scenario: Turno cancelado
- **WHEN** el turno pasa a `cancelado` o `ausente`
- **THEN** sus recordatorios `pendiente`/`encolado` pasan a `cancelado` y no se envían

### Requirement: Worker de recordatorios vencidos

El worker de recordatorios SHALL tomar los recordatorios `pendiente` con `programado_para <= now`, crear un `MensajeWhatsApp` con plantilla `recordatorio`, token de gestión de un solo uso y encolarlo en `whatsapp:send`, marcando el recordatorio como `encolado` de forma atómica. Dos ejecuciones concurrentes no SHALL encolar dos veces el mismo recordatorio.

**Trazabilidad**: RN-NO-01/RN-NO-03, R-06 (Redis solo colas), `platform/job-queues`.

#### Scenario: Recordatorio vencido se encola
- **WHEN** el worker corre y existe un recordatorio con `programado_para` en el pasado
- **THEN** crea un mensaje `pendiente`, lo encola en `whatsapp:send` y marca el recordatorio `encolado`

#### Scenario: Recordatorio futuro no se toca
- **WHEN** `programado_para` es futuro
- **THEN** el recordatorio sigue `pendiente` y no se encola

#### Scenario: Dos workers concurrentes
- **WHEN** dos workers procesan el mismo recordatorio a la vez
- **THEN** solo uno lo encola y el otro no genera mensaje duplicado

#### Scenario: Turno cancelado entre programación y envío
- **WHEN** el turno se canceló antes de que el worker procese el recordatorio
- **THEN** el recordatorio pasa a `cancelado` y no se envía

### Requirement: Envío con proveedor abstraído y reintento exponencial

El worker de WhatsApp SHALL consumir `whatsapp:send`, enviar mediante el proveedor configurado (`test` en v1, sin costo real) y persistir `MensajeWhatsApp.estado_envio`. Un fallo SHALL incrementar intentos, guardar el error y reprogramar el reintento con backoff exponencial; al superar el máximo SHALL quedar `fallido` y registrar una alerta de auditoría. Un mensaje enviado no SHALL reenviarse.

**Trazabilidad**: RN-NO-01, R-06, R-08, R-12 (`AGENTS.md`), DD-03/SU-03, `11_integraciones_argentinas.md`.

#### Scenario: Envío exitoso
- **WHEN** el proveedor acepta el mensaje
- **THEN** `estado_envio` pasa a `enviado` y el recordatorio a `enviado`

#### Scenario: Fallo transitorio
- **WHEN** el proveedor lanza un error en el primer intento
- **THEN** el mensaje queda `pendiente` con `intentos=1`, `ultimo_error` y un `proximo_intento` futuro

#### Scenario: Se agota el máximo de intentos
- **WHEN** se supera `WHATSAPP_MAX_INTENTOS`
- **THEN** el mensaje queda `fallido` y se registra una alerta en auditoría

#### Scenario: Reintento no duplica
- **WHEN** el worker vuelve a procesar un mensaje ya `enviado`
- **THEN** no llama al proveedor ni crea otro mensaje

### Requirement: Consulta y reenvío de notificaciones

El sistema SHALL exponer `GET /recordatorios` y `GET /notificaciones` para roles de agenda, y `POST /notificaciones/{id}/reenviar` solo para administrador y recepción. El reenvío SHALL crear un nuevo intento sin borrar el historial del mensaje original.

**Trazabilidad**: RN-SE-01, `03_actores_y_roles.md` §Matriz, R-02/R-03.

#### Scenario: Consulta por rango
- **WHEN** un recepcionista consulta recordatorios de un rango
- **THEN** recibe los recordatorios del rango con turno, ventana y estado

#### Scenario: Reenvío manual
- **WHEN** un administrador reenvía un mensaje `fallido`
- **THEN** se crea un nuevo intento `pendiente`, se encola y el original conserva su historial

#### Scenario: Rol sin permiso de reenvío
- **WHEN** un odontólogo, asistente o auditor intenta reenviar
- **THEN** responde HTTP 403

#### Scenario: Mensaje inexistente
- **WHEN** se reenvía un id que no existe
- **THEN** responde HTTP 404

### Requirement: Plantillas mínimas con enlace tokenizado

Cada mensaje SHALL generarse desde una plantilla (`recordatorio`, `confirmacion`, `oferta_hueco`) con variables de paciente, fecha/hora, profesional y un enlace de gestión con token de un solo uso (RN-NO-03). El enlace SHALL apuntar a la página pública de gestión de C-07.

**Trazabilidad**: US-010/CA-1, RN-NO-03, `11_integraciones_argentinas.md` (plantillas mínimas).

#### Scenario: Plantilla de recordatorio
- **WHEN** se prepara un mensaje de recordatorio
- **THEN** incluye nombre del paciente, fecha/hora en `UTC-3`, matrícula y `gestion_url` con token

#### Scenario: Token no almacenado en claro
- **WHEN** se persiste el mensaje
- **THEN** la base guarda solo el hash del token, nunca el valor crudo

#### Scenario: Proveedor real deshabilitado en v1
- **WHEN** `WHATSAPP_PROVIDER=test`
- **THEN** no se realiza ninguna llamada a Meta y el envío se simula
