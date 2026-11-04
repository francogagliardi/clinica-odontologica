# Proposal

## Why

C-06/C-07 permiten reservar, pero nadie avisa ni permite gestionar el turno sin llamar. US-010 y el Flujo 2 exigen recordatorios 48/24 h por WhatsApp oficial, con enlace tokenizado para confirmar, cancelar o reprogramar, y que la respuesta actualice la agenda sin intervención manual. Sin esto, la clínica depende del teléfono y el paciente pierde el turno por olvido.

C-09 agrega la capa de comunicaciones asíncrona sobre PostgreSQL + Redis, respetando R-06 (Redis solo colas): el estado de cada mensaje vive en la base, no en la cola.

## What Changes

- Agrega modelos y migración `0008_whatsapp_recordatorios`:
  - `Recordatorio`: turno, ventana (48 h/24 h), `programado_para`, estado (`pendiente`, `encolado`, `enviado`, `fallido`, `cancelado`).
  - `MensajeWhatsApp`: recordatorio/turno, plantilla (`recordatorio`, `confirmacion`, `oferta_hueco`), `estado_envio`, `respuesta`, `proveedor_mensaje_id` único, intentos, último error y payload JSONB.
- Programa automáticamente los recordatorios de 48 h y 24 h al crear un turno (si el turno está a más de 48/24 h), persistiéndolos en PostgreSQL y encolando los vencidos en Redis `recordatorios:due`.
- Agrega workers ejecutables:
  - `recordatorios`: busca vencidos `pendiente`, crea el mensaje y lo encola en `whatsapp:send`.
  - `whatsapp`: consume `whatsapp:send`, llama al proveedor (capa de prueba en v1), persiste el resultado y reintenta con backoff exponencial hasta un máximo; nunca duplica el mensaje.
- Agrega un cliente de WhatsApp abstraído (`WHATSAPP_PROVIDER=test` por defecto, sin costo real en v1, R-12/DD-03) y plantillas mínimas con enlace tokenizado de un solo uso.
- Agrega webhook público `POST /webhooks/whatsapp`:
  - Verifica `X-Hub-Signature-256` con `WHATSAPP_APP_SECRET`.
  - Idempotente por `proveedor_mensaje_id`: un duplicado responde 200 sin reaplicar.
  - Confirmar → `confirmado`; cancelar → `cancelado` + punto de extensión para lista de espera (C-10); reprogramar → valida RN-TU-01 con el servicio de C-06; token vencido/fuera de plazo → `derivado`, sin tocar el turno.
- Agrega endpoints autenticados:
  - `GET /recordatorios` por rango/turno.
  - `GET /notificaciones` y `POST /notificaciones/{id}/reenviar` (administrador/recepción).
- Agrega tests: idempotencia del webhook, token vencido, caída del proveedor con reintento sin duplicar, programación 48/24, firma inválida y reprogramación válida.

## Capabilities

### New Capabilities
- `comunicaciones/recordatorios`: programación 48/24 h, mensajes persistidos y workers con reintento.
- `comunicaciones/whatsapp-webhook`: recepción idempotente de respuestas y actualización de la agenda.

### Modified Capabilities
- Ninguna: el alta de turno mantiene su contrato; la programación de recordatorios se especifica en la capability nueva.

## Impact

- **Backend**:
  - `app/models/comunicaciones.py`, `app/models/__init__.py`, migración `0008`.
  - `app/infrastructure/whatsapp.py` (cliente de prueba), `app/application/recordatorios.py` (programación y procesamiento).
  - `app/workers/recordatorios.py`, `app/workers/whatsapp.py`, `app/workers/__main__.py`.
  - `app/api/recordatorios.py`, `app/api/notificaciones.py`, `app/api/webhooks.py`, `app/schemas/comunicaciones.py`, `app/main.py`.
  - `app/application/turnos.py` (hook de programación al crear), `app/core/settings.py` (proveedor, secret, TTL, reintentos).
  - Tests unitarios e integración; actualización del head de migraciones.
- **Docker**: servicios worker opcionales en Compose (perfil `workers`) para no romper el arranque demo.
- **API Surface**: `/recordatorios`, `/notificaciones`, `/notificaciones/{id}/reenviar`, `/webhooks/whatsapp`.
- **Riesgos y mitigaciones**:
  - **Costo real de WhatsApp**: v1 usa proveedor de prueba y no llama a Meta (R-12); el adaptador real queda detrás de una interfaz.
  - **Plantillas no aprobadas**: el envío real queda bloqueado hasta aprobación; se documenta como riesgo de Discovery.
  - **Duplicados del webhook**: idempotencia por id de proveedor + transacción.
  - **Lista de espera**: C-09 solo deja el punto de extensión; C-10 implementa la oferta FIFO.
  - **Workers**: si no están corriendo, los recordatorios quedan `pendiente`/`encolado`; PostgreSQL conserva la verdad y `POST /notificaciones/{id}/reenviar` permite recuperarlos.
