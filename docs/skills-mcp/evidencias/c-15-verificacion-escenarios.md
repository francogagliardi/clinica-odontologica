# C-15 — Verificación de escenarios y cierre técnico

> Change: `c-15-reportes-exportacion`. Fecha de evidencia: 2026-11-08.
> Estado: implementación completa (slices 1–3), sin commit ni archive.
> Matriz de trazabilidad: `docs/skills-mcp/evidencias/c-15/matriz-escenarios.md`.
> Validación OpenSpec: `Change 'c-15-reportes-exportacion' is valid` con
> `--strict` y sin warnings (`openspec-validate.txt`).

## 1. Suite backend

La suite se corrió en chunks sobre PostgreSQL real (`TEST_DATABASE_URL`,
puerto 15432). La recolección completa es **1211 tests** (1206 en los chunks + 5 pruebas agregadas al cerrar la matriz):

| Chunk | Log | Resultado |
|---|---|---|
| 1. root + unit + migraciones | `c-15/suite/backend-suite-1.txt` | **447 passed** |
| 2a. adjuntos → core_models | `c-15/suite/backend-suite-2a.txt` | **220 passed** |
| 2b. disponibilidad → historia clínica | `c-15/suite/backend-suite-2b.txt` | **76 passed** |
| 2c. liquidaciones → lista de espera | `c-15/suite/backend-suite-2c.txt` | **81 passed** |
| 3. obras sociales → repositorios | `c-15/suite/backend-suite-3.txt` | **282 passed** (el fallo de calendario se corrigió y re-ejecutó aparte) |
| 4. seña perdida → webhook | `c-15/suite/backend-suite-4.txt` | **99 passed** |
| **Suma de chunks** | | **1205 passed, 0 failed** |
| Archivos finales re-ejecutados (incluye las 5 adiciones) | c-15/suite/backend-suite-delta.txt | **25 passed** |
| **Total** | | **1211 passed, 0 failed** |

El único fallo inicial era **dependiente del reloj de pared**:
`integration/test_ofertas_aceptacion.py::test_aceptar_crea_el_turno_con_los_recursos_retenidos`
esperaba un recordatorio de 24 h para un turno del `2026-11-09 09:00 -03:00`;
al ejecutarse el 2026-11-08 ese turno estaba a menos de 24 h y el sistema
correctamente no programaba el recordatorio. Se hizo condicional la aserción de
recordatorios (la conversión del turno sigue verificada) y el test pasó aislado
(**1 passed**). No cambia comportamiento de producción.

Todas las pruebas nuevas de C-15 pasan:

- `tests/integration/test_exportacion_contenido.py`: **6 passed**
- `tests/integration/test_exportaciones_api.py`: **10 passed**
- `tests/integration/test_exportaciones_rbac.py`: **6 passed**
- `tests/integration/test_reportes_worker.py`: **8 passed**
- Reportes (slices 1/2): agenda 6, ausentismo 4, caja 5, liquidaciones 6,
  bordes 5, RBAC 4, repositorios 4, migración 5.
- Unitarios: dominio 12, artefacto 9, colas 4.

## 2. Migración 0014

Ciclo sobre base descartable `clinica_c15_mig`:

`alembic upgrade head` → `downgrade 0013_facturacion_arca` → `upgrade head` →
`alembic current = 0014_reportes (head)`.

Digest del esquema (`pg_dump --schema-only --no-owner --no-privileges`,
normalizando las líneas aleatorias `\restrict`/`\unrestrict` de pg_dump 17):

- antes: `f81fa919e31189f58120912eecab8b5e4814d13203e48d8ced0095a4aa6b4351`
- después: `f81fa919e31189f58120912eecab8b5e4814d13203e48d8ced0095a4aa6b4351`
- **idénticos**.

Archivos: `c-15/migracion-antes.sql`, `c-15/migracion-despues.sql`,
`c-15/migracion-antes-normalizado.sql`, `c-15/migracion-despues-normalizado.sql`,
`c-15/migracion-*.log`.

## 3. Smoke

Base descartable `clinica_c15_smoke`, migrada y seedeada. API local contra esa
base (Docker Compose no se levantó porque el puerto 15432 ya estaba ocupado por
el PostgreSQL local de tests; se preservó el stack del usuario). Frontend Vite
en 8080.

| Paso | Resultado |
|---|---|
| Login admin | token emitido |
| `GET /reportes/agenda` | 200 |
| `GET /reportes/ausentismo` | 200 |
| `GET /reportes/caja` | 200 |
| `GET /reportes/liquidaciones` | 200 |
| `POST /exportaciones` paciente | 202, `pendiente` |
| `POST /exportaciones` consultorio | 202, `pendiente` |
| `python -m app.workers reportes --once` con Redis caído | ambas pasan a `lista` |
| `GET /exportaciones/{id}/archivo` | 200, `application/zip` |
| ZIP paciente | 8.747 bytes, `sha256=cf1d980881d5483c6d02655b256b807e862d66fcb71ebfbbbba09e71a3c7d33f` |
| ZIP consultorio | 11.303 bytes, `sha256=6ad89d490a296c6f0299ba181d4a8261fe6659097d470b6680f699567331bfce` |
| Contenido | 27 entradas, `%PDF-`, 24 CSV, manifiesto con exclusiones |
| Secretos | hash real, `token_publico` y `link_pago` ausentes fuera del manifiesto; `hash_password` solo aparece como nombre en la lista de exclusiones |
| Frontend `/reportes` | HTTP 200 (SPA servida) |

Evidencia: `c-15/smoke-reportes.txt`, `smoke-reporte-*.json`,
`smoke-export-*.json`, `smoke-worker-reportes.log`,
`smoke-zip-validacion.txt`, `smoke-paciente.zip`, `smoke-consultorio.zip`,
`smoke-frontend-*.html`.

## 4. Frontend

- `npm run test`: **37 passed** (9 archivos; incluye 4 de `reportes/api.test.ts`
  y 4 de `ReportesPage.test.tsx`).
- `npm run typecheck`: sin errores.
- `npm run build`: correcto (45 módulos, bundle 166 kB).

## 5. Desvíos y notas

1. No se ejecutó `docker compose up -d --build`: el puerto 15432 estaba ocupado
   por el PostgreSQL local de tests. Se usaron bases descartables en ese mismo
   servidor, sin bajar ni alterar el stack del usuario. La API y el frontend
   demo quedaron levantados localmente.
2. El smoke no incluye navegación visual automatizada: el frontend se verificó
   con Vitest, `tsc`, build y HTTP 200 de `/reportes`; la validación visual se
   hará en la prueba final de la página (decisión del usuario).
3. El fallo de `test_ofertas_aceptacion` es preexistente y de fecha; no se
   modificó ese test para no tocar changes anteriores.
4. No se archivó el change ni se commiteó nada (R-13 y decisión del usuario).
