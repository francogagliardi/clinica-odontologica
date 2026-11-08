# Design

## Context

Ver `proposal.md` para la motivación. El estado relevante del repo:

- C-14 dejó el head de migraciones en `0013_facturacion_arca`; existen `Cobro`, `CajaDiaria`, `MovimientoCaja`, `Comprobante`, `ComprobanteEnvio`, `LiquidacionObraSocial` e `ItemLiquidacion` con sus totales y estados.
- `Turno` guarda `inicio`/`fin` con zona, `estado` (`reservado|confirmado|en_sala|atendido|cancelado|ausente`), `es_sobreturno` y `color_sobreturno`; `Profesional` guarda `dias_atencion`, `hora_desde`, `hora_hasta` y `duracion_base_min`, que son la base de la ocupación.
- `GET /turnos` ya impone un rango máximo de 62 días (`schemas/turnos.py`), la zona es el offset fijo UTC-3 y los listados usan `reject_unexpected_query_except` para rechazar filtros no declarados.
- `platform/job-queues` fija hoy tres nombres (`whatsapp:send`, `recordatorios:due`, `arca:emitir`) y R-06 prohíbe que Redis sea fuente de verdad. C-14 demostró el patrón de job durable con claim, backoff y barrido de pendientes sin depender de la cola.
- `AuditMixin`, `RegistroAuditoria` append-only, `UnitOfWork`/repositorios, `require_role`, `get_consultorio_demo_id` y `infrastructure/audit.registrar` son los patrones vigentes (R-01..R-05, R-11).
- La SPA usa un router por `pathname` en `App.tsx`, `fetchJson`/`postJson` en `shared/api/client.ts`, sesión en memoria y permisos visuales que nunca reemplazan a la API.
- `backend/requirements.txt` no tiene biblioteca de PDF; la imagen `python:3.12-slim` no trae librerías de sistema para renderizado.

## Goals / Non-Goals

**Goals:**

- Entregar cuatro reportes agregados, deterministas y verificables, con totales calculados en PostgreSQL y rango acotado.
- Exportar el universo completo de un paciente o consultorio en un artefacto único (PDF + JSON + CSV), sin secretos.
- Sacar la generación del request con un job durable y observable, sin convertir Redis en fuente de verdad.
- Aplicar RBAC y auditoría sin reabrir los contratos de C-06/C-13/C-14.

**Non-Goals:**

- Reportes programados, envío por email/WhatsApp, BI o consultas ad-hoc.
- Diseño visual o sistema de componentes (C-17); la UI es funcional.
- Exportación incremental, filtros por rango en la exportación o formatos adicionales (XLSX).
- Retención comercial, cobro por exportar, borrado automático punitivo o cuotas.
- Cambiar tablas o endpoints existentes de agenda, caja, fiscal o liquidaciones.

## Decisions

### D1 — Dos capabilities: consulta agregada y egreso de datos

**Decisión**: `reportes/reportes` cubre las consultas de solo lectura; `reportes/exportacion` cubre solicitud, job, artefacto, descarga, RBAC y auditoría. Ambas comparten el módulo `app/application/reportes.py`, pero se especifican y prueban por separado. `platform/job-queues` recibe un delta MODIFIED por la cuarta cola.

**Por qué**: los reportes son lecturas acotadas con RBAC de tablero; la exportación es un egreso de PII y datos clínicos con ciclo de vida propio (job, artefacto, descarga). Mezclarlas en una capability obligaría a que cada cambio de exportación arrastre los reportes y viceversa. La separación también permite que C-16 endurezca la exportación sin tocar los agregados.

**Alternativa descartada**: una sola capability `reportes`. Menos archivos, pero el propósito y los escenarios de privacidad quedan diluidos y el delta de `platform/job-queues` se vuelve implícito.

### D2 — Reportes sincrónicos acotados; exportaciones asincrónicas

**Decisión**: los cuatro reportes se resuelven en el request con rango obligatorio ≤62 días y detalle ≤1000 filas. La exportación (que no tiene rango y puede abarcar todo el consultorio) siempre se encola: `POST /exportaciones` persiste una fila y responde 202; el worker `reportes` genera el artefacto.

**Por qué**: un reporte de 62 días es una consulta SQL acotada y cabe en el request; una exportación de consultorio recorre todas las entidades, adjuntos binarios y genera PDF/ZIP, por lo que bloquear el request sería el problema que el roadmap pide evitar. DD-07c lista explícitamente "reportes pesados" entre los jobs de Redis, y el test de C-15 exige que el job pesado no bloquee el request.

**Costo**: se agrega una cola, un worker, una tabla y un endpoint de estado. **Beneficio**: el request queda constante, el progreso es observable y un fallo se reintenta sin perder la solicitud.

**Alternativa descartada**: todo sincrónico. Simple, pero una exportación grande mantiene una conexión y memoria del worker web, y contradice el scope de CHANGES.md §C-15.

**Alternativa descartada**: exportación sincrónica solo para paciente y asincrónica para consultorio. Dos caminos, dos contratos y más tests; la exportación de un paciente con adjuntos también puede ser pesada.

### D3 — Redis acelera, PostgreSQL decide: `exportaciones` es el job durable

**Decisión**: la solicitud inserta `exportaciones` y hace `try_enqueue(redis, REPORTES_GENERAR, str(id))` best-effort. El worker hace `BRPOP` de un id y además barre `exportaciones` con `estado='pendiente'` y `proximo_intento <= now()` (o nulo). El claim es un `UPDATE ... WHERE id=:id AND estado='pendiente' AND (proximo_intento IS NULL OR proximo_intento <= now()) AND (reclamado_at IS NULL OR reclamado_at < now() - interval '5 minutes') RETURNING id`. La generación ocurre fuera de la transacción de base y la persistencia usa `WHERE id=:id AND claim_token=:token AND estado='generando'`.

**Por qué**: replica el patrón probado de C-14. Si Redis se cae, el barrido retoma; si el id se duplica, el claim lo descarta; si el proceso muere, el claim vence a los 5 minutos. Mantener un lock de fila durante la generación bloquearía el barrido y alargaría la transacción.

**Estados**: `pendiente → generando → lista | fallida`. Un fallo antes del máximo vuelve a `pendiente` con backoff exponencial (`min(2**intentos, 60)` minutos, tope de 3 intentos por defecto). Al máximo queda `fallida` con `ultimo_error`. Un `lista` nunca vuelve a `generando`; repetir el job es no-op.

**Artefacto**: se guarda en `exportaciones.contenido` (`BYTEA`) para que PostgreSQL siga siendo la única persistencia (R-04) y el volumen de una clínica demo no justifique un volumen Docker adicional. `tamano_bytes` y `generada_at` acompañan al blob.

**Alternativa descartada**: guardar el ZIP en disco o en Redis. Disco agrega un volumen y un estado fuera de PostgreSQL; Redis es volátil y R-06 lo prohíbe para datos durables.

### D4 — PDF con `fpdf2` (Python puro)

**Decisión**: generar el PDF con `fpdf2` pineado en `requirements.txt`. Usar fuentes core (`Helvetica`) con textos en español, tablas por sección, encabezado con consultorio/alcance/fecha UTC-3 y pie con el id de exportación. El PDF es un **resumen legible**: incluye totales y hasta 500 filas por sección, e indica que el detalle completo está en JSON/CSV.

**Por qué**: `fpdf2` es Python puro (sin compilación ni `libpango`/`cairo`), se instala en `python:3.12-slim` sin `apt`, genera PDFs deterministas y soporta tablas y saltos de página. Es la opción de menor riesgo operativo para una demo contenerizada.

**Alternativas descartadas**: `reportlab` funciona y es BSD, pero arrastra `Pillow` y más superficie de build; `WeasyPrint` exige pango/cairo y fuentes del sistema en la imagen, lo que complica el Dockerfile y duplica el tamaño. El PDF no necesita HTML/CSS: el diseño visual es C-17.

**Límite**: si una sección supera 500 filas, el PDF la trunca explícitamente; el estructurado no. Eso evita PDFs de miles de páginas y mantiene el requisito "PDF + estructurado", donde la completitud vive en el estructurado.

### D5 — Estructurado: JSON completo + un CSV por entidad + manifiesto

**Decisión**: el ZIP contiene:

1. `exportacion.pdf`.
2. `datos.json`: objeto con `version: 1`, `exportacion_id`, `alcance`, `generado_en` (UTC-3), `consultorio` y una clave por entidad con su lista de filas.
3. `manifiesto.json`: `exportacion_id`, `alcance`, `generado_en`, `entidades: [{nombre, filas, archivo}]`, `total_filas`, `pdf_secciones` y `exclusiones` (lista de campos no exportados).
4. `csv/<entidad>.csv`: encabezado con las columnas de la entidad y una fila por registro (UTF-8, coma, quoting estándar).
5. `adjuntos/<adjunto_id>_<nombre_saneado>` para los binarios clínicos.

**Por qué**: JSON preserva tipos y relaciones para reimportar; CSV permite abrir cada entidad en una planilla sin parsear el JSON; el manifiesto hace verificable la completitud (conteos) y deja explícito qué se excluyó. Un solo ZIP evita tres descargas y tres estados.

**Alternativa descartada**: JSON único. Portable, pero poco usable para análisis en planilla. **Alternativa descartada**: CSV en ZIP sin JSON. Pierde tipos/estructura y complica la verificación automática.

### D6 — Alcance, entidades y exclusiones

**Decisión**: matriz de entidades incluida:

| Entidad | Paciente | Consultorio |
|---|---|---|
| `pacientes` | el paciente | todos |
| `obras_sociales` | la del paciente | todas |
| `turnos` | los del paciente | todos |
| `historias_clinicas` / `evoluciones` | las del paciente | todas |
| `odontogramas` / `hallazgos_dentales` | los del paciente | todos |
| `adjuntos` | los del paciente (binario + metadata) | todos |
| `consentimientos` | los del paciente | todos |
| `presupuestos` / `items_presupuesto` | los del paciente | todos |
| `prestaciones` | las referenciadas | todas |
| `cobros` / `cajas_diarias` / `movimientos_caja` | los del paciente / sus cajas | todos |
| `comprobantes` / `comprobantes_envios` | los del paciente | todos |
| `liquidaciones_obras_sociales` / `items_liquidacion` | las que tocan sus presupuestos | todas |
| `recordatorios` / `mensajes_whatsapp` | los de sus turnos | todos |
| `entradas_lista_espera` | las del paciente | todas |
| `registro_auditoria` | filas cuyo `entidad_id` es del paciente o sus entidades | todas |
| `usuarios` | no se incluye | id, nombre, email y roles activos |

**Exclusiones obligatorias** (en todos los alcances): `usuarios.hash_password`, `turnos.token_publico`, la tabla de tokens de un solo uso, `comprobantes.claim_token`, `cobros.link_pago`, `proveedor_pago_id`, `proveedor_preferencia_id`, `proveedor_mensaje_id`, `payload_envio`, `respuesta_proveedor`, `mensajes_whatsapp.payload` y cualquier secreto de settings. El manifiesto lista estas exclusiones para que el usuario sepa qué no se exportó.

**Por qué**: RN-SE-03 exige los datos del paciente/consultorio, no credenciales ni material que permita actuar en su nombre. Exportar un `token_publico` o un `link_pago` activo convertiría el ZIP en un vector de acceso; un `hash_password` es material de ataque offline. Los CAE, QR fiscales e importes sí se exportan porque son respaldo fiscal.

**Aislamiento**: toda consulta del exportador filtra por `consultorio_id` resuelto del usuario/tenant demo. Un `paciente_id` de otro consultorio es 404 antes de crear la fila.

### D7 — Un solo artefacto por solicitud en curso

**Decisión**: además de la PK, un índice único parcial sobre `(consultorio_id, solicitado_por, alcance, COALESCE(paciente_id, uuid_nil))` con `WHERE estado IN ('pendiente','generando')` impide dos exportaciones en curso idénticas. El servicio, ante un conflicto, devuelve la fila existente con 202. Una exportación `lista` o `fallida` no bloquea una nueva solicitud.

**Por qué**: el botón de la UI puede repetirse; duplicar jobs idénticos gasta CPU y confunde la lista. La idempotencia es por combinación de alcance/paciente/solicitante, no global: dos usuarios pueden exportar el mismo paciente sin pisarse. Si el índice expresado no está disponible en la versión de PostgreSQL, se implementa con `COALESCE` (portable) y el servicio conserva la misma semántica.

### D8 — Fórmulas de los reportes en SQL

**Decisión**:

- **Agenda**: `total_turnos` y `por_estado` con `COUNT(*) FILTER (WHERE estado=...)`. Ocupación por profesional: `minutos_disponibles` = suma de `(hora_hasta-hora_desde)` por cada fecha del rango cuyo `isodow` esté en `dias_atencion`; `minutos_ocupados` = suma de `EXTRACT(EPOCH FROM (fin-inicio))/60` de turnos `reservado|confirmado|en_sala|atendido` no sobreturno; `ocupacion_porcentaje = ROUND(ocupados*100.0/NULLIF(disponibles,0), 2)`, `0.00` si no hay agenda. Los sobreturnos se informan en `minutos_sobreturno`.
- **Ausentismo**: conteos por estado final (`atendido|cancelado|ausente`); tasas con denominador `atendidos+cancelados+ausentes`; `sin_cierres=true` si el denominador es 0. `turnos_activos` cuenta `reservado|confirmado|en_sala` por separado.
- **Caja**: `total_aprobado = SUM(monto) FILTER (WHERE estado='aprobado')`; totales por medio solo sobre aprobados; `por_estado` sobre todos los cobros del rango; movimientos por `tipo`/`medio`; cajas con sus campos de cierre tal como quedaron persistidos (una caja abierta no se recalcula). Para el odontólogo, el alcance propio se aplica por el `profesional_id` del turno o del presupuesto asociado al cobro.
- **Liquidaciones**: cabeceras con `desde <= :hasta AND hasta >= :desde`; agregados por `(obra_social_id, estado)` y por prestación desde `items_liquidacion` activos; `total_cobertura` y `cantidad_practicas` suman cabeceras, el detalle por prestación suma ítems.

**Fechas**: `desde`/`hasta` son fechas locales; el rango se convierte a `[desde 00:00 -03:00, hasta+1 00:00 -03:00)` para `timestamptz`, igual que `GET /turnos`. Para columnas `date` (cobros, cajas, liquidaciones) se compara directo contra las fechas locales.

**Por qué**: una sola definición por métrica, auditable con `EXPLAIN`, y el cliente no suma nada (R-07). Las fórmulas quedan en la spec como escenarios verificables.

**Detalle**: cada reporte devuelve el detalle ordenado (`inicio, id` o `fecha, id`), acotado por `limite` (default 500, máximo 1000) y acompañado de `total_detalle`/`detalle_truncado`; los agregados se calculan sobre el rango completo, no sobre el detalle truncado.

### D9 — RBAC de reportes y exportación

**Reportes** (matriz `03_actores_y_roles.md` fila Reportes):

| Reporte | Administrador | Odontólogo | Recepción | Auditor | Asistente |
|---|---|---|---|---|---|
| Agenda | todo | propio | sí | sí | 403 |
| Ausentismo | todo | propio | sí | sí | 403 |
| Caja | todo | propio | sí | sí | 403 |
| Liquidaciones | todo | sí (lectura) | 403 | sí | 403 |

El odontólogo se resuelve por `profesionales.usuario_id == current_user.id`; si pide otro `profesional_id`, 403. La recepción no recibe liquidaciones porque su matriz es "R básico" en Reportes y "RU" en Obras sociales, pero el reporte agrega cobertura de todas las OS; se documenta como decisión conservadora.

**Exportación**:

| Alcance | Administrador | Odontólogo | Recepción | Auditor | Asistente |
|---|---|---|---|---|---|
| Paciente | sí | solo pacientes con turno o presupuesto propio | 403 | 403 | 403 |
| Consultorio | sí | 403 | 403 | 403 | 403 |

**Por qué**: la matriz solo otorga "R+export" al administrador. El odontólogo puede exportar la ficha de un paciente que atiende (su matriz clínica es CRUD propio) pero no el consultorio completo ni pacientes ajenos; recepción y auditor quedan en lectura. Exportar es un egreso de PII, no una lectura más.

**Aislamiento**: el listado/estado/archivo filtra por `solicitado_por` para no administradores; el administrador ve todo el consultorio. Un id ajeno responde 404 sin revelar metadatos.

### D10 — Auditoría de exportaciones y no auditoría de reportes

**Decisión**: auditar `exportacion.solicitar` (usuario, IP, dispositivo), `exportacion.generar` / `exportacion.fallida` (usuario nulo, worker), `exportacion.descargar` (usuario, IP, dispositivo). Los reportes y el sondeo de estado no auditan: son lecturas repetitivas y su auditoría ahogaría la tabla sin aportar trazabilidad de escritura. Las solicitudes rechazadas no dejan fila porque la transacción se revierte antes del `registrar`.

**Por qué**: RN-SE-02 pide quién registró qué; el egreso de datos es el evento sensible. Auditar cada refresco de tablero generaría ruido y no es lo que exige la regla. La descarga sí se audita porque es el momento en que los datos salen del sistema.

### D11 — Límites y volumen

**Decisión**:

- Reportes: rango ≤62 días; `limite` default 500/máximo 1000; detalle truncado no altera totales.
- Exportación: `EXPORTACION_MAX_FILAS=50000` por entidad y `EXPORTACION_MAX_BYTES=67108864` (64 MB) para el ZIP. Al excederse, la exportación queda `fallida` con `ultimo_error='limite_excedido:<entidad|campo>'`, no deja artefacto parcial y el usuario puede solicitar otra (por ejemplo, por paciente).
- Sin paginación de la exportación en v1: el alcance es la unidad de partición.
- Sin borrado automático del artefacto: se conserva hasta que una operación futura lo decida; no hay ventana que impida exportar (RN-SE-03).

**Por qué**: una clínica demo no se acerca a los topes; los límites existen para que un error de consulta no agote memoria del worker. El fallo es explícito y recuperable, no silencioso.

### D12 — Modelo y migración `0014_reportes`

**`exportaciones`**:

- `id UUID PK`; `consultorio_id` FK `RESTRICT`; `solicitado_por` FK `usuarios RESTRICT`; `alcance` (`paciente|consultorio`); `paciente_id UUID?` FK `pacientes RESTRICT`; `estado` (`pendiente|generando|lista|fallida`).
- `contenido BYTEA?`, `tamano_bytes BIGINT?`, `generada_at TIMESTAMPTZ?`.
- `intentos INT NOT NULL DEFAULT 0`, `proximo_intento TIMESTAMPTZ?`, `ultimo_error TEXT?`, `claim_token UUID?`, `reclamado_at TIMESTAMPTZ?`.
- `created_at/updated_at` (sin baja lógica: el historial de exportaciones no se borra; no hereda `AuditMixin` para no ofrecer `deleted_at`).
- CHECK `alcance_paciente_coherente`: `(alcance='paciente' AND paciente_id IS NOT NULL) OR (alcance='consultorio' AND paciente_id IS NULL)`.
- CHECK `estado_coherente`: `lista` exige `contenido`, `tamano_bytes>0` y `generada_at`; `pendiente|generando|fallida` los prohíben; `fallida` exige `ultimo_error`; `intentos>=0`; `tamano_bytes IS NULL OR tamano_bytes>0`.
- Índices: `ix_exportaciones_estado_proximo (estado, proximo_intento)`, `ix_exportaciones_consultorio_fecha (consultorio_id, created_at)`, `ix_exportaciones_paciente (paciente_id)`, único parcial `uq_exportaciones_en_curso` sobre `(consultorio_id, solicitado_por, alcance, COALESCE(paciente_id, '00000000-0000-0000-0000-000000000000'::uuid)) WHERE estado IN ('pendiente','generando')`.

**Downgrade**: `DROP TABLE exportaciones`. No se alteran tablas existentes; no hay backfill.

### D13 — API, bordes estrictos y configuración

- `GET /reportes/agenda?desde&hasta&profesional_id&sillon_id&estado&limite`.
- `GET /reportes/ausentismo?desde&hasta&profesional_id&limite`.
- `GET /reportes/caja?desde&hasta&medio&estado&limite`.
- `GET /reportes/liquidaciones?desde&hasta&obra_social_id&estado&limite`.
- `POST /exportaciones` (`alcance`, `paciente_id?`, `extra='forbid'`); `GET /exportaciones?estado&alcance`; `GET /exportaciones/{id}`; `GET /exportaciones/{id}/archivo`.
- Todos los GET usan `reject_unexpected_query_except` con la lista exacta de filtros; los cuerpos Pydantic v2 usan `extra='forbid'`. Las respuestas no incluyen secretos ni rutas internas.
- `Settings` suma `exportacion_max_filas: int = 50000`, `exportacion_max_bytes: int = 67108864`, `exportacion_max_intentos: int = 3`, `reportes_worker_interval_seconds: int = 30`, `exportacion_claim_timeout_seconds: int = 300`; se documentan en `.env.example` y en el entorno falso de tests.
- `app/core/queues.py` suma `REPORTES_GENERAR = "reportes:generar"` a `ALL_QUEUES`; el worker suma el modo `reportes` (`python -m app.workers reportes [--once]`), sin cambiar los modos existentes.

### D14 — UI funcional, sin sistema de diseño

**Decisión**: `frontend/src/features/reportes/api.ts` (tipos + fetches autenticados con `authHeaders()`), `frontend/src/pages/ReportesPage.tsx` en `/reportes` (agregado a `App.tsx`), con:

- Login reutilizando `LoginForm`/`Session` si no hay sesión.
- Selector de reporte (agenda, ausentismo, caja, liquidaciones), rango de fechas y filtros; cada tablero muestra totales y tabla de detalle.
- Botón **Exportar** (paciente o consultorio según rol) que hace `POST`, muestra `estado` y sondea `GET /exportaciones/{id}` hasta `lista`/`fallida` con `setInterval` limpiado al desmontar; al quedar lista habilita la descarga.
- Errores de la API mostrados verbatim con `describeFailure`; ninguna suma, tasa ni validación de negocio en el cliente.
- Sin estilos de diseño ni componentes de C-17: HTML semántico y clases mínimas.

**Por qué**: el change necesita una superficie usable para demostrar US-041, pero el sistema visual está fuera de alcance. La UI no replica cálculos: solo presenta lo que la API ya agregó (R-07).

### D15 — Estrategia de pruebas

- **Unitarias**: fórmulas de ocupación/tasas y armado de manifiesto/secciones PDF; clasificación de entidades; límites y nombres de cola (`ALL_QUEUES` ahora cuatro); backoff del job; saneamiento de nombres de adjuntos.
- **Integración con PostgreSQL real**: migración `0014`; CHECKs e índice único en curso por SQL directo; los cuatro reportes contra un dataset determinista (totales esperados, rango 62 días, filtros, truncación, RBAC, cualquier tenant); exportación de paciente y consultorio (entradas del ZIP, conteos, PDF `%PDF-`, binarios, secretos ausentes); worker (202 sin esperar, claim, duplicado, fallo con backoff, tope, barrido sin Redis); descarga 200/409; idempotencia del POST; auditoría y append-only.
- **Frontend (Vitest)**: render de totales desde API mockeada, error 403 mostrado, botón de exportación que sondea hasta `lista` y habilita descarga, sin sumas locales.
- **Evidencia**: `docs/skills-mcp/evidencias/c-15/` con salidas de tests, `curl` del smoke, ZIP de muestra y verificación de migración; `openspec validate --strict`.

## Risks / Trade-offs

- **ZIP en `BYTEA`** → una exportación mediana infla la tabla; mitigado con `EXPORTACION_MAX_BYTES` y con que el artefacto es regenerable. Si el volumen crece, un change posterior puede moverlo a object storage sin cambiar la API.
- **PDF truncado por sección** → el usuario podría esperar todo en el PDF; mitigado con el aviso explícito y el detalle completo en CSV/JSON.
- **`fpdf2` con fuentes core** → acentos y símbolos fuera de Latin-1 pueden no renderizar; el contenido es español estándar. Si se necesita Unicode completo, se agrega una fuente TTF en un change posterior.
- **Worker no corriendo en demo** → la exportación queda `pendiente`; el Compose de C-16 debe levantar el worker `reportes`. Se documenta en el smoke y en `README`.
- **Ocupación en minutos** → depende de `dias_atencion`/horario vigentes, no del histórico de agenda; un cambio de horario pasado altera la ocupación calculada. Se acepta como definición v1 y se documenta en la spec.
- **Auditoría de filas del paciente** → se selecciona por `entidad_id` de sus entidades; una fila de auditoría con `entidad_id` de otra entidad no se incluye. Es una aproximación trazable, no un grafo perfecto.
- **Exportación de consultorio sin rango** → puede ser grande; los topes la hacen fallar explícitamente y el usuario puede exportar por paciente.
- **Recepción sin liquidaciones** → decisión conservadora sobre "R básico"; si el usuario prefiere que recepción vea el reporte de liquidaciones, es un cambio de una línea en el guard y de un escenario.
- **Retención del artefacto** → se conserva sin purga automática; no hay ventana punitiva, pero la tabla crece. Una purga administrativa queda para un change posterior.

## Migration Plan

1. `alembic upgrade head` aplica `0014_reportes`; solo crea `exportaciones` e índices.
2. Instalar `fpdf2` (ya en `requirements.txt`) y reconstruir la imagen de la API/worker.
3. Configurar `EXPORTACION_MAX_FILAS`, `EXPORTACION_MAX_BYTES`, `EXPORTACION_MAX_INTENTOS` y `REPORTES_WORKER_INTERVAL_SECONDS`; los defaults alcanzan para la demo.
4. Desplegar API + worker `reportes`. El seed no cambia: C-15 no crea datos de demo.
5. Smoke: login admin, abrir `/reportes`, ver los cuatro tableros, exportar un paciente y el consultorio, correr el worker, descargar el ZIP y verificar PDF/JSON/CSV.
6. Rollback: `alembic downgrade 0013_facturacion_arca` elimina `exportaciones`; los artefactos se pierden pero son regenerables y ninguna tabla de dominio se toca.

## Open Questions

- **Dataset de demo**: el seed actual no tiene profesionales, turnos ni cobros; C-16 completará el seed demo. C-15 verifica totales contra un dataset determinista creado por los tests, no contra el seed. ¿Se quiere que C-15 agregue un seed histórico opcional o se deja todo el seed a C-16? No cambia la API ni las tareas de C-15.
- **Purga de artefactos**: v1 no borra exportaciones. ¿Se acepta que la tabla crezca y que una purga administrativa quede para un change posterior? No afecta el contrato de disponibilidad sin cargo.
