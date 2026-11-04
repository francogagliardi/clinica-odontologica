# Design

## Context

C-06/C-07 ya crean turnos, emiten tokens y permiten gestionar desde un enlace. C-09 agrega la capa asíncrona de recordatorios y el webhook de respuestas. R-06 exige que Redis sea solo cola y PostgreSQL la fuente de verdad; R-12 prohíbe costos reales de terceros en v1 (capa de prueba).

## Goals / Non-Goals

**Goals:**
- Programar recordatorios 48/24 h al crear turnos y cancelarlos si el turno se cierra.
- Workers idempotentes con reintento exponencial y estado en PostgreSQL.
- Webhook firmado e idempotente que confirma, cancela o reprograma.
- Endpoints de consulta y reenvío.
- Plantillas mínimas con enlace tokenizado.

**Non-Goals:**
- Envío real a Meta (queda detrás de `WHATSAPP_PROVIDER=test`).
- Lista de espera y oferta FIFO (C-10); solo el punto de extensión.
- Aprobación de plantillas de Meta (riesgo externo).
- Panel visual de notificaciones (C-15/C-16).
- Reprogramación conversacional completa (v1 acepta `nueva_fecha` en el payload).

## Decisions

### D1 — Modelos y migración `0008_whatsapp_recordatorios`

`recordatorios`:

| Columna | Regla |
|---|---|
| `id`, `turno_id` | UUID, FK a `turnos` |
| `ventana` | `48h`/`24h`, CHECK |
| `programado_para` | timestamptz |
| `estado` | `pendiente`, `encolado`, `enviado`, `fallido`, `cancelado` |
| `created_at`/`updated_at` | auditoría |

Índice único `(turno_id, ventana)` para idempotencia; índice `(estado, programado_para)` para el worker.

`mensajes_whatsapp`:

| Columna | Regla |
|---|---|
| `id`, `recordatorio_id` (nullable), `turno_id` | UUID |
| `plantilla` | `recordatorio`, `confirmacion`, `oferta_hueco` |
| `estado_envio` | `pendiente`, `enviado`, `fallido` |
| `respuesta` | `ninguna`, `confirmado`, `cancelado`, `reprogramado`, `derivado` |
| `proveedor_mensaje_id` | string único nullable (idempotencia del webhook) |
| `intentos`, `proximo_intento`, `ultimo_error`, `payload` JSONB | reintento |
| `created_at`/`updated_at` | auditoría |

Migración `down_revision = "0007_reserva_publica"`.

### D2 — Programación al crear el turno

`app/application/recordatorios.py::programar_recordatorios(uow, turno)`:

- Calcula `inicio - 48h` y `- 24h`.
- Crea solo las ventanas cuyo `programado_para > now`.
- Usa el índice único `(turno_id, ventana)` con `ON CONFLICT DO NOTHING` para que un reintento del alta no duplique.
- Se llama desde `crear_turno` después del `flush` del turno.

Al cancelar un turno (backoffice o link público), `cancelar_recordatorios(uow, turno_id)` pasa `pendiente`/`encolado` a `cancelado`; no borra historia.

### D3 — Worker de recordatorios y claim atómico

`app/workers/recordatorios.py::procesar_vencidos(uow, redis, now)`:

1. Selecciona recordatorios `pendiente` con `programado_para <= now` y turno aún activo.
2. Reclama cada uno con `UPDATE ... WHERE estado='pendiente' RETURNING` (atómico).
3. Crea `MensajeWhatsApp` con plantilla `recordatorio`, token de gestión y payload.
4. Encola el id del mensaje en `whatsapp:send`; si el encolado falla, deja el mensaje `pendiente` para el reintento y el recordatorio `fallido` (PostgreSQL conserva la verdad).
5. Marca el recordatorio `encolado`.

Dos workers concurrentes: solo uno gana el `UPDATE`; el otro no crea mensaje.

### D4 — Worker de WhatsApp y reintento

`app/workers/whatsapp.py::procesar_entrante(redis, cliente, uow, now)`:

1. `BRPOP whatsapp:send` (timeout corto).
2. Carga el mensaje; si no está `pendiente`, lo ignora (idempotencia).
3. Llama a `cliente.enviar(...)`; el proveedor de prueba solo registra y devuelve un id `test-<uuid>`.
4. Éxito: `estado_envio=enviado`, `proveedor_mensaje_id`, recordatorio `enviado`.
5. Fallo: `intentos += 1`; si `intentos >= WHATSAPP_MAX_INTENTOS` → `fallido` + `RegistroAuditoria(accion="whatsapp_fallo")`; si no, `proximo_intento = now + 2**intentos minutos` y se reencola cuando vence.

El loop del worker consulta también mensajes `pendiente` con `proximo_intento <= now` para no depender de una cola con delay (Redis list no soporta delay).

### D5 — Proveedor abstraído

`app/infrastructure/whatsapp.py`:

```python
class WhatsAppClient(Protocol):
    async def enviar(self, telefono: str, plantilla: str, variables: dict) -> str: ...

class TestWhatsAppClient:
    async def enviar(...) -> str: return f"test-{uuid4()}"
```

`WHATSAPP_PROVIDER` selecciona el cliente; en v1 solo existe `test`. El real se implementa cuando las plantillas estén aprobadas (DD-03/SU-03). No se lee ningún token de Meta.

### D6 — Plantillas y token

`plantillas.py` arma el texto con paciente, fecha/hora `UTC-3`, profesional y `gestion_url`. El token es `gestion_turno` de C-07 (misma página de gestión), con TTL de 7 días. Solo se persiste el hash; la URL se guarda en `payload` (sin token crudo en columnas indexadas).

### D7 — Webhook normalizado y firma

`POST /webhooks/whatsapp` recibe:

```json
{
  "mensajes": [
    {
      "id": "wamid.123",
      "telefono": "+54911...",
      "respuesta": "confirmar|cancelar|reprogramar",
      "nueva_fecha": "2026-11-10T09:00:00-03:00"
    }
  ]
}
```

La firma `X-Hub-Signature-256: sha256=<hex>` se valida con HMAC-SHA256 sobre el cuerpo crudo y `WHATSAPP_APP_SECRET`. En producción, un adaptador traduce el formato anidado de Meta a este formato normalizado antes de llamar al servicio.

### D8 — Idempotencia del webhook

`procesar_webhook(uow, mensajes)`:

- Por cada `id`, si ya existe un `MensajeWhatsApp.proveedor_mensaje_id`, responde `aplicado=false` y sigue.
- Si no existe, busca el mensaje por el id del proveedor (el mensaje emitido guarda su id al enviarse) o deriva si es desconocido.
- Procesa una sola acción por mensaje.

Como el `proveedor_mensaje_id` se conoce recién cuando el worker envía, el webhook busca el mensaje por ese id. Un evento de un mensaje desconocido se marca `derivado` y responde 200.

### D9 — Acciones y reprogramación

- Confirmar/cancelar usan `puede_transicionar` y el estado del turno.
- Cancelar dispara `al_cancelar_turno(turno)` → por ahora registra un log/evento en `RegistroAuditoria` con `accion="hueco_liberado"`; C-10 lo consumirá.
- Reprogramar reutiliza la lógica de C-06: se extrae `reprogramar_turno` a `app/application/turnos.py` y la usan el router, C-07 y el webhook.
- Turno pasado, token vencido o acción inválida → `respuesta=derivado`, sin cambio.

### D10 — Endpoints y RBAC

- `GET /recordatorios?desde&hasta&turno_id`: administrador, odontólogo, recepcionista, asistente, auditor.
- `GET /notificaciones?desde&hasta&estado`: los mismos roles.
- `POST /notificaciones/{id}/reenviar`: administrador y recepcionista; crea un nuevo `MensajeWhatsApp` `pendiente` clonando plantilla/payload y encola; el original no se modifica.
- Webhook: público con firma.

### D11 — Workers y Compose

Se agregan `app/workers/recordatorios.py`, `app/workers/whatsapp.py` y un `__main__.py` con modo `recordatorios|whatsapp`. En Compose quedan bajo el perfil `workers` para no romper el arranque demo:

```bash
docker compose --profile workers up -d
```

Sin workers, los recordatorios quedan `pendiente` y el reenvío manual sigue disponible.

### D12 — Configuración

Nuevas variables:

- `WHATSAPP_PROVIDER=test`
- `WHATSAPP_APP_SECRET` (obligatoria, sin default)
- `WHATSAPP_MAX_INTENTOS=5`
- `WHATSAPP_WORKER_INTERVAL_SECONDS=60`
- `WHATSAPP_RECORDATORIO_VENTANAS=48,24` (opcional; default 48,24)

Se documentan en `.env.example`.

## Risks / Trade-offs

- **Sin proveedor real**: el flujo completo se prueba con `test`; el adaptador real requiere plantillas aprobadas.
- **Webhook normalizado**: Meta manda un payload anidado; el adaptador real queda documentado y aislado.
- **Reprogramación por texto**: v1 acepta `nueva_fecha` estructurada; el parser conversacional libre queda para una iteración posterior.
- **Lista de espera**: solo se emite el evento; C-10 lo consume.
- **Reloj**: los tests inyectan `now` para no depender del tiempo real.
