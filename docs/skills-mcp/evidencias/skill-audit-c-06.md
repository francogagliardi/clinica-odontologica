# Auditoría de escenarios — c-06-turnos-anti-solapamiento

Fecha: 2026-11-03. Auditoría con `spec-scenario-auditor` antes de implementar.
Alcance: `agenda/turnos` (36 escenarios) y delta MODIFIED de `agenda/recursos-agendables` (10 escenarios).

## Matriz de trazabilidad

| Requirement | Regla KB | Escenario esperado | Error de negocio | Borde | Veredicto |
|---|---|---|---|---|---|
| Alta de turno con duración derivada | RN-TU-01/RN-TU-02 (`05_reglas_de_negocio.md:7–8`); `04_modelo_de_datos.md` §Turno | sí (alta con prestación y fin calculado) | sí (recurso inexistente 404; fuera de agenda 422) | sí (sin prestación, `fin <= inicio`, borde de datos) | OK |
| Anti-solapamiento por profesional y por sillón | RN-TU-01; R-10 (`AGENTS.md`) | sí (consecutivos y recursos distintos) | sí (mismo profesional/sillón 409) | sí (concurrencia real y SQL directo `23P01`) | OK |
| Sobreturno con marca y color explícitos | RN-TU-06 (`05_reglas_de_negocio.md:12`); US-002/CA-2 | sí (sobreturno marcado 201) | sí (sin color 422; normal contra sobreturno 409) | sí (color sin marca 422) | OK |
| Los bloqueos impiden reservar | RN-TU-07 (`05_reglas_de_negocio.md:13`) | sí (bloqueo adyacente no afecta) | sí (solape con bloqueo 409) | sí (bloqueo de otro recurso sin efecto) | OK |
| Máquina de estados del turno | `04_modelo_de_datos.md` §Turno; RN-TU-03/05; R-10 | sí (flujo reservado→atendido) | sí (transición inválida 422) | sí (idempotencia y turno inexistente 404) | OK |
| Reprogramación con la misma garantía | RN-TU-01/02/07; US-002/CA-3; Flujo 2 | sí (mover a slot libre) | sí (slot ocupado 409; terminal 422) | sí (concurrencia de dos reprogramaciones) | OK |
| Acceso a turnos por rol | RN-SE-01 (`05_reglas_de_negocio.md:44`); matriz (`03_actores_y_roles.md:20–27`) | sí (recepción opera) | sí (odontólogo ajeno 403) | sí (sin token 401) | OK |
| Disponibilidad real (MODIFIED) | RN-TU-01/02/07; US-001/CA-1 | sí (slots por duración; turno de otro profesional no afecta) | sí (profesional inexistente 404) | sí (cancelado libera; día completo `[]`) | OK |

## Huecos detectados

Ninguno: los 46 escenarios cubren las tres clases por requirement y conservan los 6 escenarios originales de C-04 en el bloque MODIFIED.

## Escenarios no verificables

Ninguno: todos se observan por HTTP (status + body), por filas/constraints en PostgreSQL (`23P01`, CHECK) o por la consulta de disponibilidad.

## Escenarios sin tarea de verificación

Ninguno: las tareas 4.1, 5.1, 6.1, 7.1, 8.1, 9.1, 9.2 y 10.1 nombran el test o el comando que verifica cada bloque.

## Deriva de dominio (KB vs spec)

- **Ventana de agenda** — la KB define `dias_atencion`, `hora_desde` y `hora_hasta` (04, §Profesional) pero no prohíbe explícitamente un turno fuera de esa ventana. Se agrega como coherencia de negocio (design D4): un turno debe caber en la agenda del profesional. Si la cátedra permite cargas fuera de horario, se relaja en C-08.
- **Turno normal contra sobreturno** — RN-TU-06 dice que el sobreturno lleva marca explícita para no ser un solapamiento silencioso; no aclara si un turno normal puede invadir uno. Se adopta la lectura estricta (design D3): solo el sobreturno marcado puede solaparse. Queda documentado.
- **`plazo_cancelacion_horas`** — RN-TU-03 pide un plazo configurable por consultorio; la KB no fija el nombre ni el default. Se agrega 24 h como default (design D8), aplicable en C-07.
- **`seña_id` diferida** — el modelo de la KB lo incluye, pero la tabla de cobros es C-13. Se difiere para no crear una FK huérfana; se registra como deuda explícita.
- **Estados activos para disponibilidad** — la KB lista los estados pero no cuáles ocupan agenda. Se consideran activos `reservado`, `confirmado`, `en_sala` y `atendido`; `cancelado` y `ausente` liberan (design D11).

## Veredicto

**LISTO PARA APPLY** — sin huecos de escenarios. Las cuatro derivaciones (ventana, normal-vs-sobreturno, plazo por consultorio y estados activos) están justificadas en `design.md` y no contradicen la KB.
