# Spec Delta

## Purpose

Define la identidad visual y el sistema de componentes de la SPA, los shells de navegación pública y de backoffice, los estados de interfaz y las garantías de accesibilidad, responsive, movimiento reducido e impresión, sin alterar contratos, comportamiento funcional ni el manejo en memoria de la sesión.

## ADDED Requirements

### Requirement: Tokens de diseño como fuente única

La SPA SHALL definir sus decisiones visuales como custom properties CSS en un archivo de tokens —color, tipografía, espaciado, radios, bordes, foco, sombra y movimiento— y toda regla de presentación SHALL consumirlas con `var(--…)`. No SHALL existir colores literales fuera del archivo de tokens.

**Trazabilidad**: R-07 (`AGENTS.md`), `platform/frontend-baseline` §Convenciones, DD-07.

#### Scenario: Inventario completo de tokens

- **WHEN** se audita el archivo de tokens
- **THEN** existen grupos nombrados para color, tipografía, espaciado, radios, bordes, foco y movimiento, y cada token tiene un valor declarado y documentado

#### Scenario: Componente con color literal

- **WHEN** se busca un valor hexadecimal, `rgb()` o `hsl()` en las reglas de componentes
- **THEN** no aparece ninguno fuera del archivo de tokens y la verificación falla si se introduce uno

#### Scenario: Cambio global de un token

- **WHEN** se modifica el token de color primario
- **THEN** botones, enlaces, foco y badges cambian de forma consistente sin editar componentes

### Requirement: Identidad tipográfica y contraste AA

La SPA SHALL usar una escala tipográfica documentada con serif para titulares y sans del sistema para interfaz, sin fuentes remotas ni descargas de red, y SHALL garantizar contraste WCAG AA: al menos 4.5:1 en texto normal, 3:1 en texto grande y 3:1 en bordes y anillo de foco de controles.

**Trazabilidad**: R-07, `platform/frontend-baseline`, WCAG 2.2 AA.

#### Scenario: Pares de tokens conformes

- **WHEN** se calcula el contraste de cada par texto/fondo y control/fondo declarado en los tokens
- **THEN** todos los pares de texto alcanzan 4.5:1 (o 3:1 si el texto es grande) y los de interfaz alcanzan 3:1

#### Scenario: Par de contraste insuficiente

- **WHEN** un token se cambia a un valor que incumple el umbral de su par
- **THEN** la verificación falla nombrando el par y el ratio obtenido, y no se publica el cambio

#### Scenario: Zoom y reflujo

- **WHEN** se aplica 200 % de zoom sobre una vista de 1280 px de ancho
- **THEN** el contenido se refluye sin pérdida de información ni scroll horizontal de página

### Requirement: Shell de backoffice con navegación protegida

Las rutas de backoffice SHALL renderizar un shell con marca, rail de navegación (Agenda, Reportes, Usuarios, Auditoría), identidad de la sesión y acción Salir, con `aria-current="page"` en la ruta activa y un skip link como primer elemento enfocable. Sin sesión, el shell no SHALL exponer enlaces protegidos.

**Trazabilidad**: R-03, R-07, `03_actores_y_roles.md`, `platform/frontend-baseline`.

#### Scenario: Sesión activa en agenda

- **WHEN** un usuario con sesión abre `/agenda`
- **THEN** ve el rail con los cuatro módulos, Agenda marcada con `aria-current="page"`, su identidad y la acción Salir

#### Scenario: Backoffice sin sesión

- **WHEN** se abre `/reportes`, `/usuarios` o `/auditoria` sin sesión
- **THEN** se muestra el acceso y no aparecen enlaces a módulos protegidos

#### Scenario: Ruta desconocida

- **WHEN** se abre una ruta que no existe
- **THEN** se muestra el 404 con el shell público y sin navegación protegida

#### Scenario: Salir conserva el comportamiento

- **WHEN** se activa Salir desde el shell
- **THEN** la sesión en memoria se descarta, la vista vuelve al acceso y no se escribe nada en el almacenamiento del navegador

### Requirement: Shell público de reserva y privacidad

Las rutas públicas (`/reservar`, `/reservar/gestion/:token`, `/privacidad` y 404) SHALL usar un shell sobrio con marca, acceso a reservar y enlace a la política de privacidad, sin navegación de backoffice ni datos de sesión. El contenido SHALL limitar su medida de línea y mantener un único `h1`.

**Trazabilidad**: R-03, R-07, RN-NO-03, `07_flujos_principales.md` §Flujo 1.

#### Scenario: Reserva pública

- **WHEN** se abre `/reservar`
- **THEN** se ve la marca, el enlace a privacidad y el formulario público, sin rail de Agenda, Reportes, Usuarios ni Auditoría

#### Scenario: Enlace de gestión válido

- **WHEN** el token de gestión es válido y el turno está disponible
- **THEN** la página muestra el resumen del turno, la seña y las acciones permitidas dentro del shell público

#### Scenario: Enlace vencido o usado

- **WHEN** el token está vencido, usado o es ajeno
- **THEN** se muestra el error de la API verbatim, sin acciones de confirmar o cancelar y sin revelar datos de otro turno

### Requirement: Componentes compartidos y estados

La SPA SHALL exponer componentes reutilizables para botón, campo de texto, selector, tarjeta, tabla, badge, estado, vacío, error, carga y encabezado de página, con variantes y estados default, hover, foco visible, deshabilitado, cargando y error. Los componentes SHALL ser presentacionales: reciben datos y callbacks, sin validar reglas de negocio ni llamar a la API.

**Trazabilidad**: R-07, `platform/frontend-baseline` §Convenciones, R-02 (validación en el backend).

#### Scenario: Operación por teclado

- **WHEN** se recorre la interfaz con Tab, Enter y Espacio
- **THEN** cada control es alcanzable y operable, y el foco visible se distingue del estado normal con al menos 3:1 de contraste

#### Scenario: Control deshabilitado

- **WHEN** una acción está deshabilitada por falta de selección o por estado de la API
- **THEN** no se puede activar, se anuncia como deshabilitada y no dispara ninguna llamada de red

#### Scenario: Error y carga anunciados

- **WHEN** un componente recibe un error o entra en carga
- **THEN** el error se anuncia en una región `alert` con el mensaje verbatim y la carga se anuncia en una región `status` sin duplicar el anuncio

#### Scenario: Etiqueta accesible exacta

- **WHEN** un campo muestra una etiqueta visible y una ayuda o error
- **THEN** su nombre accesible es exactamente la etiqueta visible y la ayuda se asocia por `aria-describedby`, sin concatenarse al nombre

### Requirement: Estados de UX y errores de API verbatim

Toda pantalla SHALL presentar carga, vacío, error y deshabilitado con el mismo patrón visual y semántico. Los errores de la API SHALL mostrarse verbatim con su código (401/403/404/409/410/422) sin reinterpretación local, y un token vencido SHALL explicarse sin ocultar el mensaje del servidor.

**Trazabilidad**: R-07, `platform/frontend-baseline` §Configuración del cliente, RN-NO-03.

#### Scenario: Conflicto 409

- **WHEN** la API responde 409 en agenda o usuarios
- **THEN** se muestra una alerta con el código y el detalle del servidor, y el estado visual de la pantalla no cambia

#### Scenario: Permiso 403

- **WHEN** la API responde 403
- **THEN** se muestra el mensaje verbatim y no se habilitan controles de escritura que la API prohíbe

#### Scenario: Validación 422

- **WHEN** la API responde 422 por datos inválidos
- **THEN** el mensaje del servidor se muestra tal cual y el cliente no agrega validaciones ni mensajes propios

#### Scenario: Lista vacía

- **WHEN** una consulta termina sin filas y sin error
- **THEN** se muestra un estado vacío con título, explicación y una acción opcional, sin filas ni totales inventados

#### Scenario: Token vencido

- **WHEN** el enlace del paciente responde 410
- **THEN** se muestra el 410 verbatim junto con una indicación de pedir un enlace nuevo, sin botones de confirmar o cancelar

### Requirement: Layout de las nueve rutas existentes

Cada ruta SHALL tener un layout terminado y coherente —portada, reserva pública, gestión por token, agenda, reportes, usuarios, auditoría, privacidad y 404— con exactamente un `h1`, jerarquía de encabezados sin saltos y acciones primarias visibles. El rediseño no SHALL alterar textos de etiquetas, roles ni comportamiento observado por las pruebas.

**Trazabilidad**: R-07, `platform/frontend-baseline`, `06_funcionalidades.md` US-001–US-041.

#### Scenario: Inventario de rutas

- **WHEN** se recorren las nueve rutas
- **THEN** cada una renderiza un solo `h1`, el shell que le corresponde y ninguna ruta queda sin estilos

#### Scenario: Portada con doble entrada

- **WHEN** se abre `/`
- **THEN** se ven dos entradas claras —reservar turno e ingresar al backoffice— y el estado del sistema, conservando el título de backoffice

#### Scenario: Agenda en sus tres vistas

- **WHEN** se alterna Día, Semana y Mes
- **THEN** las grillas conservan sus clases y atributos observables, los estados de turno se distinguen por color y texto, y el sobreturno y el bloqueo siguen visibles

#### Scenario: Reportes y exportación

- **WHEN** se abren los cuatro tableros y el panel de exportación
- **THEN** los totales, tablas y estados de exportación se leen con jerarquía clara y sin truncar valores

#### Scenario: Privacidad de lectura larga

- **WHEN** se abre `/privacidad`
- **THEN** el texto se presenta con medida de línea legible, versión y fecha destacadas, hash en tipografía monoespaciada y sin casilla de aceptación

### Requirement: Diseño responsive y tablas desbordadas

El layout SHALL adaptarse sin scroll horizontal de página desde 320 px: rail lateral en escritorio, barra superior con menú desplegable en tablet y móvil, y tablas con contenedor de scroll propio. Las acciones principales SHALL mantener un objetivo táctil mínimo de 44×44 px y las tablas SHALL conservar encabezados asociados a sus celdas.

**Trazabilidad**: R-07, `platform/frontend-baseline`, WCAG 2.2 AA (reflujo y tamaño de objetivo).

#### Scenario: Ancho mínimo de 320 px

- **WHEN** se abre cualquier ruta a 320 px de ancho
- **THEN** no hay scroll horizontal de página, el menú se ofrece como desplegable y la acción principal sigue siendo alcanzable

#### Scenario: Transición de rail a barra superior

- **WHEN** el ancho baja de 1024 px
- **THEN** el rail lateral se reemplaza por una barra superior con el mismo contenido de navegación y estado activo

#### Scenario: Tabla más ancha que la pantalla

- **WHEN** una tabla de reportes o auditoría excede el ancho disponible
- **THEN** se desplaza dentro de una región enfocable con nombre accesible, sin arrastrar la página completa

#### Scenario: Objetivos táctiles

- **WHEN** se miden las acciones principales en móvil
- **THEN** cada una tiene al menos 44×44 px de área activa

### Requirement: Movimiento reducido y preferencias

Las transiciones SHALL limitarse a cambios de estado propios de la interfaz —foco, selección, despliegue— con duración de 120 a 180 ms y SHALL respetar `prefers-reduced-motion: reduce`, eliminando desplazamientos y animaciones no esenciales. No SHALL existir animaciones automáticas en bucle.

**Trazabilidad**: R-07, WCAG 2.2 AA (movimiento), `frontend-design` §Restraint.

#### Scenario: Preferencia de movimiento reducido

- **WHEN** el sistema operativo declara `prefers-reduced-motion: reduce`
- **THEN** las transiciones no esenciales tienen duración cero y no hay desplazamientos ni escalados

#### Scenario: Página en reposo

- **WHEN** la interfaz queda inactiva
- **THEN** no hay animaciones en bucle, destellos ni movimiento que compita con la lectura

#### Scenario: Movimiento que explica un cambio

- **WHEN** se abre el menú móvil o se selecciona un horario
- **THEN** la transición comunica el cambio de estado y no se repite en otros elementos de la página

### Requirement: Impresión legible de reportes

La vista de reportes SHALL ofrecer una hoja de impresión que oculte navegación, filtros y acciones, use texto negro sobre blanco, conserve totales y tablas y evite cortar filas entre páginas. Las demás rutas SHALL imprimirse legibles y sin controles de navegación.

**Trazabilidad**: R-07, `06_funcionalidades.md` US-041, `platform/frontend-baseline`.

#### Scenario: Impresión de reportes

- **WHEN** se imprime `/reportes`
- **THEN** no aparecen rail, filtros ni botones, y los totales y tablas se imprimen en negro sobre blanco

#### Scenario: Tabla que cruza páginas

- **WHEN** una tabla ocupa más de una página impresa
- **THEN** el encabezado se repite y ninguna fila queda partida entre páginas

#### Scenario: Impresión de una ruta pública

- **WHEN** se imprime `/privacidad`
- **THEN** el texto se imprime legible, sin menú ni acciones, y conserva versión y hash

### Requirement: Presentación sin cambios de contrato ni de sesión

El cambio SHALL ser exclusivamente de presentación: no SHALL agregar ni modificar endpoints, contratos de API, llamadas de red, reglas de negocio ni persistencia del token. La sesión SHALL seguir en memoria, los errores SHALL seguir viniendo del servidor y la suite existente, el typecheck y el build SHALL permanecer en verde.

**Trazabilidad**: R-03, R-07, `platform/frontend-baseline`, R-13.

#### Scenario: Sesión en memoria

- **WHEN** se recarga una ruta de backoffice con sesión activa
- **THEN** la sesión se pierde y no existe ninguna entrada en `localStorage`, `sessionStorage` ni cookie con el token

#### Scenario: Mismas llamadas de red

- **WHEN** se compara la actividad de red antes y después del rediseño en cada flujo
- **THEN** los endpoints, métodos y cuerpos enviados son los mismos

#### Scenario: Suite y build

- **WHEN** se ejecutan los tests, el typecheck y el build
- **THEN** los 64 tests preexistentes siguen en verde, los nuevos pasan y no hay errores de tipos ni de compilación

#### Scenario: Regresión funcional

- **WHEN** se recorren reserva, agenda, reportes, usuarios, auditoría y privacidad
- **THEN** cada flujo conserva su comportamiento observable y solo cambia su presentación
