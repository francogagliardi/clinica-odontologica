# Auditoría de escenarios — c-07-reserva-online-publica

Fecha: 2026-11-03. Auditoría con `spec-scenario-auditor` antes de implementar.
Alcance: `agenda/reserva-publica`, 34 escenarios.

## Matriz de trazabilidad

| Requirement | Regla KB | Esperado | Error de negocio | Borde | Veredicto |
|---|---|---|---|---|---|
| Catálogo público del consultorio | US-001/CA-1 (`06_funcionalidades.md`); `03_actores_y_roles.md` §Rutas públicas; RN-NO-03 | sí (catálogo 200 sin token) | sí (slug inexistente 404) | sí (recursos inactivos excluidos; sin JWT) | OK |
| Disponibilidad pública real | US-001/CA-1; RN-TU-01/02/07 | sí (slots reales) | sí (recurso inexistente 404) | sí (fecha inválida 422; día inhábil `[]`) | OK |
| Reserva pública con paciente existente o nuevo | US-001/CA-2; Flujo 1; RN-TU-01/02/07 | sí (paciente nuevo 201) | sí (DNI con otro teléfono 409; slot tomado 409) | sí (concurrencia; teléfono inválido sin residuos) | OK |
| Asignación automática de sillón | RN-TU-01; `04_modelo_de_datos.md` §Sillon/§ProfesionalSillon | sí (elige libre) | sí (sin sillón 409) | sí (prefiere habilitados; `sillon_id` 422) | OK |
| Seña pendiente y política visible | RN-TU-04/08 (`05_reglas_de_negocio.md:10,14`); Flujo 1 paso 4 | sí (pendiente + monto) | sí (prestación inexistente 404) | sí (sin seña `no_requiere`) | OK |
| Token de gestión de un solo uso | RN-NO-03 (`05_reglas_de_negocio.md:40`) | sí (enlace y hash) | sí (usado/vencido 410) | sí (GET no consume; propósito distinto) | OK |
| Confirmar o cancelar desde el enlace | RN-NO-02/03; RN-TU-03/04; Flujo 2 | sí (confirmar/cancelar 200) | sí (transición inválida 422) | sí (plazo y concurrencia del token) | OK |
| Confirmación por WhatsApp best-effort | US-001/CA-3; RN-NO-01; R-06 | sí (encolada) | — (Redis caído no es error de negocio: degradación) | sí (`pendiente_reintento`, reserva 201) | OK (error de negocio cubierto por la reserva 409 de otro requirement) |
| Página pública de reserva | US-001; Flujo 1; R-07 | sí (carga y reserva) | sí (409/422 visibles) | sí (gestión por token) | OK |

## Huecos detectados

Ninguno bloqueante. En `Confirmación por WhatsApp best-effort` no hay un error de negocio propio porque el fallo de Redis es una degradación deliberada: la reserva debe seguir siendo 201. La clase de error queda cubierta por los requirements de reserva (409/422) y se documenta acá.

## Escenarios no verificables

Ninguno: API (status/body), PostgreSQL (hash del token, fila del turno), Redis (RPUSH capturado con cliente falso) y render de componentes.

## Escenarios sin tarea de verificación

Ninguno: las tareas 4.1, 5.1, 5.2, 6.1, 7.1, 7.2, 8.1 y 9.1 nombran el test que cubre cada bloque.

## Deriva de dominio (KB vs spec)

- **Sillón automático** — la KB no dice quién elige el sillón; se decide que lo asigna el backend (design D4) para que el paciente no pueda imponer un recurso físico.
- **DNI con teléfono distinto → 409** — la KB exige DNI único por consultorio (04, §Paciente) pero no define qué hacer si el teléfono no coincide. Se adopta la lectura de seguridad para evitar suplantación (design D3).
- **Token de 7 días** — RN-NO-03 exige vencimiento, no un plazo; se fija 7 días configurable (design D6).
- **`sena_estado` en el turno** — el modelo de la KB tiene `seña_id`; como la tabla de cobros es C-13, se guarda un estado hasta que exista el cobro (design D5).
- **Rate limiting** — no está en el alcance de C-07; se registra como deuda para C-16.

## Veredicto

**LISTO PARA APPLY** — sin huecos de escenarios; las derivaciones están justificadas en `design.md`.
