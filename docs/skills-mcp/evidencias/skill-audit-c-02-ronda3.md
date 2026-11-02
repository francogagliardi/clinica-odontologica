# Auditoría de escenarios — c-02-core-models-seguridad (ronda 3, sesión nueva)

> Verificación exigida por el TP: **en una sesión nueva, comprobar que el agente encuentra y utiliza la skill**.
> Se lanzó un subagente con contexto vacío (sin ruta de la skill, sin las specs en contexto) y esta consigna:
> *"este proyecto tiene una skill propia pensada para esta tarea; descubrila con las referencias del proyecto, cargala y auditá `c-02-core-models-seguridad`"*.
> Resultado: el subagente encontró la skill por `AGENTS.md` → `.agents/skills/` → `.atl/skill-registry.md` (y la confirmó en `knowledge-base/09` DD-13), la invocó con la herramienta `skill` y ejecutó el procedimiento completo.

## Qué encontró la sesión nueva (y las rondas anteriores no)

Veredicto emitido: **BLOQUEADO POR HUECOS**, con 8 hallazgos accionables sobre las specs que la ronda 2 había declarado "listas". Los relevantes:

1. **Unicidad + baja lógica inconsistente.** El email usaba índice único parcial, pero `rol.nombre` y `consultorio.slug` usaban `unique` plano: un rol o consultorio dado de baja **bloqueaba su nombre para siempre**. Nadie lo había decidido.
2. **`AuditMixin` sin error de negocio real.** El requirement exigía `deleted_at` + `is_active` en la misma operación, pero nada en la base lo garantizaba; un `UPDATE` directo podía dejar estado parcial. Propuso un CHECK `(deleted_at IS NULL) = is_active` (`23514`).
3. **`BaseRepository` sin probar su afirmación central.** Ningún escenario demostraba que el repositorio **no commitea**; y "borrado físico no expuesto" es ausencia de interfaz, no error de dominio. Propuso probar el no-commit con una segunda sesión y la propagación de la violación de integridad.
4. **Seed**: faltaban la reejecución con otra contraseña (¿reescribe el hash silenciosamente?) y la concurrencia (dos seeds → `23505`).
5. **Auditoría**: `usuario_id` nulo era un `SHALL` sin `WHEN` propio, y faltaba la supervivencia a la baja lógica del usuario referenciado.
6. **Migración**: faltaba la paridad `Base.metadata` ↔ esquema migrado (el riesgo declarado de escribir la migración a mano) y la idempotencia de `upgrade head`.
7. **Escenarios no verificables**: "ningún identificador es un entero secuencial" (negación no falsable) y "sin conexiones filtradas" (sin borde observable).
8. **Denominador inventado**: `tasks.md` decía "12 escenarios" cuando había 23; la ronda 2 había dicho 15. Un conteo mal declarado hace inauditable la cobertura.

## Correcciones aplicadas (antes → después)

| # | Antes | Después |
|---|---|---|
| 1 | `unique` plano en `slug` y `rol.nombre` | Tres índices únicos parciales (`WHERE deleted_at IS NULL`); escenario nuevo de reutilización tras baja |
| 2 | Coherencia de baja solo en el mixin | CHECK en PostgreSQL + escenario de rechazo `23514` |
| 3 | `add`/`get` sin probar el no-commit; borrado físico como "error" | Escenario de no-commit contra una segunda sesión; violación de integridad como error de negocio; borrado físico como ausencia de interfaz |
| 4 | Solo conteos de la segunda corrida | Escenarios de reejecución con otra contraseña (hash intacto) y de dos seeds concurrentes |
| 5 | `usuario_id` nulo entre paréntesis | Escenario propio de acción del sistema + supervivencia a la baja del usuario |
| 6 | Reversibilidad solamente | Paridad ORM↔esquema + `upgrade` repetido no-op |
| 7 | `THEN` no falsables | `pg_typeof(id) = uuid` + versión 4; `pg_stat_activity` sin `idle in transaction` |
| 8 | "12 escenarios" (ronda 2: "15") | **32 escenarios** (15 + 17), con tabla de cobertura en tasks 6.1 |

Además se declaró en el `Purpose` de la spec la **procedencia** de las decisiones que la KB no fija (UUID v4, baja lógica, atributos de `Consultorio`, `SEED_ADMIN_PASSWORD`): vienen de `design.md` (governance CRÍTICO) y de R-04/R-08, no de una regla `RN-*` inventada. Y se corrigió el dueño del seed diferido: los usuarios demo odontólogo/recepcionista son de **C-16**, no de C-04–C-06.

## Lección sobre el límite de la herramienta

La skill funcionó, pero **no reemplaza la revisión humana ni una segunda ejecución independiente**: la ronda 2 —la misma skill, el mismo día— declaró "LISTO PARA APPLY" con huecos que una sesión nueva encontró en minutos. La diferencia no fue la skill: fue el **contexto previo**. Quien acaba de escribir la spec tiende a confirmar su propio diseño; una ejecución sin memoria del razonamiento anterior audita el texto, no la intención. Consecuencia práctica para el proyecto: **la auditoría de la skill debe correrse en una sesión/subagente distinto del que redactó las specs**.

## Veredicto

**LISTO PARA APPLY** tras las correcciones — 32 escenarios con las tres clases, trazabilidad declarada, verificación asignada por tarea y `openspec validate --strict` en verde. Sigue pendiente la **aprobación humana de `design.md`** (governance CRÍTICO) antes de escribir código.
