# Matriz de escenarios — C-15 Reportes y exportación

> Fuente: `openspec/changes/c-15-reportes-exportacion/specs/reportes/reportes/spec.md`,
> `.../specs/reportes/exportacion/spec.md` y `.../specs/platform/job-queues/spec.md`.
> Cada escenario tiene al menos un test que lo cubre; no quedan escenarios sin
> cobertura. Los nombres son los archivos de `backend/tests/` y
> `frontend/src/`.

## `reportes/reportes`

| Escenario | Cobertura |
|---|---|
| Agenda · totales por estado y recurso | `integration/test_reportes_agenda.py::test_totales_por_estado_recurso_y_ocupacion_50` |
| Agenda · ocupación contra la agenda configurada | `integration/test_reportes_agenda.py::test_totales_por_estado_recurso_y_ocupacion_50` |
| Agenda · rango por encima del máximo | `integration/test_reportes_agenda.py::test_rango_de_62_dias_se_acepta_y_63_se_rechaza` |
| Agenda · rango en el límite y zona horaria | `integration/test_reportes_agenda.py::test_turno_de_las_2330_utc3_se_cuenta_en_el_dia_local` |
| Agenda · profesional sin agenda o inexistente | `integration/test_reportes_agenda.py::test_filtro_por_profesional_y_profesionales_invalidos` |
| Agenda · sobreturnos no inflan la ocupación | `integration/test_reportes_agenda.py::test_sobreturnos_no_inflan_la_ocupacion` |
| Ausentismo · tasas sobre turnos cerrados | `integration/test_reportes_ausentismo.py::test_tasas_sobre_turnos_cerrados_y_activos_aparte` |
| Ausentismo · turnos activos fuera de la tasa | `integration/test_reportes_ausentismo.py::test_tasas_sobre_turnos_cerrados_y_activos_aparte` |
| Ausentismo · rango sin turnos cerrados | `integration/test_reportes_ausentismo.py::test_rango_sin_cierres_no_divide_por_cero` |
| Ausentismo · detalle con identidad y fecha local | `integration/test_reportes_ausentismo.py::test_detalle_con_identidad_y_fecha_local` |
| Ausentismo · filtro por profesional propio y ajeno | `integration/test_reportes_ausentismo.py::test_filtro_por_profesional` + `integration/test_reportes_rbac.py::test_odontologo_solo_sus_agregados_y_403_con_otro_profesional` |
| Ausentismo · rango inválido | `integration/test_reportes_bordes.py::test_limite_y_fechas_invalidas_devuelven_422` |
| Caja · totales por medio y estado | `integration/test_reportes_caja.py::test_totales_por_medio_estado_y_movimientos` |
| Caja · cobros no aprobados no son ingreso | `integration/test_reportes_caja.py::test_totales_por_medio_estado_y_movimientos` |
| Caja · movimientos y deudas separados | `integration/test_reportes_caja.py::test_totales_por_medio_estado_y_movimientos` |
| Caja · arqueo cerrado y caja abierta | `integration/test_reportes_caja.py::test_arqueo_cerrado_y_caja_abierta_sin_recalcular` |
| Caja · filtro de medio inválido o no declarado | `integration/test_reportes_caja.py::test_medio_invalido_y_parametro_extra_devuelven_422` |
| Caja · consultorio sin cajas en el rango | `integration/test_reportes_caja.py::test_rango_sin_cajas_ni_cobros_devuelve_ceros` |
| Liquidaciones · agregado por obra social y estado | `integration/test_reportes_liquidaciones.py::test_agregados_por_estado_obra_social_y_prestacion` |
| Liquidaciones · cruce de período, no contención | `integration/test_reportes_liquidaciones.py::test_cruce_de_periodo_octubre_noviembre` |
| Liquidaciones · prácticas por prestación | `integration/test_reportes_liquidaciones.py::test_agregados_por_estado_obra_social_y_prestacion` |
| Liquidaciones · rango sin liquidaciones | `integration/test_reportes_liquidaciones.py::test_rango_vacio_devuelve_ceros_sin_listas` |
| Liquidaciones · obra social de otro consultorio | `integration/test_reportes_liquidaciones.py::test_obra_social_de_otro_consultorio_devuelve_404` |
| Liquidaciones · ítems dados de baja no cuentan | `integration/test_reportes_liquidaciones.py::test_item_con_baja_logica_no_suma` |
| Rango · detalle truncado con totales completos | `integration/test_reportes_bordes.py::test_limite_500_sobre_1200_filas_con_totales_completos` |
| Rango · orden estable del detalle | `integration/test_reportes_bordes.py::test_orden_estable_por_inicio_e_id` |
| Rango · límite fuera de rango | `integration/test_reportes_bordes.py::test_limite_y_fechas_invalidas_devuelven_422` |
| Rango · fechas faltantes o invertidas | `integration/test_reportes_bordes.py::test_limite_y_fechas_invalidas_devuelven_422` |
| Rango · metadatos de la consulta | `integration/test_reportes_bordes.py::test_metadatos_comunes_de_la_consulta` |
| Rango · totales calculados en el servidor | `integration/test_reportes_agenda.py` (totales) + frontend `pages/ReportesPage.test.tsx` (muestra 99 aunque `por_estado` sume 5) |
| RBAC reportes · administrador los cuatro | `integration/test_reportes_rbac.py::test_matriz_completa_de_acceso` |
| RBAC reportes · odontólogo solo sus agregados | `integration/test_reportes_rbac.py::test_odontologo_solo_sus_agregados_y_403_con_otro_profesional` |
| RBAC reportes · odontólogo lee liquidaciones | `integration/test_reportes_rbac.py::test_matriz_completa_de_acceso` |
| RBAC reportes · recepción básica | `integration/test_reportes_rbac.py::test_matriz_completa_de_acceso` |
| RBAC reportes · auditor en lectura total | `integration/test_reportes_rbac.py::test_matriz_completa_de_acceso` |
| RBAC reportes · asistente sin acceso | `integration/test_reportes_rbac.py::test_matriz_completa_de_acceso` |
| RBAC reportes · sin token y lectura sin efectos | `integration/test_reportes_rbac.py::test_sin_token_devuelve_401` + `test_lectura_no_audita_ni_modifica_filas` |

## `reportes/exportacion`

| Escenario | Cobertura |
|---|---|
| Paciente · solicitud 202 pendiente | `integration/test_exportaciones_api.py::test_paciente_202_pendiente_y_estado` |
| Paciente · inexistente, inactivo o ajeno | `integration/test_exportaciones_api.py::test_paciente_inexistente_inactivo_o_ajeno_404` |
| Paciente · alcance o campo no declarado 422 | `integration/test_exportaciones_api.py::test_alcance_invalido_campo_extra_y_consultorio_con_paciente_422` |
| Paciente · sin datos clínicos | `integration/test_exportacion_contenido.py::test_paciente_sin_datos_clinicos_exporta_secciones_vacias` |
| Paciente · adjuntos incluidos | `integration/test_exportacion_contenido.py::test_zip_contiene_entidades_conteos_coherentes_adjunto_y_pdf` |
| Consultorio · exportación total 202 | `integration/test_exportaciones_api.py::test_consultorio_202_sin_paciente` |
| Consultorio · paciente declarado 422 | `integration/test_exportaciones_api.py::test_alcance_invalido_campo_extra_y_consultorio_con_paciente_422` |
| Consultorio · todos los pacientes, ningún otro tenant | `integration/test_exportacion_contenido.py::test_exportacion_de_consultorio_no_incluye_otro_tenant` |
| Consultorio · directorio de usuarios sin credenciales | `integration/test_exportacion_contenido.py::test_secretos_ausentes_y_directorio_de_usuarios_sin_hash` |
| ZIP · entradas obligatorias | `integration/test_exportacion_contenido.py::test_zip_contiene_entidades_conteos_coherentes_adjunto_y_pdf` |
| ZIP · conteos coherentes | mismo test (manifiesto = JSON = CSV) |
| ZIP · secretos y credenciales ausentes | `integration/test_exportacion_contenido.py::test_secretos_ausentes_y_directorio_de_usuarios_sin_hash` |
| ZIP · PDF legible y no vacío | `integration/test_exportacion_contenido.py::test_zip_contiene_entidades_conteos_coherentes_adjunto_y_pdf` |
| ZIP · auditoría y comunicaciones incluidas | `integration/test_exportacion_contenido.py::test_zip_contiene_entidades_conteos_coherentes_adjunto_y_pdf` |
| ZIP · volumen por encima del límite | `integration/test_exportacion_contenido.py::test_limite_de_filas_deja_fallida_sin_artefacto` + `test_limite_de_bytes_deja_fallida_sin_artefacto` |
| Generación · el request no espera | `integration/test_exportaciones_api.py::test_paciente_202_pendiente_y_estado` |
| Generación · worker deja lista | `integration/test_reportes_worker.py::test_worker_deja_lista_con_artefacto` |
| Generación · job duplicado no duplica | `integration/test_reportes_worker.py::test_mismo_id_dos_veces_no_duplica_ni_retrocede` + `test_dos_workers_reclaman_y_solo_uno_genera` |
| Generación · fallo transitorio con backoff | `integration/test_reportes_worker.py::test_fallo_transitorio_programa_backoff_y_se_recupera` |
| Generación · fallo definitivo | `integration/test_reportes_worker.py::test_fallo_en_el_maximo_queda_fallida` |
| Generación · Redis caído no pierde | `integration/test_reportes_worker.py::test_barrido_procesa_pendientes_sin_redis` |
| Generación · estado de otro consultorio 404 | `integration/test_exportaciones_rbac.py::test_estado_y_archivo_de_otro_consultorio_404` |
| Descarga · lista 200 zip | `integration/test_exportaciones_api.py::test_descarga_lista_y_409_antes_de_tiempo` |
| Descarga · antes de tiempo 409 | mismo test |
| Descarga · fallida 409 con error | mismo test |
| Idempotencia · solicitud repetida en curso | `integration/test_exportaciones_api.py::test_idempotencia_en_curso_y_un_solo_job` |
| Idempotencia · nueva tras fallo o lista | `integration/test_exportaciones_api.py::test_nueva_exportacion_tras_lista_o_fallida` |
| Disponibilidad · sin cargos ni límites comerciales | `integration/test_exportaciones_api.py::test_idempotencia_en_curso_y_un_solo_job` + `test_nueva_exportacion_tras_lista_o_fallida` |
| RBAC export · administrador ambos alcances | `integration/test_exportaciones_rbac.py::test_administrador_exporta_ambos_alcances` |
| RBAC export · odontólogo paciente propio | `integration/test_exportaciones_rbac.py::test_odontologo_solo_pacientes_propios` |
| RBAC export · odontólogo paciente ajeno 403 | mismo test |
| RBAC export · odontólogo consultorio 403 | mismo test |
| RBAC export · recepción/asistente/auditor 403 y sin token 401 | `integration/test_exportaciones_rbac.py::test_recepcion_asistente_auditor_403_y_sin_token_401` |
| RBAC export · exportación ajena 404 | `integration/test_exportaciones_rbac.py::test_listado_estado_y_archivo_ajenos_404` |
| Auditoría · solicitud | `integration/test_exportaciones_api.py::test_auditoria_solicitar_generar_y_descargar` |
| Auditoría · generación worker | `integration/test_reportes_worker.py::test_worker_deja_lista_con_artefacto` |
| Auditoría · descarga | `integration/test_exportaciones_api.py::test_auditoria_solicitar_generar_y_descargar` |
| Auditoría · solicitud rechazada sin fila | `integration/test_exportaciones_api.py::test_solicitud_rechazada_no_deja_auditoria` |
| Auditoría · sondeo sin auditoría repetida | `integration/test_exportaciones_api.py::test_auditoria_solicitar_generar_y_descargar` |
| Auditoría · exportación inmutable (`P0001`) | `integration/test_core_models.py` y `integration/test_fiscal_auditoria.py` (trigger append-only de `registro_auditoria`) |

## `platform/job-queues`

| Escenario | Cobertura |
|---|---|
| Nombres reservados presentes y exclusivos | `test_queues.py::test_reserved_queue_names_match_spec` + `test_reserved_names_are_exclusive` |
| Exportación encolada en la cola reservada | `integration/test_exportaciones_api.py::test_idempotencia_en_curso_y_un_solo_job` (`reportes:generar`) |
| Cola desconocida rechazada al encolar | `test_queues.py::test_unknown_queue_is_rejected_before_redis` |

## UI funcional

| Escenario | Cobertura |
|---|---|
| Render de totales desde la API | `frontend/src/pages/ReportesPage.test.tsx::muestra los cuatro tableros con los totales de la API` |
| 403 mostrado verbatim | `frontend/src/pages/ReportesPage.test.tsx::muestra un 403 de la API verbatim` |
| Selector de rango/límite | `frontend/src/pages/ReportesPage.test.tsx::envía el rango y el límite elegidos` |
| Exportar, sondear hasta lista y descargar | `frontend/src/pages/ReportesPage.test.tsx::exporta, sondea hasta lista y habilita la descarga` |
| Sin sumas locales | mismo test de totales con totales deliberadamente inconsistentes |
