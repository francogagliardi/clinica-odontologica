# Spec Delta

## MODIFIED Requirements

### Requirement: Seed idempotente y seguro por entorno

El sistema SHALL proveer un seed reproducible e idempotente que cree los cinco roles, el consultorio demo, un administrador con `SEED_ADMIN_PASSWORD`, y el elenco demo completo (odontólogo, recepcionista, asistente y auditor con `SEED_DEMO_PASSWORD`), profesional vinculado, dos sillones, prestaciones, OS Demo, pacientes y turnos ficticios. Ejecutarlo dos veces no SHALL duplicar ni reescribir credenciales.

#### Scenario: Primera ejecución del seed

- **WHEN** se ejecuta el seed con `SEED_ADMIN_PASSWORD` y `SEED_DEMO_PASSWORD` sobre una base migrada y vacía
- **THEN** quedan exactamente 5 roles, 1 consultorio demo, 5 usuarios (administrador y el elenco demo), 1 profesional vinculado al odontólogo, 2 sillones, las prestaciones demo, 1 “OS Demo”, 3 pacientes ficticios y 3 turnos futuros sin solapamiento
- **AND** las contraseñas almacenadas son hashes verificables, no texto plano

#### Scenario: Cada rol demo puede iniciar sesión

- **WHEN** se hace login con cada uno de los cinco usuarios demo
- **THEN** los cinco responden HTTP 200 con sus roles activos y el administrador conserva el rol `administrador`

#### Scenario: Seed sin contraseña configurada

- **WHEN** se ejecuta el seed sin `SEED_ADMIN_PASSWORD`
- **THEN** el proceso aborta con un mensaje que nombra la variable faltante y no deja roles, consultorio ni usuario creados a medias

#### Scenario: Seed sin contraseña del elenco demo

- **WHEN** se ejecuta el seed sin `SEED_DEMO_PASSWORD`
- **THEN** el proceso aborta nombrando la variable faltante y la transacción no deja ningún registro nuevo

#### Scenario: Segunda ejecución no duplica

- **WHEN** se ejecuta el seed dos veces seguidas sobre la misma base
- **THEN** los conteos de roles, usuarios, profesional, sillones, prestaciones, obras sociales, pacientes y turnos son idénticos a los de la primera ejecución y el proceso termina sin error

#### Scenario: Reejecución con otra contraseña no cambia credenciales

- **WHEN** se ejecuta el seed de nuevo con contraseñas distintas a las de la primera corrida
- **THEN** los hashes de los usuarios existentes se conservan intactos y los conteos no varían

#### Scenario: Dos seeds simultáneos no fallan

- **WHEN** se lanzan dos procesos de seed en paralelo sobre la misma base
- **THEN** ambos terminan sin error de unicidad y el resultado sigue siendo un registro por clave natural y exactamente un elenco demo

#### Scenario: Base parcialmente sembrada

- **WHEN** el seed corre sobre una base que ya tiene algunos roles, pacientes o prestaciones pero le faltan otros registros demo
- **THEN** completa solo los faltantes, respeta los existentes y deja los conteos esperados sin duplicar

#### Scenario: Datos ficticios, sin PII real

- **WHEN** se inspeccionan los usuarios, pacientes y turnos creados por el seed
- **THEN** todos usan dominios `.test`, nombres “Demo” y documentos/teléfonos ficticios, sin datos de personas reales
