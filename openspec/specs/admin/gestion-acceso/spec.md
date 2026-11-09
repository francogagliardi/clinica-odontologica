# admin/gestion-acceso Specification

## Purpose
Permite al administrador crear y mantener las cuentas del backoffice, asignar los cinco roles fijos de la matriz y activar o desactivar cuentas sin dejar la clínica sin administrador, con cada mutación trazada en la auditoría append-only.

## Requirements

### Requirement: Alta, consulta y edición de usuarios

El sistema SHALL exponer la gestión de usuarios (`POST/GET /usuarios`, `GET/PATCH /usuarios/{id}`) solo para `administrador` activo. El email SHALL normalizarse y ser único entre cuentas no dadas de baja; la contraseña SHALL ser write-only y hasheada; ninguna respuesta SHALL incluir el hash. Otros roles SHALL recibir 403 y sin token 401.

**Trazabilidad**: US-040/CA-1, RN-SE-01, `03_actores_y_roles.md` §RBAC, R-03, `security/rbac-guards`.

#### Scenario: Alta de usuario con roles

- **WHEN** un administrador crea un usuario con nombre, email, contraseña válida y una lista de roles del catálogo
- **THEN** responde HTTP 201 con `id`, email normalizado y roles asignados, sin `hash_password`
- **AND** el usuario puede iniciar sesión con esa contraseña

#### Scenario: Email duplicado

- **WHEN** se intenta crear o editar un usuario con un email que ya pertenece a otra cuenta no dada de baja, incluso con distinta capitalización o espacios
- **THEN** responde HTTP 409 y no se crea ni modifica ninguna cuenta

#### Scenario: Datos inválidos o rol inexistente

- **WHEN** el alta envía un rol que no está en el catálogo, una lista de roles vacía, un email inválido o una contraseña de menos de 8 caracteres
- **THEN** responde HTTP 422 y la transacción no deja usuario creado

#### Scenario: Edición parcial y usuario inexistente

- **WHEN** un administrador envía un `PATCH` con un solo campo editable y luego consulta un `id` inexistente
- **THEN** el primer caso responde HTTP 200 conservando los demás campos y el segundo HTTP 404

#### Scenario: Listado con cuentas inactivas

- **WHEN** un administrador consulta `GET /usuarios` sin filtro y luego con `incluir_inactivos=true` mientras existe una cuenta desactivada
- **THEN** la primera respuesta solo incluye cuentas activas y la segunda incluye la desactivada con su estado, sin exponer hashes

#### Scenario: Acceso denegado por rol o sin token

- **WHEN** un odontólogo, recepcionista, asistente o auditor invoca un endpoint de gestión de usuarios, o la petición no trae Bearer válido
- **THEN** los cuatro roles reciben HTTP 403 en la gestión y la petición sin token HTTP 401, sin ejecutar la operación
- **AND** `GET /usuarios/me` sigue respondiendo HTTP 200 para el rol autenticado

### Requirement: Contraseña administrada sin exponerla

El sistema SHALL permitir a un administrador fijar una nueva contraseña con `POST /usuarios/{id}/password`, hashearla con bcrypt y responder sin el hash. La contraseña anterior SHALL dejar de funcionar de inmediato y la nueva SHALL permitir el login. Una contraseña corta SHALL responder 422 y un usuario inexistente 404.

**Trazabilidad**: US-040/CA-1, RN-SE-01, R-03 (`AGENTS.md`), `security/jwt-auth`, `security/rbac-guards`.

#### Scenario: Cambio de contraseña exitoso

- **WHEN** un administrador cambia la contraseña de un usuario activo y luego ese usuario intenta login con la anterior y con la nueva
- **THEN** el cambio responde HTTP 200 sin hash, el login con la anterior responde 401 y con la nueva responde 200

#### Scenario: Contraseña inválida o usuario inexistente

- **WHEN** se envía una contraseña de menos de 8 caracteres o se apunta a un `id` inexistente
- **THEN** responde HTTP 422 o HTTP 404 respectivamente, sin modificar credenciales

#### Scenario: El hash no se filtra por ningún borde

- **WHEN** se inspeccionan las respuestas de alta, edición, cambio de contraseña y listado
- **THEN** ninguna contiene `hash_password`, la contraseña en claro ni un campo equivalente

### Requirement: Catálogo fijo de roles y asignación

El sistema SHALL exponer `GET /roles` de solo lectura, solo para `administrador`, con los cinco roles sembrados. La asignación SHALL hacerse con `PUT /usuarios/{id}/roles`, que reemplaza el conjunto de forma atómica, ignora duplicados y rechaza roles desconocidos o listas vacías. No SHALL existir alta, edición ni baja de roles por API.

**Trazabilidad**: US-040/CA-1, RN-SE-01, `03_actores_y_roles.md` §RBAC, DD-07b, `security/core-models`.

#### Scenario: Asignación y reemplazo de roles

- **WHEN** un administrador asigna `odontologo` a un usuario y luego reemplaza el conjunto por `odontologo` y `asistente`
- **THEN** ambas respuestas son HTTP 200 y el usuario queda solo con los dos roles del último reemplazo

#### Scenario: Rol desconocido o lista vacía

- **WHEN** el `PUT` incluye `superadmin`, un rol con otro casing no reconocido, o una lista vacía
- **THEN** responde HTTP 422 y el usuario conserva exactamente sus roles anteriores

#### Scenario: Roles repetidos en la misma petición

- **WHEN** el `PUT` envía dos veces el mismo rol o repite una asignación ya existente
- **THEN** responde HTTP 200, no duplica el vínculo y el usuario conserva un solo vínculo por rol

#### Scenario: El catálogo no se puede modificar por API

- **WHEN** se intenta `POST`, `PATCH` o `DELETE` sobre `/roles`
- **THEN** el sistema responde HTTP 405 y el catálogo de cinco roles queda intacto

#### Scenario: Catálogo restringido al administrador

- **WHEN** un odontólogo, recepcionista, asistente o auditor consulta `GET /roles`
- **THEN** los cuatro reciben HTTP 403 y no obtienen el catálogo

### Requirement: Activación y desactivación de cuentas

El sistema SHALL activar y desactivar cuentas con `PATCH /usuarios/{id}` (`activo` booleano), sin borrado físico ni pérdida de historial. Una cuenta desactivada SHALL fallar el login y cualquier token vigente SHALL responder 401; reactivarla SHALL restaurar el acceso. El sistema SHALL rechazar con 409 la desactivación del propio usuario autenticado.

**Trazabilidad**: US-040/CA-1, RN-SE-01/RN-SE-02, `security/rbac-guards`, R-03.

#### Scenario: Desactivación y reactivación

- **WHEN** un administrador desactiva una cuenta y luego la reactiva
- **THEN** la desactivación responde HTTP 200, el login de esa cuenta responde 401 mientras está inactiva y vuelve a responder 200 tras la reactivación

#### Scenario: Token vigente de una cuenta desactivada

- **WHEN** una cuenta obtiene un token y, antes de que expire, un administrador la desactiva
- **THEN** el mismo token responde HTTP 401 en el siguiente request porque los roles y el estado se releen de PostgreSQL

#### Scenario: Auto-desactivación

- **WHEN** un administrador intenta desactivar su propia cuenta
- **THEN** responde HTTP 409 y su cuenta sigue activa

#### Scenario: Usuario inexistente y sin borrado físico

- **WHEN** se intenta desactivar un `id` inexistente o se invoca `DELETE /usuarios/{id}`
- **THEN** el primer caso responde HTTP 404 y el segundo HTTP 405; ninguna fila se elimina

### Requirement: Invariante del último administrador activo

El sistema SHALL rechazar con HTTP 409 toda operación que dejaría cero usuarios activos con el rol `administrador`, incluyendo desactivar o quitar el rol al último administrador. La verificación SHALL ejecutarse en la misma transacción bajo un lock global, para que dos operaciones concurrentes no eliminen a los dos últimos.

**Trazabilidad**: US-040/CA-1, RN-SE-01, `03_actores_y_roles.md` §RBAC, R-04/R-05, design.md D2.

#### Scenario: Quitar el rol al último administrador

- **WHEN** existe un solo administrador activo y se intenta reemplazar sus roles por `odontologo`
- **THEN** responde HTTP 409 con un mensaje que explica que el sistema quedaría sin administrador y sus roles no cambian

#### Scenario: Desactivar al último administrador

- **WHEN** existe un solo administrador activo y se intenta desactivarlo
- **THEN** responde HTTP 409 y la cuenta sigue activa con su rol

#### Scenario: Operación permitida cuando queda otro administrador

- **WHEN** existen dos administradores activos y se desactiva uno, o se le quita el rol a uno de ellos
- **THEN** responde HTTP 200 y queda exactamente un administrador activo

#### Scenario: Auto-remoción con otro administrador

- **WHEN** un administrador se quita a sí mismo el rol `administrador` mientras queda otro administrador activo
- **THEN** responde HTTP 200 y su token pierde el acceso a la gestión de usuarios en el siguiente request

#### Scenario: Auto-remoción del último administrador

- **WHEN** el único administrador activo intenta quitarse a sí mismo el rol `administrador`
- **THEN** responde HTTP 409 y conserva el rol

#### Scenario: Dos desactivaciones concurrentes de los dos últimos administradores

- **WHEN** dos transacciones intentan desactivar simultáneamente a los dos únicos administradores activos
- **THEN** exactamente una responde HTTP 200 y la otra HTTP 409
- **AND** al final queda un administrador activo y ninguna operación parcial

### Requirement: Auditoría de las mutaciones de acceso

El sistema SHALL registrar en `registro_auditoria` exactamente una fila por mutación aceptada de usuarios o roles, con actor, acción, entidad, identificador, IP, dispositivo y timestamp, en la misma transacción. Una operación rechazada o sin cambios efectivos no SHALL dejar fila. El registro SHALL ser append-only y sin contraseñas ni hashes.

**Trazabilidad**: US-040/CA-2, RN-SE-02, `security/core-models` §Auditoría append-only, R-11.

#### Scenario: Fila de auditoría por cambio aceptado

- **WHEN** un administrador crea un usuario, le asigna roles y lo desactiva
- **THEN** quedan tres filas con su `usuario_id`, acciones `usuario.crear`, `usuario.roles` y `usuario.desactivar`, el `entidad_id` del usuario afectado, IP y dispositivo

#### Scenario: Operación rechazada no deja auditoría

- **WHEN** un intento de alta por email duplicado o de quitar el rol al último administrador termina en 409
- **THEN** no se agrega ninguna fila de auditoría y el estado previo queda intacto

#### Scenario: Sin cambios efectivos

- **WHEN** un `PATCH` o un `PUT` de roles envía exactamente los valores que el usuario ya tenía
- **THEN** responde HTTP 200 y no agrega una fila de auditoría nueva

#### Scenario: La auditoría no guarda secretos

- **WHEN** se inspeccionan las filas generadas por un cambio de contraseña o de roles
- **THEN** no contienen la contraseña, el hash ni el valor crudo de ningún token

### Requirement: UI funcional de usuarios y roles

La SPA SHALL ofrecer `/usuarios` para un administrador autenticado: listado con estado y roles, alta, edición, asignación de roles, activación/desactivación y cambio de contraseña. La UI SHALL ocultar acciones no permitidas y SHALL mostrar los errores de la API tal cual, sin replicar validaciones ni reglas de negocio en el cliente.

**Trazabilidad**: US-040/CA-1, R-07 (`AGENTS.md`), `platform/frontend-baseline`, C-17 fuera de alcance.

#### Scenario: Recorrido de administración

- **WHEN** un administrador abre `/usuarios` e ingresa con sus credenciales
- **THEN** ve la lista con nombre, email, estado y roles, y puede crear un usuario y asignarle roles desde la pantalla

#### Scenario: Error de la API visible

- **WHEN** la API responde 409 al intentar desactivar al último administrador
- **THEN** la pantalla muestra el mensaje del backend sin reinterpretarlo y no cambia la fila localmente

#### Scenario: Sin sesión o con rol insuficiente

- **WHEN** se abre `/usuarios` sin sesión, o con una sesión de recepcionista
- **THEN** la primera vista pide login y la segunda muestra el 403 de la API sin habilitar acciones de escritura
