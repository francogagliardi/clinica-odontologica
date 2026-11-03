# Spec Delta

## Purpose

Administra los convenios de obra social del consultorio con su nomenclador de referencia y reglas locales de cobertura, base sobre la que C-12 calculará cobertura y copago por ítem (RN-OS-02) usando el convenio ficticio **OS Demo** mientras no exista integración real (DD-11).

## ADDED Requirements

### Requirement: Administración de convenios de obra social

El sistema SHALL permitir alta, consulta, edición y baja lógica de obras sociales del consultorio. El nombre SHALL ser único entre convenios activos y la baja lógica SHALL liberarlo. El alta y la baja SHALL exigir administrador; la edición SHALL admitir administrador o recepcionista; odontólogo y auditor SHALL solo leer.

**Trazabilidad**: RN-SE-01, `03_actores_y_roles.md` §Matriz de permisos (columna Obras sociales), `04_modelo_de_datos.md` §ObraSocial/Convenio, DD-11.

#### Scenario: Alta de convenio y lectura por odontólogo
- **WHEN** un administrador hace `POST /obras-sociales` con un nombre no repetido, `nomenclador_ref` y reglas válidas
- **THEN** el sistema responde HTTP 201 con el convenio creado
- **AND** un odontólogo autenticado obtiene HTTP 200 en `GET /obras-sociales` y ve ese convenio

#### Scenario: Nombre duplicado entre convenios activos
- **WHEN** se intenta crear un segundo convenio activo del mismo consultorio con el mismo nombre, sin distinguir mayúsculas
- **THEN** el sistema responde HTTP 409 y el índice único parcial lo impide también por SQL directo

#### Scenario: Baja lógica libera el nombre
- **WHEN** un administrador da de baja un convenio y crea otro activo con el mismo nombre
- **THEN** el alta responde HTTP 201 y el convenio anterior no aparece en `GET /obras-sociales`

#### Scenario: Escritura según la matriz de roles
- **WHEN** un recepcionista intenta `POST /obras-sociales` o `DELETE /obras-sociales/{id}`
- **THEN** el sistema responde HTTP 403
- **AND** el mismo recepcionista puede `PUT /obras-sociales/{id}` y recibe HTTP 200

#### Scenario: Asistente sin acceso al módulo de obras sociales
- **WHEN** un asistente autenticado intenta `GET /obras-sociales`
- **THEN** el sistema responde HTTP 403 porque la matriz no le asigna la columna Obras sociales

#### Scenario: Convenio inexistente o inactivo
- **WHEN** se consulta o edita un convenio que no existe o tiene baja lógica
- **THEN** el sistema responde HTTP 404

#### Scenario: Petición sin token
- **WHEN** cualquier endpoint de obras sociales se invoca sin encabezado Bearer válido
- **THEN** el sistema responde HTTP 401

### Requirement: Reglas locales de cobertura validadas

El sistema SHALL persistir `reglas_cobertura` como objeto JSONB y validarlo en el borde: porcentajes de cobertura y copago entre 0 y 100, suma de ambos menor o igual a 100, y códigos de prestación en mayúsculas, sin repetir y existentes en el catálogo activo. Un convenio sin reglas SHALL aceptarse con objeto vacío.

**Trazabilidad**: RN-OS-01/RN-OS-02 (validación preventiva y cálculo por ítem), `04_modelo_de_datos.md` §ObraSocial/Convenio, DD-11, C-04 §`comercial/prestaciones`.

#### Scenario: Convenio con reglas locales completas
- **WHEN** el alta envía `reglas_cobertura` con `cobertura_porcentaje=60`, `copago_porcentaje=40` y `prestaciones_cubiertas=["CONS","LIM"]`
- **THEN** el sistema responde HTTP 201 y devuelve las mismas reglas normalizadas en mayúsculas

#### Scenario: Suma de porcentajes mayor a 100
- **WHEN** el alta envía `cobertura_porcentaje=70` y `copago_porcentaje=40`
- **THEN** el sistema responde HTTP 422 porque la suma no puede superar 100

#### Scenario: Porcentaje fuera de rango
- **WHEN** el alta envía un porcentaje negativo o mayor a 100
- **THEN** el sistema responde HTTP 422 y no persiste el convenio

#### Scenario: Código de prestación inexistente o duplicado
- **WHEN** `prestaciones_cubiertas` incluye un código que no existe en el catálogo activo, o el mismo código repetido
- **THEN** el sistema responde HTTP 422 y no persiste el convenio

#### Scenario: Convenio sin reglas
- **WHEN** el alta omite `reglas_cobertura`
- **THEN** el sistema responde HTTP 201 con `reglas_cobertura` igual a `{}` porque las reglas pueden definirse después

#### Scenario: Reglas con forma inválida
- **WHEN** `reglas_cobertura` se envía como lista, número o string en lugar de objeto
- **THEN** el sistema responde HTTP 422

### Requirement: Validación externa deshabilitada en v1

En v1 la cobertura SHALL validarse solo contra reglas locales, por lo que un convenio con `validacion_externa=true` SHALL rechazarse con 422: no existe integración con nomencladores reales habilitada.

**Trazabilidad**: DD-11 (obra social ficticia, 1 real en segunda iteración), R-12 (sin costos reales de terceros en v1), RN-OS-01.

#### Scenario: Alta con validación externa solicitada
- **WHEN** el alta envía `validacion_externa=true`
- **THEN** el sistema responde HTTP 422 con detalle que la validación externa no está disponible en v1

#### Scenario: Convenio local por defecto
- **WHEN** el alta omite `validacion_externa`
- **THEN** el sistema responde HTTP 201 con `validacion_externa=false` y las reglas locales como única fuente de cobertura

#### Scenario: Validación externa explícita en falso
- **WHEN** el alta envía `validacion_externa=false` de forma explícita
- **THEN** el sistema responde HTTP 201 igual que si se hubiera omitido y persiste `false`
