# Spec Delta

## Purpose

Provee generación, verificación de vigencia y consumo atómico de tokens públicos opacos de un solo uso para enlaces de pacientes y recordatorios sin sesión (RN-NO-03). C-03 entrega el servicio y la tabla; los endpoints públicos de negocio y su mapeo a HTTP los montan C-07 y C-09.

## ADDED Requirements

### Requirement: Generación y verificación de tokens opacos públicos

El sistema SHALL emitir tokens aleatorios de 256 bits asociados a un propósito (`tipo`), una entidad y una vigencia temporal, y SHALL verificarlos antes de autorizar una acción pública.

**Trazabilidad**: RN-NO-03 (`05_reglas_de_negocio.md`), `08_arquitectura_propuesta.md` §Seguridad, `03_actores_y_roles.md` §Rutas públicas tokenizadas.

#### Scenario: Emisión y consulta de token válido vigente
- **WHEN** se emite un token con `tipo = "confirmacion_turno"`, entidad y vencimiento futuro, y se verifica antes de expirar con el mismo propósito
- **THEN** el servicio devuelve el registro asociado con `usado = false` y los datos de la entidad

#### Scenario: Token público inexistente
- **WHEN** se verifica una cadena aleatoria que no fue emitida
- **THEN** el servicio rechaza con `TokenNotFoundError`
- **AND** el mensaje de error no contiene el valor crudo recibido

#### Scenario: Token vencido o de otro propósito
- **WHEN** se verifica un token cuya `expira_at` ya pasó, o un token válido presentado para un `tipo` distinto al emitido
- **THEN** el servicio rechaza con `TokenExpiredError` o `TokenPurposeError` respectivamente, sin consumirlo
- **AND** un token de propósito distinto presentado al consumo no se marca como usado

### Requirement: Consumo atómico de un solo uso

El sistema SHALL consumir el token exactamente una vez mediante una única sentencia SQL atómica, de modo que dos peticiones concurrentes nunca ejecuten la acción dos veces. El contrato de error (`TokenAlreadyUsedError`) es el que C-07/C-09 mapean a HTTP 410 Gone.

**Trazabilidad**: RN-NO-03, `CHANGES.md` C-03.

#### Scenario: Consumo exitoso de token por primera vez
- **WHEN** se consume un token vigente no utilizado
- **THEN** el registro queda con `usado = true` y `usado_at` con la marca temporal

#### Scenario: Intento de reutilización de token ya consumido
- **WHEN** se intenta consumir o verificar nuevamente un token ya usado
- **THEN** el servicio rechaza con `TokenAlreadyUsedError` (HTTP 410 en C-07/C-09)

#### Scenario: Consumo concurrente del mismo token
- **WHEN** dos sesiones intentan consumir simultáneamente el mismo token
- **THEN** exactamente una tiene éxito y la otra recibe `TokenAlreadyUsedError`, sin doble ejecución

### Requirement: Token almacenado solo como hash

El sistema SHALL persistir únicamente el digest SHA-256 del token, nunca el valor crudo, para que una filtración de base de datos no entregue enlaces públicos vivos.

**Trazabilidad**: RN-NO-03, R-08 (secretos fuera de repositorios y capas), `08_arquitectura_propuesta.md` §Seguridad.

#### Scenario: Persistencia con digest SHA-256
- **WHEN** se emite un token
- **THEN** la fila guarda `token_hash` de 64 caracteres hexadecimales igual a `sha256(token)` y distinto del valor crudo

#### Scenario: El valor crudo no es recuperable de la base
- **WHEN** se inspeccionan todas las columnas de `tokens_un_solo_uso`
- **THEN** no existe el valor crudo del token ni una columna `token` en claro

#### Scenario: Digest único por emisión
- **WHEN** se emiten dos tokens
- **THEN** sus `token_hash` son distintos y el índice único `uq_tokens_un_solo_uso_token_hash` lo garantiza
