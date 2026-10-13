# Arquitectura Propuesta

> Stack exacto decidido (DD-07 refinada en DD-07a–DD-07e, 2026-10-13): backend Python + FastAPI + JWT + SQLAlchemy + PostgreSQL + Redis; frontend React + TypeScript + Vite (SPA); Docker / Docker Compose (servicios api, frontend, db, redis como mínimo). Hospedaje default demo local, nube free aceptable (P-05 final pendiente).

## Topología

```
browser (React + TS + Vite SPA)
   │  HTTPS/JSON (Bearer JWT)
   ▼
api (FastAPI + Uvicorn) ── SQLAlchemy ──► db (PostgreSQL)
   │                              ▲
   │ enqueue/dequeue              │ Redis: SOLO async (ver abajo),
   ▼                              │ nunca persistencia primaria
 redis (colas + scheduling) ──────┘
   │
   ▼ (workers en 2.º plano)
WhatsApp Business API · Mercado Pago · ARCA (sandbox/homologación en v1)
```

**Qué usa Redis y qué NO**: Redis se usa exclusivamente para lo asincrónico — (a) cola de recordatorios/notificaciones programadas (48/24 h, Flujo 2), (b) cola de envío WhatsApp con reintentos (Flujos 2, 4, 5), (c) jobs en segundo plano (conciliación MP diferida, ofertas de lista de espera, generación de reportes pesados). Toda persistencia de dominio (turnos, historia clínica, caja, auditoría) vive en PostgreSQL vía SQLAlchemy; Redis nunca es fuente de verdad.

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|---|---|---|
| Capas (presentación / aplicación / dominio / persistencia) | Backend | Separar reglas de agenda/caja de integraciones externas |
| Transacción de anti-solapamiento | Alta/reprogramación de turnos | RN-TU-01 exige atomicidad profesional+sillón |
| Webhooks idempotentes | Mercado Pago, WhatsApp | Reintentos de terceros sin doble cobro ni doble mensaje |
| Cola de reintentos (Redis) | Factura ARCA, envíos WhatsApp | Degradación elegante ante caídas (Flujo 4) |
| Token de un solo uso con vencimiento | Enlaces públicos | Seguridad de rutas sin login (RN-NO-03) |
| Auditoría append-only | Escrituras clínicas/admin | RN-SE-02, inmutabilidad |
| Sandbox/homologación primero | MP, ARCA, WhatsApp prueba | Restricción universitaria: sin costo de terceros en v1 |

## Estructura de directorios (FastAPI + React + TS + Vite)

```
clinica-odontologica/
├── knowledge-base/          # esta KB (documentación, no código)
├── docs/discovery/          # fuentes Discovery (no mezclar con KB)
├── openspec/                # especificaciones y changes
├── docker-compose.yml       # servicios: api, frontend, db, redis (mínimo)
├── backend/
│   ├── Dockerfile
│   └── app/
│       ├── domain/          # entidades y reglas RN-*
│       ├── application/     # casos de uso (flujos 1–5)
│       ├── infrastructure/  # PostgreSQL (SQLAlchemy), Redis (colas), WhatsApp, MP, ARCA, PUCO
│       ├── models/          # modelos SQLAlchemy (tablas de `04_modelo_de_datos.md`)
│       ├── schemas/         # esquemas Pydantic (request/response por recurso, ver 02)
│       ├── api/             # routers FastAPI por recurso (ver 02: /pacientes, /turnos, …)
│       │   └── deps.py      # dependencias comunes (DB session, usuario JWT actual, RBAC)
│       ├── core/            # config, security (JWT), redis client, scheduler de recordatorios
│       ├── workers/         # jobs en 2.º plano (recordatorios, WhatsApp, conciliación, reportes)
│       └── main.py          # entrypoint FastAPI
└── frontend/
    ├── Dockerfile
    ├── vite.config.ts
    └── src/
        ├── features/        # agenda, reserva, clinica, caja, reportes
        ├── shared/          # componentes, clientes API (fetch/axios con Bearer JWT)
        └── pages/           # backoffice + reserva pública
```

## Flujo de autenticación JWT

1. `POST /usuarios/login` (credenciales) → backend verifica hash → responde `access_token` (JWT corto, p. ej. 30–60 min) + datos de rol.
2. La SPA (React+Vite) guarda el token en memoria (no en `localStorage` si hay XSS hardening — ver Seguridad) y lo envía como `Authorization: Bearer <jwt>` en cada llamada.
3. `api/deps.py` valida firma/expiración (`JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`), carga el usuario y aplica RBAC de `03_actores_y_roles.md` en cada router (nunca solo en UI).
4. Rutas públicas (reserva, confirmación por enlace) NO usan JWT de sesión: usan token opaco de un solo uso con vencimiento propio (RN-NO-03), validado contra la DB.

Despliegue v1: default **demo local vía Docker Compose** (api con Uvicorn + db PostgreSQL + redis + frontend Vite servido/preview, túnel para webhooks MP/WhatsApp); alternativa aceptada **nube de capa gratuita**. Decisión final según constraints de entrega (P-05).

## Seguridad

- Autenticación: login con credenciales para backoffice devuelve JWT Bearer (flujo arriba); enlaces públicos por token opaco de un solo uso (sin contraseña).
- Autorización: RBAC de `03_actores_y_roles.md` aplicado en API (nunca solo en UI).
- Validación de input: DNI/teléfono/formatos AR, duraciones positivas, estados de turno por máquina de estados.
- Secrets management: credenciales MP/ARCA/WhatsApp solo vía variables de entorno; nada hardcodeado; sandbox en v1.
- Datos de salud: política de privacidad publicada, respaldo cifrado, auditoría de accesos; alcance legal validado con asesoramiento (RN-SE-04).

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|---|---|---|---|
| `DATABASE_URL` | Conexión a la DB | `postgres://user:pass@localhost:5432/clinica` | Y |
| `WHATSAPP_API_TOKEN` | Token API oficial Meta | `EAA...` | Y |
| `WHATSAPP_PHONE_ID` | ID del número remitente | `123456789` | N |
| `MP_ACCESS_TOKEN` | Token Mercado Pago (sandbox v1) | `TEST-...` | Y |
| `ARCA_CUIT` / `ARCA_CERT` / `ARCA_KEY` | Fiscales para homologación | — | Y |
| `APP_BASE_URL` | URL pública (enlaces y webhooks) | `http://localhost:3000` | N |
| `JWT_SECRET` | Firma de access tokens backoffice | aleatorio 256 bit | Y |
| `JWT_ALGORITHM` | Algoritmo de firma JWT | `HS256` | N |
| `JWT_EXPIRE_MINUTES` | Vida del access token | `60` | N |
| `REDIS_URL` | Conexión a colas/jobs (recordatorios, WhatsApp, 2.º plano) | `redis://redis:6379/0` | Y |
