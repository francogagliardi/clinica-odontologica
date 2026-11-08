# Validación manual pendiente (prueba final de la página)

> Decisión del usuario 2026-11-03: no se prueban los changes uno por uno; la aceptación funcional se hace al final, sobre la página completa.
> Este archivo acumula qué probar y con qué resultado esperado. Cada cierre de change agrega su bloque.

Estado: C-05 y C-06 cerrados con verificación automática; falta la prueba manual acumulada.

## C-05 — Pacientes y obras sociales

API: `http://127.0.0.1:8000/docs` (usuario `admin@clinica.test`; contraseña en `backend/.env`).

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Pacientes precargados | `GET /pacientes?apellido=Demo` | 3 pacientes ficticios |
| 2 | Alta de paciente | `POST /pacientes` con DNI `44.555.666`, teléfono `11 6666-7777` | 201; DNI `44555666`; teléfono `+5491166667777` |
| 3 | Búsqueda formateada | `GET /pacientes?dni=44.555.666` | 200 con ese paciente |
| 4 | DNI repetido | Repetir el alta | 409 |
| 5 | Teléfono ausente/inválido | Alta sin teléfono o con `123` | 422 |
| 6 | Búsqueda sin criterio | `GET /pacientes` | 422 |
| 7 | Obra social demo | `GET /obras-sociales` | “OS Demo” con reglas 60/40 sobre CONS, LIM, OBT |
| 8 | Alta de convenio | `POST /obras-sociales` con códigos en minúscula | 201 y códigos en mayúsculas |
| 9 | Código inexistente | Convenio con `NOEXISTE` | 422 |
| 10 | Validación externa | `validacion_externa=true` | 422 |
| 11 | Sin token | Cualquier endpoint sin Authorize | 401 |
| 12 | Baja de paciente | `DELETE /pacientes/{id}` admin, luego `GET` | 204 y luego 404 |

## C-06 — Turnos y agenda

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Alta con prestación | `POST /turnos` con ENDO (90 min), lunes 2026-11-09 09:00-03:00 | 201, estado `reservado`, fin 10:30 |
| 2 | Alta sin prestación | Mismo alta sin `prestacion_id` | 201, fin 10:00 (base 60) |
| 3 | Solape de profesional | Segundo turno 09:30 con otro sillón | 409 |
| 4 | Solape de sillón | Turno 09:30 de otro profesional en el mismo sillón | 409 |
| 5 | Consecutivos | Turno 10:00 | 201 |
| 6 | Fuera de agenda | Turno sábado o 11:30 | 422 |
| 7 | Sobreturno | `es_sobreturno=true` + `color_sobreturno=#F97316` sobre 09:30 | 201, marca y color visibles |
| 8 | Sobreturno sin color | Igual sin color | 422 |
| 9 | Turno normal sobre sobreturno | Turno normal 09:30 | 409 |
| 10 | Bloqueo | Crear bloqueo 09:30–10:30 del profesional, luego turno 09:30 | 409 |
| 11 | Transiciones | `PATCH /turnos/{id}/estado` confirmado → en_sala → atendido | 200 en cada paso |
| 12 | Transición inválida | reservado → atendido, o cancelado → confirmado | 422 |
| 13 | Cancelación | Cancelar un turno y consultar disponibilidad | 200; el slot vuelve |
| 14 | Reprogramación libre | Mover 09:00 a 11:00 | 200, fin recalculado 12:00 |
| 15 | Reprogramación ocupada | Mover a un horario ya tomado | 409, turno original intacto |
| 16 | Reprogramar cancelado | `PATCH /reprogramar` sobre cancelado | 422 |
| 17 | Disponibilidad real | `GET /profesionales/{id}/disponibilidad?fecha=2026-11-09` | slots libres sin los turnos activos |
| 18 | Día completo | Cargar 09, 10 y 11 | `[]` |
| 19 | RBAC odontólogo | Login de odontólogo: `GET /turnos` 200, `POST` 403, estado de turno ajeno 403 | según matriz |
| 20 | RBAC asistente/auditor | `GET /turnos` 200; crear/reprogramar/cambiar estado 403 | solo lectura |
| 21 | Sin token | Cualquier endpoint de turnos | 401 |

## C-07 — Reserva pública (pendiente de cierre)

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Catálogo público | Abrir `/reservar` en el navegador | Profesionales y prestaciones visibles, sin login |
| 2 | Disponibilidad | Elegir profesional, prestación y fecha | Slots reales sin turnos activos ni bloqueos |
| 3 | Reserva | Completar nombre, apellido, DNI y teléfono, elegir slot | 201; muestra enlace de gestión y estado de seña |
| 4 | Seña | Reservar ENDO | Seña pendiente con monto y política visibles |
| 5 | DNI repetido con otro teléfono | Reservar con un DNI existente y teléfono distinto | 409 visible, sin turno nuevo |
| 6 | Solape | Dos pestañas al mismo slot | Una reserva OK, la otra 409 |
| 7 | Gestión | Abrir el enlace del turno | Resumen con confirmar/cancelar |
| 8 | Token usado | Cancelar y recargar el enlace | 410 |
| 9 | Cancelación fuera de plazo | Forzar un turno cercano y cancelar | Aviso de pérdida de seña |
| 10 | WhatsApp | Ver logs/Redis `whatsapp:send` | Encolada o `pendiente_reintento` si Redis falla |

## C-08 — Agenda backoffice

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Login | Abrir `/agenda` con admin | Pide login; al ingresar muestra la agenda |
| 2 | Token en memoria | Refrescar `/agenda` | Vuelve a pedir login (no hay token persistido) |
| 3 | Vistas | Cambiar Día/Semana/Mes | Grillas distintas y datos del rango correcto |
| 4 | Filtros | Elegir profesional y sillón | Solo turnos de ese recurso |
| 5 | Colores | Ver turnos en estados distintos | Color/etiqueta por estado |
| 6 | Bloqueo | Crear bloqueo y ver la agenda | Franja con el motivo |
| 7 | Sobreturno | Crear sobreturno desde Swagger | Badge y color diferenciados |
| 8 | Drag válido | Arrastrar un turno a un horario libre | PATCH 200 y la grilla se actualiza |
| 9 | Drag inválido | Arrastrar sobre un turno/bloqueo | 409 visible y el turno no se mueve |
| 10 | Rol odontólogo | Login de odontólogo | Solo puede arrastrar sus turnos |
| 11 | Asistente/auditor | Login de esos roles | Agenda visible sin acciones |

## C-09 — Recordatorios y webhook WhatsApp

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Programación | Crear un turno a más de 48 h | Se crean recordatorios 48 h y 24 h (`GET /recordatorios?turno_id=...`) |
| 2 | Worker de recordatorios | `python -m app.workers recordatorios` con un recordatorio vencido | Encola un mensaje y el recordatorio pasa a `encolado` |
| 3 | Worker de WhatsApp | `python -m app.workers whatsapp` | El mensaje pasa a `enviado` (proveedor test) |
| 4 | Webhook válido | Firmar el body con `WHATSAPP_APP_SECRET` y responder `confirmar` | 200, turno `confirmado` |
| 5 | Webhook duplicado | Reenviar el mismo body | 200 `aplicado=false`, sin doble cambio |
| 6 | Firma inválida | Enviar sin firma | 401 |
| 7 | Cancelación | Webhook `cancelar` | 200, turno `cancelado` y evento `hueco_liberado` en auditoría |
| 8 | Reprogramación | Webhook con `nueva_fecha` libre | 200, turno movido |
| 9 | Colisión | `nueva_fecha` ocupada | 200 `derivado=true`, turno intacto |
| 10 | Reenvío manual | `POST /notificaciones/{id}/reenviar` como admin | 201, nuevo mensaje `pendiente` |
| 11 | Proveedor caído | Simular fallo del worker | Reintento con backoff; al máximo, `fallido` + auditoría |

## C-10 — Lista de espera automática

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Alta en la lista | `POST /lista-espera` (recepción) con paciente + prestación | 201, estado `pendiente`, `orden` creciente |
| 2 | Duplicado | Repetir la misma alta | 409, no se crea otra fila |
| 3 | Listado y baja | `GET /lista-espera` y `DELETE /lista-espera/{id}` de una pendiente | 200 en orden FIFO; la baja responde 200 y desaparece |
| 4 | Slot retenido | Con una entrada pendiente, cancelar un turno compatible | La entrada pasa a `ofrecido`; el horario desaparece de la disponibilidad pública y del backoffice |
| 5 | Bloqueo de altas | `POST /turnos` y `PATCH /reprogramar` sobre el horario retenido (también con sobreturno) | 409 en todos los casos |
| 6 | Mensaje y enlace | Correr el worker de recordatorios una vez | Mensaje `oferta_hueco` pendiente/encolado y `GET /reservar/oferta/{token}` 200 con prestación, profesional y vencimiento |
| 7 | Aceptar | `POST /reservar/oferta/{token}/aceptar` | 200 con el turno en el profesional y sillón retenidos; entrada `convertido`; el slot queda ocupado por el turno |
| 8 | Rechazar | Con dos entradas compatibles, rechazar la primera | 200; la segunda recibe el mismo horario y un mensaje nuevo |
| 9 | Vencimiento | Forzar `oferta_expira_en = now() - interval '1 minute'` y correr el worker | La entrada pasa a `vencido`, rota a la siguiente; sin más entradas el slot vuelve a disponibilidad |
| 10 | Webhook de oferta | Responder «aceptar»/«rechazar» firmado sobre el mensaje de oferta | 200 `aplicado=true`; un solo turno; el evento duplicado responde `aplicado=false` |
| 11 | RBAC | `GET /lista-espera` con odontólogo/asistente/auditor y `POST` con odontólogo | 200 de lectura (el odontólogo solo sus entradas) y 403 en escritura |

## C-11 — Historia clínica y odontograma

### Qué se aplicó (resumen no técnico)

La clínica ya puede abrir una ficha clínica por paciente, escribir evoluciones y firmarlas, corregirlas con una nueva evolución enlazada (sin borrar la anterior), registrar el estado de cada pieza dental en un odontograma que guarda versiones, subir fotos o PDF como adjuntos y dejar registrado el consentimiento informado. Todo queda auditado con usuario, IP y dispositivo, y cada rol ve o escribe solo lo que permite la matriz.

### Qué no cambia todavía

- No hay pantalla de ficha clínica: se prueba por Swagger (`http://127.0.0.1:8000/docs`).
- No están los presupuestos/planes de tratamiento (C-12) ni caja/facturación.
- El consentimiento guarda hashes de integridad, no una firma digital certificada.
- El asistente no está vinculado a un profesional concreto: solo accede mientras el paciente está `en_sala`.

### Datos demo para probar

- API/Swagger: `http://127.0.0.1:8000/docs`.
- Administrador: `admin@clinica.test` / `demo-admin-pass-2026` (lee toda la ficha, no escribe).
- Odontólogo: `odonto.demo@clinica.test` / `demo-odonto-pass-2026`.
- El odontólogo demo tiene turnos el 2026-11-09 con Ana Demo (`reservado`), Bruno Demo (`confirmado`) y Carla Demo (`en_sala`).

### Pruebas manuales

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Abrir historia | Login odontólogo; `POST /historia-clinica` con el `paciente_id` de Ana Demo | 201 con `abierta_por` y `fecha_apertura`; repetir da 409 |
| 2 | Lectura del admin | Login admin; `GET /historia-clinica/{id}` y `GET /pacientes/{id}/consentimientos` | 200; un `POST` clínico da 403 |
| 3 | Evolución y firma | `POST /historia-clinica/{id}/evoluciones` con texto; `POST .../{evolucion_id}/firmar` con `{}` | 201 borrador; 200 firmada con `firmada_por` y `fecha_firma` |
| 4 | Firmada inmutable | `PUT` sobre la evolución firmada | 403 y el texto no cambia |
| 5 | Rectificatoria | `POST .../evoluciones` con `rectifica_a` de la firmada; firmarla; leer la original | 201; la original conserva texto y muestra `rectificada_por` |
| 6 | Odontograma | `POST .../odontograma/hallazgos` pieza 16/mesial/caries/K02.1; luego pieza 21; luego corregir 16/mesial | Versiones 1, 2 y 3; la versión 1 conserva caries; la vigente muestra el estado nuevo |
| 7 | FDI inválida | Enviar pieza 19 o cara `lateral` | 422 sin versión nueva |
| 8 | Hallazgo inmutable | `PUT` o `DELETE /odontograma/hallazgos/{id}` | 405; el hallazgo no cambia |
| 9 | Adjunto | `POST /adjuntos` multipart con `historia_id` y un PNG; descargar con `GET /adjuntos/{id}` | 201; descarga 200 con MIME, bytes idénticos y `X-Content-Type-Options: nosniff` |
| 10 | Adjunto inseguro | Subir `.exe`, `text/html`, un archivo >5 MB o un PNG con bytes de PDF; nombre con `..` y separadores | 422 en los cuatro casos; el nombre traversal se guarda como `passwd` |
| 11 | Consentimiento | `POST /pacientes/{id}/consentimientos` con `procedimiento_invasivo` + `v1-2026-11`; enviar `texto` o `firma_ref` en el body | 201 con hashes; los campos extra dan 422; `GET` lista descendente |
| 12 | Asistente | Login asistente; paciente Carla (`en_sala`) lectura y edición de borrador; paciente Bruno (`confirmado`) | 200 en Carla, 403 en Bruno; no puede crear, firmar, adjuntar ni consentir |
| 13 | Sin token | Cualquier endpoint clínico sin `Authorize` | 401 |
| 14 | Auditoría | Consultar `registro_auditoria` con usuario admin de la base demo | Una fila por acción (`historia_clinica.crear`, `evolucion.*`, `odontograma.versionar`, `adjunto.crear`, `consentimiento.registrar`) con usuario, IP y dispositivo |

### Estado de verificación

- Suite backend completa: **720 tests en verde**.
- Frontend: **28 tests en verde** y `tsc --noEmit` sin errores.
- Smoke HTTP contra base descartable: flujo completo en verde; `P0001`, `23505` y `23514` verificados por SQL directo.
- Pendiente: prueba visual de la ficha cuando exista el change de UI clínica y validación de la cátedra sobre el vínculo asistente→profesional.

## C-12 — Presupuestos y planes de tratamiento

### Qué se aplicó (resumen no técnico)

El odontólogo ya puede armar un presupuesto o plan de tratamiento con una o varias prestaciones, indicando pieza dental (opcional) y cantidad. El sistema calcula solo los precios, la cobertura de la obra social y el copago del paciente; el cliente no puede enviar importes. El presupuesto se entrega como borrador, el paciente lo puede aceptar o rechazar, y luego el plan avanza a “en curso” y “finalizado”. Mientras es borrador se puede editar o recalcular la cobertura si cambian las reglas del convenio. Todo movimiento queda auditado con usuario, IP y dispositivo.

### Qué no cambia todavía

- No hay pantalla de presupuestos: se prueba por Swagger (`http://127.0.0.1:8000/docs`).
- No están los cobros, señas ni Mercado Pago (C-13) ni la facturación ARCA/liquidación de obras sociales (C-14).
- No hay PDF, envío por WhatsApp ni portal del paciente para consultar el presupuesto.
- La aceptación **no** exige consentimiento informado: el consentimiento se sigue registrando con C-11 y se exigirá al registrar la práctica invasiva.

### Datos demo para probar

- API/Swagger: `http://127.0.0.1:8000/docs`.
- Administrador: `admin@clinica.test` / `demo-admin-pass-2026`.
- Odontólogo: `odonto.demo@clinica.test` / `demo-odonto-pass-2026` (profesional `MP-DEMO-1`).
- Recepción: `recepcion.demo@clinica.test` / `demo-staff-pass-2026`.
- Asistente: `asistente.demo@clinica.test` / `demo-staff-pass-2026`.
- Auditor: `auditor.demo@clinica.test` / `demo-staff-pass-2026`.
- Turnos del odontólogo el 2026-11-09: Ana Demo `reservado`, Bruno Demo `confirmado`, Carla Demo `en_sala`.
- OS Demo cubre el 60 % de `CONS`, `LIM` y `OBT`. `EXO` no está cubierta. Carla no tiene obra social.

### Pruebas manuales

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Alta con OS Demo | Login odontólogo; `POST /presupuestos` con Ana y dos ítems (`CONS` ×1 y `OBT` con pieza 16 ×2) | 201 borrador; cobertura 60 %; subtotal, cobertura y copago calculados por el servidor |
| 2 | Paciente sin obra social | Mismo alta con Carla y `CONS` ×2 | 201; cobertura 0; copago = subtotal |
| 3 | Prestación no cubierta | Alta con Ana y `EXO` | 201; `cobertura_estado=calculada`; cobertura 0 y copago = total |
| 4 | Cobertura pendiente | Como admin, crear una obra social **sin** `cobertura_porcentaje` y un paciente con esa obra social; alta con `CONS` | 201; `pendiente_verificacion`; cobertura 0; copago = total |
| 5 | Aceptar un pendiente | `PATCH /presupuestos/{id}/estado` con `{"estado":"aceptado"}` | 200; estado aceptado; no se bloquea por consentimiento ni por historia clínica |
| 6 | Idempotencia | Repetir el mismo `PATCH` con `aceptado` | 200 y no se duplica la auditoría de aceptación |
| 7 | Editar borrador | `PUT /presupuestos/{id}` con otros ítems | 200; se reemplazan los ítems, se recalculan precios/cobertura/totales y los anteriores quedan dados de baja lógica |
| 8 | Precio congelado y re-cotización | Cambiar `precio_base` de `CONS` con `PUT /prestaciones/{id}`; leer un presupuesto viejo y luego editar un borrador | El presupuesto viejo conserva su precio y totales; el `PUT` del borrador toma el precio nuevo |
| 9 | Recalcular cobertura | Corregir la obra social pendiente a 60 % con `PUT /obras-sociales/{id}`; `POST /presupuestos/{id}/recalcular` con `{}` | 200 `calculada`; la cobertura cambia y los precios unitarios quedan intactos |
| 10 | Transición inválida | `PATCH .../estado` con `en_curso` sobre un borrador | 422 y el presupuesto sigue en borrador |
| 11 | Editar fuera de borrador | `PUT` sobre un presupuesto aceptado | 409 sin cambios |
| 12 | Baja lógica | `DELETE /presupuestos/{id}` sobre borrador y sobre aceptado | 204 en borrador (desaparece del listado); 409 en aceptado |
| 13 | RBAC | Login recepción/asistente/auditor: `GET /presupuestos` y un `POST`/`PUT`/`PATCH`/`DELETE` | Lectura 200; escritura 403 |
| 14 | Sin token | Cualquier endpoint de presupuestos sin `Authorize` | 401 |
| 15 | Auditoría | Consultar `registro_auditoria` de la base demo | Una fila por acción (`presupuesto.crear/editar/recalcular/aceptar/rechazar/en_curso/finalizar/eliminar`) con usuario, IP y dispositivo; las acciones repetidas no generan filas extra |

### Estado de verificación

- Suite backend completa: **829 tests en verde**.
- Frontend: **28 tests en verde** y `tsc --noEmit` sin errores.
- Smoke HTTP contra base descartable: 8/8 pasos en verde; `23514` y `P0001` verificados por SQL directo.
- OpenSpec: change válido y 4/4 artefactos completos.
- Pendiente: prueba visual cuando exista la UI de presupuestos y la integración con caja/facturación (C-13/C-14).

## C-13 — Caja, cobros y Mercado Pago

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Abrir caja | `POST /caja/abrir` con `monto_apertura=0` | 201, caja `abierta` del día UTC-3 |
| 2 | Segunda apertura | Repetir el alta | 409 |
| 3 | Cobro efectivo | `POST /cobros` tipo `tratamiento`, medio `efectivo`, monto ≤ copago | 201 `aprobado` y movimiento de ingreso |
| 4 | Cobro sin caja | Cobrar con la caja cerrada | 409 |
| 5 | Seña válida | `POST /cobros` tipo `sena` sobre turno con ENDO y monto 10.000 | 201 `pendiente`/`aprobado`; turno `sena_estado=pagada` al conciliar |
| 6 | Seña inválida | Seña sobre prestación sin `requiere_sena`, monto distinto o turno cancelado | 422 |
| 7 | Segunda seña | Repetir una seña viva | 409 |
| 8 | Seña MP | Cobro `mercadopago` | 201 `pendiente` con link de sandbox |
| 9 | Webhook aprobado | Simular pago y enviar webhook firmado | 200; cobro `aprobado`, seña pagada e ingreso MP en caja |
| 10 | Webhook duplicado | Reenviar el mismo pago | 200 sin segundo ingreso |
| 11 | Firma inválida | Webhook sin firma o adulterada | 401 |
| 12 | Arqueo | `GET /caja/arqueo` | Efectivo, MP y deudas separados; diferencia 0 si cuadra |
| 13 | Cierre descuadrado | `POST /caja/cerrar` con monto distinto | 409 y caja sigue abierta |
| 14 | Cierre cuadrado | Cerrar con el monto del sistema | 200; repetir → 409 |
| 15 | Reembolso | `POST /cobros/{id}/reembolsar` | 200 `reembolsado`, auditoría, sin llamada real a MP |
| 16 | RBAC | Recepción cobra; odontólogo solo lectura de sus cobros y sin `/caja`; asistente 403; auditor lectura | según matriz |

## C-14 — Facturación ARCA, cobertura y liquidaciones

> Cierre sin espera por change (decisión del usuario 2026-11-03): la aceptación funcional se hará en la prueba final de la página. Resumen no técnico: cada cobro aprobado obtiene un comprobante interno numerado y verificable; el sistema intenta además la factura fiscal simulada de ARCA y, si no puede, conserva el comprobante interno y reintenta. Se puede consultar la cobertura de una práctica antes de atender y liquidar por período lo que la obra social cubre, con cierre que congela totales.

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Cobro efectivo genera comprobante | Cobrar en efectivo y consultar `GET /comprobantes?cobro_id=…` | 201; comprobante `pendiente` con número interno, tipo B, importe y QR interno |
| 2 | Cobro pendiente/rechazado no factura | Crear cobro MP pendiente o webhook rechazado | No existe comprobante |
| 3 | Emisión fiscal simulada | Ejecutar `python -m app.workers arca --once` y consultar el comprobante | `emitido` con CAE de 14 dígitos, número fiscal y QR AFIP verificable |
| 4 | Reemisión | Repetir el worker sobre el mismo comprobante | No cambia el CAE ni crea otra fila |
| 5 | ARCA caído | Simular indisponibilidad, consultar y reintentar | Comprobante interno `pendiente`; reintento lo deja `pendiente` y el worker lo emite al volver |
| 6 | Envío simulado | `POST /comprobantes/{id}/enviar` con `canal=whatsapp` | 201 con destino del paciente; repetir → 200 sin duplicar |
| 7 | Envío no emitido | Enviar un comprobante `pendiente`/`fallido` | 409 |
| 8 | Cobertura cubierta | `GET /obras-sociales/cobertura` con paciente de OS Demo y CONS | 200 `cubierta`, 60 %, copago 40 % |
| 9 | Cobertura no cubierta | Paciente sin OS o práctica fuera del convenio | 200 `no_cubierta`, cobertura 0 y copago igual al precio |
| 10 | Cobertura pendiente | Convenio inactivo/sin reglas o paciente sin `nro_afiliado` | 200 `pendiente_verificacion`, montos nulos |
| 11 | Cobertura no escribe | Consultar cobertura y revisar turnos/presupuestos/cobros | Sin altas ni modificaciones |
| 12 | Liquidación | Crear presupuesto aceptado con ítem cubierto y cobro de tratamiento aprobado, luego `POST /obras-sociales/liquidaciones` | 201 `borrador` con ítem trazable y total de coberturas |
| 13 | Sin prácticas | Liquidar un período sin cobros aprobados | 422 y sin cabecera |
| 14 | Período inválido/solapado | Fechas invertidas / período que se cruza | 422 / 409 |
| 15 | Cierre | `POST /obras-sociales/liquidaciones/{id}/cerrar` | 200 `cerrada` con totales congelados; repetir → 200 sin cambios |
| 16 | Borrado de borrador | `DELETE /obras-sociales/liquidaciones/{id}` | 204; el período y los ítems quedan disponibles |
| 17 | RBAC | Recepción crea/edita observaciones pero no cierra; odontólogo/auditor solo lectura; asistente 403; sin token 401 | según matriz |

## C-15 — Reportes y exportación de datos

### Qué se aplicó (resumen no técnico)

La clínica ya puede consultar cuatro tableros de solo lectura: agenda y ocupación, ausentismo, caja y liquidaciones por obra social. Los totales se calculan en el servidor y la pantalla solo los muestra. Además, el administrador (y el odontólogo para sus propios pacientes) puede pedir una exportación: el sistema prepara un ZIP con un PDF legible, un JSON completo, un CSV por entidad y los adjuntos clínicos. El pedido responde al instante y un worker lo procesa en segundo plano; si el worker está caído, la solicitud queda pendiente y se recupera sola. El ZIP no incluye contraseñas, tokens, links de pago ni datos crudos de proveedores.

### Qué no cambia todavía

- No hay sistema de diseño ni estilos definitivos: es una pantalla funcional (el diseño visual es C-17).
- No hay reportes programados, envío por email/WhatsApp ni exportación incremental/XLSX.
- El worker `reportes` debe estar corriendo para que una exportación pase de `pendiente` a `lista`.
- No hay purga automática de exportaciones: se conservan y se pueden volver a solicitar sin cargo.
- La prueba visual y de aceptación final se hace sobre la página completa, no change por change.

### Datos demo para probar

- API/Swagger: `http://127.0.0.1:8000/docs`.
- Pantalla: `http://127.0.0.1:8080/reportes`.
- Administrador: `admin@clinica.test` / `demo-admin-pass-2026`.
- Odontólogo demo: `odonto.demo@clinica.test` / `demo-odonto-pass-2026`.
- Pacientes seed: Ana, Bruno y Carla Demo.
- Para exportar un paciente se necesita su `id`: `GET /pacientes?apellido=Demo` o la tabla de la base demo.

### Pruebas manuales

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | Login y cuatro tableros | Abrir `/reportes` con admin | Pide login; al entrar se ven Agenda, Ausentismo, Caja y Liquidaciones |
| 2 | Rango y filtros | Cambiar Desde/Hasta, límite y profesional | Las cuatro consultas se refrescan con el rango elegido |
| 3 | Detalle acotado | Rango con más de 500 turnos | La tabla muestra hasta 500 y aparece “truncado”, pero los totales siguen completos |
| 4 | Exportar un paciente | Escribir el id de Ana y pulsar “Exportar paciente” | 202; estado `pendiente` y luego `lista` si el worker corre |
| 5 | Exportar el consultorio | Pulsar “Exportar consultorio” como admin | 202; un odontólogo recibe 403 |
| 6 | Worker sin Redis | `python -m app.workers reportes --once` | Toma pendientes vencidos por barrido y las deja `lista` |
| 7 | Descarga | Pulsar “Descargar ZIP” con estado `lista` | 200 `application/zip` y archivo descargado |
| 8 | Contenido del ZIP | Abrir el ZIP | `exportacion.pdf`, `datos.json`, `manifiesto.json`, `csv/*.csv` y `adjuntos/*` |
| 9 | Privacidad | Buscar `hash_password`, tokens, `link_pago` y payloads en JSON/CSV | No aparecen valores; el manifiesto solo nombra las exclusiones |
| 10 | Idempotencia | Repetir el mismo POST mientras está pendiente | Mismo `id`, un solo job |
| 11 | Descarga antes de tiempo | Descargar una exportación `pendiente`/`generando`/`fallida` | 409; en `fallida` muestra el error |
| 12 | RBAC reportes | Recepción: agenda/ausentismo/caja 200 y liquidaciones 403; asistente 403; auditor los cuatro 200 | Según matriz |
| 13 | RBAC exportación | Odontólogo: paciente propio 202, paciente ajeno 403, consultorio 403 | Según matriz |
| 14 | Aislamiento | Consultar una exportación de otro consultorio | 404 sin datos |
| 15 | Límites | Bajar `EXPORTACION_MAX_FILAS` o `EXPORTACION_MAX_BYTES` y exportar | `fallida` con error que nombra el límite, sin ZIP parcial |

### Estado de verificación

- Suite backend: **1205 tests en verde de 1206**; el único fallo es el test preexistente de recordatorio 24 h de `test_ofertas_aceptacion`, dependiente de la fecha 2026-11-08 y ajeno a C-15.
- Frontend: **37 tests en verde**, `tsc --noEmit` y `npm run build` correctos.
- Migración 0014: ciclo `upgrade → downgrade 0013 → upgrade` con digest de esquema idéntico.
- Smoke: cuatro reportes 200; exportaciones de paciente y consultorio `lista`; ZIP con PDF/JSON/CSV/adjuntos y sin secretos; `/reportes` 200.
- OpenSpec: `validate --strict` válido y sin warnings.
- Pendiente: prueba visual final en la página completa y, si se desea, levantar el stack Compose cuando el puerto 15432 esté libre.

## Prueba final de la página

Cuando estén todos los changes:

1. Levantar el stack con `docker compose up -d --build` y ejecutar migraciones + seed.
2. Abrir `http://127.0.0.1:8080` y recorrer el flujo completo: reserva pública (C-07), agenda visual (C-08), recordatorios simulados (C-09), historia clínica (C-11), presupuestos (C-12), caja (C-13) y reportes (C-15).
3. Registrar acá los defectos encontrados con change, endpoint/pantalla y resultado esperado vs obtenido.
