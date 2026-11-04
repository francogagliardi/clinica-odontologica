# comunicaciones/ofertas-hueco Specification

## Purpose
Entrega la oferta de un hueco liberado por WhatsApp con un token de un solo uso de propósito propio y procesa la aceptación o el rechazo del paciente desde el enlace o desde el mensaje, sin intervención manual y sin duplicar turnos.

## Requirements

### Requirement: Mensaje de oferta con la plantilla existente

El sistema SHALL persistir un `MensajeWhatsApp` con plantilla `oferta_hueco`, ligado a la entrada de lista de espera y sin turno asociado, con las variables de paciente, fecha/hora en `UTC-3`, profesional y enlace de oferta. SHALL encolarlo en `whatsapp:send`; un fallo de Redis NO SHALL romper la cancelación que originó la oferta.

**Trazabilidad**: RN-NO-01/RN-NO-02 (`05_reglas_de_negocio.md:38–39`), `06_funcionalidades.md:28` US-003/CA-2, `04_modelo_de_datos.md:81–83` §MensajeWhatsApp, R-06/R-12.

#### Scenario: Oferta encolada
- **WHEN** se libera un hueco con una entrada compatible
- **THEN** existe un mensaje `oferta_hueco` en estado `pendiente` con `lista_espera_id` y su id aparece en la cola `whatsapp:send`

#### Scenario: Redis caído al ofrecer
- **WHEN** la cola no acepta el trabajo durante la cancelación
- **THEN** la cancelación responde HTTP 200, el mensaje queda `pendiente` con `proximo_intento` y la entrada sigue `ofrecido`

#### Scenario: Mensaje sin turno asociado
- **WHEN** se persiste el mensaje de oferta antes de que exista un turno
- **THEN** la fila se guarda con `turno_id` nulo y el envío de prueba la procesa igual que un recordatorio

#### Scenario: Reintento no duplica
- **WHEN** el worker de WhatsApp reprocesa el mismo mensaje de oferta
- **THEN** no envía de nuevo ni crea otro mensaje

### Requirement: Token de oferta de propósito propio

La oferta SHALL emitir un token opaco de un solo uso de tipo `oferta_hueco` asociado a la entrada, con vencimiento no mayor al de la oferta y guardando solo su hash. Un token usado, vencido, de otro propósito o cuya entrada ya no esté `ofrecido` SHALL responder 410.

**Trazabilidad**: RN-NO-03 (`05_reglas_de_negocio.md:40`), `03_actores_y_roles.md:31–36` §Rutas públicas, `security/single-use-token`, US-003/CA-2.

#### Scenario: Emisión del token
- **WHEN** se crea la oferta
- **THEN** las variables del mensaje incluyen el enlace de oferta y la base guarda solo el hash con tipo `oferta_hueco`

#### Scenario: Token reutilizado
- **WHEN** se intenta aceptar o rechazar con un token ya consumido
- **THEN** responde HTTP 410 y ninguna entrada cambia de estado

#### Scenario: Token vencido
- **WHEN** el token superó su vencimiento
- **THEN** responde HTTP 410 sin revelar datos del hueco ni del paciente

#### Scenario: Token de otro propósito
- **WHEN** se usa un token `gestion_turno` en la ruta de oferta, o uno `oferta_hueco` en la gestión de turno
- **THEN** responde HTTP 410 en ambos casos

#### Scenario: Entrada que ya no está ofrecida
- **WHEN** el token sigue vigente pero la entrada fue convertida o vencida
- **THEN** responde HTTP 410 y no se crea ni modifica ningún turno

### Requirement: Consulta pública de la oferta

`GET /reservar/oferta/{token}` SHALL mostrar sin consumir el token la prestación, el profesional, la fecha/hora en `UTC-3` y el vencimiento de la oferta. NO SHALL exponer teléfono, DNI ni otros datos sensibles del paciente.

**Trazabilidad**: RN-NO-03, `03_actores_y_roles.md` §Rutas públicas, US-003, R-03 (RBAC en el borde).

#### Scenario: Consulta de una oferta vigente
- **WHEN** el paciente abre el enlace de una oferta vigente
- **THEN** responde HTTP 200 con prestación, profesional, inicio y `vence_en`

#### Scenario: Consultar dos veces no consume
- **WHEN** se consulta el mismo enlace dos veces antes de aceptar o rechazar
- **THEN** ambas respuestas son HTTP 200 con el mismo contenido

#### Scenario: Oferta vencida
- **WHEN** la oferta superó `oferta_expira_en`
- **THEN** responde HTTP 410

#### Scenario: Respuesta sin datos sensibles
- **WHEN** se inspecciona el cuerpo de la consulta
- **THEN** no incluye teléfono, DNI, email ni identificadores internos del paciente

### Requirement: Aceptación de la oferta por enlace

`POST /reservar/oferta/{token}/aceptar` SHALL consumir el token atómicamente, reclamar la entrada y convertirla en turno según `agenda/lista-espera`, usando el profesional, sillón y horario retenidos. Si la retención venció y el horario ya fue tomado SHALL responder 409 marcando la entrada `vencido` y rotando al siguiente, sin crear turno ni perder el consumo del token.

**Trazabilidad**: RN-TU-01/RN-TU-05, RN-NO-02/RN-NO-03, Flujo 5 paso 2, `agenda/turnos` §Anti-solapamiento, `agenda/lista-espera` §Retención atómica.

#### Scenario: Aceptación exitosa
- **WHEN** el paciente acepta una oferta vigente con el hueco retenido
- **THEN** responde HTTP 200 con el turno creado en el sillón retenido y el token queda usado

#### Scenario: Retención vencida y hueco tomado
- **WHEN** la retención venció, otra reserva ocupó el horario y después llega la aceptación
- **THEN** responde HTTP 409, la entrada queda `vencido`, no hay turno nuevo y se ofrece al siguiente

#### Scenario: Aceptaciones concurrentes del mismo enlace
- **WHEN** dos aceptaciones simultáneas usan el mismo token
- **THEN** exactamente una responde HTTP 200 y la otra HTTP 410, con un solo turno

#### Scenario: Aceptar una oferta ya vencida
- **WHEN** se acepta después de `oferta_expira_en`
- **THEN** responde HTTP 410 y no se crea turno

### Requirement: Rechazo de la oferta por enlace

`POST /reservar/oferta/{token}/rechazar` SHALL consumir el token, liberar la retención, marcar la entrada `vencido` y ofrecer el mismo hueco a la siguiente entrada compatible, que SHALL retenerlo de nuevo. Sin siguiente entrada, NO SHALL quedar retención y el hueco SHALL volver a la disponibilidad pública.

**Trazabilidad**: US-003/CA-2, Flujo 5 paso 2 y casos de error, RN-TU-05.

#### Scenario: Rechazo con siguiente entrada
- **WHEN** el paciente rechaza una oferta vigente y existe otra entrada compatible
- **THEN** responde HTTP 200, su entrada queda `vencido` y la siguiente pasa a `ofrecido`

#### Scenario: Rechazo sin siguiente entrada
- **WHEN** rechaza la última entrada compatible
- **THEN** responde HTTP 200, no se crea nueva oferta, la retención se libera y el hueco vuelve a la disponibilidad pública

#### Scenario: Rechazo repetido
- **WHEN** se repite el rechazo con el token ya consumido
- **THEN** responde HTTP 410 y no se rota dos veces la lista

#### Scenario: Rechazo de una oferta ya convertida
- **WHEN** la entrada ya fue convertida en turno antes del rechazo
- **THEN** responde HTTP 410 y el turno existente no se modifica

### Requirement: Aceptación o rechazo por respuesta de WhatsApp

El webhook SHALL reconocer «aceptar» y «rechazar» sobre un mensaje `oferta_hueco` y aplicar la misma conversión o rotación que el enlace, de forma idempotente por `proveedor_mensaje_id`. Una acción no reconocida sobre una oferta SHALL responder 200 con `aplicado=false` y `derivado=true`.

**Trazabilidad**: RN-NO-02 (`05_reglas_de_negocio.md:39`), `comunicaciones/whatsapp-webhook` §Idempotencia por id de proveedor, US-003/CA-1, R-12.

#### Scenario: Aceptar desde WhatsApp
- **WHEN** llega «aceptar» para un mensaje de oferta vigente con el hueco libre
- **THEN** se crea el turno, el mensaje registra `respuesta=aceptado` y responde `aplicado=true`

#### Scenario: Rechazar desde WhatsApp
- **WHEN** llega «rechazar» para un mensaje de oferta vigente
- **THEN** la entrada queda `vencido`, el mensaje registra `respuesta=rechazado` y se ofrece al siguiente

#### Scenario: Evento duplicado del proveedor
- **WHEN** el mismo `proveedor_mensaje_id` llega dos veces
- **THEN** la segunda responde HTTP 200 con `aplicado=false` y no crea un segundo turno

#### Scenario: Acción no aplicable a una oferta
- **WHEN** llega «confirmar» o «reprogramar» sobre un mensaje `oferta_hueco`
- **THEN** responde HTTP 200 con `aplicado=false` y `derivado=true`, sin cambiar la entrada ni el turno
