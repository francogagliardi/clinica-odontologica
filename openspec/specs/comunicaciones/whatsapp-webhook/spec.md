# comunicaciones/whatsapp-webhook Specification

## Purpose
Recibe las respuestas del paciente por WhatsApp (confirmar, cancelar, reprogramar) de forma autenticada e idempotente, y actualiza la agenda sin intervención manual (RN-NO-02), derivando a recepción cuando el token venció o la acción no es válida.

## Requirements

### Requirement: Webhook autenticado con firma

`POST /webhooks/whatsapp` SHALL ser público pero exigir la firma `X-Hub-Signature-256` calculada con `WHATSAPP_APP_SECRET` sobre el cuerpo crudo. Una firma ausente o inválida SHALL responder 401 sin procesar el mensaje.

**Trazabilidad**: RN-NO-02 (`05_reglas_de_negocio.md:39`), RN-NO-03, R-08, `11_integraciones_argentinas.md` (webhooks idempotentes con ack).

#### Scenario: Firma válida
- **WHEN** el webhook recibe un cuerpo y la firma HMAC correcta
- **THEN** responde HTTP 200 y procesa el mensaje

#### Scenario: Firma inválida o ausente
- **WHEN** la firma no coincide o falta
- **THEN** responde HTTP 401 y no modifica ningún turno ni mensaje

#### Scenario: Cuerpo inválido con firma válida
- **WHEN** el JSON no tiene la forma esperada
- **THEN** responde HTTP 422 sin aplicar cambios

### Requirement: Idempotencia por id de proveedor

El webhook SHALL registrar cada `proveedor_mensaje_id` una sola vez. Un evento duplicado SHALL responder 200 con `aplicado=false` y no SHALL volver a cambiar el turno.

**Trazabilidad**: RN-NO-02, R-12 (webhooks idempotentes), `MensajeWhatsApp`.

#### Scenario: Primer evento
- **WHEN** llega un id de proveedor desconocido con una acción válida
- **THEN** se aplica la acción y se registra `aplicado=true`

#### Scenario: Evento duplicado
- **WHEN** el mismo id de proveedor llega dos veces
- **THEN** la segunda responde HTTP 200 con `aplicado=false` y el turno no cambia otra vez

#### Scenario: Id desconocido sin mensaje asociado
- **WHEN** el id no corresponde a ningún mensaje emitido
- **THEN** responde HTTP 200 con `aplicado=false` y `derivado=true` (Meta no debe reintentar)

### Requirement: Confirmar o cancelar desde WhatsApp

Con un mensaje válido, «confirmar» SHALL pasar el turno `reservado` a `confirmado`; «cancelar» SHALL pasarlo a `cancelado` cuando la transición sea válida y disparar el punto de extensión de lista de espera (C-10). La respuesta del mensaje SHALL persistirse.

**Trazabilidad**: RN-NO-02, Flujo 2 pasos 2–3, RN-TU-05 (punto de extensión), `agenda/turnos` (máquina de estados).

#### Scenario: Confirmación
- **WHEN** el paciente responde «confirmar» a un recordatorio de un turno `reservado`
- **THEN** el turno pasa a `confirmado` y el mensaje registra `respuesta=confirmado`

#### Scenario: Cancelación
- **WHEN** el paciente responde «cancelar» a un turno `reservado` o `confirmado`
- **THEN** el turno pasa a `cancelado`, el mensaje registra `respuesta=cancelado` y se emite el evento de hueco liberado para C-10

#### Scenario: Acción inválida por estado
- **WHEN** el turno ya está `cancelado` o `atendido`
- **THEN** responde HTTP 200 con `aplicado=false`, `derivado=true` y no cambia el estado

#### Scenario: Confirmación duplicada en el mismo cuerpo
- **WHEN** el mismo mensaje trae dos acciones
- **THEN** se aplica solo la primera y el resto se ignora

### Requirement: Reprogramación desde WhatsApp

Si la respuesta incluye una nueva fecha/hora, el sistema SHALL reprogramar el turno aplicando las mismas validaciones de C-06 (agenda, bloqueos y anti-solapamiento). Una colisión SHALL derivar a recepción sin mover el turno.

**Trazabilidad**: RN-NO-02, RN-TU-01/02/07, Flujo 2 paso 2, `agenda/turnos` §Reprogramación.

#### Scenario: Reprogramación válida
- **WHEN** el paciente envía «reprogramar» con una nueva fecha libre dentro de la agenda
- **THEN** el turno se mueve, `fin` se recalcula y el mensaje registra `respuesta=reprogramado`

#### Scenario: Reprogramación con colisión
- **WHEN** la nueva fecha se solapa con otro turno o bloqueo
- **THEN** responde HTTP 200 con `aplicado=false`, `derivado=true` y el turno conserva su horario

#### Scenario: Reprogramación sin fecha
- **WHEN** la acción es «reprogramar» pero no trae `nueva_fecha`
- **THEN** se deriva a recepción sin modificar el turno

### Requirement: Derivación por token vencido o fuera de plazo

Si el enlace o el turno ya no admiten gestión (token vencido, turno pasado, cancelación fuera del plazo configurado), el webhook SHALL marcar `respuesta=derivado` y responder 200 sin aplicar cambios, para que Meta no reintente indefinidamente.

**Trazabilidad**: RN-NO-02/RN-NO-03, RN-TU-03 (`05_reglas_de_negocio.md:9`), Flujo 2 casos de error.

#### Scenario: Turno ya pasado
- **WHEN** llega una acción sobre un turno con `inicio` anterior al momento actual
- **THEN** responde HTTP 200 con `derivado=true` y no cambia el turno

#### Scenario: Token vencido
- **WHEN** el mensaje referencia un token de gestión vencido
- **THEN** responde HTTP 200 con `derivado=true` y no revela datos del turno

#### Scenario: Cancelación fuera del plazo
- **WHEN** la cancelación llega fuera del `plazo_cancelacion_horas` del consultorio
- **THEN** se deriva a recepción o se aplica la política de pérdida de C-07, sin doble efecto
