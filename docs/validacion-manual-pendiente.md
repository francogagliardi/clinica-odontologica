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

## Prueba final de la página

Cuando estén todos los changes:

1. Levantar el stack con `docker compose up -d --build` y ejecutar migraciones + seed.
2. Abrir `http://127.0.0.1:8080` y recorrer el flujo completo: reserva pública (C-07), agenda visual (C-08), recordatorios simulados (C-09), historia clínica (C-11), presupuestos (C-12), caja (C-13) y reportes (C-15).
3. Registrar acá los defectos encontrados con change, endpoint/pantalla y resultado esperado vs obtenido.
