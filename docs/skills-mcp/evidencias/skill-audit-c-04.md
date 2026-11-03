# Auditoría de escenarios — c-04-recursos-agendables

Fecha: 2026-11-02. Skill: `spec-scenario-auditor` (ronda 1). Alcance: las tres delta specs de C-04 y su cruce con `tasks.md`.

## Matriz de trazabilidad

| Requirement | Regla KB | Escenario esperado | Error de negocio | Borde | Veredicto |
|---|---|---|---|---|---|
| Registro de profesionales con agenda configurada | RN-TU-02 (`05:8`), RN-SE-01 (`03:18-27`), `04:38-40`, DD-07a–e (`09:38-52`) | sí (alta + lectura recepción) | sí (409 matrícula, 403 rol, 409 usuario) | sí (baja lógica libera, agenda inválida 422) | OK |
| Sillones y habilitación idempotente profesional ↔ sillón | RN-SE-01 (`03:18-27`), RN-TU-01 (`05:7`), `04:42-44` | sí (alta + listado) | sí (409 nombre, 403 rol, 404 recurso) | sí (baja libera, habilitación repetida) | OK |
| Disponibilidad base por profesional | RN-TU-02 (`05:8`), RN-TU-07 (`05:13`), US-001/CA-1 (`06:11`) | sí (slots con prestación) | sí (404 profesional, 404 prestación) | sí (día no habilitado, último incompleto, 422 borde) | OK |
| Catálogo de prestaciones con duración y precio | RN-TU-02 (`05:8`), RN-SE-01 (`03:18-27`), `04:67-68` | sí (alta + lectura) | sí (409 código, 403 rol, 422 rangos) | sí (baja libera código) | OK |
| Seña opcional por prestación (RN-TU-08) | RN-TU-04 (`05:10`), RN-TU-08 (`05:14`), DD-10 (`09:80-83`), `04:68` | sí (seña con monto visible) | sí (422 sin monto, 422 monto incoherente) | sí (monto ≤ 0, quitar seña) | OK |
| Alta de bloqueo por profesional o por sillón | RN-TU-07 (`05:13`), R-10, `04:52-53` | sí (recepción crea) | sí (XOR 422, rango 422, 404 recurso) | sí (bloqueos solapados) | OK |
| Control de acceso a bloqueos por rol y propiedad | RN-SE-01 (`03:23` odontólogo `RU (propios)`), RN-TU-07 (`05:13`) | sí (odontólogo propio) | sí (403 ajeno, 403 sillón, 403 asistente/auditor) | sí (profesional con `usuario_id` nulo) | OK |
| Efecto del bloqueo en la disponibilidad | RN-TU-07 (`05:13`), RN-TU-01 (`05:7`) | sí (bloqueo quita slots) | sí (404 sillón inexistente/inactivo) | sí (fuera de horario, otro profesional, baja lógica) | OK |

## Huecos detectados

Ronda 1 detectó dos y se cerraron antes de implementar:

- **Control de acceso a bloqueos por rol y propiedad** — faltaba un escenario de borde. Agregado: profesional con `usuario_id` nulo no reclamable por un odontólogo → HTTP 403 (respaldo: `design.md` D2, no regla `RN-*`).
- **Efecto del bloqueo en la disponibilidad** — faltaba un error de negocio. Agregado: consulta con sillón inexistente/inactivo → HTTP 404 (respaldo: RN-TU-01 y `04:42-44`, un sillón no reservable no condiciona disponibilidad).

## Escenarios no verificables

Ninguno. Todos los `THEN` se observan en un borde declarado:

- HTTP status + body de `/profesionales`, `/sillones`, `/prestaciones`, `/bloqueos` y `/profesionales/{id}/disponibilidad`.
- Fila/índice/CHECK en PostgreSQL para unicidad parcial, XOR, rangos, seña y baja lógica (los tests de integración usan `alembic upgrade head`).
- Función pura `app/domain/agenda.py` para los casos de slots, siempre espejada por un test de integración del endpoint.

## Escenarios sin tarea de verificación

Ninguno tras el cruce con `tasks.md`:

- Profesionales → 2.1; sillones/habilitación → 3.1; prestaciones y seña → 4.1; bloqueos → 5.1; lógica de slots y efecto de bloqueos → 6.1; borde de disponibilidad y 404 de sillón → 6.3; seed → 7.1.

## Deriva de dominio (KB vs spec)

- **Seña opcional** — la KB (RN-TU-08, DD-10) define la seña como opcional y no prohíbe un `monto_sena` cuando `requiere_sena=false`. La spec exige `monto_sena = null` en ese caso. No se presenta como regla `RN-*`: la spec declara que proviene de `design.md` D8 de este change.
- **`usuario_id` nullable / bloqueo propio** — la KB no define qué pasa si un profesional no tiene usuario. La spec lo trata como decisión de `design.md` D2 (C-16 crea el usuario odontólogo demo), no como regla de negocio.
- **Offset fijo UTC-3** — la KB no fija zona horaria; `design.md` D4 la acota a v1 y deja la zona por consultorio para C-06.

## Veredicto

**LISTO PARA APPLY** — las tres specs cubren las tres clases de escenario por requirement, todas las reglas citadas existen en la KB (`05:7-14`, `03:18-27`, `04:38-68`) y cada escenario tiene tarea de verificación. Las dos decisiones que exceden la KB quedaron declaradas como procedencia de diseño, no como reglas inventadas.
