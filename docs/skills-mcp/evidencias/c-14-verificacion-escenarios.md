# Verificación de escenarios — c-14-facturacion-arca-obras-sociales

Fecha: 2026-11-08. Backend con PostgreSQL real (base descartable para tests y smoke), proveedor ARCA `test` sin red ni certificados. Frontend sin cambios. Stack Compose arriba; demo reseedeada al finalizar.

## Resultado global

- **Suite backend: 1109 passed, 0 failed.** Se ejecutó en cinco chunks forenses porque el runner tiene un límite de 1 h por comando; entre los cinco cubren exactamente `pytest tests -q`:
  - `c-14-suite-backend-a.txt`: 224 passed (23:09)
  - `c-14-suite-backend-b.txt`: 225 passed (21:06)
  - `c-14-suite-backend-c.txt`: 209 passed (17:35)
  - `c-14-suite-backend-d.txt`: 69 passed (06:15)
  - `c-14-suite-backend-e.txt`: 382 passed (unit + tests raíz, 00:04)
- Frontend: **28 passed** (`npm test`) y `npm run typecheck` limpio.
- Migración `0013_facturacion_arca` reversible: `upgrade head → downgrade 0012_caja_cobros → upgrade head` con **digest de esquema idéntico** (`7eb5d903…c8e25`).
- Smoke completo en base descartable con API temporal (puerto 8099): 13/13 pasos en verde.
- `openspec validate c-14-facturacion-arca-obras-sociales --strict`: **válido**.
- `openspec status --change c-14-facturacion-arca-obras-sociales`: **4/4 artefactos completos**.

## Matriz requirement → test

### `fiscal/comprobantes-arca` (9 requirements)

| Requirement | Test(s) |
|---|---|
| Comprobante único por cobro aprobado | `test_comprobantes_efectivo.py`, `test_comprobantes_mp.py`, `test_comprobantes_creacion_auditoria.py`, `test_comprobantes_numeracion.py` |
| Emisión fiscal con CAE y QR | `test_arca_worker.py`, `test_comprobantes_api.py`, `tests/unit/test_fiscal_dominio.py` |
| Proveedor ARCA simulado sin red ni certificados | `tests/unit/test_arca_provider.py` |
| Fallback interno cuando ARCA no está disponible | `test_arca_worker.py` (fallo, backoff, barrido), smoke ARCA caído |
| Worker `arca:emitir` con reintentos e idempotencia | `test_arca_worker.py` (claim, concurrencia, job duplicado, CAE + fallo de persistencia) |
| Idempotencia fiscal garantizada por PostgreSQL | `test_fiscal_migracion.py` (`23505`), `test_comprobantes_numeracion.py` |
| Consulta y envío del comprobante | `test_comprobantes_api.py` |
| Reintento manual de emisión | `test_comprobantes_api.py`, `test_fiscal_auditoria.py` |
| RBAC y auditoría de comprobantes | `test_comprobantes_rbac.py`, `test_fiscal_auditoria.py` |

### `comercial/liquidaciones-obras-sociales` (6 requirements)

| Requirement | Test(s) |
|---|---|
| Validación preventiva de cobertura | `test_cobertura.py`, `test_liquidaciones_rbac.py` |
| Cobertura solo local en v1 | `test_cobertura.py` (proveedor inyectado + campos acotados) |
| Liquidación por período con trazabilidad | `test_liquidaciones_alta.py` |
| Período coherente y no solapado | `test_liquidaciones_periodo.py` (409 y `23P01`), `tests/unit/test_liquidaciones_dominio.py` |
| Estados, cierre y borrado de borrador | `test_liquidaciones_estado.py` |
| Consulta y RBAC de liquidaciones | `test_liquidaciones_consulta.py`, `test_liquidaciones_rbac.py` |
| Auditoría de liquidaciones | `test_fiscal_auditoria.py` |

### Persistencia, migración y dominio

| Verificación | Test(s) |
|---|---|
| Tablas, CHECKs, índices y exclusion constraint | `tests/unit/test_models_metadata.py`, `test_fiscal_migracion.py` |
| Head 0013 y downgrade/upgrade | `test_migration.py`, `test_fiscal_migracion.py`, `tests/test_migrations_env.py` |
| QR fiscal/interno, backoff y fecha UTC-3 | `tests/unit/test_fiscal_dominio.py` |
| Totales, cierre idempotente y período | `tests/unit/test_liquidaciones_dominio.py` |
| Secuencias internas/fiscales y claim | `test_fiscal_repos.py`, `test_comprobantes_numeracion.py` |

## SQLSTATE observados

- `23505`: segundo comprobante por cobro, CAE duplicado, número fiscal duplicado, número interno duplicado, envío duplicado por canal.
- `23514`: importe ≤ 0, estado fiscal incoherente, `fallido` sin error, período invertido en base, cierre incoherente.
- `23P01`: solapamiento de períodos de la misma obra social (servicio responde 409).
- `P0001`: `UPDATE`/`DELETE` directo sobre `registro_auditoria` (append-only).

## Smoke C-14 (base `clinica_c14_smoke`, API temporal :8099)

| Paso | Resultado |
|---|---|
| Login admin | 200 |
| Profesional demo | 201 |
| Cobertura cubierta 60/40 | 200 `cubierta`, 60 %, copago 4800,00 |
| Cobertura pendiente sin afiliado | 200 `pendiente_verificacion`, montos nulos |
| Abrir caja del día | 201 |
| Cobro efectivo + comprobante interno | 201, comprobante `pendiente` nº 1 |
| `python -m app.workers arca --once` | `emitido` con CAE de 14 dígitos y nº fiscal 1 |
| Envío WhatsApp simulado | 201 `registrado`, proveedor `test-…` |
| ARCA caído (cliente sin disponibilidad) | Comprobante interno conservado, `pendiente`, intentos 1, error explícito |
| Reintento manual + worker | 200 y luego `emitido` con CAE |
| Liquidación de un ítem | 201, total 7200,00, 1 práctica trazable |
| Cierre de liquidación | 200 `cerrada`, totales congelados |
| Segundo período solapado | 409 |

Limpieza: base descartable eliminada, cola `arca:emitir` vaciada, demo reseedeada en `0013_facturacion_arca`, stack Compose arriba y saludable.

## Notas

- La suite completa se ejecutó en chunks por el límite de tiempo del runner; la suma (224 + 225 + 209 + 69 + 382 = 1109) equivale a `pytest tests -q`.
- ARCA caído en el smoke se simuló con `TestArcaClient(disponible=False)` porque v1 no tiene proveedor real (R-12); el worker real usa el doble `test` sin red.
- No se modificaron specs, `CHANGES.md` ni changes anteriores. No hubo commit ni archive.
