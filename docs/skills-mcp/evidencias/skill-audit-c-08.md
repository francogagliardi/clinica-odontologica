# Auditoría de escenarios — c-08-agenda-backoffice-ui

Fecha: 2026-11-03. Auditoría con `spec-scenario-auditor` antes de implementar. 22 escenarios.

## Matriz de trazabilidad

| Requirement | Regla KB | Esperado | Error de negocio | Borde | Veredicto |
|---|---|---|---|---|---|
| Login con token en memoria | R-03 (`AGENTS.md`); DD-07b | sí (login 200) | sí (401 visible) | sí (recarga sin token; logout) | OK |
| Filtros y vistas día/semana/mes | US-002/CA-1; RN-TU-01 | sí (tres vistas) | sí (422 de rango) | sí (día vacío; navegación) | OK |
| Diferenciación visual | US-002/CA-1–2; RN-TU-06/07 | sí (color por estado) | — | sí (bloqueo, sobreturno, cancelado) | OK |
| Reprogramación por arrastre | US-002/CA-3; RN-TU-01; R-07 | sí (200 y refresco) | sí (409/422 visibles) | sí (offset -03:00; sin lógica local) | OK |
| Acciones según rol | RN-SE-01; matriz | sí (recepción) | sí (403 forzado) | sí (odontólogo propio; asistente/auditor lectura) | OK |

## Huecos detectados

- **Diferenciación visual** no tiene un “error de negocio” propio: es un requirement de presentación. Sus casos de error son los del drag (409/422) y la ausencia de datos. No bloqueante.

## Escenarios no verificables

Ninguno: render DOM, llamadas fetch capturadas y estados visibles (`role="alert"`, clases/etiquetas).

## Escenarios sin tarea de verificación

Ninguno: tareas 1.1, 2.1, 2.2, 3.1, 4.1, 5.1, 6.1 y 7.1 nombran el test.

## Deriva de dominio (KB vs spec)

- **Sin nombre de paciente**: `TurnoResponse` solo expone `paciente_id`; la KB no obliga a mostrar el nombre en la grilla. Se muestra matrícula/prestación/hora y queda como mejora (design D4).
- **Drag & drop nativo**: la KB/US pide arrastre, no una librería; se usa HTML5 nativo (design D6).
- **Sesión en memoria**: R-03 lo exige; el costo es re-loguear al refrescar.

## Veredicto

**LISTO PARA APPLY** — sin huecos bloqueantes; las limitaciones están documentadas en `design.md`.
