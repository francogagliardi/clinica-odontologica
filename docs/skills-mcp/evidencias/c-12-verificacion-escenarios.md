# C-12 — Verificación de escenarios (presupuestos y planes)

> Evidencia de cierre del change `c-12-presupuestos-planes`.
> Fecha: 2026-11-04. Governance: ALTO (RN-CL-02, RN-OS-02, RN-SE-02, R-02, R-04, R-11).
> No se archivó ni commiteó el change. Stack demo arriba y reseedeado.

## Resultado global

| Suite | Comando | Resultado |
|---|---|---|
| Backend completa | `pytest tests -q` (TEST_DATABASE_URL al PostgreSQL del Compose) | **829 passed**, 2 warnings, 42:11 |
| Frontend unitarias | `npm test` | **28 passed** (7 archivos) |
| Frontend tipos | `npm run typecheck` | sin errores |
| OpenSpec validate | `openspec validate c-12-presupuestos-planes --strict` | `Change 'c-12-presupuestos-planes' is valid` |
| OpenSpec status | `openspec status --change c-12-presupuestos-planes` | `Progress: 4/4 artifacts complete` |
| Smoke HTTP | API temporal `127.0.0.1:18000` contra `clinica_smoke` | 8/8 pasos OK; DB eliminada |

### Tests C-12 por archivo

| Archivo | Tests |
|---|---|
| `backend/tests/unit/test_presupuestos_domain.py` | 30 |
| `backend/tests/unit/test_models_metadata.py` (incluye 5 de C-12) | 47 |
| `backend/tests/test_migrations_env.py` | 13 |
| `backend/tests/integration/test_migration.py` (incluye C-12) | 23 |
| `backend/tests/integration/test_presupuestos_repos.py` | 3 |
| `backend/tests/integration/test_presupuestos_cobertura.py` | 6 |
| `backend/tests/integration/test_presupuestos_alta.py` | 18 |
| `backend/tests/integration/test_presupuestos_consulta.py` | 17 |
| `backend/tests/integration/test_presupuestos_estados.py` | 12 |
| `backend/tests/integration/test_presupuestos_rbac.py` | 9 |
| `backend/tests/integration/test_presupuestos_auditoria.py` | 4 |

## Matriz requirement → escenario → test → resultado

### 1. Alta de presupuesto con ítems y precios del servidor

| Escenario | Test | Resultado |
|---|---|---|
| Alta 201 con dos ítems y snapshot de `precio_base` | `test_presupuestos_alta.py::test_alta_con_os_demo_devuelve_201_y_dos_items` | OK |
| 2 × CONS al 60 % → cobertura 12.000,00 | `test_presupuestos_alta.py::test_alta_con_dos_items_de_cons_calcula_cobertura_12000` | OK |
| Cliente envía precios/totales → 422 | `test_presupuestos_alta.py::test_el_cliente_no_puede_fijar_precios_ni_totales` | OK |
| Sin ítems / lista vacía → 422 | `test_presupuestos_alta.py::test_sin_items_o_items_vacios_responde_422` | OK |
| Paciente/profesional/prestación inexistente, inactivo u otro consultorio → 404 | `test_presupuestos_alta.py::test_referencias_inexistentes_o_de_otro_consultorio_404`, `test_paciente_o_prestacion_dados_de_baja_404`, `test_profesional_inactivo_404` | OK |
| Cantidad ≤ 0 → 422 + CHECK `23514` | `test_cantidad_no_positiva_responde_422`; `test_migration.py::test_c12_sql_directo_rechaza_invariantes` | OK |
| Pieza FDI inválida 19/49/86 → 422; pieza 48 se acepta | `test_presupuestos_alta.py::test_pieza_fdi_invalida_responde_422_y_la_valida_se_acepta`; CHECK `23514` | OK |

### 2. Cálculo de cobertura y copago por ítem (RN-OS-02)

| Escenario | Test | Resultado |
|---|---|---|
| 60 % sobre 2 × 10.000,00 → 12.000,00 / 8.000,00 | `test_presupuestos_domain.py::test_cobertura_parcial_de_60_sobre_dos_items` | OK |
| Cobertura 0 % y 100 % | `test_presupuestos_domain.py::test_cobertura_cero_y_cien` | OK |
| Paciente sin obra social → cobertura 0, copago = total | `test_presupuestos_domain.py::test_sin_convenio_la_cobertura_es_cero`; `test_presupuestos_alta.py::test_alta_sin_obra_social_cobra_todo_al_paciente` | OK |
| Redondeo half-up 33,33 × 60 % = 20,00 / 13,33 | `test_presupuestos_domain.py::test_redondeo_half_up_sin_centavos_perdidos` | OK |
| Totales = suma de ítems e invariante por ítem | `test_presupuestos_domain.py::test_totales_son_la_suma_de_los_items`; `test_presupuestos_alta.py::test_sql_de_totales_coherentes_y_pendiente_distinto_de_cero` | OK |
| Prestación fuera del convenio → 0 conocido, estado `calculada` | `test_presupuestos_alta.py::test_prestacion_fuera_del_convenio_tiene_cobertura_cero_conocida`; `test_presupuestos_cobertura.py::test_prestacion_fuera_de_la_lista_no_se_cubre` | OK |
| CHECK por ítem roto por SQL directo → `23514` | `test_migration.py::test_c12_sql_directo_rechaza_invariantes` | OK |

### 3. Cobertura no verificable no bloquea el presupuesto

| Escenario | Test | Resultado |
|---|---|---|
| Convenio sin `cobertura_porcentaje` → 201 pendiente, cobertura 0 | `test_presupuestos_alta.py::test_convenio_sin_porcentaje_queda_pendiente`; `test_presupuestos_cobertura.py::test_convenio_sin_porcentaje_no_es_verificable` | OK |
| Convenio con baja lógica → 201 pendiente, sin 500 | `test_presupuestos_alta.py::test_convenio_inactivo_queda_pendiente`; `test_presupuestos_cobertura.py::test_convenio_con_baja_logica_no_es_verificable` | OK |
| Proveedor no disponible (override) → 201 pendiente y filas persistidas | `test_presupuestos_alta.py::test_proveedor_no_disponible_responde_201_y_persiste` | OK |
| Reglas no interpretables → `None` | `test_presupuestos_cobertura.py::test_reglas_no_interpretables_no_son_verificables` | OK |
| Aceptación con cobertura pendiente no se bloquea | `test_presupuestos_estados.py::test_aceptacion_no_exige_consentimiento_ni_historia` y smoke paso 3 | OK |

### 4. Máquina de estados

| Escenario | Test | Resultado |
|---|---|---|
| Camino completo borrador → aceptado → en_curso → finalizado | `test_presupuestos_estados.py::test_camino_completo_de_estados` | OK |
| Saltos inválidos desde borrador → 422 | `test_presupuestos_estados.py::test_saltos_invalidos_desde_borrador_422` | OK |
| Aceptado no se rechaza → 422 | `test_presupuestos_estados.py::test_aceptado_no_se_rechaza_422` | OK |
| Terminales rechazado/finalizado → 422 | `test_presupuestos_estados.py::test_estados_terminales_422` | OK |
| Repetición del estado actual → 200 sin auditoría extra | `test_presupuestos_estados.py::test_repetir_estado_actual_200_sin_auditoria_extra`, `test_borrador_a_borrador_es_idempotente` | OK |
| Destino inexistente o `borrador` desde otro estado → 422 | `test_presupuestos_estados.py::test_destino_inexistente_o_borrador_desde_otro_estado_422` | OK |
| Body con datos clínicos → 422 | `test_presupuestos_estados.py::test_patch_con_campos_clinicos_422` | OK |
| DELETE 204 solo borrador; 409 aceptado; desaparece del listado | `test_delete_borrador_204_y_desaparece_del_listado`, `test_delete_aceptado_409_y_no_borra`, `test_delete_inexistente_404` | OK |

### 5. Edición y recálculo solo en borrador

| Escenario | Test | Resultado |
|---|---|---|
| PUT reemplaza ítems y recalcula | `test_presupuestos_consulta.py::test_put_reemplaza_items_y_recalcula` | OK |
| PUT fuera de borrador → 409 sin cambios | `test_put_fuera_de_borrador_409_sin_cambios` | OK |
| PUT con importes del cliente → 422 | `test_put_con_importes_del_cliente_422` | OK |
| PUT cambia paciente y recalcula contra nueva cobertura | `test_put_cambia_paciente_y_recalcula_cobertura` | OK |
| PUT re-cotiza con el `precio_base` vigente | `test_put_resnapshot_del_precio_vigente`, `test_put_recotiza_dos_items_de_la_misma_prestacion` | OK |
| Recalcular pendiente → calculada sin tocar precios | `test_recalcular_pendiente_a_calculada_sin_tocar_precios` | OK |
| Recalcular fuera de borrador → 409 | `test_recalcular_fuera_de_borrador_409` | OK |
| Recalcular con campos extra → 422 | `test_recalcular_con_campos_extra_422` | OK |
| Ítems reemplazados con baja lógica | `test_put_reemplaza_items_y_recalcula`; `test_presupuestos_repos.py::test_baja_logica_de_items_reemplazados` | OK |

### 6. Precio unitario congelado por ítem

| Escenario | Test | Resultado |
|---|---|---|
| Cambio de catálogo no altera un presupuesto existente | `test_presupuestos_consulta.py::test_cambio_de_precio_no_altera_presupuesto_existente` | OK |
| Cambio de catálogo no altera un aceptado | `test_cambio_de_precio_no_altera_un_aceptado` | OK |
| Baja de prestación no rompe la ficha; nuevo alta 404 | `test_baja_de_prestacion_no_rompe_ficha_y_bloquea_altas` | OK |
| PUT del borrador toma el precio vigente | `test_put_resnapshot_del_precio_vigente`, `test_put_recotiza_dos_items_de_la_misma_prestacion` | OK |

### 7. Acceso a presupuestos por rol

| Escenario | Test | Resultado |
|---|---|---|
| Administrador CRUD sobre cualquier profesional | `test_presupuestos_rbac.py::test_administrador_crud_sobre_cualquier_profesional` | OK |
| Odontólogo propio 201; paciente ajeno 403; `profesional_id` ajeno 403 | `test_odontologo_crea_solo_para_su_paciente_y_profesional` | OK |
| Odontólogo sin fila en `profesionales` → 403 (crear y listar) | `test_odontologo_sin_fila_en_profesionales_403` | OK |
| Recepción lectura 200 / escritura 403 | `test_recepcion_lee_y_no_escribe` | OK |
| Asistente y auditor lectura 200 / escritura 403 | `test_asistente_y_auditor_leen_y_no_escriben` | OK |
| Paciente sin turno vigente → 403 | `test_paciente_sin_turno_vigente_403` | OK |
| Presupuesto de otro odontólogo → 403 (GET/PUT/PATCH/DELETE) | `test_presupuesto_de_otro_odontologo_403` | OK |
| Odontólogo edita su propio presupuesto | `test_odontologo_edita_su_propio_presupuesto` | OK |
| Sin token → 401 en todos los endpoints | `test_sin_token_todos_los_endpoints_401` | OK |

### 8. Auditoría de las escrituras de presupuesto

| Escenario | Test | Resultado |
|---|---|---|
| Las 8 acciones con usuario, IP y `User-Agent` | `test_presupuestos_auditoria.py::test_todas_las_acciones_auditan_usuario_ip_y_agente` | OK |
| Rechazos 422/403/409/404 sin fila | `test_rechazos_no_dejan_fila_de_auditoria` | OK |
| Acción idempotente no audita de nuevo | `test_accion_idempotente_no_audita_de_nuevo` | OK |
| UPDATE/DELETE directo sobre `registro_auditoria` → `P0001` | `test_auditoria_de_presupuesto_es_append_only_p0001`; regresión `test_core_models.py -k auditoria` (4 passed) | OK |

### 9. Consulta y listado

| Escenario | Test | Resultado |
|---|---|---|
| Ficha con ítems y totales | `test_presupuestos_consulta.py::test_ficha_devuelve_items_y_totales` | OK |
| Filtros por paciente/profesional/estado y orden descendente | `test_listado_filtra_y_ordena_descendente` | OK |
| Query no declarada → 422 | `test_consulta_rechaza_query_desconocida` | OK |
| Inexistente o de otro consultorio → 404 | `test_ficha_inexistente_o_de_otro_consultorio_404` | OK |
| Odontólogo lista solo los propios | `test_odontologo_lista_solo_los_propios` | OK |

### 10. Aceptación sin bloqueo por consentimiento (RN-CL-03)

| Escenario | Test | Resultado |
|---|---|---|
| Aceptar sin consentimiento ni historia clínica | `test_presupuestos_estados.py::test_aceptacion_no_exige_consentimiento_ni_historia` | OK |
| Body de aceptación con campos clínicos → 422 | `test_patch_con_campos_clinicos_422` | OK |

## SQLSTATE observados

| SQLSTATE | Operación | Evidencia |
|---|---|---|
| `23514` | `cantidad = 0` en `items_presupuesto` | `test_migration.py::test_c12_sql_directo_rechaza_invariantes` |
| `23514` | Pieza FDI `19/49/86` | mismo test; smoke SQL directo |
| `23514` | `cobertura_item + copago_item ≠ precio_unitario * cantidad` | mismo test |
| `23514` | `subtotal ≠ cobertura_calculada + copago` | mismo test |
| `23514` | Baja lógica incoherente (`deleted_at` con `is_active=true`) | mismo test |
| `P0001` | `UPDATE`/`DELETE` de `registro_auditoria` | `test_presupuestos_auditoria.py::test_auditoria_de_presupuesto_es_append_only_p0001`; smoke SQL directo |
| `P0001` | Regresión C-02 (append-only) | `test_core_models.py -k auditoria` (4 passed) |

## Smoke HTTP

Base descartable `clinica_smoke`, API temporal `127.0.0.1:18000` con imagen `clinica-odontologica-api`, red `clinica-odontologica_default`. La demo no recibió datos del smoke.

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
docker run -d --name clinica-c12-smoke --network clinica-odontologica_default --env-file backend/.env `
  -e DATABASE_URL="postgresql+asyncpg://clinica:changeme-generate-a-password@db:5432/clinica_smoke" `
  -e REDIS_URL="redis://redis:6379/0" -p 127.0.0.1:18000:8000 clinica-odontologica-api
```

| Paso | Resultado observado |
|---|---|
| 1. Alta OS Demo (CONS ×1 + OBT ×2) | **201**; subtotal 62.000,00; cobertura 37.200,00; copago 24.800,00 |
| 2. Alta con convenio sin porcentaje | **201** `pendiente_verificacion`; cobertura 0; copago = total |
| 3. Aceptar pendiente | **200** `aceptado`; conserva `pendiente_verificacion`; repetir da **200** sin fila nueva |
| 4. PUT del borrador tras cambiar `precio_base` a 13.000 | **200**; ítem re-cotizado a 13.000; subtotal 26.000; cobertura 15.600; copago 10.400 |
| 5. Corregir convenio a 60 % y recalcular | **200** `calculada`; precio intacto 13.000; cobertura 7.800; copago 5.200 |
| 6. Transición inválida / PUT sobre aceptado | **422** / **409** |
| 7. Recepción: lectura / escrituras | **200** / **403** en POST, PUT, PATCH y DELETE |
| 8. Baja de borrador por admin | **204** |

Auditoría del smoke:

```text
presupuesto.aceptar     1
presupuesto.crear       3
presupuesto.editar      1
presupuesto.eliminar    1
presupuesto.recalcular  1
duplicados (entidad_id, accion): 0 filas
filas sin usuario/IP/User-Agent: 0
```

SQL directo sobre la DB de smoke:

```text
UPDATE registro_auditoria  -> ERROR: P0001 (append-only)
DELETE registro_auditoria  -> ERROR: P0001 (append-only)
INSERT item con pieza 19   -> ERROR: 23514 (ck_items_presupuesto_pieza_fdi_valida)
```

Limpieza:

```powershell
docker stop clinica-c12-smoke; docker rm clinica-c12-smoke
docker exec clinica-odontologica-db-1 psql -U clinica -d postgres -c "DROP DATABASE IF EXISTS clinica_smoke;"
docker exec clinica-odontologica-api-1 python -m app.seed
```

La demo quedó en `0011_presupuestos (head)`, con el seed canónico y el actor de prueba manual de C-11 (`odonto.demo@clinica.test`) con sus tres turnos del 2026-11-09.

## OpenSpec

- `openspec validate c-12-presupuestos-planes --strict` → `Change 'c-12-presupuestos-planes' is valid`.
- `openspec status --change c-12-presupuestos-planes` → `Progress: 4/4 artifacts complete` (`proposal`, `specs`, `design`, `tasks`).
