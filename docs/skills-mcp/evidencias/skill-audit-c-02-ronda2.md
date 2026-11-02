# Auditoría de escenarios — c-02-core-models-seguridad (ronda 2)

> ⚠️ **Superada por la ronda 3** (`skill-audit-c-02-ronda3.md`): esta ronda se ejecutó con el mismo contexto que redactó las specs y declaró "LISTO PARA APPLY" sin ver los huecos que una sesión nueva encontró después. Se conserva como evidencia del proceso, no como veredicto vigente.

> Segunda invocación de `spec-scenario-auditor` sobre las specs corregidas y con `tasks.md` ya escrito.
> Objetivo: confirmar que los huecos de la ronda 1 quedaron cerrados y que cada escenario tiene tarea de verificación.

## Matriz de trazabilidad

| Requirement | Regla KB | Esperado | Error de negocio | Borde | Verificación en tasks | Veredicto |
|---|---|---|---|---|---|---|
| Entidades de identidad con identificadores opacos | `04_modelo_de_datos.md` l. 85–87 | sí | sí (rol/slug duplicado) | sí (email tras baja) + sí (rol repetido) | 1.1, 1.2, 3.1, 5.3 | OK |
| Seed idempotente y seguro por entorno | `04_modelo_de_datos.md` l. 92–98 | sí | sí (sin `SEED_ADMIN_PASSWORD`) | sí (doble ejecución) | 5.1, 5.2 | OK |
| Auditoría append-only a nivel de base | RN-SE-02 (`05_reglas_de_negocio.md` l. 45) | sí | sí (UPDATE/DELETE) | sí (TRUNCATE) | 4.1, 4.2, 3.1 | OK |
| AuditMixin con baja lógica | R-04 (DD-07a–e) | sí | sí (baja invisible) | sí (doble baja) | 1.1, 2.1 | OK |
| BaseRepository genérico sin transacciones propias | R-04 | sí | sí (borrado físico no expuesto) | sí (`None` + listado) | 2.1, 2.2 | OK |
| UnitOfWork con transacción por caso de uso | R-04 | sí | sí (rollback) | sí (sesión tras rollback) | 2.3 | OK |
| Migración declarativa reversible con índices | R-04 + R-05 | sí | parcial (base inalcanzable) | sí (upgrade/downgrade) | 3.1, 3.2, 3.3 | OK |

## Huecos detectados

- Ninguno abierto. Los cuatro de la ronda 1 están cerrados: borde de asignación repetida de rol (nuevo escenario), duplicado de `Consultorio.slug` (escenario ampliado), falso error de negocio del repositorio (reemplazado por "borrado físico no disponible" y el `None` movido a contrato), y la deriva del seed declarada en `Purpose` + `design.md`.

## Escenarios sin tarea de verificación

- Ninguno: los 15 escenarios de las dos specs mapean a una tarea con verificación explícita (sección 0 no cuenta como verificación de implementación).

## Deriva de dominio (KB vs spec)

- **Seed recortado** — declarado como nota de alcance en `Purpose` (no como requisito), con dueño C-04/C-05/C-06. Sin conflicto silencioso.
- **`usuario_id` opcional en auditoría** — justificado en el texto del requirement citando `03_actores_y_roles.md` (actor "Sistema / bot WhatsApp"). Sin invención.
- **Patrones sin `RN-*`** — declarados como R-04/`08_arquitectura_propuesta.md`, sin inventar reglas de negocio.

## Hallazgo adicional (herramienta, no escenario)

- `openspec validate --strict` marcó el requirement de seed por superar 500 caracteres (advertencia de redacción, no de contenido). Se corrigió moviendo la nota de alcance de la KB al `Purpose` de la spec, donde no compite con el enunciado normativo. Antes: 1 advertencia `--strict`; después: `Change 'c-02-core-models-seguridad' is valid`.

## Veredicto

**LISTO PARA APPLY** — 15 escenarios con las tres clases, trazabilidad explícita a KB/reglas duras y verificación asignada por tarea. Pendiente de aprobación humana de las decisiones de `design.md` (governance CRÍTICO) antes de escribir código.
