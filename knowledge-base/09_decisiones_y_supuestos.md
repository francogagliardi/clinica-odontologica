# Decisiones y Supuestos

## Decisiones documentadas

### DD-01 — SaaS web multi-usuario en nube como modelo v1
**Decisión**: construir web SaaS multi-usuario, no local-first ni autohospedado.
**Contexto**: 16 de 18 competidores son SaaS nube; reserva 24/7 y WhatsApp exigen backend siempre disponible.
**Alternativas consideradas**: local-first tipo Odontoly (resiliente a cortes, pero sin nube real ni automatizaciones); servidor local tipo Open Dental (costo IT para la clínica, inglés, sin ARCA/MP/WhatsApp).
**Justificación**: el diferencial (WhatsApp incluido, ARCA+MP, lista de espera) requiere servidor central.
**Trade-offs aceptados**: dependencia de internet (mitigada a futuro con modo degradado US-058); costo de hospedaje (pregunta P-05).

### DD-02 — Odontograma FDI como notación clínica
**Decisión**: notación FDI por pieza y cara, con CIE-10 donde aplique.
**Contexto**: estándar en DentalCore, FLAP, Odontias, ClinIA.
**Alternativas**: nomenclatura universal/chilena (Dentidesk) — descartada por mercado AR.
**Trade-offs**: ninguno relevante.

### DD-03 — WhatsApp incluido, no módulo pago aparte
**Decisión**: mensajería oficial incluida en el plan base.
**Contexto**: el informe detecta WhatsApp como costo extra (AgendaPro +$7.900/mes, FLAP en paquetes, DentalTec packs USD 9) pese a ser el canal dominante; es el diferenciador declarado del MVP.
**Trade-offs**: costo de mensajes asumido en el pricing; en v1 universitaria se usa capa de prueba/sandbox.

### DD-04 — ARCA + Mercado Pago + validación de obras sociales en el mismo flujo v1
**Decisión**: los tres en el MVP (con homologación/sandbox), no postergados.
**Contexto**: solo el líder DentalCore los integra juntos; la mitad de los locales carece de alguno.
**Trade-offs**: complejidad de integración temprana; riesgo de dependencias de terceros (ver `11_integraciones_argentinas.md`).

### DD-05 — Exportación total sin cautividad desde el día uno
**Decisión**: exportación PDF + estructurado siempre disponible, sin cargos ni penalizaciones.
**Contexto**: antídoto contra la cautividad detectada (Dentidesk: ventana 30 días con posible cargo + 30 % reactivación).
**Trade-offs**: ninguno; es también requisito ético con datos de salud.

### DD-06 — Precio ARS publicado + prueba gratuita
**Decisión**: pricing transparente como diferenciador.
**Contexto**: 9 de 12 regionales no publican precios; los que sí (Odontias, DenPro, AgendaPro, Doctoralia) validan el modelo.
**Trade-offs**: cifras volátiles; requieren revisión antes de fijar pricing (verificación H13–H14 pendiente con demo).

### DD-07 — Stack v1: FastAPI + SPA + PostgreSQL [REFINADA 2026-10-13 — ver DD-07a–DD-07e]
**Decisión original**: backend Python FastAPI (API REST), frontend SPA web responsive, PostgreSQL.
**Contexto**: respuesta P-06 (opción a, sin requisito de cátedra en otro sentido).
**Estado**: REFINADA el 2026-10-13 por stack exacto del usuario; el contenido normativo pasa a DD-07a–DD-07e. Se conserva por trazabilidad; no usar su formulación genérica ("SPA") para decisiones nuevas.
**Alternativas consideradas**: Node/Nest + React + PostgreSQL; Laravel + MySQL — descartadas por simplicidad del MVP e integración directa con clientes REST/SOAP.
**Trade-offs aceptados**: equipo debe manejar ecosistema Python para los clientes ARCA (SOAP) y MP.

### DD-07a — Backend v1: Python + FastAPI + SQLAlchemy + PostgreSQL (2026-10-13)
**Decisión**: API REST en Python con FastAPI; ORM SQLAlchemy (2.x); PostgreSQL como única persistencia de dominio.
**Contexto**: stack exacto definido por el usuario; refina DD-07.
**Trade-offs aceptados**: el equipo asume migraciones (Alembic) y modelado ORM de las 14 entidades de `04_modelo_de_datos.md`.

### DD-07b — Autenticación v1: JWT Bearer (2026-10-13)
**Decisión**: backoffice con JWT Bearer (access token corto, firma `JWT_SECRET`); rutas públicas con token opaco de un solo uso con vencimiento (RN-NO-03), no con JWT de sesión.
**Contexto**: stack exacto definido por el usuario; flujo detallado en `08_arquitectura_propuesta.md`.
**Trade-offs aceptados**: manejo de expiración/renovación en la SPA; tokens revocables solo vía expiración corta en v1.

### DD-07c — Async v1: Redis para colas y jobs en segundo plano (2026-10-13)
**Decisión**: Redis como broker/colas exclusivamente para (a) recordatorios/notificaciones programadas 48/24 h, (b) envío WhatsApp con reintentos, (c) jobs en segundo plano (conciliación MP diferida, ofertas de lista de espera, reportes pesados). Nunca como persistencia primaria.
**Contexto**: stack exacto definido por el usuario; topología en `08_arquitectura_propuesta.md`, operación en `11_integraciones_argentinas.md`.
**Trade-offs aceptados**: un servicio más en Compose (redis); workers a operar en demo local.

### DD-07d — Frontend v1: React + TypeScript + Vite SPA (2026-10-13)
**Decisión**: SPA en React + TypeScript construida con Vite (backoffice + reserva pública responsive).
**Contexto**: stack exacto definido por el usuario; refina el genérico "SPA" de DD-07.
**Trade-offs aceptados**: build Vite a servir como servicio `frontend` en Compose.

### DD-07e — Contenedores v1: Docker / Docker Compose con api, frontend, db, redis (2026-10-13)
**Decisión**: entrega demo local contenerizada con Compose y servicios mínimos `api`, `frontend`, `db` (PostgreSQL), `redis`; webhooks vía túnel.
**Contexto**: stack exacto definido por el usuario; coherente con DD-12 (default demo local).
**Trade-offs aceptados**: el equipo mantiene `Dockerfile`s y `docker-compose.yml` desde el día uno.

### DD-08 — Alcance v1: independiente + clínica multi-profesional (confirma SU-02)
**Decisión**: el MVP sirve a ambos segmentos desde el día uno; multisucursal queda posterior (US-054).
**Contexto**: respuesta P-01 (opción b).
**Trade-offs aceptados**: RBAC y agenda multi-recurso obligatorios en v1 (sin atajo "solo un profesional").

### DD-09 — ARCA real en homologación dentro de v1
**Decisión**: factura electrónica B/C con CAE y QR contra ambiente de homologación ARCA en el MVP (diferenciador DD-04).
**Contexto**: respuesta P-03 (opción a).
**Trade-offs aceptados**: alta de certificados de homologación y cola de reintentos (Flujo 4) dentro del alcance v1.

### DD-10 — Seña opcional por prestación
**Decisión**: la seña solo es exigible si la prestación la define (`requiere_seña`); nunca obligatoria por defecto. Ver RN-TU-08.
**Contexto**: respuesta P-02 (opción a).
**Trade-offs aceptados**: la reserva sin seña depende de recordatorios + lista de espera contra el ausentismo.

### DD-11 — Obra social ficticia para la demo, 1 real en segunda iteración
**Decisión**: seed con convenio ficticio propio ("OS Demo"); incorporar una obra social real con nomenclador en la iteración siguiente.
**Contexto**: respuesta P-04 (opción c).
**Trade-offs aceptados**: la validación preventiva (RN-OS-01) se demuestra contra reglas locales en v1, no contra servicio externo.

### DD-12 — Hospedaje: default demo local, nube free aceptable
**Decisión**: ambas opciones (a)/(b) válidas; default demo local; decisión final según constraints de entrega.
**Contexto**: respuesta P-05 (parcial — falta el cierre por constraints).
**Trade-offs aceptados**: webhooks de MP/WhatsApp requieren URL pública (túnel) en modo demo local.

## Supuestos inferidos

### SU-01 — [CERRADO por P-06, REFINADO 2026-10-13] Stack exacto: Python + FastAPI + JWT + SQLAlchemy + PostgreSQL + Redis + Docker/Compose + React + TS + Vite (DD-07a–DD-07e).

### SU-02 — [CONFIRMADO por P-01] v1 cubre independiente + clínica pequeña multi-profesional
**Origen**: checklist Discovery + respuesta P-01(b). Ver DD-08. Ya no es supuesto: es alcance decidido.

### SU-03 — Sandbox/homologación suficiente para la entrega universitaria
**Supuesto**: MP sandbox, ARCA homologación y WhatsApp prueba alcanzan para demostrar el MVP con datos ficticios.
**Origen**: restricción "sin presupuesto para licencias pagas" del Discovery.
**Riesgo si es falso**: alguna integración exige aprobación/costo incluso en prueba.
**Cómo validar**: spike temprano de cada integración (ver `11_integraciones_argentinas.md`).
