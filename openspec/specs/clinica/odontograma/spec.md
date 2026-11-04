# clinica/odontograma Specification

## Purpose
Registra el estado dental del paciente en notación FDI por pieza y cara, con diagnósticos, preservando cada versión del odontograma como un snapshot inmutable y auditable.

## Requirements

### Requirement: Registro de hallazgos con notación FDI

El sistema SHALL registrar hallazgos por pieza FDI, cara y estado sobre la versión vigente de la historia. Piezas válidas: permanentes 11–18, 21–28, 31–38 y 41–48; temporarias 51–55, 61–65, 71–75 y 81–85. Caras válidas: mesial, distal, vestibular, lingual, oclusal, incisal y completa. `cie10` SHALL ser opcional con formato CIE-10. Pieza, cara, estado o CIE-10 inválidos SHALL responder 422 sin crear versión.

**Trazabilidad**: RN-CL-01 (`05_reglas_de_negocio.md:18`), US-020/CA-1 (`06_funcionalidades.md:46`), `04_modelo_de_datos.md` §HallazgoDental (`:65`), Flujo 3 paso 2 (`07_flujos_principales.md:35`).

#### Scenario: Hallazgo en una pieza permanente
- **WHEN** un odontólogo registra un hallazgo en la pieza `16`, cara `mesial`, estado `caries`, con `cie10=K02.1` para un paciente propio
- **THEN** el sistema responde HTTP 201 con el hallazgo persistido en la versión 1 del odontograma y el CIE-10 almacenado tal cual

#### Scenario: Hallazgo en una pieza temporaria
- **WHEN** se registra un hallazgo en la pieza `75`, cara `oclusal`, estado `obturacion`
- **THEN** el sistema responde HTTP 201 porque `75` es una pieza temporaria válida

#### Scenario: Piezas fuera de la notación FDI
- **WHEN** se intenta registrar un hallazgo en cada una de las piezas `19`, `20`, `29`, `49`, `56`, `86` o `99`
- **THEN** el sistema responde HTTP 422 en todos los casos y no crea ninguna versión
- **AND** el CHECK de PostgreSQL rechaza el `INSERT` directo de esas piezas

#### Scenario: Cara inválida
- **WHEN** se envía `cara=lateral` o `cara=superior`
- **THEN** el sistema responde HTTP 422 y no crea la versión

#### Scenario: Estado clínico inválido
- **WHEN** se envía un `estado` fuera del catálogo clínico permitido (por ejemplo `desconocido`)
- **THEN** el sistema responde HTTP 422 y no crea la versión

#### Scenario: CIE-10 con formato inválido
- **WHEN** se envía `cie10=caries` o `cie10=k021`
- **THEN** el sistema responde HTTP 422 porque no cumple el formato CIE-10

#### Scenario: Historia inexistente
- **WHEN** se registra un hallazgo con el identificador de una historia inexistente o dada de baja
- **THEN** el sistema responde HTTP 404 y no crea la versión

### Requirement: Odontograma versionado por snapshots inmutables

Cada alta o corrección de hallazgo SHALL crear una nueva versión completa: la versión N+1 copia los hallazgos vigentes de N y aplica el cambio, sin modificar N. SHALL existir a lo sumo un hallazgo por pieza y cara por versión, y la versión vigente SHALL ser la de mayor número. Ninguna versión ni hallazgo anterior SHALL modificarse o borrarse por API ni por SQL (`P0001`). Dos escrituras concurrentes no SHALL producir versiones duplicadas.

**Trazabilidad**: RN-CL-01, RN-CL-04 por analogía de inmutabilidad (`05_reglas_de_negocio.md:18,21`), `04_modelo_de_datos.md` §Odontograma (`:64`), US-020/CA-1, R-11.

#### Scenario: Primera versión del odontograma
- **WHEN** se registra el primer hallazgo de una historia sin odontograma previo
- **THEN** se crea la versión 1 con exactamente ese hallazgo y `GET /historia-clinica/{id}/odontograma` devuelve `version=1`

#### Scenario: Segundo hallazgo crea una versión nueva
- **WHEN** se registra un hallazgo en otra pieza sobre una historia con versión 1
- **THEN** se crea la versión 2 con los dos hallazgos vigentes
- **AND** la versión 1 sigue conteniendo solo el hallazgo original

#### Scenario: Corrección de un hallazgo existente
- **WHEN** se registra un hallazgo en la misma pieza y cara que uno vigente, con un estado distinto
- **THEN** se crea una versión nueva donde esa pieza y cara tienen un único hallazgo con el estado nuevo
- **AND** la versión anterior conserva el estado anterior para trazabilidad

#### Scenario: Escrituras concurrentes no duplican versión
- **WHEN** dos peticiones registran hallazgos simultáneamente sobre la misma historia
- **THEN** se crean dos versiones consecutivas sin números repetidos y la versión vigente contiene ambos cambios
- **AND** el índice único `(historia_id, version)` rechaza con SQLSTATE `23505` cualquier intento de duplicar número

#### Scenario: UPDATE directo de una versión
- **WHEN** se ejecuta `UPDATE odontogramas SET version = 99` por SQL directo
- **THEN** PostgreSQL rechaza la operación con SQLSTATE `P0001` y la versión original permanece intacta

#### Scenario: UPDATE o DELETE directo de un hallazgo
- **WHEN** se ejecuta `UPDATE hallazgos_dentales SET estado = 'sano'` o `DELETE FROM hallazgos_dentales` por SQL directo
- **THEN** PostgreSQL rechaza ambas operaciones con SQLSTATE `P0001` y el hallazgo permanece intacto

#### Scenario: Intento de editar un hallazgo por API
- **WHEN** se llama `PUT` o `DELETE` sobre `/odontograma/hallazgos/{id}`
- **THEN** el sistema responde HTTP 405 porque los hallazgos solo se agregan creando una versión nueva, y no cambia ningún dato

### Requirement: Lectura del odontograma por versión

El sistema SHALL exponer la versión vigente del odontograma y cualquier versión histórica por número. Sin versiones registradas SHALL responder 200 con `version` nula y lista vacía. Una versión inexistente SHALL responder 404. Cada hallazgo SHALL devolver pieza, cara, estado, diagnóstico, CIE-10 opcional y fecha.

**Trazabilidad**: US-020/CA-1, `04_modelo_de_datos.md` §Odontograma / HallazgoDental (`:63-65`), RN-CL-01.

#### Scenario: Historia sin odontograma registrado
- **WHEN** se consulta `GET /historia-clinica/{id}/odontograma` de una historia sin hallazgos
- **THEN** el sistema responde HTTP 200 con `version=null` y `hallazgos=[]`

#### Scenario: Lectura de la versión vigente
- **WHEN** existen las versiones 1, 2 y 3 de un odontograma y se consulta la versión vigente
- **THEN** el sistema responde HTTP 200 con `version=3` y exactamente los hallazgos del snapshot 3

#### Scenario: Lectura de una versión histórica
- **WHEN** se consulta `GET /historia-clinica/{id}/odontograma/versiones/1` después de crearse la versión 3
- **THEN** el sistema responde HTTP 200 con los hallazgos originales de la versión 1, sin los cambios posteriores

#### Scenario: Versión inexistente
- **WHEN** se consulta la versión `99` de un odontograma que solo tiene hasta la 3
- **THEN** el sistema responde HTTP 404 y no devuelve hallazgos de otra versión

#### Scenario: Odontograma de otro paciente
- **WHEN** se consulta el odontograma con el identificador de una historia de otro consultorio o paciente
- **THEN** el sistema responde HTTP 404 y no expone datos clínicos

### Requirement: Auditoría de cada versión del odontograma

Toda creación de versión SHALL registrar en la misma transacción una fila de `RegistroAuditoria` con usuario, acción, entidad, identificador de la versión, IP y dispositivo. Una petición rechazada por validación no SHALL dejar versión ni auditoría.

**Trazabilidad**: RN-SE-02 (`05_reglas_de_negocio.md:45`), `security/core-models` §Auditoría append-only, R-11.

#### Scenario: Auditoría de una versión creada
- **WHEN** se registra un hallazgo válido que crea la versión 2
- **THEN** queda una fila `odontograma.versionar` con `entidad='odontograma'`, el `entidad_id` de la versión 2, el usuario, la IP y el dispositivo

#### Scenario: Validación fallida no deja rastro
- **WHEN** se intenta registrar un hallazgo con pieza `19` o cara inválida
- **THEN** la respuesta es HTTP 422 y no existe ni versión nueva ni fila de auditoría asociada

#### Scenario: Una auditoría por versión
- **WHEN** se crean las versiones 1, 2 y 3 en peticiones separadas
- **THEN** existen exactamente tres filas `odontograma.versionar`, una por cada identificador de versión
