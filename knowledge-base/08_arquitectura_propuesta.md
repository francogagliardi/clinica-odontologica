# Arquitectura Propuesta

> Stack decidido (DD-07): Python FastAPI + SPA + PostgreSQL. Hospedaje default demo local, nube free aceptable (P-05 final pendiente).

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|---|---|---|
| Capas (presentación / aplicación / dominio / persistencia) | Backend | Separar reglas de agenda/caja de integraciones externas |
| Transacción de anti-solapamiento | Alta/reprogramación de turnos | RN-TU-01 exige atomicidad profesional+sillón |
| Webhooks idempotentes | Mercado Pago, WhatsApp | Reintentos de terceros sin doble cobro ni doble mensaje |
| Cola de reintentos | Factura ARCA, envíos WhatsApp | Degradación elegante ante caídas (Flujo 4) |
| Token de un solo uso con vencimiento | Enlaces públicos | Seguridad de rutas sin login (RN-NO-03) |
| Auditoría append-only | Escrituras clínicas/admin | RN-SE-02, inmutabilidad |
| Sandbox/homologación primero | MP, ARCA, WhatsApp prueba | Restricción universitaria: sin costo de terceros en v1 |

## Estructura de directorios (FastAPI + SPA)

```
clinica-odontologica/
├── knowledge-base/          # esta KB (documentación, no código)
├── docs/discovery/          # fuentes Discovery (no mezclar con KB)
├── openspec/                # especificaciones y changes
├── backend/
│   └── app/
│       ├── domain/          # entidades y reglas RN-*
│       ├── application/     # casos de uso (flujos 1–5)
│       ├── infrastructure/  # PostgreSQL, WhatsApp, MP, ARCA, PUCO
│       ├── api/             # routers FastAPI por recurso (ver 02)
│       └── main.py          # entrypoint FastAPI
└── frontend/
    └── src/
        ├── features/        # agenda, reserva, clinica, caja, reportes
        ├── shared/          # componentes, clientes API
        └── pages/           # backoffice + reserva pública
```

Despliegue v1: default **demo local** (Uvicorn + PostgreSQL local, túnel para webhooks MP/WhatsApp); alternativa aceptada **nube de capa gratuita**. Decisión final según constraints de entrega (P-05).

## Seguridad

- Autenticación: login con credenciales para backoffice; enlaces públicos por token (sin contraseña).
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
| `JWT_SECRET` | Firma de sesiones backoffice | aleatorio 256 bit | Y |
