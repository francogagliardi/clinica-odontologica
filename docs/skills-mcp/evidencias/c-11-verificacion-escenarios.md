# C-11 — Verificación de escenarios (historia clínica y odontograma)

> Evidencia de cierre del change `c-11-historia-clinica-odontograma`.
> Fecha: 2026-11-04. Governance: CRÍTICO (RN-CL-01/03/04, RN-SE-02, R-03, R-04, R-11).
> No se archivó ni commiteó el change; el stack quedó arriba para prueba manual.

## Resultado global

| Suite | Comando | Resultado |
|---|---|---|
| Backend completa | `pytest tests -q` (TEST_DATABASE_URL al PostgreSQL del Compose) | **720 passed**, 2 warnings |
| Frontend unitarias | `npm test` | **28 passed** (7 archivos) |
| Frontend tipos | `npm run typecheck` | sin errores |
| Validación OpenSpec | `openspec validate c-11-historia-clinica-odontograma --strict` | ver sección final |
| Smoke HTTP | API temporal contra DB descartable `clinica_smoke` | exitoso; DB eliminada |

Tests nuevos del slice 3:

| Archivo | Tests |
|---|---|
| `backend/tests/integration/test_odontograma.py` | 23 |
| `backend/tests/integration/test_clinica_rbac.py` | 7 |

Tests de slices 1/2 que sostienen el cierre:

| Archivo | Tests |
|---|---|
| `backend/tests/integration/test_historia_clinica.py` | 15 |
| `backend/tests/integration/test_evoluciones.py` | 16 |
| `backend/tests/integration/test_adjuntos.py` | 16 |
| `backend/tests/integration/test_consentimientos.py` | 10 |
| `backend/tests/integration/test_clinica_repos.py` | 5 |
| `backend/tests/integration/test_clinica_auth.py` | 9 |
| `backend/tests/unit/test_clinica_domain.py` | 85 |
| `backend/tests/unit/test_models_metadata.py` | 42 |

## Matriz requirement → escenario → test → resultado

### `clinica/historia-clinica`

| Requirement | Escenario | Test | Resultado |
|---|---|---|---|
| Historia única por paciente | Apertura 201 + lecturas por id y paciente | `test_historia_clinica.py::test_apertura_devuelve_201_y_las_lecturas_200` | OK |
| Historia única por paciente | Segunda historia activa 409 | `test_historia_clinica.py::test_segunda_historia_activa_responde_409` | OK |
| Historia única por paciente | Paciente inexistente/baja 404 | `test_historia_clinica.py::test_paciente_inexistente_o_dado_de_baja_404` | OK |
| Historia única por paciente | Paciente de otro consultorio 404 | `test_historia_clinica.py::test_apertura_de_paciente_de_otro_consultorio_404` | OK |
| Historia única por paciente | Paciente sin historia 404 con detalle | `test_historia_clinica.py::test_paciente_sin_historia_responde_404_con_detalle` | OK |
| Historia única por paciente | Historia de otro consultorio 404 | `test_historia_clinica.py::test_historia_de_otro_consultorio_404` | OK |
| Evolución borrador y firma | Alta, edición por autor, firma con autor/fecha | `test_evoluciones.py::test_alta_de_borrador`, `test_edicion_del_borrador_por_su_autor`, `test_firma_fija_autor_fecha_y_texto` | OK |
| Evolución borrador y firma | Firma idempotente | `test_evoluciones.py::test_firma_repetida_es_idempotente` | OK |
| Evolución borrador y firma | Firma con cuerpo inesperado 422 | `test_evoluciones.py::test_firma_con_cuerpo_inesperado_422` | OK |
| Evolución borrador y firma | Edición/borrado de firmada 403 y texto intacto | `test_evoluciones.py::test_firmada_rechaza_edicion_y_borrado_403` | OK |
| Evolución borrador y firma | UPDATE/DELETE directo P0001 | `test_evoluciones.py::test_firmada_rechaza_update_y_delete_directo_p0001` | OK |
| Evolución borrador y firma | Descarte de borrador 204 | `test_evoluciones.py::test_descarte_de_borrador_204` | OK |
| Rectificatoria enlazada | Alta enlazada, original intacta, firma y `rectificada_por` | `test_evoluciones.py::test_rectificatoria_enlazada_y_original_intacta` | OK |
| Rectificatoria enlazada | Rectificar borrador/otra historia 422 | `test_evoluciones.py::test_rectificar_borrador_422`, `test_rectificar_evolucion_de_otra_historia_422` | OK |
| Rectificatoria enlazada | Referencia inexistente 404 | `test_evoluciones.py::test_rectificar_inexistente_404` | OK |
| Rectificatoria enlazada | Segunda activa 409 + INSERT directo 23505 | `test_evoluciones.py::test_segunda_rectificatoria_activa_409_y_23505` | OK |
| Rectificatoria enlazada | Cadena de rectificatorias | `test_evoluciones.py::test_cadena_de_rectificatorias` | OK |
| Adjuntos clínicos | PNG/PDF válidos con bytes en PostgreSQL | `test_adjuntos.py::test_subida_png_persiste_los_bytes`, `test_subida_pdf_valida` | OK |
| Adjuntos clínicos | Falta `historia_id`/parte extra 422 | `test_adjuntos.py::test_multipart_sin_historia_o_con_parte_extra_422` | OK |
| Adjuntos clínicos | Historia inexistente/otro consultorio 404 | `test_adjuntos.py::test_historia_inexistente_o_de_otro_consultorio_404` | OK |
| Adjuntos clínicos | MIME/extension/magic bytes 422 | `test_adjuntos.py::test_contenido_no_permitido_422` | OK |
| Adjuntos clínicos | >5 MB 422 + CHECK directo 23514 | `test_adjuntos.py::test_archivo_mayor_a_cinco_mb_422`, `test_check_de_tamano_rechaza_insert_directo` | OK |
| Adjuntos clínicos | Nombre traversal saneado y descarga sin rutas | `test_adjuntos.py::test_nombre_con_path_traversal_se_sanea` | OK |
| Adjuntos clínicos | Descarga 200, MIME/bytes, `nosniff`; 401/404 | `test_adjuntos.py::test_descarga_autenticada_devuelve_bytes_y_headers`, `test_descarga_sin_token_o_inexistente` | OK |
| Adjuntos clínicos | Listado metadata sin bytes | `test_adjuntos.py::test_listado_por_historia_sin_bytes` | OK |
| Consentimiento versionado | 201 con hashes canónicos | `test_consentimientos.py::test_registro_valido_calcula_hashes_en_el_servidor` | OK |
| Consentimiento versionado | Texto/hashes enviados por el cliente 422 | `test_consentimientos.py::test_cliente_no_puede_enviar_texto_ni_firmas` | OK |
| Consentimiento versionado | Tipo/versión inválidos 422 | `test_consentimientos.py::test_tipo_o_version_invalidos_422` | OK |
| Consentimiento versionado | Paciente inexistente/baja/otro consultorio 404 | `test_consentimientos.py::test_paciente_inexistente_baja_o_de_otro_consultorio_404` | OK |
| Consentimiento versionado | Dos actos del mismo tipo/versión | `test_consentimientos.py::test_dos_consentimientos_del_mismo_tipo_y_version` | OK |
| Consentimiento versionado | UPDATE/DELETE directo P0001 | `test_consentimientos.py::test_update_y_delete_directo_p0001` | OK |
| Auditoría clínica | Apertura con usuario/IP/User-Agent | `test_historia_clinica.py::test_auditoria_de_la_apertura` | OK |
| Auditoría clínica | Escritura rechazada no deja fila | `test_historia_clinica.py::test_apertura_rechazada_no_deja_auditoria` | OK |
| Control de acceso | Matriz transversal por rol | `test_clinica_rbac.py` (7 tests) | OK |

### `clinica/odontograma`

| Requirement | Escenario | Test | Resultado |
|---|---|---|---|
| Registro FDI | Pieza permanente 16 con CIE-10 | `test_odontograma.py::test_primera_version_con_pieza_permanente` | OK |
| Registro FDI | Pieza temporaria 75 | `test_odontograma.py::test_pieza_temporaria_valida` | OK |
| Registro FDI | Piezas 19/20/29/49/56/86/99 → 422 | `test_odontograma.py::test_piezas_fuera_de_fdi_422` | OK |
| Registro FDI | Cara/estado/CIE-10 inválidos → 422 | `test_odontograma.py::test_cara_estado_o_cie10_invalidos_422` | OK |
| Registro FDI | Historia inexistente/otro consultorio 404 | `test_odontograma.py::test_historia_inexistente_o_de_otro_consultorio_404` | OK |
| Snapshots inmutables | v1 = 1; v2 copia; v3 corrige misma pieza/cara | `test_odontograma.py::test_versionado_snapshots_y_correccion` | OK |
| Snapshots inmutables | Concurrencia sin repetir versión | `test_odontograma.py::test_concurrencia_no_repite_version` | OK |
| Snapshots inmutables | PUT/DELETE de hallazgo → 405 | `test_odontograma.py::test_hallazgo_no_admite_put_ni_delete_405` | OK |
| Snapshots inmutables | UPDATE/DELETE directo → P0001 | `test_odontograma.py::test_triggers_directos_p0001` | OK |
| Lectura por versión | Sin versiones → `version=null`, `[]` | `test_odontograma.py::test_historia_sin_odontograma_devuelve_version_nula` | OK |
| Lectura por versión | Versión histórica y vigente MAX(version) | `test_odontograma.py::test_versionado_snapshots_y_correccion` | OK |
| Lectura por versión | Versión inexistente 404 | `test_odontograma.py::test_version_inexistente_404` | OK |
| Auditoría del odontograma | Una fila por versión; inválido sin rastro | `test_odontograma.py::test_auditoria_por_version_y_sin_rastro_si_falla` | OK |
| Control de acceso | Lectura por rol y escritura solo odontólogo propio | `test_odontograma.py::test_rbac_de_odontograma` | OK |

## SQLSTATE observados

| SQLSTATE | Operación | Evidencia |
|---|---|---|
| `P0001` | `UPDATE evoluciones` sobre firmada; `DELETE` de firmada | `test_firmada_rechaza_update_y_delete_directo_p0001` |
| `P0001` | `UPDATE`/`DELETE` de `odontogramas` y `hallazgos_dentales` | `test_triggers_directos_p0001` |
| `P0001` | `UPDATE`/`DELETE` de `consentimientos` | `test_update_y_delete_directo_p0001` |
| `23505` | Segunda rectificatoria activa (INSERT directo) | `test_segunda_rectificatoria_activa_409_y_23505` |
| `23505` | Versión duplicada `(historia_id, version)` | smoke SQL directo y `test_migration.py` |
| `23514` | Adjunto con `tamano` > 5 MB | `test_check_de_tamano_rechaza_insert_directo` |
| `23514` | Hallazgo con pieza FDI inválida (INSERT directo) | `test_migration.py` y smoke SQL directo |

## Smoke HTTP (API + DB descartables)

El smoke se corrió contra una base `clinica_smoke` creada para la ocasión y una API temporal en `127.0.0.1:18000`, para no ensuciar la base demo ni las filas append-only. Al terminar se detuvo el contenedor temporal y se eliminó la base.

Preparación:
```powershell
docker compose -f docker-compose.yml -f C:\Users\Franco Gagliardi\AppData\Local\Temp\opencode\clinica-compose.override.yml up -d --build
docker exec clinica-odontologica-db-1 psql -U clinica -d postgres -c "CREATE DATABASE clinica_smoke;"
docker run --rm --network clinica-odontologica_default --env-file backend/.env `
  -e DATABASE_URL="postgresql+asyncpg://clinica:changeme-generate-a-password@db:5432/clinica_smoke" `
  -e REDIS_URL="redis://redis:6379/0" clinica-odontologica-api alembic upgrade head
docker run --rm --network clinica-odontologica_default --env-file backend/.env `
  -e DATABASE_URL="postgresql+asyncpg://clinica:changeme-generate-a-password@db:5432/clinica_smoke" `
  -e REDIS_URL="redis://redis:6379/0" clinica-odontologica-api python -m app.seed
```

Flujo y respuestas observadas:

| Paso | Resultado |
|---|---|
| Login admin | 200 |
| Abrir historia | 201 |
| Leer historia | 200 |
| Crear evolución | 201 |
| Firmar evolución | 200 |
| Editar evolución firmada | **403** |
| Crear rectificatoria | 201 |
| Firmar rectificatoria y leer original | 200; `rectificada_por` informado |
| Hallazgo FDI válido (16/mesial/caries/K02.1) | 201, `version=1` |
| Hallazgo FDI inválido (pieza 19) | **422** |
| Leer odontograma vigente / versión 1 | 200 / 200 |
| Leer versión 99 | **404** |
| Subir PNG con nombre `..\..\etc\passwd` | 201, nombre `passwd` |
| Descargar adjunto | 200; bytes idénticos; `X-Content-Type-Options: nosniff`; `attachment` |
| Registrar consentimiento | 201, `firma_ref` con prefijo `sha256:` |
| Listar consentimientos | 200, 1 fila |

Auditoría observada en la DB de smoke:

```json
{
  "adjunto.crear": 1,
  "consentimiento.registrar": 1,
  "evolucion.crear": 1,
  "evolucion.firmar": 2,
  "evolucion.rectificar": 1,
  "historia_clinica.crear": 1,
  "login_exitoso": 1,
  "odontograma.versionar": 1
}
```

SQL directo sobre la DB de smoke:

```text
P0001 update firmada: P0001
P0001 update hallazgo: P0001
P0001 delete hallazgo: P0001
23505 version duplicada: 23505
23514 pieza 19: 23514
```

Limpieza:
```powershell
docker stop clinica-c11-smoke
docker exec clinica-odontologica-db-1 psql -U clinica -d postgres -c "DROP DATABASE IF EXISTS clinica_smoke;"
```
La DB demo no recibió datos del smoke: se reseedeó tras la suite y quedó en `0010_historia_clinica`; el stack de Compose quedó arriba (`api`, `frontend`, `db`, `redis`), con `api` y `frontend` healthy.

Para la prueba manual se dejó un odontólogo demo (`odonto.demo@clinica.test` / `demo-odonto-pass-2026`) con tres turnos el 2026-11-09 (Ana `reservado`, Bruno `confirmado`, Carla `en_sala`). El administrador demo conserva solo lectura clínica.

## OpenSpec

`openspec validate c-11-historia-clinica-odontograma --strict` ejecutado sin warnings (ver salida en el reporte de cierre).
