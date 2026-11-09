# Spec Delta

## Purpose

Expone el registro append-only que ya protege PostgreSQL como una consulta de solo lectura, filtrable y paginada para administradores y auditores, sin abrir ninguna vía de escritura ni alterar el historial.

## ADDED Requirements

### Requirement: Consulta de auditoría de solo lectura

`GET /auditoria` SHALL devolver filas de `registro_auditoria` ordenadas por `timestamp` descendente y luego por `id` descendente, con id, usuario, email, acción, entidad, entidad_id, IP, dispositivo y timestamp. No SHALL existir endpoint de escritura, y una lectura no SHALL agregar filas ni modificar datos.

**Trazabilidad**: US-040/CA-2, RN-SE-02, `03_actores_y_roles.md` (Auditor), `security/core-models`.

#### Scenario: Lectura paginada del historial

- **WHEN** un administrador autenticado consulta `GET /auditoria` sobre una base con acciones registradas
- **THEN** responde HTTP 200 con las filas más recientes primero y todos los campos de trazabilidad

#### Scenario: Intento de escritura sobre auditoría

- **WHEN** se invoca `POST`, `PUT`, `PATCH` o `DELETE` sobre `/auditoria`
- **THEN** el sistema responde HTTP 405 y el historial queda intacto

#### Scenario: Tabla vacía y auditoría de la lectura

- **WHEN** se consulta la auditoría en una base sin filas, o se compara el conteo antes y después de una lectura autorizada
- **THEN** el primer caso responde HTTP 200 con lista vacía y `total=0`, y la lectura no agrega ninguna fila

#### Scenario: Usuario dado de baja sigue trazado

- **WHEN** la fila de auditoría pertenece a un usuario con baja lógica
- **THEN** la fila sigue apareciendo con su `usuario_id` y el email histórico resuelto, sin romper la consulta

### Requirement: Filtros y paginación acotada

`GET /auditoria` SHALL aceptar `usuario_id`, `entidad`, `accion`, `desde`, `hasta`, `limite` (default 100, máximo 500) y `offset` (≥0). `desde` y `hasta` SHALL ser fechas UTC-3 inclusivas; `total` SHALL contarse antes de paginar. Un parámetro no declarado, límite fuera de rango, offset negativo o rango invertido SHALL responder 422.

**Trazabilidad**: US-040/CA-2, RN-SE-02, R-05, `reportes/reportes` §Rango y detalle acotado.

#### Scenario: Filtros combinados

- **WHEN** se consulta por `usuario_id`, `entidad`, `accion` y un rango de fechas que contiene tres filas
- **THEN** responde HTTP 200 con esas tres filas, `total=3` y solo las coincidentes

#### Scenario: Límite, offset y total

- **WHEN** hay 120 filas coincidentes y se consulta con `limite=50&offset=100`
- **THEN** responde HTTP 200 con 20 filas, `total=120`, `limite=50` y `offset=100`

#### Scenario: Parámetros inválidos

- **WHEN** se envía `limite=0`, `limite=501`, un `offset` negativo, `desde` posterior a `hasta` o un filtro no declarado
- **THEN** el sistema responde HTTP 422 y no ejecuta la consulta

#### Scenario: Bordes inclusivos y orden estable

- **WHEN** dos filas comparten exactamente el mismo `timestamp` y una cae justo en `desde` o `hasta`
- **THEN** ambas se ordenan por `id` descendente de forma reproducible y las fechas de borde se incluyen

### Requirement: Acceso a la auditoría por rol

Solo `administrador` y `auditor` SHALL leer `/auditoria`; `odontologo`, `recepcionista` y `asistente` SHALL recibir 403 y sin token 401. El `auditor` SHALL ser solo lectura en toda la API: cualquier mutación de usuarios, roles, agenda, clínica, caja o reportes SHALL responder 403 sin alterar filas.

**Trazabilidad**: `03_actores_y_roles.md` §RBAC, RN-SE-01, R-03, `security/rbac-guards`.

#### Scenario: Administrador y auditor leen

- **WHEN** un administrador y un auditor consultan `GET /auditoria`
- **THEN** ambos reciben HTTP 200 con el mismo historial

#### Scenario: Roles sin acceso

- **WHEN** un odontólogo, un recepcionista o un asistente consultan `GET /auditoria`
- **THEN** los tres reciben HTTP 403

#### Scenario: Auditor no escribe

- **WHEN** un auditor intenta crear un usuario, cambiar roles, crear un turno, registrar una evolución, cobrar o solicitar una exportación
- **THEN** todas las mutaciones responden HTTP 403 y ninguna fila de dominio ni de auditoría cambia

#### Scenario: Petición sin token

- **WHEN** se consulta `/auditoria` sin `Authorization: Bearer` válido
- **THEN** responde HTTP 401

### Requirement: UI funcional de auditoría

La SPA SHALL ofrecer `/auditoria` para administrador y auditor autenticados, con filtros por usuario, entidad, acción y rango de fechas, tabla de resultados y paginación. La pantalla SHALL ser de solo lectura, sin controles de alta, edición o borrado, y SHALL mostrar los errores de la API tal cual.

**Trazabilidad**: US-040/CA-2, `03_actores_y_roles.md` (Auditor), R-07, `platform/frontend-baseline`, C-17 fuera de alcance.

#### Scenario: Recorrido del visor

- **WHEN** un auditor abre `/auditoria`, inicia sesión y aplica un filtro por acción y fecha
- **THEN** ve la tabla paginada y puede avanzar o retroceder páginas sin controles de escritura

#### Scenario: Error de permisos visible

- **WHEN** un odontólogo abre `/auditoria` con su sesión
- **THEN** la pantalla muestra el 403 de la API sin habilitar filtros ni resultados

#### Scenario: Sin sesión

- **WHEN** se abre `/auditoria` sin sesión
- **THEN** la pantalla pide login y no consulta el historial
