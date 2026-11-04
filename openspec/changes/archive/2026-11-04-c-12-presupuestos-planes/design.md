# Design

## Context

C-01–C-11 dejaron agenda, pacientes, comunicaciones, lista de espera e historia clínica con consentimientos. El head de Alembic es `0010_historia_clinica`; el "007" que menciona `CHANGES.md` para este change está desactualizado y la migración real es `0011_presupuestos`.

Restricciones que mandan sobre el diseño:

- Governance **ALTO**: el presupuesto alimenta cobros (C-13) y facturación/liquidaciones (C-14), así que importes, cobertura y estados no pueden quedar inconsistentes ni depender del cliente (R-02, R-04, R-11, RN-CL-02, RN-OS-02).
- Patrones existentes que se reutilizan: `AuditMixin` + baja lógica, `RegistroAuditoria` append-only con trigger `P0001` (C-02), `UnitOfWork`/repositorios que nunca commitean, Pydantic `extra='forbid'`, `require_role`, máquina de estados pura como `app/domain/turnos.py`, tests de integración contra PostgreSQL real.
- Datos de entrada: catálogo de prestaciones y OS Demo con `cobertura_porcentaje=60` y `prestaciones_cubiertas=["CONS","LIM","OBT"]` (seed, DD-11).
- Sin frontend en este change: C-12 entrega API, migración y evidencia, igual que C-11.

## Goals / Non-Goals

**Goals:**

- Persistir el presupuesto y sus ítems con importes coherentes calculados siempre en el servidor.
- Calcular cobertura y copago por ítem contra las reglas locales del convenio, con redondeo explícito y sin centavos perdidos.
- Representar la incertidumbre de cobertura (`pendiente_verificacion`) sin bloquear la atención ni la aceptación.
- Ciclo de vida auditable: estados válidos, edición solo en borrador, precios congelados y auditoría en la misma transacción.
- Aplicar la matriz RBAC con una definición explícita de "presupuesto propio".

**Non-Goals:**

- Cobros, señas, Mercado Pago (C-13) y facturación/liquidación (C-14): C-12 solo deja `presupuesto_id` referenciable.
- Validación preventiva contra nomencladores reales (RN-OS-01 externa): v1 usa reglas locales (DD-11).
- UI, PDF, envío por WhatsApp/email y ruta pública de consulta del paciente.
- Cambiar tablas, requisitos o contratos de C-04/C-05/C-06/C-11.

## Decisions

### D1 — Una sola capacidad: `comercial/presupuestos`

El alta, el cálculo, la máquina de estados, el snapshot de precios, la auditoría y el RBAC están acoplados por la misma transacción y el mismo recurso; separarlos en `presupuestos` + `cobertura` duplicaría RBAC y auditoría y obligaría a versionar dos contratos que cambian juntos. `comercial/presupuestos` sigue el dominio "Comercial" de `04_modelo_de_datos.md` y convive con `comercial/prestaciones` y `comercial/obras-sociales`. Se descartó `clinica/presupuestos` porque el presupuesto es una oferta comercial (C-13 lo cobra), no un acto clínico firmado.

### D2 — Migración `0011_presupuestos`, escrita a mano

`down_revision = "0010_historia_clinica"`. Se escribe a mano (como `0010`) porque autogenerate no emite índices parciales, CHECKs de FDI con fórmula ni CHECKs de coherencia de importes. Solo crea `presupuestos` e `items_presupuesto` con índices y CHECKs; no altera ninguna tabla existente, así que el downgrade las dropea sin efectos colaterales.

### D3 — Modelo de datos

| Tabla | Columnas principales | Protección |
|---|---|---|
| `presupuestos` | `id`, `consultorio_id`, `paciente_id`, `profesional_id`, `creado_por`, `estado`, `cobertura_estado`, `subtotal`, `cobertura_calculada`, `copago` + `AuditMixin` | CHECKs de estado, `cobertura_estado`, importes `>= 0` y `subtotal = cobertura_calculada + copago`; baja lógica coherente; índices `(consultorio_id, paciente_id, created_at)` y `(profesional_id, estado)` |
| `items_presupuesto` | `id`, `presupuesto_id`, `prestacion_id`, `pieza`, `cantidad`, `precio_unitario`, `cobertura_item`, `copago_item` + `AuditMixin` | CHECK `cantidad > 0`, importes `>= 0`, `cobertura_item + copago_item = precio_unitario * cantidad`, pieza FDI válida cuando no es nula; índice `(presupuesto_id)` |

Decisiones de modelo:

- `creado_por` (usuario) es una adición de diseño, igual que en `evoluciones`: distingue quién armó la oferta del profesional responsable y es lo que se audita. Un recepcionista no crea presupuestos (matriz `R`), pero un administrador sí puede crear para cualquier profesional.
- `cobertura_calculada` y `copago` son columnas persistidas, no derivadas en lectura: C-13 necesita el importe acordado y C-14 la cobertura informada, y ambos deben sobrevivir aunque cambien las reglas del convenio.
- `items_presupuesto` hereda `AuditMixin`: al editar un borrador los ítems reemplazados se dan de baja lógica, nunca se borran físicamente. No hay unicidad `(presupuesto_id, prestacion_id, pieza)` porque un mismo tratamiento puede cotizarse en dos líneas por decisión del odontólogo; la duplicación no rompe ninguna suma.
- La coherencia **entre** tablas (`subtotal` = suma de ítems) no se puede expresar con un CHECK. Se garantiza calculando los tres totales desde los ítems en la misma transacción y se verifica con tests de integración (HTTP y SQL); no se agrega un trigger de recálculo porque acoplaría la tabla a cada escritura sin aportar más que la transacción única.
- Sin constraint de unicidad por paciente/profesional: un paciente puede tener varios presupuestos (alternativas de tratamiento) y más de un plan `en_curso` (por ejemplo ortodoncia y endodoncia en paralelo). Se documenta como recomendación, no como regla inventada.

### D4 — Cálculo puro, `Decimal` y redondeo half-up

`app/domain/presupuestos.py` no hace I/O y concentra la aritmética que también verifican los tests unitarios:

```
total_item    = (precio_unitario * cantidad).quantize(CENTAVO)
cobertura_item = (total_item * porcentaje / 100).quantize(CENTAVO, ROUND_HALF_UP)
copago_item   = total_item - cobertura_item
subtotal      = Σ total_item
cobertura_calculada = Σ cobertura_item
copago        = Σ copago_item
```

- Se usa `Decimal` de punta a punta (`Numeric(12,2)`), nunca `float`. `ROUND_HALF_UP` es la regla comercial argentina esperada y es determinista: 19,998 → 20,00 (el caso de borde del escenario).
- El copago se obtiene **por resta**, no aplicando `copago_porcentaje`: así `cobertura + copago = total` siempre, aun cuando las reglas de C-05 admitan `cobertura + copago < 100`. `copago_porcentaje` queda como metadata del convenio y no como segunda fuente de verdad.
- Los totales suman ítems ya cuantizados, por lo que no hay diferencias de un centavo entre la suma de líneas y el encabezado.
- `precio_unitario * cantidad` es exacto en dos decimales porque el precio es `Numeric(12,2)` y la cantidad es un entero; aun así se cuantiza por contrato.

Matriz de decisión de cobertura (determinista, testeable):

| Situación del paciente | Resultado |
|---|---|
| Sin `obra_social_id` | `calculada`, cobertura 0, copago = total |
| Convenio activo con `cobertura_porcentaje` definido y prestación en `prestaciones_cubiertas` | `calculada`, cobertura = porcentaje |
| Convenio activo con porcentaje definido y prestación fuera de la lista | `calculada`, cobertura 0 (0 conocido) |
| Convenio con `cobertura_porcentaje` ausente | `pendiente_verificacion`, cobertura 0 |
| Convenio inexistente o con baja lógica | `pendiente_verificacion`, cobertura 0 |
| Proveedor de cobertura no disponible o reglas no interpretables | `pendiente_verificacion`, cobertura 0 |

### D5 — Proveedor de cobertura como seam inyectable

`app/application/presupuestos.py` define:

- `CoberturaConvenio` (porcentaje + conjunto de códigos cubiertos) y `CoberturaNoDisponible`.
- `CoberturaProvider` (Protocol) con `async resolver(uow, paciente) -> CoberturaConvenio | None`, donde `None` significa "no verificable" (pendiente).
- `LocalCoberturaProvider`: lee el convenio del paciente, valida que esté activo y del consultorio, y traduce `reglas_cobertura`. Es la implementación v1 (DD-11).
- `get_cobertura_provider()` como dependencia FastAPI, overridable en tests.

El servicio captura `CoberturaNoDisponible`, deja el presupuesto en `pendiente_verificacion` y responde 201; nunca convierte una caída en 500. Se descartó llamar al cálculo directamente desde el router: el seam permite probar el modo pendiente sin servicio externo (`app.dependency_overrides[get_cobertura_provider]`) y deja el lugar exacto donde entrará un nomenclador real sin reescribir el servicio. Se descartó también un cliente HTTP simulado: agrega configuración y latencia sin aportar cobertura de tests que el fake no dé.

El proveedor **resuelve reglas**, no importes: la aritmética vive en el dominio puro, así el mismo cálculo se testea sin base de datos.

### D6 — Máquina de estados y códigos HTTP

`_TRANSICIONES` en el dominio, con la misma forma que `domain/turnos.py`:

```
borrador  → aceptado | rechazado
aceptado  → en_curso
en_curso  → finalizado
rechazado → ∅        finalizado → ∅
```

- Repetir el estado actual es idempotente: 200, sin UPDATE y sin auditoría nueva.
- Transición inexistente o destino fuera del catálogo: **422**, sin cambios.
- `PUT`, `DELETE` y `recalcular` sobre un presupuesto que salió de `borrador`: **409** (el recurso existe, su estado impide la operación). Se distinguen 422 (transición no prevista) de 409 (operación válida en otro estado) para que el cliente sepa si corregir el destino o el momento.
- `DELETE` solo da de baja lógica un `borrador`; un `rechazado` se conserva como historial comercial.
- No se permite volver a `borrador` desde ningún estado: la oferta entregada no se "desacepta".

### D7 — Snapshot de precio y semántica del recálculo

- Al crear el presupuesto, cada ítem copia el `precio_base` vigente a `precio_unitario`. La copia es la decisión central: un presupuesto es una oferta, y cambiar el catálogo no puede re-preciar retroactivamente algo ya cotizado ni, menos, algo aceptado. `04_modelo_de_datos.md` lista `precio` en `ItemPresupuesto` (no solo la FK a `Prestacion`), lo que respalda guardar el valor.
- `PUT` es reemplazo completo del borrador y **re-cotiza**: cada ítem del cuerpo toma el `precio_base` actual. Es explícito (el odontólogo está editando la oferta) y evita la ambigüedad de "actualizar algunos precios y otros no".
- `POST /{id}/recalcular` solo refresca **cobertura** contra las reglas vigentes del convenio; no toca precios. Sirve para el caso real de una cobertura que estaba pendiente y se corrigió, sin re-cotizar.
- Un presupuesto fuera de `borrador` no cambia precios, cobertura ni totales por ninguna vía de la API.

### D8 - Consentimiento: se difiere al acto clínico (confirmado por el usuario 2026-11-04)

`US-021/CA-3` y RN-CL-03 piden consentimiento firmado para prácticas invasivas, y el roadmap agrega "consentimiento firmado si aplica" al aceptar. Hoy no existe forma de saber si un ítem es invasivo: `Prestacion` no tiene flag y `04_modelo_de_datos.md` no relaciona `Presupuesto` con `Consentimiento` (el ERD cuelga el consentimiento del paciente y de la historia, no del presupuesto).

Decisión: **C-12 no bloquea la aceptación por consentimiento**. El consentimiento se sigue registrando con `POST /pacientes/{id}/consentimientos` (C-11, RN-CL-03) y la exigencia se aplicará cuando se registre la práctica invasiva (C-13/C-14, RN-OS-01 "antes de registrar la práctica"). Fundamentos:

1. Un presupuesto es una cotización, no la práctica: exigir la firma para aceptar un plan que puede ejecutarse semanas después invierte el orden clínico y bloquea la aceptación remota.
2. Inferir invasividad por `especialidad` (opción c) es frágil y crearía una regla de negocio que la KB no tiene.
3. Agregar `requiere_consentimiento` a `Prestacion` (opción b) cambia el contrato de `comercial/prestaciones` y agrega una columna que la KB no define; no se justifica dentro del alcance de C-12.

Se fija en la spec con escenarios propios: la aceptación responde 200 sin consentimiento ni historia clínica, el consentimiento se sigue registrando por C-11, y el cuerpo de aceptación rechaza campos clínicos con 422. **Confirmado por el usuario el 2026-11-04: se mantiene la opción (a).** Si la cátedra exige gatear la aceptación, se agrega `requiere_consentimiento` a `Prestacion` en un change posterior.

Por la misma razón, la aceptación **no exige historia clínica abierta**: la KB no lo pide y C-12 no lo inventa. La cobertura **pendiente tampoco bloquea** la aceptación (RN-OS-02 y Flujo 3: el paciente decide con el copago informado y la clínica verifica después).

### D9 — "Presupuesto propio": dos momentos, un criterio

- **Al crear** no existe fila de presupuesto, así que se reutiliza la definición de C-11: `paciente_propio(uow, usuario, paciente_id)` exige un turno no borrado del paciente con el profesional vinculado al usuario, en estado `reservado|confirmado|en_sala|atendido`. Además el `profesional_id` enviado SHALL ser el del odontólogo autenticado; pedir otro profesional responde 403.
- **Sobre un presupuesto existente** la propiedad es directa: `presupuesto.profesional_id == profesional_del_usuario.id`. No se vuelve a mirar el turno porque el presupuesto pudo crearse en una consulta anterior y el turno pudo cerrarse; atar el acceso al turno haría que un presupuesto aceptado quede inaccesible para su propio autor al día siguiente.
- El administrador no tiene restricción de propiedad (matriz `CRUD`), pero sí de consultorio. Recepcionista, asistente y auditor leen todo el consultorio; el asistente lee todo porque la columna "Presupuestos" dice `R` (a diferencia de la ficha clínica, que decía `RU (asistidos)`).
- Un odontólogo sin fila en `profesionales` recibe 403, igual que en C-11.

### D10 — Contratos HTTP

| Método y ruta | Cuerpo | Respuesta |
|---|---|---|
| `POST /presupuestos` | `{paciente_id, profesional_id, items:[{prestacion_id, pieza?, cantidad}]}` | 201; 404 paciente/profesional/prestación; 422; 403 |
| `GET /presupuestos?paciente_id&profesional_id&estado` | — | 200 lista descendente; 422 query desconocida |
| `GET /presupuestos/{id}` | — | 200 con ítems y totales; 404; 403 |
| `PUT /presupuestos/{id}` | mismo cuerpo completo que el alta | 200; 409 fuera de borrador; 422 |
| `PATCH /presupuestos/{id}/estado` | `{estado}` | 200; 422 transición inválida; 403 |
| `POST /presupuestos/{id}/recalcular` | `{}` (`RecalculoRequest`, extra forbid) | 200; 409 fuera de borrador |
| `DELETE /presupuestos/{id}` | — | 204 borrador; 409 fuera de borrador |

Todos los cuerpos usan Pydantic `extra='forbid'`; por eso `precio_unitario`, coberturas y totales enviados por el cliente son 422 sin lógica adicional. Los endpoints sin query declaran `reject_unexpected_query`; el listado usa `reject_unexpected_query_except("paciente_id","profesional_id","estado")`.

Respuesta de ficha: `id`, `consultorio_id`, `paciente_id`, `profesional_id`, `creado_por`, `estado`, `cobertura_estado`, `subtotal`, `cobertura_calculada`, `copago`, `items[]` (con `prestacion_id`, `pieza`, `cantidad`, `precio_unitario`, `cobertura_item`, `copago_item`) y `created_at`/`updated_at`. Importes como `Decimal` de dos decimales.

### D11 — Estructura de código y transacción

- `app/models/comercial.py`: `Presupuesto` e `ItemPresupuesto` junto a `Prestacion`/`ObraSocial` (mismo dominio Comercial).
- `app/schemas/presupuestos.py`: create/update/response; validadores de items no vacíos, cantidad y FDI; `RecalculoRequest` vacío.
- `app/domain/presupuestos.py`: transiciones, `calcular_item`, `calcular_presupuesto`, constantes y quantización.
- `app/application/presupuestos.py`: `CoberturaProvider`, `LocalCoberturaProvider`, `get_cobertura_provider`, resolución de paciente/profesional/prestaciones, armado de ítems, totales y auditoría.
- `app/api/presupuestos.py`: router; registro en `app/main.py`.
- `app/infrastructure/repositories.py` + `uow.py`: `PresupuestoRepository` (listados por consultorio/paciente/profesional/estado, `get` con ítems activos) e `ItemPresupuestoRepository`.
- Toda la operación ocurre dentro del `UnitOfWork` del request: se persiste el presupuesto, sus ítems y la auditoría, y el `__aexit__` hace commit o rollback. Los repositorios nunca commitean.

### D12 — Auditoría

Se reutiliza `audit.registrar` (C-02) con `entidad='presupuesto'` y las acciones `presupuesto.crear`, `presupuesto.editar`, `presupuesto.recalcular`, `presupuesto.eliminar`, `presupuesto.aceptar`, `presupuesto.rechazar`, `presupuesto.en_curso`, `presupuesto.finalizar`. La fila se inserta después de persistir y antes de responder, dentro de la misma transacción; una validación fallida o un 403 no dejan rastro. IP y `User-Agent` truncado se toman con `client_ip`/`dispositivo` de `app/api/deps.py`.

### D13 — Tests

- **Unitarios** (`tests/unit/test_presupuestos_domain.py`): transiciones válidas/ inválidas e idempotencia; cobertura 0/60/100 %; redondeo `19,998 → 20,00`; `cobertura + copago = total` en cada ítem; totales iguales a la suma; cantidad y porcentaje límite.
- **Integración** (`tests/integration/test_presupuestos*.py`): migración y CHECKs (`23514`), alta con OS Demo y sin cobertura, pendiente por reglas ausentes/convenio inactivo/proveedor caído (override), edición y recálculo, snapshot de precio, máquina de estados (422/409/idempotencia), RBAC completo, auditoría por acción y ausencia de auditoría en rechazos, y `UPDATE`/`DELETE` directo sobre auditoría → `P0001`.
- La evidencia va a `docs/skills-mcp/evidencias/c-12-verificacion-escenarios.md` con la matriz requirement→escenario→test→resultado.

## Risks / Trade-offs

- **[Totales no verificados por constraint entre tablas]** → Se calculan siempre desde los ítems en una única transacción, los CHECKs cubren la coherencia por ítem y los tests comparan encabezado contra suma; un `UPDATE` manual por SQL puede desalinearlos y es un riesgo aceptado y documentado (mismo criterio que otras invariantes de servicio del proyecto).
- **[Cobertura pendiente puede volverse un cajón]** → `pendiente_verificacion` es visible en la ficha, no bloquea, y `POST /{id}/recalcular` permite resolverla cuando se corrige el convenio; C-14 la usará para la validación preventiva real.
- **[El snapshot de precio puede quedar viejo si el catálogo sube]** → Es el comportamiento buscado de una oferta; para re-cotizar existe `PUT` del borrador. Un presupuesto aceptado con precio viejo es una decisión comercial, no un bug.
- **[Sin unicidad de presupuesto activo]** → Varios borradores y varios planes `en_curso` son legítimos; si la cátedra exige "un plan activo", se agrega un índice parcial en un change posterior, no por conveniencia.
- **[Consentimiento no exigido al aceptar]** → Documentado y con confirmación pendiente (D8); el riesgo es de alcance, no técnico.
- **[Proveedor de cobertura como seam sin implementación externa]** → Hoy solo existe `LocalCoberturaProvider`; el Protocol evita reescribir el servicio cuando C-14 conecte un nomenclador, pero agrega una indirección mínima.
- **[Decimal serializado como string]** → Coherente con los importes existentes del proyecto; los clientes deben formatear, no recomputar.

## Migration Plan

1. `alembic upgrade head` crea `0011_presupuestos`: tablas `presupuestos` e `items_presupuesto`, índices y CHECKs.
2. No hay backfill: los presupuestos se crean desde la API; el seed demo (C-16) podrá agregar ejemplos sin tocar esta migración.
3. Rollback: `alembic downgrade 0010_historia_clinica` dropea ambas tablas en orden inverso (`items_presupuesto` antes que `presupuestos`); no afecta tablas de C-01–C-11.
4. El seed existente no cambia: OS Demo ya trae las reglas que estos tests necesitan.

## Open Questions

- **Confirmación requerida antes de `/opsx-apply`**: ¿C-12 debe exigir consentimiento informado al aceptar un plan con prácticas invasivas (opción b, agregando `requiere_consentimiento` a `Prestacion`) o se difiere al registro de la práctica (decisión actual, opción a)? Si se elige b, hay que revisar la spec y el alcance de la migración antes de implementar.
- ¿La cátedra espera un endpoint público para que el paciente consulte el presupuesto aceptado? La matriz le da `R propios`, pero v1 no tiene enlace público para este recurso; se deja para el portal del paciente (US-052).
- ¿Se necesita un PDF o envío por WhatsApp del presupuesto para la demo? C-12 no lo incluye; puede ser un change de frontend/comunicaciones posterior.
