# Clínica Odontológica — Base de Conocimiento

Base generada por `kb-creator` (Mode A, `source: "ingest"`) desde `docs/discovery/informe-discovery.md`, `docs/discovery/verificacion-fuentes.md` y la sección `discovery` de `.active-orchestrator-state.json`. Fase cerrada con respuestas del usuario (2026-10-13): stack exacto Python + FastAPI + JWT + SQLAlchemy + PostgreSQL + Redis + Docker/Compose + React + TS + Vite (DD-07 refinada en DD-07a–DD-07e), alcance independiente + multi-profesional, ARCA en homologación, OS ficticia demo. Único punto abierto: hospedaje final (default demo local).

## Índice de Archivos

| Archivo | Contenido |
|---------|-----------|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos por actor, alcance MVP, fuera de alcance, métricas |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack exacto (FastAPI+JWT+SQLAlchemy+PG+Redis+React+TS+Vite+Compose), arquitectura SaaS, integraciones, API REST |
| [03_actores_y_roles.md](03_actores_y_roles.md) | 8 actores, matriz RBAC, rutas públicas tokenizadas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | 7 dominios, ERD, 14 entidades, seed demo |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | 26 reglas RN-TU/CL/AD/OS/NO/SE |
| [06_funcionalidades.md](06_funcionalidades.md) | 5 épicas v1 (US-001–US-041) + épica 6 posterior |
| [07_flujos_principales.md](07_flujos_principales.md) | Reserva, WhatsApp, atención+presupuesto, cobro+ARCA, lista de espera |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Topología (api/frontend/db/redis), layout FastAPI, JWT, colas Redis, seguridad, env vars |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | 17 decisiones DD (DD-07 refinada en DD-07a–DD-07e) + supuestos SU (SU-01 cerrado y refinado, SU-02 confirmado) |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | 2 inconsistencias + P-01–P-08 respondidas/cerradas; abiertos P-05 (final), P-09–P-11 |
| [11_integraciones_argentinas.md](11_integraciones_argentinas.md) | WhatsApp, Mercado Pago, ARCA, cobertura: estrategia sandbox |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Antes de codificar → [10](10_preguntas_abiertas.md)

## Resumen Ejecutivo

Sistema SaaS (Python + FastAPI + JWT + SQLAlchemy + PostgreSQL + Redis + Docker/Compose + React + TS + Vite) de gestión odontológica para Argentina que centraliza agenda multi-profesional/multi-sillón con reserva online 24/7, WhatsApp oficial incluido, historia clínica con odontograma FDI y administración con Mercado Pago + ARCA en homologación + obras sociales (demo con convenio ficticio). MVP definido en 5 épicas con 26 reglas de negocio; único punto abierto: hospedaje final de entrega.
