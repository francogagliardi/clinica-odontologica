# agenda/agenda-backoffice-ui Specification

## Purpose
Da a la recepción y al odontólogo una agenda visual día/semana/mes por profesional y sillón, con turnos coloreados por estado, bloqueos y sobreturnos diferenciados y reprogramación por arrastre que delega toda validación en la API (US-002).

## Requirements

### Requirement: Login del backoffice con token en memoria

La SPA SHALL autenticar contra `POST /usuarios/login` y mantener el Bearer JWT **solo en memoria**, sin `localStorage` ni cookies. Sin token, `/agenda` SHALL mostrar el formulario de login. Un 401 SHALL mostrarse con el mensaje de la API.

**Trazabilidad**: R-03 (`AGENTS.md`), DD-07b, `03_actores_y_roles.md` §RBAC, RN-SE-01.

#### Scenario: Login exitoso
- **WHEN** un usuario ingresa credenciales válidas y las envía
- **THEN** la agenda carga profesionales y turnos con el header `Authorization: Bearer`
- **AND** `localStorage` y `sessionStorage` no contienen el token

#### Scenario: Credenciales inválidas
- **WHEN** el login responde 401
- **THEN** la página muestra el mensaje de la API y no navega a la agenda

#### Scenario: Sesión perdida al refrescar
- **WHEN** la página se recarga sin token en memoria
- **THEN** se vuelve a mostrar el formulario de login y no se hacen llamadas autenticadas

#### Scenario: Cerrar sesión
- **WHEN** el usuario hace clic en “Salir”
- **THEN** el token se descarta de memoria y la agenda deja de estar visible

### Requirement: Filtros y vistas día, semana y mes

La agenda SHALL permitir elegir profesional, sillón y vista (`día`, `semana`, `mes`), y navegar a la fecha anterior/siguiente. El rango consultado SHALL respetar el límite de 62 días de `GET /turnos`; un rango inválido SHALL mostrar el 422 de la API.

**Trazabilidad**: US-002/CA-1, RN-TU-01, `agenda/turnos` (listado por rango), R-05.

#### Scenario: Vista día
- **WHEN** se elige “día” para una fecha
- **THEN** la grilla muestra las horas de atención y los turnos de ese día

#### Scenario: Vista semana
- **WHEN** se elige “semana”
- **THEN** se muestran siete columnas de día y los turnos de cada una

#### Scenario: Vista mes
- **WHEN** se elige “mes”
- **THEN** se muestra la grilla del mes y los turnos por día, sin superar el rango máximo de la API

#### Scenario: Filtro por profesional y sillón
- **WHEN** se selecciona un profesional o un sillón
- **THEN** la consulta incluye ese filtro y la grilla muestra solo los turnos correspondientes

#### Scenario: Navegación de fechas
- **WHEN** se presiona “anterior” o “siguiente”
- **THEN** el rango se desplaza un día, una semana o un mes según la vista y se vuelve a consultar

#### Scenario: Día sin turnos
- **WHEN** el rango no tiene turnos
- **THEN** la grilla se muestra vacía con un mensaje, sin error de consola

### Requirement: Diferenciación visual por estado, bloqueo y sobreturno

Cada turno SHALL mostrar un color o marca por estado (`reservado`, `confirmado`, `en_sala`, `atendido`, `cancelado`, `ausente`). Los bloqueos SHALL renderizarse como franjas ocupadas y los sobreturnos SHALL llevar marca y color propios, distintos de un turno normal.

**Trazabilidad**: US-002/CA-1 y CA-2, RN-TU-06/RN-TU-07, `agenda/bloqueos`.

#### Scenario: Color por estado
- **WHEN** la grilla renderiza turnos en distintos estados
- **THEN** cada estado tiene una clase/color distinto y una etiqueta accesible

#### Scenario: Bloqueo visible
- **WHEN** el rango incluye un bloqueo del profesional o del sillón
- **THEN** se muestra como franja ocupada con su motivo

#### Scenario: Sobreturno diferenciado
- **WHEN** un turno tiene `es_sobreturno=true`
- **THEN** muestra la marca de sobreturno y `color_sobreturno` del backend, sin confundirse con un turno normal

#### Scenario: Turno cancelado
- **WHEN** un turno está `cancelado` o `ausente`
- **THEN** se muestra atenuado pero visible, sin ocupar visualmente como uno activo

### Requirement: Reprogramación por arrastre sin lógica local

La agenda SHALL permitir arrastrar un turno a otro horario y llamar a `PATCH /turnos/{id}/reprogramar` con el nuevo `inicio`. La UI NO SHALL validar solapamientos, bloqueos ni agenda por su cuenta: SHALL mostrar el 409/422 de la API y dejar el turno en su lugar hasta que la API confirme. Tras un 200 SHALL refrescar la grilla.

**Trazabilidad**: US-002/CA-3, RN-TU-01, R-07 (sin lógica de negocio en el cliente), `agenda/turnos`.

#### Scenario: Reprogramación válida
- **WHEN** se arrastra un turno a un horario libre y la API responde 200
- **THEN** la grilla se refresca y el turno aparece en el nuevo horario

#### Scenario: Colisión al reprogramar
- **WHEN** la API responde 409 por solapamiento o bloqueo
- **THEN** la página muestra el mensaje de la API y el turno queda en su horario original

#### Scenario: Turno cerrado
- **WHEN** se intenta arrastrar un turno `cancelado`, `ausente` o `atendido` y la API responde 422
- **THEN** el error se muestra y la grilla no cambia

#### Scenario: Zona horaria
- **WHEN** se calcula el nuevo `inicio` desde la celda de destino
- **THEN** se envía en ISO con el offset `-03:00` de la API, sin reinterpretar la zona en el navegador

### Requirement: Acciones según el rol

La UI SHALL habilitar la reprogramación a administrador y recepcionista; el odontólogo SHALL poder arrastrar solo los turnos de su propio profesional; asistente y auditor SHALL ver la agenda en modo lectura. La UI SHALL ocultar o deshabilitar la acción, pero un 403 de la API SHALL mostrarse si se fuerza.

**Trazabilidad**: RN-SE-01, `03_actores_y_roles.md` §Matriz (Agenda/Turnos), `agenda/turnos` §Acceso por rol.

#### Scenario: Recepción reprograma
- **WHEN** una recepcionista arrastra cualquier turno
- **THEN** la acción está habilitada y la API decide

#### Scenario: Odontólogo solo sus turnos
- **WHEN** un odontólogo ve un turno de otro profesional
- **THEN** ese turno no es arrastrable; los propios sí

#### Scenario: Asistente y auditor en lectura
- **WHEN** un asistente o auditor abre la agenda
- **THEN** no ve acciones de reprogramación y la grilla sigue siendo visible

#### Scenario: 403 forzado
- **WHEN** la API responde 403 a una acción forzada
- **THEN** el mensaje de la API se muestra y no se modifica la grilla
