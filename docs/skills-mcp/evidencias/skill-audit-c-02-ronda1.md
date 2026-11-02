# Auditoría de escenarios — c-02-core-models-seguridad (ronda 1)

> Evidencia de invocación de la skill `spec-scenario-auditor` (ver `.agents/skills/spec-scenario-auditor/SKILL.md`).
> Entrada: `openspec/changes/c-02-core-models-seguridad/specs/**` (ronda 1, antes de correcciones).
> KB consultada: `knowledge-base/04_modelo_de_datos.md`, `05_reglas_de_negocio.md` (RN-SE-02), `03_actores_y_roles.md`, `08_arquitectura_propuesta.md`, `CHANGES.md` (C-02).

## Matriz de trazabilidad

| Requirement | Regla KB | Esperado | Error de negocio | Borde | Veredicto |
|---|---|---|---|---|---|
| Entidades de identidad con identificadores opacos | `04_modelo_de_datos.md` §Usuario/Rol/RegistroAuditoria (l. 85–87) | sí | sí (rol duplicado) | sí (email tras baja lógica) | **hueco**: falta duplicado en `Consultorio.slug` y asignación repetida de rol |
| Seed idempotente y seguro por entorno | `04_modelo_de_datos.md` §Seed (l. 92–98) | sí | sí (sin `SEED_ADMIN_PASSWORD`) | sí (segunda ejecución) | OK, con deriva intencional documentada |
| Auditoría append-only a nivel de base | `05_reglas_de_negocio.md` RN-SE-02 (l. 45) | sí | sí (UPDATE/DELETE) | sí (TRUNCATE) | OK |
| AuditMixin con baja lógica | sin `RN-*` directa; se apoya en R-04 (DD-07a–e) | sí | sí (baja no visible) | sí (doble baja) | OK, pero ver deriva |
| BaseRepository genérico sin transacciones propias | sin `RN-*` directa; R-04 | sí | **mal clasificado** | sí (listado) | **hueco** |
| UnitOfWork con transacción por caso de uso | sin `RN-*` directa; R-04 | sí | sí (excepción revierte) | sí (sesión tras rollback) | OK |
| Migración declarativa reversible con índices | R-04 + R-05 (índices) | sí | parcial (base inalcanzable) | sí (upgrade/downgrade) | OK con observación |

## Huecos detectados

- **Entidades de identidad** — falta el borde de **asignación repetida del mismo rol** a un usuario (PK compuesta `UsuarioRol`). Sugerido: **WHEN** se asigna dos veces el mismo rol al mismo usuario **THEN** la segunda asignación no duplica el vínculo ni deja el usuario en estado inconsistente (decisión: operación idempotente, no error 500).
- **Entidades de identidad** — el escenario de error cubre solo `Rol.nombre`; el `Consultorio.slug` también es único y no tiene escenario. Sugerido: ampliar el escenario a "valor único duplicado (rol o slug de consultorio) → `23505`".

## Escenarios no verificables

- Ninguno: los `THEN` se observan en PostgreSQL (constraints, triggers, conteos) o en la interfaz pública del repositorio.

## Escenarios sin tarea de verificación

- Todos: `tasks.md` todavía no existe en este change. Se resolverá en la ronda 2 (cada escenario debe mapear a una tarea que diga cómo se verifica).

## Deriva de dominio (KB vs spec)

- **Seed** — la KB (`04_modelo_de_datos.md`, l. 94–98) pide 5 roles, **3 usuarios** (admin, odontólogo, recepcionista), 1 consultorio con 2 sillones, prestaciones, obra social y turnos ficticios. La spec recorta a 5 roles + 1 consultorio + 1 admin porque `CHANGES.md` C-02 lo limita y las demás entidades (sillón, prestación, obra social, paciente, turno) **no existen todavía** (C-04/C-05/C-06). Deriva intencional y documentada: no es error, pero debe quedar dicho en la spec para que nadie lea "seed completo" donde no lo hay.
- **Auditoría** — la KB no dice si `usuario_id` es obligatorio; `03_actores_y_roles.md` (l. 16) reconoce al actor "Sistema / bot WhatsApp", así que un `usuario_id` opcional está justificado y debe citarse, no asumirse.
- **`BaseRepository` / `UnitOfWork` / `AuditMixin`** — no hay regla `RN-*`; son patrones de `08_arquitectura_propuesta.md` (§Patrones aplicados) + R-04. No inventar RN inexistentes para "tener trazabilidad".

## Observación de clasificación

- **BaseRepository** — el escenario rotulado como "error de negocio" (`get` de un id inexistente devuelve `None`) **no es un error de negocio**: es el contrato del repositorio, y el `404` se decide en la capa HTTP (que en C-02 no existe). Un error de negocio verificable en esta capa es intentar un **borrado físico**: la interfaz pública no debe exponerlo (R-04, baja lógica). Se propone reemplazar el escenario mal clasificado.

## Veredicto

**BLOQUEADO POR HUECOS** — corregir: (1) borde de asignación repetida de rol; (2) duplicado de `Consultorio.slug` en el escenario de error; (3) reemplazar el falso "error de negocio" del repositorio por el intento de borrado físico, y mover el `None` a borde/contrato; (4) declarar la deriva intencional del seed y la justificación de `usuario_id` opcional.
