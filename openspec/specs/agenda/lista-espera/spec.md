# agenda/lista-espera Specification

## Purpose
Gestiona la lista de espera FIFO de un consultorio y el ciclo completo de un hueco liberado: alta de entradas, selección compatible por orden, retención atómica del horario, oferta con vencimiento, rotación al siguiente y conversión a turno sin solapamiento, liberando el horario cuando nadie acepta.

## Requirements

### Requirement: Alta de entrada en la lista de espera

El sistema SHALL crear una entrada `pendiente` con paciente, prestación y profesional opcional activos y del consultorio, asignando un `orden` monótono que define el FIFO. SHALL exigir prestación y SHALL rechazar con 409 una segunda entrada `pendiente` del mismo paciente, prestación y profesional (o sin profesional).

**Trazabilidad**: RN-TU-05 (`05_reglas_de_negocio.md:11`), US-003/CA-1 (`06_funcionalidades.md:24–29`), `04_modelo_de_datos.md:55–57` §EntradaListaEspera, R-04.

#### Scenario: Alta válida toma el siguiente orden
- **WHEN** un recepcionista autenticado hace `POST /lista-espera` con un paciente y una prestación activos
- **THEN** el sistema responde HTTP 201 con `estado=pendiente` y un `orden` mayor que el de la entrada anterior

#### Scenario: Entrada pendiente duplicada
- **WHEN** se intenta dar de alta la misma combinación paciente + prestación + profesional que ya tiene una entrada `pendiente`
- **THEN** el sistema responde HTTP 409 y no crea una segunda fila

#### Scenario: Recurso inexistente, inactivo o de otro consultorio
- **WHEN** el alta referencia un paciente, prestación o profesional inexistente, dado de baja o de otro consultorio
- **THEN** el sistema responde HTTP 404 con el recurso faltante y no crea la entrada

#### Scenario: Cuerpo inválido o campo extra
- **WHEN** el alta omite la prestación, envía un `orden` o `estado` manual, o incluye un campo no declarado
- **THEN** el sistema responde HTTP 422 y no crea la entrada

### Requirement: Baja de una entrada pendiente

El sistema SHALL permitir dar de baja una entrada solo mientras esté `pendiente`, retirándola del FIFO mediante baja lógica. Una entrada `ofrecido`, `convertido` o `vencido` no SHALL poder retirarse con 409, para no cortar una oferta en curso ni falsear una conversión.

**Trazabilidad**: RN-TU-05, `04_modelo_de_datos.md:55–57` §EntradaListaEspera, R-04, RN-SE-02.

#### Scenario: Baja de una entrada pendiente
- **WHEN** un recepcionista hace `DELETE /lista-espera/{id}` sobre una entrada `pendiente`
- **THEN** responde HTTP 200 y la entrada deja de aparecer en `GET /lista-espera` sin borrar su historial

#### Scenario: Baja de una entrada ofrecida
- **WHEN** se intenta dar de baja una entrada en estado `ofrecido`
- **THEN** responde HTTP 409 y la oferta continúa vigente hasta aceptarse, rechazarse o vencer

#### Scenario: Entrada inexistente o de otro consultorio
- **WHEN** el id no existe, ya fue dado de baja o pertenece a otro consultorio
- **THEN** responde HTTP 404 y no modifica nada

#### Scenario: Una entrada dada de baja no recibe ofertas
- **WHEN** se libera un hueco compatible después de dar de baja la única entrada pendiente
- **THEN** no se crea oferta ni mensaje y el hueco queda disponible públicamente

### Requirement: Selección FIFO con compatibilidad

Ante un hueco liberado, el sistema SHALL seleccionar la entrada `pendiente` de menor `orden` cuya prestación coincida y cuyo profesional sea compatible: si la entrada fija un profesional, SHALL ser el del hueco; si no lo fija, SHALL aceptar el profesional del hueco. El sillón de la oferta SHALL ser el sillón liberado. Las entradas `ofrecido`, `convertido` o `vencido` no SHALL ser candidatas.

**Trazabilidad**: RN-TU-05 (`05_reglas_de_negocio.md:11`), Flujo 5 paso 1 (`07_flujos_principales.md:51–54`), US-003/CA-1, `04_modelo_de_datos.md:55–57`.

#### Scenario: Dos entradas compatibles
- **WHEN** se cancela un turno y hay dos entradas compatibles con distinto `orden`
- **THEN** solo la de menor `orden` pasa a `ofrecido` y recibe el mensaje de oferta

#### Scenario: Primera entrada incompatible por profesional
- **WHEN** la entrada de menor `orden` fija un profesional distinto al del hueco y la siguiente no fija profesional
- **THEN** la primera sigue `pendiente` y la segunda recibe la oferta

#### Scenario: Entrada sin profesional acepta cualquier hueco de su prestación
- **WHEN** el hueco pertenece a un profesional distinto al habitual de la entrada sin `profesional_id`
- **THEN** la entrada se ofrece, registra el profesional del hueco en `oferta_profesional_id` y conserva el sillón liberado en `oferta_sillon_id`

#### Scenario: Sin entradas compatibles
- **WHEN** no existe ninguna entrada `pendiente` de la prestación del hueco
- **THEN** no se crea entrada ofrecida, ni retención, ni mensaje, ni trabajo de cola, y el hueco permanece disponible

### Requirement: Oferta con vencimiento y rotación

La oferta SHALL retener el hueco con el profesional, sillón, inicio y fin liberados y `oferta_expira_en = now + TTL` configurable. Al vencer o rechazarse, el sistema SHALL liberar esa retención, marcar la entrada `vencido` y ofrecer el mismo hueco a la siguiente entrada compatible; si el horario ya no está libre, NO SHALL ofrecerlo ni crear una nueva retención.

**Trazabilidad**: US-003/CA-2 (`06_funcionalidades.md:28`), Flujo 5 paso 2 y casos de error (`07_flujos_principales.md:55–57`), RN-TU-05, R-06.

#### Scenario: Vencimiento rota al siguiente
- **WHEN** vence la oferta de la entrada con menor `orden` y existe otra compatible
- **THEN** la primera queda `vencido` y libera su retención, la segunda pasa a `ofrecido` reteniendo el mismo horario, recibe nueva fecha de vencimiento y se encola un nuevo mensaje

#### Scenario: Hueco ya ocupado al rotar
- **WHEN** al vencer la retención el horario fue reservado por otra vía
- **THEN** no se ofrece a la siguiente entrada, no se crea una nueva retención, la entrada vencida no se convierte y no se crea ningún turno

#### Scenario: Vencimiento en el borde exacto
- **WHEN** `oferta_expira_en` es exactamente igual al instante de evaluación
- **THEN** la oferta se considera vencida, la retención deja de bloquear y se procesa la rotación

#### Scenario: Última entrada sin aceptación
- **WHEN** vence la oferta de la última entrada compatible
- **THEN** no queda ninguna oferta activa ni retención, y `GET /reservar/{slug}/disponibilidad` vuelve a mostrar el hueco

### Requirement: Conversión a turno sin solapamiento

Al aceptarse una oferta, el sistema SHALL reclamar la entrada de forma atómica y crear el turno con las reglas de C-06 (duración, agenda, bloqueos y anti-solapamiento) usando el profesional, el sillón y el horario retenidos, sin elección del paciente. La entrada SHALL quedar `convertido` con su `turno_id` y la retención SHALL liberarse en la misma transacción; exactamente una aceptación SHALL ganar.

**Trazabilidad**: RN-TU-01 (`05_reglas_de_negocio.md:7`), RN-TU-05/RN-NO-02 (`:11,39`), Flujo 5 paso 2, `04_modelo_de_datos.md` §Turno, R-10.

#### Scenario: Aceptación convierte la entrada
- **WHEN** se acepta una oferta vigente y el hueco sigue retenido
- **THEN** responde HTTP 200 con el turno creado en el profesional, sillón y horario retenidos, la entrada queda `convertido` con `turno_id`, la retención deja de existir y se programan los recordatorios

#### Scenario: Retención vencida y horario ya tomado
- **WHEN** la retención venció sin barrido y otra reserva ocupó el horario antes de la aceptación
- **THEN** responde HTTP 409, la entrada queda `vencido`, no se crea turno y se ofrece al siguiente compatible

#### Scenario: Dos aceptaciones concurrentes
- **WHEN** dos peticiones aceptan simultáneamente la misma oferta
- **THEN** exactamente una crea el turno y la otra responde 409 o 410, sin filas duplicadas ni doble retención

#### Scenario: Reserva pública simultánea al vencer la retención
- **WHEN** la retención vence y una reserva pública y la aceptación compiten por el mismo horario
- **THEN** solo una crea turno y la otra recibe el conflicto, sin solapamiento en la base

### Requirement: Retención atómica del hueco ofrecido

Al ofrecerse un hueco, el sistema SHALL retenerlo con el profesional, sillón, inicio y fin liberados y `oferta_expira_en`, de forma atómica: una exclusion constraint SHALL impedir dos retenciones solapadas. La retención SHALL ocultar el slot de la disponibilidad pública y del backoffice y bloquear altas y reprogramaciones. SHALL liberarse al convertir, rechazar o vencer.

**Trazabilidad**: RN-TU-05 (`05_reglas_de_negocio.md:11`), RN-TU-01 (`:7`), Flujo 5 (`07_flujos_principales.md:51–57`), `agenda/turnos` §Reservas bloqueadas por retenciones, `agenda/reserva-publica`, `agenda/recursos-agendables`.

#### Scenario: La cancelación retiene el hueco
- **WHEN** se cancela un turno y una entrada compatible pasa a `ofrecido`
- **THEN** la entrada guarda el profesional, sillón, inicio y fin liberados con su vencimiento, y `GET /reservar/{slug}/disponibilidad` y `GET /profesionales/{id}/disponibilidad` ya no muestran ese horario

#### Scenario: La aceptación libera la retención
- **WHEN** la oferta se convierte en turno
- **THEN** la entrada deja de estar `ofrecido`, no queda ninguna retención activa para ese rango y el turno creado es el único ocupante del horario

#### Scenario: Dos cancelaciones no retienen dos veces el mismo horario
- **WHEN** dos cancelaciones concurrentes liberan rangos que se solapan y ambas buscan entrada compatible
- **THEN** solo una retención se crea y la otra oferta se descarta sin dejar una segunda entrada `ofrecido` sobre el mismo rango

#### Scenario: Retención vencida sin barrido no bloquea
- **WHEN** existe una entrada `ofrecido` con `oferta_expira_en <= now` que el worker todavía no procesó
- **THEN** la disponibilidad vuelve a mostrar el horario y un alta normal puede reservarlo con HTTP 201

#### Scenario: El rechazo libera y el siguiente retiene
- **WHEN** el paciente rechaza la oferta
- **THEN** su retención se libera y la siguiente entrada compatible retiene el mismo profesional, sillón, inicio y fin

#### Scenario: Nadie acepta y no queda retención
- **WHEN** vence la última oferta compatible sin aceptación
- **THEN** no queda ninguna entrada `ofrecido` ni retención para ese rango y el horario aparece disponible públicamente

### Requirement: Acceso a la lista de espera por rol

El alta y la baja SHALL exigir rol `administrador` o `recepcionista`; el odontólogo SHALL leer las entradas de sus propios profesionales; asistente y auditor SHALL solo leer. Toda respuesta SHALL limitarse al consultorio del usuario y toda petición sin token SHALL responder 401.

**Trazabilidad**: RN-SE-01 (`05_reglas_de_negocio.md:44`), `03_actores_y_roles.md:20–27` §RBAC (Agenda/Turnos), R-03.

#### Scenario: Recepción administra la lista
- **WHEN** un recepcionista crea, lista y da de baja una entrada
- **THEN** responde HTTP 201, 200 y 200 respectivamente

#### Scenario: Odontólogo intenta crear o borrar
- **WHEN** un odontólogo hace `POST` o `DELETE` en `/lista-espera`
- **THEN** responde HTTP 403 y la lista no cambia

#### Scenario: Asistente y auditor solo leen
- **WHEN** un asistente o auditor hace `GET /lista-espera`
- **THEN** responde HTTP 200; cualquier alta o baja responde HTTP 403

#### Scenario: Sin token o consultorio ajeno
- **WHEN** la petición no trae Bearer válido o el recurso pertenece a otro consultorio
- **THEN** responde HTTP 401 o HTTP 404 respectivamente, sin filtrar datos
