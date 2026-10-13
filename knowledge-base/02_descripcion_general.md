# Descripción General

## Stack tecnológico

> **Decisión DD-07 (2026-10-13, respuesta P-06; refinada 2026-10-13 a stack exacto DD-07a–DD-07e)**: backend Python + FastAPI (JWT, SQLAlchemy, PostgreSQL, Redis) + frontend React + TypeScript + Vite (SPA) + Docker / Docker Compose. Sin requisito de cátedra en otro sentido.

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

## Arquitectura general

SaaS web multi-usuario en nube (modelo validado por 16 de 18 competidores relevados; la excepción local-first es Odontoly y la autohospedada es Open Dental — ambas descartadas como modelo para v1, ver `09_decisiones_y_supuestos.md` DD-01):

```
Paciente (enlace reserva / WhatsApp)
        ↕
Frontend React + TypeScript + Vite ──→ API REST (FastAPI) ──→ PostgreSQL (vía SQLAlchemy)
        ↕                    ↕                         ↕
Recepción / Odontólogo   Integraciones: WhatsApp Business API,   Redis: cola de recordatorios,
clínica (backoffice)     Mercado Pago, ARCA, (deseable) PUCO     envíos WhatsApp, jobs en 2.º plano
```

Justificación de alto nivel: un único backend centraliza agenda (anti-solapamiento transaccional), historia clínica y caja, evitando la doble carga que el informe identifica como problema; los tres integradores obligatorios (WhatsApp, MP, ARCA) son los que distinguen al líder DentalCore (4,63) del resto.

## Integraciones externas

| Servicio | Propósito | Tipo |
|---|---|---|
| WhatsApp Business API (Meta, oficial) | Recordatorios, confirmación/cancelación/reprogramación, lista de espera | REST + webhooks (canal oficial, no extra opcional) |
| Mercado Pago | Cobro de señas y tratamientos, conciliación | SDK / API REST + webhooks (sandbox en v1) |
| ARCA (ex AFIP) | Factura electrónica B/C con CAE y QR | Web services SOAP (homologación en v1) |
| PUCO / verificación de cobertura (deseable) | Validación preventiva de obra social | API REST (etapa posterior si no hay acceso) |
| Google Calendar (deseable) | Sincronización de agenda profesional | API REST / OAuth (posterior) |
| API pública propia (futura) | Integraciones radiología, marketing, terceros | REST documentada (posterior) |

Detalle operativo y riesgos de cada integración en `11_integraciones_argentinas.md`.

## API REST (resumen por recurso, propuesta v1)

- `/pacientes` — alta, búsqueda, ficha, documentos.
- `/profesionales` + `/sillones` — recursos agendables, disponibilidad, bloqueos.
- `/turnos` — crear (con anti-solapamiento), confirmar, cancelar, reprogramar, sobreturnos.
- `/lista-espera` — alta, oferta automática de huecos por orden.
- `/historia-clinica` + `/odontograma` — evoluciones, odontograma FDI, adjuntos.
- `/presupuestos` — planes de tratamiento, estados, cobertura/copago calculado.
- `/cobros` + `/comprobantes` — caja, señas MP, facturas ARCA.
- `/obras-sociales` — convenios, validación de cobertura.
- `/usuarios` + `/roles` — RBAC.
- `/recordatorios` + `/notificaciones` — programación y envío WhatsApp.
- `/reportes` — agenda, ausentismo, caja, liquidaciones.
