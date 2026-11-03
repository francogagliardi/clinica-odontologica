# comercial/prestaciones Specification

## Purpose
Entrega el catálogo de prestaciones que la agenda y los presupuestos reutilizan: código único, duración variable (RN-TU-02) y seña opcional por prestación con su monto visible (RN-TU-08, DD-10). La escritura es de administración; la lectura queda disponible para los roles que reservan, atienden o auditan.

Nota de procedencia: la KB define la seña como opcional pero no prohíbe un monto cuando no se exige. La coherencia `requiere_sena = false → monto_sena = null` es una decisión de `design.md` D8 de este change, no una regla `RN-*`; se declara aquí para que nadie la lea como regla de negocio inventada.

## Requirements

### Requirement: Catálogo de prestaciones con duración y precio

El sistema SHALL permitir dar de alta, consultar, modificar y dar de baja lógicamente prestaciones con `codigo` único entre activas, `nombre`, `duracion_min > 0`, `precio_base >= 0` y `especialidad` opcional. La escritura SHALL exigir rol `administrador`; la lectura SHALL estar disponible para los roles de agenda y facturación (`administrador`, `odontologo`, `recepcionista`, `asistente`, `auditor`).

**Trazabilidad**: RN-TU-02, RN-SE-01, `04_modelo_de_datos.md` §Prestacion, `06_funcionalidades.md` US-002.

#### Scenario: Alta de prestación y lectura por recepción
- **WHEN** un administrador hace `POST /prestaciones` con código, nombre, duración y precio válidos
- **THEN** el sistema responde HTTP 201 con la prestación creada
- **AND** un recepcionista obtiene HTTP 200 en `GET /prestaciones` y la ve en el catálogo

#### Scenario: Código de prestación duplicado entre activas
- **WHEN** un administrador intenta crear una segunda prestación activa con el mismo `codigo`
- **THEN** el sistema responde HTTP 409 y el índice único parcial lo impide también por SQL directo

#### Scenario: Escritura de prestaciones por un rol no administrador
- **WHEN** un odontólogo, recepcionista, asistente o auditor intenta `POST`, `PUT` o `DELETE` sobre `/prestaciones`
- **THEN** el sistema responde HTTP 403

#### Scenario: Baja lógica libera el código
- **WHEN** un administrador da de baja una prestación y crea otra activa con el mismo `codigo`
- **THEN** el alta responde HTTP 201 y la prestación anterior no aparece en `GET /prestaciones`

#### Scenario: Duración o precio fuera de rango
- **WHEN** el alta o la modificación envía `duracion_min <= 0` o `precio_base < 0`
- **THEN** el sistema responde HTTP 422 y no persiste el cambio
- **AND** los CHECK de PostgreSQL rechazan la misma fila por SQL directo

### Requirement: Seña opcional por prestación (RN-TU-08)

El sistema SHALL modelar la seña como opcional por prestación: si `requiere_sena` es verdadero, `monto_sena` SHALL ser obligatorio y estrictamente positivo; si es falso, `monto_sena` SHALL quedar nulo. La condición de seña y el monto SHALL ser visibles en la respuesta del catálogo para que la reserva pueda informarlos (RN-TU-04).

**Trazabilidad**: RN-TU-04, RN-TU-08, DD-10 (`09_decisiones_y_supuestos.md`), `04_modelo_de_datos.md` §Prestacion.

#### Scenario: Prestación con seña y monto visible
- **WHEN** un administrador crea una prestación con `requiere_sena = true` y `monto_sena > 0`
- **THEN** el sistema responde HTTP 201 y la respuesta muestra `requiere_sena = true` y el `monto_sena` informado

#### Scenario: Seña exigida sin monto
- **WHEN** el alta o la modificación envía `requiere_sena = true` sin `monto_sena`
- **THEN** el sistema responde HTTP 422, porque RN-TU-08 exige que la seña tenga monto
- **AND** el CHECK de PostgreSQL impide persistir la fila por SQL directo

#### Scenario: Monto de seña sin seña exigida
- **WHEN** el alta o la modificación envía `requiere_sena = false` junto con un `monto_sena` no nulo
- **THEN** el sistema responde HTTP 422 por dato incoherente, en lugar de guardar un monto sin efecto

#### Scenario: Monto de seña no positivo
- **WHEN** el alta o la modificación envía `requiere_sena = true` con `monto_sena = 0` o negativo
- **THEN** el sistema responde HTTP 422 y no persiste la prestación

#### Scenario: Quitar la seña de una prestación existente
- **WHEN** un administrador modifica una prestación de `requiere_sena = true` a `false` sin enviar `monto_sena`
- **THEN** el sistema responde HTTP 200 y persiste `monto_sena = null`
