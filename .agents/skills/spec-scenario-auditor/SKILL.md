---
name: spec-scenario-auditor
description: Audita las delta specs de un change de OpenSpec en este proyecto odontológico contra la knowledge base, verificando que cada requirement tenga al menos un escenario de funcionamiento esperado, uno de error de negocio y uno de borde, todos trazables a una regla RN-*/DD-* y verificables en un borde observable. Usala siempre que se prepare, revise o actualice un change (proposal/design/specs/tasks) o cuando el usuario diga "revisá los escenarios", "faltan casos borde", "esto es verificable", "trazabilidad RN", "preparar el change", o antes de pasar a /opsx-apply. También cuando una spec parezca correcta pero nadie pueda decir cómo se prueba.
---

# Spec Scenario Auditor

## Propósito

Una spec de este proyecto no se aprueba por sonar bien: se aprueba si cada requirement
puede demostrarse con escenarios verificables y si cada regla de dominio citada existe
de verdad en `knowledge-base/`. Esta skill audita eso y devuelve una tabla de trazabilidad
más la lista de huecos, con el escenario sugerido para cerrarlos.

El valor está en detectar dos fallas típicas antes de implementar:

1. **Escenarios que no prueban nada** (tautológicos, o que solo se pueden verificar leyendo
   el código interno en vez de un borde observable).
2. **Reglas inventadas o deriva de dominio**: la spec afirma algo que la KB no dice, o dice
   lo contrario. La KB es la fuente de verdad; la spec no puede ampliarla por conveniencia.

## Entradas

- **Obligatorio**: nombre del change (`openspec/changes/<nombre>/`) o una ruta a `specs/**/spec.md`.
- **Opcional**: capacidades a auditar (si no se indica, todas las de `specs/`); profundidad
  (`rápida` = solo huecos de tipo de escenario; `completa` = incluye trazabilidad y verificación en tasks).

Si el change no existe o no tiene specs, decilo y no inventes contenido: pedí la ruta correcta.

## Procedimiento

1. **Leer el contexto del change**: `proposal.md`, `design.md`, `tasks.md` y cada
   `specs/<capability>/spec.md`. Si `tasks.md` o `design.md` no existen todavía, registralo
   como hueco (no como error) y seguí con lo que haya.
2. **Leer la KB que el change declara**: el bloque "Leer antes" de `CHANGES.md` para ese change
   y los archivos de `knowledge-base/` que menciona. No audites contra memoria: citá archivo y
   línea de la regla (`RN-*`, `DD-*`, `US-*`).
3. **Construir la matriz de trazabilidad**: una fila por requirement con la regla de la KB que
   lo respalda (o `— sin respaldo` si no hay ninguna).
4. **Clasificar cada escenario**:
   - `esperado`: el camino feliz del requirement.
   - `error de negocio`: una regla del dominio impide la operación (ej. duplicado, transición
     inválida, solapamiento, token vencido). Debe esperar un código/estado concreto.
   - `borde`: límite o caso raro que igual debe comportarse bien (ej. baja lógica + reutilización
     de un valor único, reintento idempotente, concurrencia, conjunto vacío).
5. **Marcar huecos por requirement**: falta alguna de las tres clases, o hay dos escenarios de la
   misma clase y ninguna de otra.
6. **Verificar la verificabilidad** de cada escenario: el `WHEN/THEN` debe poder observarse en un
   borde declarado (HTTP status + body, fila/índice en PostgreSQL, render de la SPA). Si solo se
   puede comprobar mirando una función privada o un mock interno, marcalo como no verificable y
   proponé el borde correcto.
7. **Cruzar con `tasks.md`**: cada escenario debe tener una tarea que diga cómo se verifica
   (test, comando, consulta SQL o paso manual). Un escenario sin tarea de verificación es un hueco.
8. **Reportar** con el formato de abajo. No reescribas la spec: devolvé el diagnóstico y los
   escenarios sugeridos para que quien prepara el change decida.

## Formato de salida

Usá exactamente esta estructura:

```markdown
# Auditoría de escenarios — <change>

## Matriz de trazabilidad

| Requirement | Regla KB | Escenario esperado | Error de negocio | Borde | Veredicto |
|---|---|---|---|---|---|
| <nombre> | RN-XX-NN (archivo:línea) | sí/no | sí/no | sí/no | OK / hueco |

## Huecos detectados

- **<requirement>** — falta <clase>. Sugerido: **WHEN** ... **THEN** ... (respaldo: RN-XX-NN)

## Escenarios no verificables

- **<escenario>** — se verifica en <detalle interno>. Borde observable propuesto: <HTTP/SQL/UI>.

## Escenarios sin tarea de verificación

- **<escenario>** — falta en tasks.md: <verificación concreta propuesta>.

## Deriva de dominio (KB vs spec)

- **<requirement>** — la spec dice <X>; la KB dice <Y> (archivo:línea). No resolver en silencio:
  <opciones>.

## Veredicto

<LISTO PARA APPLY | BLOQUEADO POR HUECOS> — <1–3 líneas con lo mínimo a corregir>.
```

## Criterios de revisión (cómo saber que el resultado sirve)

Antes de entregar el informe, comprobá:

- Cada requirement tiene las tres clases, o el hueco está listado con nombre y sugerencia.
- Toda regla citada existe en la KB y la cita incluye archivo (y línea si es posible).
- Ningún escenario nuevo inventa comportamiento: si la KB no lo dice, aparece en "Deriva de dominio"
  como pregunta, nunca como requisito.
- Cada `THEN` es observable sin leer código interno.
- El veredicto es accionable: se entiende qué corregir y en qué archivo.

## Anti-patrones que hay que marcar

- `THEN` del tipo "el sistema funciona correctamente" o "responde bien" (no falsable).
- Escenarios que repiten el mismo caso con otro nombre para "llegar a tres".
- Verificar consultando la DB *detrás* de una API cuando el borde declarado es la API
  (excepto cuando el requirement es explícitamente de persistencia).
- Requisitos de seguridad/auditoría sin escenario de intento de violación (ej. UPDATE sobre una
  tabla append-only).
- Specs que asumen datos de producción o cifras comerciales no evidenciadas (IN-01/IN-02).

## Checklist de borde para este dominio

Cuando el change toque estos temas, exigí el borde correspondiente:

- **Unicidad + baja lógica**: un valor único liberado por `deleted_at` debe poder reutilizarse.
- **Idempotencia**: seed o webhook ejecutado dos veces no duplica ni falla.
- **Concurrencia**: dos altas simultáneas sobre el mismo recurso → una gana, la otra recibe conflicto.
- **Máquina de estados**: transición inválida debe rechazarse con código específico.
- **Tokens públicos**: vencido o ya usado → rechazo explícito, sin filtrar datos.
- **Auditoría append-only**: UPDATE/DELETE deben fallar en la base, no solo en la app.
