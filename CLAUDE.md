# Clínica Odontológica (Argentina) — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` y `CHANGES.md`. No editar a mano sin re-sincronizar ambos archivos.
> Proyecto universitario: Metodología I — integrante Franco Nicolás Gagliardi. Flujo spec-driven vía `openspec/`.

---

## Stack Tecnológico

> Decisión DD-07 (refinada en DD-07a–DD-07e): backend Python + FastAPI (JWT, SQLAlchemy, PostgreSQL, Redis) + frontend React + TypeScript + Vite (SPA) + Docker / Docker Compose. Sin requisito de cátedra en otro sentido.

| Capa | Tecnología decidida | Versión mínima |
|---|---|---|
| Frontend | React + TypeScript + Vite (SPA web responsive) | Vite vigente |
| Backend | Python + FastAPI (API REST) | FastAPI vigente |
| Autenticación | JWT (Bearer para backoffice; tokens de un solo uso con vencimiento para enlaces públicos) | — |
| ORM | SQLAlchemy | SQLAlchemy 2.x |
| Base de datos | PostgreSQL con respaldo cifrado | PostgreSQL vigente |
| Async / jobs | Redis (cola de recordatorios/notificaciones, envío WhatsApp, jobs en segundo plano) | Redis vigente |
| Contenedores | Docker / Docker Compose (servicios: api, frontend, db, redis como mínimo) | Docker vigente |
| Mensajería | WhatsApp Business API oficial (Meta) | API vigente Meta |
| Pagos | Mercado Pago SDK/API (modo sandbox en v1) | API vigente MP |
| Facturación | Web services ARCA (ex AFIP, ambiente de homologación en v1) | WS vigentes ARCA |
| Hospedaje | Default demo local; nube de capa gratuita aceptable (decisión final pendiente — P-05) | — |

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md) · Topología y layout: [knowledge-base/08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) · Decisiones DD-07a–DD-07e: [knowledge-base/09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---------|---------------|
| [README.md](knowledge-base/README.md) | Índice + resumen ejecutivo del sistema |
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Propósito, alcance MVP, fuera de alcance, métricas |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack exacto, arquitectura SaaS, integraciones, API REST por recurso |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | 8 actores, matriz RBAC, rutas públicas tokenizadas |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | 7 dominios, ERD, 14 entidades, seed demo ("OS Demo") |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | 26 reglas RN-TU/CL/AD/OS/NO/SE (contrato codificable) |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | 5 épicas v1 (US-001–US-041); épica 6 posterior |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Flujos E2E 1–5 (reserva, WhatsApp, atención+presupuesto, cobro+ARCA, lista de espera) |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Topología api/frontend/db/redis, layout FastAPI, JWT, colas Redis, seguridad, env vars |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | 17 decisiones DD-01–DD-12 + DD-07a–DD-07e; supuestos SU-01–SU-03 |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | ⚠️ Inconsistencias IN-01/IN-02 + P-05 abierta (hospedaje final); P-09–P-11 |
| [11_integraciones_argentinas.md](knowledge-base/11_integraciones_argentinas.md) | WhatsApp / Mercado Pago / ARCA / cobertura: estrategia sandbox-homologación |

> ⚠️ Antes de arrancar el primer change: P-05 (hospedaje final) sigue abierta — default demo local vía Compose; IN-01 (cifras comerciales sin auditar) e IN-02 (benchmark de pricing incompleto) prohíben prometer beneficios cuantificados.

---

## Skills Disponibles

Fuente de verdad: `.atl/skill-registry.md` (generado por `skill-registry`). 6 skills instaladas; no inventar otras.

| Agente | Rol | Skills que carga |
|--------|-----|------------------|
| **Backend Core** | FastAPI + SQLAlchemy + PostgreSQL + UoW/migraciones (C-02, C-04–C-06, C-11–C-12) | `fastapi-python`, `supabase-postgres-best-practices`, `tdd` |
| **Backend Integraciones** | Auth/RBAC + WhatsApp/MP/ARCA + Redis workers + reportes (C-03, C-09–C-10, C-13–C-15) | `auth-implementation-patterns`, `fastapi-python`, `docker-patterns`, `tdd` |
| **Frontend** | React + TS + Vite SPA: reserva pública 24/7 + agenda backoffice (C-07, C-08) | `vercel-react-best-practices`, `tdd` |
| **Infra / Demo** | Docker/Compose api+frontend+db+redis, túnel webhooks, seed demo (C-01, C-16) | `docker-patterns`, `supabase-postgres-best-practices` |
| **Orquestación** | OPSX/SDD: KB → CHANGES → propose → archive | Skills de arriba según contexto; sin skill propia instalada |

Cargá la skill correspondiente al contexto ANTES de escribir código. Nota: `vercel-react-best-practices` trae reglas Next.js/RSC que NO aplican a esta SPA Vite — aplicar solo cliente/bundle/re-render.

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; no versionado — no está en el repo). Esta tabla solo mapea skill→rol.

---

## Roadmap de Changes

El plan de implementación completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 16 changes (C-01–C-16) en 7 fases (F0 cimientos → F6 cierre).
- **Camino crítico** (8): `C-01 → C-02 → C-03 → C-04 → C-06 → C-09 → C-13 → C-14` (C-05 corre en paralelo con C-04; rama clínica C-11 → C-12 ageota C-13/C-14 en paralelo).
- **Primer change**: `C-01 foundation-setup` (scaffolding + Compose api/frontend/db/redis, FastAPI health check, Vite base, `.env.example`, Alembic init, colas reservadas `whatsapp:send, recordatorios:due, arca:emitir`).
- **Gates con paralelismo**: GATE 3 (C-04 ∥ C-05), GATE 4 (C-06 ∥ C-11), GATE 5 (C-07 ∥ C-08 ∥ C-09); plan óptimo de 3 agentes en CHANGES.md §Plan óptimo.

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá las dependencias del change y los archivos de "Leer antes".

---

## Reglas Duras

> No existe `~/.claude/CLAUDE.md` global en este entorno: este archivo NO hereda nada y contiene tanto las reglas específicas del proyecto (stack-aware, DD-07a–DD-07e) como las universales mínimas. Son contrato; romperlas es un defecto. Estado: **CONFIRMADAS por el usuario (2026-10-13, R-01–R-13 sin cambios)**.

Formato `NUNCA X → hacer Y`:

- **R-01 (Python)** — NUNCA código sin `snake_case` ni firmas sin type hints → todo módulo/función con hints completos; esquemas Pydantic v2 con `extra='forbid'`.
- **R-02 (FastAPI)** — NUNCA dicts crudos en bordes ni endpoints bloqueantes → routers + esquemas Pydantic (RORO), `async def` en toda I/O de DB/API, DI vía `api/deps.py`, `HTTPException` con código específico.
- **R-03 (Auth)** — NUNCA auth solo en UI ni JWT en `localStorage` → RBAC de `03_actores_y_roles.md` aplicado en cada router; Bearer de vida corta en memoria; rutas públicas solo con token opaco de un solo uso con vencimiento (RN-NO-03); bcrypt + throttling en login.
- **R-04 (Persistencia)** — NUNCA DDL ad-hoc ni persistencia fuera de PostgreSQL → SQLAlchemy 2.x + migraciones Alembic declarativas; dominio (turnos, clínica, caja, auditoría) solo en PostgreSQL.
- **R-05 (Postgres)** — NUNCA query lenta sin `EXPLAIN (ANALYZE, BUFFERS)` ni transacciones largas en tablas calientes → índices en `(profesional_id, inicio)`, `(sillon_id, inicio)`, `estado`, `token_publico`; migraciones para todo cambio.
- **R-06 (Redis)** — NUNCA usar Redis como fuente de verdad → solo colas/jobs con nombres reservados (`whatsapp:send`, `recordatorios:due`, `arca:emitir`); estado durable siempre en PostgreSQL.
- **R-07 (Frontend)** — NUNCA `any`, componentes fuera de `PascalCase` ni lógica de negocio en el cliente → `tsconfig` estricto, fetches paralelos, UI solo presenta errores de la API (C-06 manda).
- **R-08 (Docker)** — NUNCA `:latest`, secretos en capas ni prod como root → imágenes pineadas multi-stage, non-root, secretos solo vía `.env`/`env_file` (gitignored), `.dockerignore`, healthchecks + `depends_on`.
- **R-09 (TDD)** — NUNCA código sin rojo previo ni asserts tautológicos → un slice vertical por ciclo, asserts por interfaces públicas con valores de fuente independiente.
- **R-10 (Agenda)** — NUNCA solapamiento silencioso → alta/reprogramación transaccional por profesional Y sillón (RN-TU-01), sobreturno solo con marca explícita (RN-TU-06), bloqueos bloquean (RN-TU-07), máquina de estados validada.
- **R-11 (Clínica/fiscal)** — NUNCA editar evolución firmada ni cobro sin comprobante → rectificatoria enlazada + auditoría append-only (RN-CL-04, RN-SE-02); todo cobro emite comprobante; ARCA caído → interno + job encolado, nunca pérdida (RN-AD-01).
- **R-12 (Integraciones v1)** — NUNCA costo real de terceros en v1 → WhatsApp capa de prueba, MP sandbox, ARCA homologación; webhooks idempotentes con ack + worker (sin doble cobro/mensaje); secretos solo en env vars.
- **R-13 (Universal)** — NUNCA commitear/pushear/buildear sin pedido explícito, ni co-autoría IA en commits → working tree por defecto; commits conventional-commits solo a pedido.

Ante conflicto entre la KB y este archivo, las reglas duras prevalecen.

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias y gates
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks
4. Implementar las tasks (cargando skills)       → respetando las reglas duras R-01–R-13
5. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change
```

Aplicar TODAS las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen. Warnings LF→CRLF en Windows son cosméticos; sin `.gitignore` en el repo, no commitear secretos ni `.env` reales.
