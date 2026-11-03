# Auditoría de escenarios — c-05-pacientes-cobertura-base

Fecha: 2026-11-03. Auditoría con la skill `spec-scenario-auditor` sobre las delta specs del change, antes de implementar.
Alcance: `pacientes/registro-pacientes` (22 escenarios) y `comercial/obras-sociales` (16 escenarios).

## Matriz de trazabilidad

| Requirement | Regla KB | Escenario esperado | Error de negocio | Borde | Veredicto |
|---|---|---|---|---|---|
| Registro y ficha de pacientes | `04_modelo_de_datos.md` §Paciente (líneas 32–36); RN-TU-01 (`05_reglas_de_negocio.md`); DD-11 (`09_decisiones_y_supuestos.md:85`) | sí (alta + ficha) | sí (DNI duplicado 409) | sí (baja lógica libera DNI) | OK |
| Búsqueda de pacientes con criterio obligatorio | `04_modelo_de_datos.md` §Paciente (índices); RN-SE-01 (`05_reglas_de_negocio.md:44`); R-07 (`AGENTS.md`) | sí (apellido por prefijo) | sí (sin criterio 422: no hay volcado de datos) | sí (baja excluida / lista vacía) | OK |
| Cobertura declarada del paciente | `04_modelo_de_datos.md` §Paciente y §ObraSocial/Convenio (74–75); RN-OS-01 (`05_reglas_de_negocio.md:30–33`) | sí (alta con OS) | sí (OS inexistente/baja 404) | sí (quitar cobertura limpia afiliado) | OK |
| Control de acceso al registro de pacientes | RN-SE-01 (`05_reglas_de_negocio.md:44`); matriz (`03_actores_y_roles.md:20–27`) | sí (recepción crea/edita) | sí (roles no escriben 403) | sí (sin token 401) | OK |
| Administración de convenios de obra social | RN-SE-01; matriz columna Obras sociales (`03_actores_y_roles.md:22–27`); `04_modelo_de_datos.md` §ObraSocial/Convenio; DD-11 | sí (alta + lectura) | sí (nombre duplicado 409) | sí (baja libera nombre; asistente 403) | OK |
| Reglas locales de cobertura validadas | RN-OS-01/RN-OS-02 (`05_reglas_de_negocio.md:30–33`); DD-11 | sí (reglas 60/40 completas) | sí (suma > 100 / código inexistente 422) | sí (`{}` y códigos duplicados) | OK |
| Validación externa deshabilitada en v1 | DD-11 (`09_decisiones_y_supuestos.md:85`); R-12 (`AGENTS.md`) | sí (`false` por defecto) | sí (`true` → 422) | sí (`false` explícito, agregado en esta auditoría) | OK |

## Huecos detectados

- **Validación externa deshabilitada en v1** — faltaba un escenario de borde. Se agregó: **WHEN** el alta envía `validacion_externa=false` explícito **THEN** responde 201 igual que omitido y persiste `false` (respaldo: DD-11).
- **Registro y ficha de pacientes** — el escenario de DNI duplicado decía «el índice impide por SQL directo» pero ninguna tarea lo verificaba. Se amplió 3.1 para probar el rechazo por SQL directo.
- **Administración de convenios de obra social** — mismo caso para el nombre duplicado; se amplió 6.1.
- **Búsqueda de pacientes** — el `EXPLAIN` podía dar `Seq Scan` por el tamaño de la tabla de prueba; se aclaró que se ejecuta con `enable_seqscan=off`.

## Escenarios no verificables

- Ninguno: todos los `THEN` se observan por HTTP (status + body), por índice/CHECK en PostgreSQL o por el comando de verificación declarado en `tasks.md`.

## Escenarios sin tarea de verificación

- Ninguno: los 38 escenarios quedan cubiertos por las tareas 3.1, 4.1, 5.1, 6.1, 6.2, 7.1 y 1.1–1.2.

## Deriva de dominio (KB vs spec)

- **Unicidad de nombre de obra social sin distinguir mayúsculas** — la KB describe el atributo `nombre` (04, §ObraSocial/Convenio) pero no exige unicidad ni insensibilidad a mayúsculas. Se adopta como invariante de diseño para evitar convenios duplicados, igual que `matricula` en C-04. No contradice la KB; si la cátedra pide permitir homónimos, se ajusta el índice.
- **Teléfono solo móvil `+549…`** — la KB exige «teléfono (WhatsApp)» (04, §Paciente) y C-05 pide validación de formato argentino; restringir a celular es una decisión de diseño (D3), no una regla literal. Un fijo se rechaza porque no puede recibir WhatsApp.
- **`validacion_externa=true` rechazado** — DD-11 dice que v1 valida con reglas locales y que la obra social real llega en la segunda iteración; rechazar el flag es una decisión derivada (D7) para no prometer una integración inexistente, alineada con R-12. Queda registrada como restricción de v1, no como regla de dominio.
- **RBAC de pacientes** — la matriz no tiene columna «Pacientes»; el mapeo a recepción (lectura amplia, alta/edición recepción, baja solo admin) es una decisión trazada a RN-SE-01 y documentada en design D9.

## Veredicto

**LISTO PARA APPLY** — sin huecos de escenarios ni deriva bloqueante. Las decisiones sin regla literal (unicidad de nombre, teléfono móvil estricto, `validacion_externa=false` en v1, RBAC de pacientes) están documentadas en `design.md` D3/D7/D9 para revisión del usuario.
