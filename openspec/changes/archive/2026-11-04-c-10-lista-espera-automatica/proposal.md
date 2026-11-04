# Proposal

## Why

C-09 ya detecta la cancelación y deja un punto de extensión (`hueco_liberado`), pero el hueco liberado se pierde: nadie avisa al paciente que esperaba y la clínica sigue dependiendo del teléfono para reubicarlo. US-003 y RN-TU-05 exigen que todo hueco liberado se ofrezca automáticamente por orden FIFO, con vencimiento configurable, y que la aceptación cree el turno sin solapamiento.

C-10 cierra el circuito sobre lo ya construido: modelo de lista de espera en PostgreSQL, oferta por WhatsApp reutilizando `MensajeWhatsApp` y la cola `whatsapp:send`, token de un solo uso para aceptar/rechazar y conversión a turno mediante el servicio compartido de C-06. Redis sigue siendo solo cola (R-06): el estado de cada entrada y de cada oferta vive en PostgreSQL.

## What Changes

- Agrega el modelo y la migración `0009_lista_espera`:
  - `EntradaListaEspera`: paciente, prestación, profesional opcional, `orden` monótono (identidad), estado (`pendiente`, `ofrecido`, `convertido`, `vencido`), datos de la retención (`oferta_profesional_id`, `oferta_sillon_id`, `oferta_inicio`, `oferta_fin`, `oferta_expira_en`) y `turno_id` cuando se convierte.
  - Retención atómica del hueco: exclusion constraints de PostgreSQL sobre `(oferta_profesional_id, rango de oferta)` y `(oferta_sillon_id, rango de oferta)` para las filas `ofrecido`, de modo que dos ofertas concurrentes no puedan retener el mismo horario.
  - Ajusta `mensajes_whatsapp`: `turno_id` pasa a nullable, agrega `lista_espera_id` (FK opcional) y suma `aceptado`/`rechazado` a las respuestas válidas, porque una oferta todavía no tiene turno.
- Agrega un servicio único `registrar_hueco_liberado(turno)` que se invoca desde las tres cancelaciones existentes (`PATCH /turnos/{id}/estado`, `POST /reservar/gestion/{token}/cancelar` y el webhook de WhatsApp). Escribe `RegistroAuditoria(accion="hueco_liberado")`, retiene el intervalo liberado (profesional, sillón, inicio y fin originales) y dispara la oferta en la misma transacción.
- Agrega la oferta FIFO: busca la primera entrada `pendiente` compatible (misma prestación; si la entrada fija profesional, solo ese profesional; si no, se le asigna el profesional y el sillón liberados), la reclama atómicamente, arma un `MensajeWhatsApp` con plantilla `oferta_hueco`, emite un token de propósito `oferta_hueco` y encola en `whatsapp:send` (fallo de Redis no rompe la cancelación).
- Mientras la retención está vigente (`estado='ofrecido'` y `oferta_expira_en > now`) el horario NO aparece en la disponibilidad pública ni en la del backoffice, y toda alta o reprogramación que se solape responde 409 aunque no exista un turno activo. Un `POST /turnos` con `es_sobreturno=true` tampoco puede pisarla.
- Agrega el vencimiento: el scheduler existente de recordatorios procesa ofertas `ofrecido` con `oferta_expira_en <= now`, libera la retención, las pasa a `vencido` y ofrece el mismo hueco a la siguiente entrada. Si no queda nadie, la retención desaparece y el slot vuelve a disponibilidad pública. Las lecturas y el alta ignoran retenciones vencidas aunque el worker todavía no las haya barrido.
- Agrega la aceptación y el rechazo públicos con token (`GET /reservar/oferta/{token}`, `POST .../aceptar`, `POST .../rechazar`) y por respuesta de WhatsApp (`aceptar`/`rechazar`). La aceptación reclama la entrada, crea el turno con el servicio compartido de C-06 usando el profesional, el sillón y el horario retenidos, y libera la retención al convertir.
- Agrega endpoints autenticados `/lista-espera`: alta, baja de una entrada `pendiente`, listado FIFO y consulta de estado/oferta con RBAC de Agenda/Turnos.
- Agrega tests: FIFO, filtro de compatibilidad, retención y liberación, disponibilidad oculta, 409 en alta/reprogramación, vencimiento que rota al siguiente, conversión sin solapamiento, aceptaciones concurrentes y nadie acepta con el hueco de vuelta en disponibilidad.

## Capabilities

### New Capabilities
- `agenda/lista-espera`: modelo FIFO, disparo del hueco liberado, retención atómica del horario, ciclo de oferta/vencimiento/conversión, liberación y RBAC de la lista.
- `comunicaciones/ofertas-hueco`: entrega de la oferta por WhatsApp con plantilla `oferta_hueco`, token de un solo uso de propósito propio y aceptación/rechazo sin intervención manual.

### Modified Capabilities
- `agenda/turnos`: toda alta y reprogramación SHALL rechazar con 409 cualquier turno que se solape con una retención vigente de lista de espera, incluida la reserva pública y los sobreturnos marcados. La retención es un recurso más de exclusión junto al profesional y el sillón.
- `agenda/reserva-publica`: la disponibilidad pública SHALL excluir los slots retenidos por una oferta vigente de lista de espera, no solo los ocupados por turnos activos y bloqueos.
- `agenda/recursos-agendables`: la disponibilidad del backoffice (`GET /profesionales/{id}/disponibilidad`) SHALL excluir los mismos slots retenidos.
- `comunicaciones/recordatorios` y `comunicaciones/whatsapp-webhook`: sin cambios de requisitos; C-10 reutiliza plantilla, cola, token e idempotencia y solo agrega una rama aditiva para `oferta_hueco`. El ajuste de nulabilidad de `mensajes_whatsapp.turno_id` es de esquema, no de comportamiento observable de C-09.

## Impact

- **Backend**:
  - `app/models/lista_espera.py`, `app/models/comunicaciones.py`, `app/models/__init__.py`, migración `0009_lista_espera` (columnas de retención + exclusion constraints).
  - `app/application/lista_espera.py` (FIFO, hueco liberado, retención, vencimiento, conversión) y `app/application/ofertas_hueco.py` (mensaje, token, respuestas).
  - `app/application/turnos.py`: sumar la retención vigente a `validar_solapamiento` para que el alta y la reprogramación compartidas respondan 409.
  - `app/application/webhooks.py`, `app/api/turnos.py`, `app/api/publico.py`: llamar a `registrar_hueco_liberado` en las tres cancelaciones.
  - `app/api/profesionales.py` y `app/api/publico.py`: descontar retenciones vigentes del cálculo de disponibilidad (backoffice y pública).
  - `app/api/lista_espera.py`, `app/api/ofertas.py`, `app/schemas/lista_espera.py`, `app/schemas/ofertas.py`, `app/main.py`.
  - `app/workers/__main__.py`: procesar ofertas vencidas en el tick del scheduler de recordatorios.
  - `app/core/settings.py` y `.env.example`: `lista_espera_oferta_ttl_minutos` (default 30).
  - Tests unitarios e integración; head de migraciones pasa a `0009_lista_espera`.
- **API Surface**: `/lista-espera` (POST, GET, GET por id, DELETE), `/reservar/oferta/{token}` (GET, aceptar, rechazar); `GET /reservar/{slug}/disponibilidad`, `GET /profesionales/{id}/disponibilidad`, `POST /turnos`, `PATCH /turnos/{id}/reprogramar` y `POST /reservar/{slug}/turnos` cambian de resultado ante una retención vigente.
- **Docker**: sin servicios nuevos; el worker `recordatorios` existente también vence ofertas.
- **Frontend**: sin cambios en C-10 (el alcance es API). La página de oferta queda para el test de páginas final.
- **Riesgos y mitigaciones**:
  - **Retención que oculta disponibilidad**: si el paciente no responde, el slot queda oculto hasta el TTL; se mitiga con TTL corto (30 min) y rotación automática.
  - **Worker detenido**: las entradas no rotan solas. Las consultas y el alta ignoran retenciones con `oferta_expira_en <= now`, así que el slot vuelve a estar disponible aunque el barrido esté atrasado; la rotación sí espera al worker.
  - **Carrera retención vs. alta**: la retención se inserta en la misma transacción de la cancelación y el alta valida retenciones antes de insertar; una reserva que gane el borde puede impedir la conversión, que responde 409 y rota. La exclusion constraint protege retención contra retención.
  - **Duplicados por concurrencia**: claim con `FOR UPDATE SKIP LOCKED` + exclusion constraints de retención y de turnos + consumo atómico del token.
  - **WhatsApp real**: sigue en capa de prueba (`WHATSAPP_PROVIDER=test`), sin costo real (R-12).
