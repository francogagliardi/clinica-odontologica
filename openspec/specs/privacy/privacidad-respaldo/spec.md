# privacy/privacidad-respaldo Specification

## Purpose
Publica una política de privacidad versionada y entrega un respaldo cifrado verificable, dejando explícito que el alcance legal se valida con asesoramiento humano y no con código. No registra aceptación de privacidad al reservar: el consentimiento informado clínico de prácticas invasivas sigue siendo de C-11.

## Requirements

### Requirement: Política de privacidad pública y versionada

El sistema SHALL publicar sin autenticación `GET /privacidad` con versión, fecha, texto y hash SHA-256, y `GET /privacidad/{version}`. El texto SHALL versionarse en el repositorio y ser inmutable por versión; una versión desconocida SHALL responder 404. La respuesta no SHALL incluir datos personales ni afirmar cumplimiento legal.

**Trazabilidad**: RN-SE-04, `08_arquitectura_propuesta.md` §Seguridad, `03_actores_y_roles.md` §Rutas públicas.

#### Scenario: Consulta de la política vigente

- **WHEN** un visitante sin token hace `GET /privacidad`
- **THEN** responde HTTP 200 con `version`, `vigente_desde`, `texto`, `hash` SHA-256 y `alcance_legal_validado=false`

#### Scenario: Versión desconocida

- **WHEN** se consulta `GET /privacidad/{version}` con una versión que no existe en el build
- **THEN** responde HTTP 404 sin devolver el texto de otra versión

#### Scenario: Hash estable e inmutabilidad por versión

- **WHEN** se consulta dos veces la misma versión, incluso en procesos distintos
- **THEN** el `hash` es idéntico y coincide con el SHA-256 del texto publicado

#### Scenario: Sin autenticación y sin datos personales

- **WHEN** se inspecciona la respuesta de privacidad
- **THEN** no exige Bearer, no incluye pacientes, usuarios, tokens ni secretos, y solo expone el texto público

### Requirement: Respaldo cifrado reproducible

El sistema SHALL proveer un comando reproducible que ejecute `pg_dump` formato custom y lo cifre con AES-256/PBKDF2 usando `BACKUP_PASSPHRASE` obligatoria, generando `.dump.enc` y su SHA-256. SHALL negarse sin passphrase y SHALL ofrecer una verificación que descifre y liste el contenido. Los artefactos SHALL ir a `backups/` gitignored y ninguna clave SHALL persistirse en repo o imagen.

**Trazabilidad**: RN-SE-04, R-08, DD-12/P-05.

#### Scenario: Respaldo y verificación

- **WHEN** se ejecuta el respaldo con una passphrase definida sobre la base demo y luego se ejecuta la verificación con la misma passphrase
- **THEN** se crea un archivo `.dump.enc` con su checksum, la verificación descifra y `pg_restore --list` muestra las tablas sin error

#### Scenario: Passphrase ausente

- **WHEN** se ejecuta el respaldo sin `BACKUP_PASSPHRASE`
- **THEN** el proceso aborta con un mensaje que nombra la variable y no crea archivos parciales

#### Scenario: Passphrase incorrecta

- **WHEN** se verifica el archivo con una passphrase distinta de la usada al respaldar
- **THEN** la verificación falla sin imprimir el contenido y el archivo cifrado no se altera

#### Scenario: Archivo adulterado

- **WHEN** se altera un byte del archivo cifrado
- **THEN** el checksum SHA-256 no coincide y la verificación aborta antes de descifrar

#### Scenario: El cifrado no filtra texto plano

- **WHEN** se inspecciona el archivo `.dump.enc`
- **THEN** no contiene nombres de tablas, datos de pacientes ni la cadena `CREATE TABLE`, y el repositorio no contiene la passphrase ni claves privadas

### Requirement: Alcance legal documentado como validación humana

La documentación y `/privacidad` SHALL declarar que el alcance legal (Ley 25.326/26.529) se valida con asesoramiento humano y SHALL NOT afirmar cumplimiento normativo. La política SHALL indicar versión y vigencia; el respaldo SHALL documentar passphrase, artefactos y verificación.

**Trazabilidad**: RN-SE-04, P-11, DD-12, R-13.

#### Scenario: La política no promete cumplimiento

- **WHEN** se revisa el texto de `/privacidad` y `docs/demo.md`
- **THEN** ambos explican que la validez legal requiere asesoramiento y ninguno afirma “cumplimiento Ley 25.326/26.529”

#### Scenario: El procedimiento de respaldo queda documentado

- **WHEN** un operador sigue el runbook sin conocimiento previo
- **THEN** encuentra la variable requerida, el comando de respaldo, la ubicación gitignored y el comando de verificación

#### Scenario: Sin secretos en la documentación

- **WHEN** se busca la passphrase real o claves en `README.md`, `docs/` y `.env.example`
- **THEN** solo aparecen placeholders y la instrucción de generarla por entorno

### Requirement: Página pública de privacidad

La SPA SHALL renderizar `/privacidad` con la versión vigente, fecha, texto completo y hash, y SHALL enlazarla desde `/reservar` de forma informativa, sin edición, checkbox ni bloqueo de la reserva. Un error de la API SHALL mostrarse tal cual y la página no SHALL incluir datos de pacientes ni controles de administración.

**Trazabilidad**: RN-SE-04, R-07, `platform/frontend-baseline`, C-17 fuera de alcance.

#### Scenario: Lectura de la política

- **WHEN** un visitante abre `/privacidad`
- **THEN** ve la versión vigente, la fecha, el texto y el hash, y un enlace de regreso a la reserva

#### Scenario: Enlace informativo desde la reserva

- **WHEN** se inspecciona `/reservar`
- **THEN** hay un enlace visible a `/privacidad`, sin checkbox, sin casilla premarcada y sin paso de aceptación

#### Scenario: La privacidad no bloquea la reserva

- **WHEN** un visitante completa una reserva válida con el contrato de C-07, sin campos de aceptación
- **THEN** la API responde HTTP 201 y no devuelve 422 ni 409 por privacidad

#### Scenario: Error de la API

- **WHEN** `GET /privacidad` falla o devuelve 404
- **THEN** la página muestra el mensaje del backend sin inventar un texto local
