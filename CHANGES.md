# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **Clínica Odontológica (Argentina)**.
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

Stack pinnado: Python + FastAPI + JWT + SQLAlchemy + PostgreSQL + Redis + Docker/Compose + React + TypeScript + Vite.
MVP = épicas v1 (US-001–US-041); épica 6 (US-050–US-059) posterior — fuera de este índice.

---

## Cómo usar este documento

1. Identificar el change a implementar (verificar que sus dependencias están en `openspec/changes/archive/`).
2. Leer los docs de la knowledge-base indicados en "Leer antes".
3. Ejecutar `/opsx:propose <nombre-del-change>`.
4. Al terminar el change, archivarlo con `/opsx:archive <nombre-del-change>`.
5. Marcar el checkbox `[x]` en este archivo.

---

## Árbol de dependencias

```
C-01 foundation-setup
└── C-02 core-models-seguridad
    └── C-03 auth-jwt-rbac                            ← desbloquea TODO lo protegido
          ├── C-04 recursos-agendables                ← rama A (oferta, paralela con C-05)
          │     ├── C-06 turnos-anti-solapamiento      ← JOIN A: C-04 + C-05
          │     │     ├── C-07 reserva-online-publica  ← necesita solo C-06
          │     │     ├── C-08 agenda-backoffice-ui    ← paralela con C-07
          │     │     └── C-09 whatsapp-recordatorios
          │     │           └── C-10 lista-espera-automatica  ← + C-09
          │     └── C-11 historia-clinica-odontograma ← JOIN B: C-04 + C-05
          │           └── C-12 presupuestos-planes     ← + C-05
          ├── C-05 pacientes-cobertura-base           ← rama B (demanda)
          │     ├── (JOIN A → C-06)
          │     └── (JOIN B → C-11)
          └── C-13 caja-cobros-mercadopago            ← JOIN C: C-06 + C-12
                └── C-14 facturacion-arca-obras-sociales
                      └── C-15 reportes-exportacion
                            └── C-16 admin-roles-auditoria-deploy
```

### Paralelismo por fase

> Cada "gate" es un punto de sincronización. Los changes dentro de un grupo pueden ejecutarse en paralelo.

```
GATE 0: ninguna
  → C-01 foundation-setup (solo)

GATE 1: C-01 ✓
  → C-02 core-models-seguridad (solo)

GATE 2: C-02 ✓
  → C-03 auth-jwt-rbac (solo)

GATE 3: C-03 ✓                     ← PRIMER FORK (2 paralelos)
  → C-04 recursos-agendables       [Agente A]
  → C-05 pacientes-cobertura-base  [Agente B]

GATE 4: C-04 + C-05 ✓              ← JOIN A/B
  → C-06 turnos-anti-solapamiento      [Agente A]
  → C-11 historia-clinica-odontograma  [Agente B]

GATE 5: C-06 ✓                     ← FORK MAYOR (3 paralelos) + C-11 en curso
  → C-07 reserva-online-publica    [Agente C]
  → C-08 agenda-backoffice-ui      [Agente A — si C-06 ✓]
  → C-09 whatsapp-recordatorios    [Agente B]

GATE 6: C-09 ✓ + C-11 ✓
  → C-10 lista-espera-automatica   [Agente B]
  → C-12 presupuestos-planes       [Agente A]

GATE 7: C-06 + C-12 ✓              ← JOIN C
  → C-13 caja-cobros-mercadopago   [Agente A]
  → (C-07 / C-08 / C-10 rematan en paralelo) [Agente C]

GATE 8: C-13 ✓ (+ C-12 ya ✓)
  → C-14 facturacion-arca-obras-sociales  [Agente A]
  → C-15 reportes-exportacion (arranca con C-06+C-13) [Agente B — si C-14 en curso]

GATE 9: C-14 + C-15 ✓
  → C-16 admin-roles-auditoria-deploy     [Agente A + C]
```

### Camino crítico (8 changes — mínimo irreducible)

```
C-01 → C-02 → C-03 → C-04 → C-06 → C-09 → C-13 → C-14
```

> Nota: C-05 corre en paralelo con C-04 y también ageota C-06 (misma profundidad — empate técnico).
> La rama clínica C-11 → C-12 ageota C-13/C-14 en paralelo (segundo leg crítico empatado en longitud).
> C-07/C-08/C-10/C-15/C-16 tienen flotación fuera del camino mínimo.

### Plan óptimo con 3 agentes

```
Paso │ Agente A (Backend Core)      │ Agente B (Backend Aux/Integ.)    │ Agente C (Frontend)
─────┼──────────────────────────────┼──────────────────────────────────┼─────────────────────────
  1  │ C-01 foundation-setup        │ —                                │ —
  2  │ C-02 core-models-seguridad   │ —                                │ —
  3  │ C-03 auth-jwt-rbac           │ —                                │ —
  4  │ C-04 recursos-agendables     │ C-05 pacientes-cobertura-base    │ —
  5  │ C-06 turnos-anti-solapam.    │ C-11 historia-odontograma        │ —
  6  │ C-08 agenda-backoffice-ui*   │ C-09 whatsapp-recordatorios      │ C-07 reserva-online-pública
  7  │ C-12 presupuestos-planes     │ C-10 lista-espera-automática     │ (remate C-07/C-08)
  8  │ C-13 caja-cobros-mercadopago │ C-15 reportes-exportación**      │ (apoyo C-08/C-10)
  9  │ C-14 facturación-arca-os     │ (apoyo C-15)                     │ —
 10  │ C-16 admin-roles-deploy      │ (apoyo C-16)                     │ (apoyo C-16)
```

> \* C-08 es frontend pero la lidera A por acoplamiento con la API de C-06; C coordina el diseño.
> \** C-15 arranca con C-06+C-13 y cierra contra C-14.

---

## FASE 0 — Cimientos

### [C-01] `foundation-setup`
- **Estado**: `[ ]` pendiente
- **Scope**: Scaffolding completo + infraestructura base contenerizada
  - `docker-compose.yml`: servicios `api`, `frontend`, `db` (PostgreSQL), `redis` (mínimo exigido)
  - `backend/`: `Dockerfile`, `app/` con `domain/ application/ infrastructure/ models/ schemas/ api/ (deps.py) core/ workers/ main.py`, FastAPI mínima con health check
  - `frontend/`: `Dockerfile`, `vite.config.ts`, `src/` con `features/ shared/ pages/` (backoffice + reserva pública), React + TS + Vite
  - `backend/.env.example` + `frontend/.env.example`: `DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, WHATSAPP_API_TOKEN, WHATSAPP_PHONE_ID, MP_ACCESS_TOKEN, ARCA_CUIT, ARCA_CERT, ARCA_KEY, APP_BASE_URL` (secretos sin defaults hardcodeados)
  - Alembic inicializado (sin migraciones de dominio aún)
  - Redis cableado solo como colas/jobs (nunca persistencia): nombres reservados `whatsapp:send, recordatorios:due, arca:emitir`
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/01_vision_y_objetivos.md` (qué es el sistema y por qué existe)
  - `knowledge-base/02_descripcion_general.md` §Stack tecnológico
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios
  - `knowledge-base/08_arquitectura_propuesta.md` §Variables de entorno

---

### [C-02] `core-models-seguridad`
- **Estado**: `[ ]` pendiente
- **Scope**: Modelos base de seguridad + patrones de persistencia + seed mínimo
  - Modelos: `Consultorio, Usuario, Rol, UsuarioRol, RegistroAuditoria` (append-only, RN-SE-02)
  - `AuditMixin`: `is_active, created_at, updated_at, deleted_at`
  - `BaseRepository[T]` genérico + `UnitOfWork`
  - Migración 001: tablas core + índices
  - Seed: roles (administrador, odontologo, recepcionista, asistente, auditor) + usuario administrador demo
  - Tests: mixin en modelo de prueba, seed idempotente, auditoría rechaza UPDATE/DELETE
- **Dependencias**: C-01
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Usuario / Rol / RegistroAuditoria
  - `knowledge-base/04_modelo_de_datos.md` §Seed data inicial
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones aplicados
  - `knowledge-base/05_reglas_de_negocio.md` §RN-SE-02

---

## FASE 1 — Identidad y acceso

### [C-03] `auth-jwt-rbac`
- **Estado**: `[ ]` pendiente
- **Scope**: Autenticación JWT backoffice + base RBAC + util de tokens públicos
  - `POST /usuarios/login` (credenciales) → `access_token` JWT corto + datos de rol (DD-07b; sin refresh en v1: revocación solo vía expiración corta)
  - SPA guarda el token en memoria y lo envía como `Authorization: Bearer <jwt>`
  - `api/deps.py`: valida firma/expiración (`JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES`), carga usuario, helpers `require_role()`; RBAC aplicado en cada router, nunca solo en UI
  - Hash de password con bcrypt; throttling anti-fuerza-bruta en login
  - Util `single_use_token` (crear/verificar, un solo uso + vencimiento, RN-NO-03) para C-07/C-09 — sin endpoints públicos aún
  - Tests: login ok/credenciales mal/token expirado 401, rol insuficiente 403, token opaco reutilizado 410
- **Dependencias**: C-02
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos
  - `knowledge-base/08_arquitectura_propuesta.md` §Flujo de autenticación JWT
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad
  - `knowledge-base/05_reglas_de_negocio.md` §RN-SE-01

---

## FASE 2 — Dominio agendable

> C-04 y C-05 corren en paralelo (GATE 3). C-06 hace JOIN de ambas.

### [C-04] `recursos-agendables`
- **Estado**: `[ ]` pendiente
- **Scope**: Recursos de oferta + catálogo de prestaciones + bloqueos
  - Modelos: `Profesional (matrícula, especialidades[], agenda_config), Sillon, ProfesionalSillon, Prestacion (código, duración_min, precio_base, requiere_seña, monto_seña), Bloqueo (profesional/sillon, desde/hasta, motivo)`
  - Endpoints CRUD: `/profesionales, /sillones, /prestaciones, /bloqueos` (+ disponibilidad base desde `agenda_config`)
  - Validaciones: duraciones positivas, `monto_seña` obligatorio si `requiere_seña=true` (RN-TU-08 visible)
  - Migración 002: tablas de recursos + índices
  - Seed: 1 consultorio demo con 2 sillones; catálogo mínimo (consulta, limpieza, obturación, endodoncia, extracción) con duraciones y precios ficticios
  - Tests: CRUD por rol, duración inválida 422, seña sin monto 422
- **Dependencias**: C-03
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Profesional
  - `knowledge-base/04_modelo_de_datos.md` §Prestacion
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-02
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-08

---

### [C-05] `pacientes-cobertura-base`
- **Estado**: `[ ]` pendiente
- **Scope**: Demanda — pacientes + convenios base
  - Modelos: `Paciente (DNI único por consultorio, teléfono WhatsApp requerido, obra_social_id, nro_afiliado), ObraSocial/Convenio (nomenclador_ref, reglas_cobertura)`
  - Endpoints: `/pacientes` (alta, búsqueda por dni/teléfono/apellido, ficha) + `/obras-sociales` (CRUD convenios)
  - Validación formato DNI/teléfono AR; teléfono ausente bloquea alta (canal WhatsApp requerido)
  - Migración 003: tablas + índices (dni, telefono, apellido)
  - Seed: convenio ficticio "OS Demo" (DD-11) + pacientes ficticios para la demo
  - Tests: DNI duplicado en mismo consultorio 409, teléfono inválido 422, búsqueda por índice
- **Dependencias**: C-03
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Paciente
  - `knowledge-base/04_modelo_de_datos.md` §ObraSocial / Convenio
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-11
  - `knowledge-base/05_reglas_de_negocio.md` §RN-OS-02

---

### [C-06] `turnos-anti-solapamiento`
- **Estado**: `[ ]` pendiente
- **Scope**: Núcleo de agenda con garantía transaccional anti-solapamiento (US-002)
  - Modelo `Turno`: paciente/profesional/sillon/prestacion, inicio/fin, estado (`reservado/confirmado/en_sala/atendido/cancelado/ausente`), origen (`recepcion/online/whatsapp`), `token_publico`, máquina de estados validada
  - `POST /turnos` + reprogramación: validación transaccional sin solapamiento por profesional NI por sillón (RN-TU-01); `fin = inicio + duración prestación` salvo sobreturno con marca explícita y color (RN-TU-06, nunca solapamiento silencioso); bloqueos impiden reserva (RN-TU-07); alta sin prestación usa duración base del profesional (RN-TU-02); plazo de cancelación configurable por consultorio (RN-TU-03)
  - Índices: `(profesional_id, inicio), (sillon_id, inicio), estado`; columna `token_publico` única
  - Migración 004: tabla turnos + índices de exclusión
  - Tests: reserva concurrente al mismo slot (una gana, otra 409), sobreturno sin marca 422, reserva en bloqueo 409, transición de estado inválida 422
- **Dependencias**: C-04, C-05
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Turno
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-01
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-06
  - `knowledge-base/07_flujos_principales.md` §Flujo 1: Reserva online de turno

---

## FASE 3 — Reserva y comunicaciones

> C-07, C-08 y C-09 corren en paralelo tras C-06 (GATE 5). C-10 espera a C-09.

### [C-07] `reserva-online-publica`
- **Estado**: `[ ]` pendiente
- **Scope**: Reserva pública 24/7 con enlace + token de un solo uso (US-001, Flujo 1)
  - `GET /reservar/{consultorio}/disponibilidad` (real por profesional/prestación) + `POST` público que crea turno `reservado` con validación RN-TU-01; sin JWT de sesión — token opaco de un solo uso con vencimiento (RN-NO-03)
  - Si la prestación tiene `requiere_seña=true`, la reserva deriva al pago (crea seña pendiente; el cobro/webhook se implementa en C-13) y muestra la política de pérdida (RN-TU-04) antes de confirmar
  - Confirmación encolada a `whatsapp:send` si el worker existe; si no, log + reintento (no bloquea la reserva)
  - Page pública React: profesionales/prestaciones/disponibilidad/formulario + enlace de gestión del turno
  - Tests: doble reserva concurrente pública 409, reuse de token 410, token vencido 410, teléfono inválido sin turno creado
- **Dependencias**: C-06
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-001 — Reserva online 24/7
  - `knowledge-base/07_flujos_principales.md` §Flujo 1: Reserva online de turno
  - `knowledge-base/05_reglas_de_negocio.md` §RN-NO-03
  - `knowledge-base/03_actores_y_roles.md` §Rutas públicas (sin autenticación)

---

### [C-08] `agenda-backoffice-ui`
- **Estado**: `[ ]` pendiente
- **Scope**: Agenda visual backoffice día/semana/mes (US-002, cara visible de C-06)
  - Vistas día/semana/mes por profesional y sillón con código de color por estado; bloqueos y sobreturnos diferenciados; drag & drop que reprograma validando RN-TU-01 vía API (error visible si colisiona)
  - `features/agenda` + `pages/` backoffice; cliente API con Bearer JWT
  - Sin lógica de negocio en el cliente: toda validación vive en C-06 (la UI solo presenta errores)
  - Tests: render por rol (recepcionista CRUD, odontólogo solo propios), reprogramación válida/inválida e2e
- **Dependencias**: C-06
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-002 — Agenda multi-profesional / multi-sillón
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios (frontend)
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-07
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos

---

### [C-09] `whatsapp-recordatorios`
- **Estado**: `[ ]` pendiente
- **Scope**: Recordatorios 48/24 h + gestión por WhatsApp oficial (US-010, US-001 CA-3, Flujo 2)
  - Modelos `Recordatorio (turno_id, programado_para, estado)` + `MensajeWhatsApp (plantilla, estado_envio, respuesta)` — persistencia en PostgreSQL, nunca solo Redis
  - Scheduler: programación 48/24 h en Redis `recordatorios:due`; envío vía cola `whatsapp:send` consumida por workers con reintento exponencial (plantillas mínimas: recordatorio, confirmación, oferta de hueco; capa de prueba en v1, DD-03/SU-03)
  - Webhook inbound idempotente: confirma → `confirmado`; cancela → libera + dispara lista de espera (RN-TU-05); reprograma → valida RN-TU-01; token vencido/fuera de plazo → deriva a recepción; fallo de envío → reintento + alerta a recepción
  - Endpoints `/recordatorios, /notificaciones` + webhook; spike temprano de aprobación de plantillas (riesgo Discovery)
  - Migración 005a: recordatorio + mensaje_whatsapp
  - Tests: inbound duplicado aplica una vez, vencimiento de token, caída de API → reintento sin duplicar
- **Dependencias**: C-06
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-010 — Recordatorios y gestión por WhatsApp
  - `knowledge-base/07_flujos_principales.md` §Flujo 2: Confirmación / cancelación / reprogramación por WhatsApp
  - `knowledge-base/11_integraciones_argentinas.md` §WhatsApp Business API (oficial Meta)
  - `knowledge-base/05_reglas_de_negocio.md` §RN-NO-01

---

### [C-10] `lista-espera-automatica`
- **Estado**: `[ ]` pendiente
- **Scope**: Lista de espera FIFO sobre huecos liberados (US-003, Flujo 5)
  - Modelo `EntradaListaEspera` (paciente/prestación/profesional opcional, orden, estado pendiente/ofrecido/convertido/vencido)
  - Trigger cancelación → busca compatibles por orden → ofrece por WhatsApp con vencimiento configurable (job Redis) → acepta crea turno / vence-rechaza pasa al siguiente (RN-TU-05); si nadie acepta, el hueco vuelve a disponibilidad pública
  - Endpoints `/lista-espera` (alta, baja, estado de oferta)
  - Migración 005b: entrada_lista_espera
  - Tests: oferta respeta FIFO, vencimiento rota al siguiente, conversión crea turno sin solapamiento
- **Dependencias**: C-06, C-09
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-003 — Lista de espera automática
  - `knowledge-base/07_flujos_principales.md` §Flujo 5: Lista de espera ante hueco liberado
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-05
  - `knowledge-base/04_modelo_de_datos.md` §EntradaListaEspera

---

## FASE 4 — Clínica y comercial

> C-11 corre en paralelo con C-06 (GATE 4). C-12 espera a C-11.

### [C-11] `historia-clinica-odontograma`
- **Estado**: `[ ]` pendiente
- **Scope**: Ficha clínica + odontograma FDI + consentimientos (US-020, Flujo 3 parcial)
  - Modelos: `HistoriaClinica, Evolucion` (inmutable tras firma; corrección solo por rectificatoria, RN-CL-04), `Odontograma + HallazgoDental` (FDI 11–48/51–85 por pieza/cara + CIE-10 donde aplique, RN-CL-01), `Adjunto` (fotos/documentos), `Consentimiento` (firma, texto versionado, RN-CL-03)
  - Endpoints `/historia-clinica, /odontograma` (evoluciones, hallazgos por pieza/cara, adjuntos, consentimientos); toda escritura clínica → `RegistroAuditoria`
  - Migración 006: historia/evolución/odontograma/hallazgo/adjunto/consentimiento
  - Tests: evolución firmada rechaza edición 403, rectificatoria enlaza original, pieza FDI inválida 422, adjunto sin historia 422
- **Dependencias**: C-04, C-05
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-020 — Ficha clínica con odontograma FDI
  - `knowledge-base/04_modelo_de_datos.md` §HistoriaClinica / Evolucion
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CL-04
  - `knowledge-base/07_flujos_principales.md` §Flujo 3: Atención con odontograma y presupuesto

---

### [C-12] `presupuestos-planes`
- **Estado**: `[ ]` pendiente
- **Scope**: Presupuesto / plan de tratamiento en consulta con cobertura calculada (US-021)
  - Modelos `Presupuesto (cobertura_calculada, copago, estado borrador/aceptado/rechazado/en_curso/finalizado)` + `ItemPresupuesto (prestacion/pieza/cantidad/precio/cobertura_item)`
  - Cálculo cobertura/copago por ítem contra convenio cargado (RN-OS-02; en v1 contra "OS Demo", DD-11); cobertura no validable → presupuesto marcado "cobertura pendiente de verificación" sin bloquear la atención; aceptación → plan en curso + consentimiento firmado si aplica (RN-CL-02/03)
  - Endpoints `/presupuestos` (CRUD, cambio de estado, cálculo)
  - Migración 007: presupuesto + item_presupuesto
  - Tests: copago = precio − cobertura por ítem, transición inválida 422, servicio de cobertura caído no bloquea
- **Dependencias**: C-11, C-05
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-021 — Presupuesto / plan de tratamiento en consulta
  - `knowledge-base/04_modelo_de_datos.md` §Presupuesto (plan de tratamiento)
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CL-02
  - `knowledge-base/05_reglas_de_negocio.md` §RN-OS-02

---

## FASE 5 — Caja y fiscal argentina

> JOIN C: C-13 espera a C-06 + C-12. C-14 espera a C-13 (+ C-12 ya ✓).

### [C-13] `caja-cobros-mercadopago`
- **Estado**: `[ ]` pendiente
- **Scope**: Caja diaria + señas + Mercado Pago sandbox con conciliación (US-030, Flujo 4 parcial)
  - Modelo `Cobro` (paciente, turno_id?, presupuesto_id?, monto ARS — RN-AD-04, medio efectivo/MP, estado); seña exigible solo si `requiere_seña=true` (RN-TU-08), conciliada con el turno (RN-AD-02), pérdida según política visible RN-TU-04
  - MP sandbox: preferencia/link de pago + webhook idempotente (ack inmediato + worker Redis, idempotencia por id de pago; duplicado/tardío no duplica el cobro)
  - Caja diaria con arqueo: ingresos/gastos/deudas del día cierran antes del cierre (RN-AD-03); endpoints `/cobros`
  - Migración 008a: cobro
  - Tests: webhook duplicado = un cobro, seña en prestación sin `requiere_seña` 422, arqueo descuadrado 409, cancelación tardía pierde seña
- **Dependencias**: C-06, C-12
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-030 — Caja y señas con Mercado Pago
  - `knowledge-base/07_flujos_principales.md` §Flujo 4: Cobro con Mercado Pago y factura ARCA
  - `knowledge-base/11_integraciones_argentinas.md` §Mercado Pago
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-08

---

### [C-14] `facturacion-arca-obras-sociales`
- **Estado**: `[ ]` pendiente
- **Scope**: Factura electrónica ARCA (homologación) + validación y liquidación de obras sociales (US-031, DD-04/DD-09)
  - Modelo `ComprobanteARCA` (cobro_id, tipo B/C, CAE, QR, fecha_emisión); todo cobro emite comprobante (RN-AD-01)
  - Emisión fiscal en cola Redis `arca:emitir` con reintentos; ARCA caído → comprobante interno emitido + factura fiscal encolada (nunca se pierde el cobro); factura enviada por WhatsApp/email
  - Validación preventiva de cobertura antes de registrar la práctica (RN-OS-01, local contra "OS Demo"); liquidación por período con trazabilidad (RN-OS-03); endpoints `/comprobantes, /obras-sociales/liquidaciones`
  - Migración 008b: comprobante_arca
  - Tests: ARCA caído → interno + job pendiente, reintento emite sin duplicar CAE, QR presente, liquidación cuadra prácticas incluidas
- **Dependencias**: C-13, C-12
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-031 — Facturación ARCA y obras sociales
  - `knowledge-base/11_integraciones_argentinas.md` §Facturación ARCA (ex AFIP)
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AD-01
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-09

---

## FASE 6 — Cierre y explotación

> C-15 arranca con C-06+C-13 y cierra contra C-14. C-16 es el último change.

### [C-15] `reportes-exportacion`
- **Estado**: `[ ]` pendiente
- **Scope**: Reportes básicos + exportación total sin cautividad (US-041, DD-05)
  - Endpoints `/reportes`: agenda, ausentismo, caja, liquidaciones; reportes pesados como jobs Redis en 2.º plano (DD-07c)
  - Exportación total del paciente/consultorio en todo momento (PDF + estructurado), sin cargos ni ventanas punitivas (RN-SE-03)
  - UI `features/reportes`: tableros + botón exportar
  - Tests: totales cuadran contra seed, export contiene todas las entidades, job pesado no bloquea el request
- **Dependencias**: C-06, C-13, C-14
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-041 — Reportes básicos + exportación
  - `knowledge-base/05_reglas_de_negocio.md` §RN-SE-03
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-05
  - `knowledge-base/04_modelo_de_datos.md` §ERD (textual)

---

### [C-16] `admin-roles-auditoria-deploy`
- **Estado**: `[ ]` pendiente
- **Scope**: Administración de acceso + endurecimiento + demo local entregable (US-040, DD-12)
  - CRUD `/usuarios, /roles` aplicando la matriz RBAC de `03_actores_y_roles.md` en API + UI (nunca solo en UI); visor de auditoría solo-lectura para rol auditor (RN-SE-02)
  - Paciente vía enlace solo opera sus propios turnos/datos dentro del plazo (RN-SE-01); consentimiento + política de privacidad publicada, respaldo cifrado, alcance legal validado con asesoramiento (RN-SE-04)
  - Compose demo local como default (api Uvicorn + db + redis + frontend servido; túnel para webhooks MP/WhatsApp); `.env` documentados; alternativa nube free (P-05)
  - Seed demo completo: admin + odontólogo + recepcionista, consultorio 2 sillones, prestaciones, "OS Demo", pacientes y turnos ficticios
  - Tests: matriz RBAC e2e por rol (403 donde corresponde), auditor no escribe, paciente no ve datos ajenos, `docker compose up` + flujo demo verde
- **Dependencias**: C-03, C-15
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-040 — Roles y permisos + trazabilidad
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad
  - `knowledge-base/10_preguntas_abiertas.md` §P-05
