# Actores y Roles

Fuente: informe-discovery §2 + checklist `usuarios` del estado Discovery.

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|---|---|---|
| Odontólogo independiente | Profesional con agenda propia; atiende, registra y cobra | Backoffice: agenda, ficha clínica, odontograma, presupuestos, cobros |
| Recepcionista / administrativo | Opera la agenda y la caja del consultorio/clínica | Backoffice: alta de turnos, confirmaciones, caja, señas, facturación |
| Administrador de clínica | Gestiona múltiples profesionales, sillones y reportes | Backoffice: configuración, liquidaciones, reportes, roles |
| Paciente | Persona que reserva y recibe atención | Enlace público 24/7 + WhatsApp (reserva, confirmación, cancelación, reprogramación, pago de seña) |
| Asistente | Apoyo en consulta | Backoffice limitado: agenda de su profesional, evoluciones |
| Laboratorio | Proveedor de prótesis/trabajos | Órdenes de trabajo (v1: registro básico; módulo completo posterior) |
| Auditor / obra social | Verifica cobertura y prácticas | Consulta de trazabilidad y comprobantes (alcance mínimo en v1) |
| Sistema / bot WhatsApp | Actor automático | Envía recordatorios, procesa confirmaciones, ofrece huecos de lista de espera |

## RBAC — Matriz de permisos

| Rol → Recurso | Agenda/Turnos | Ficha clínica / Odontograma | Presupuestos | Caja / Cobros | Facturación ARCA | Obras sociales | Reportes | Configuración / Roles |
|---|---|---|---|---|---|---|---|---|
| Administrador | CRUD | R | CRUD | CRUD | CRUD | CRUD | R+export | CRUD |
| Odontólogo | RU (propios) | CRUD (propios) | CRUD (propios) | R (propios) | R | R | R (propios) | — |
| Recepcionista | CRUD | R | R | CRU | CRU | RU | R básico | — |
| Asistente | R | RU (asistidos) | R | — | — | — | — | — |
| Paciente (vía enlace) | CR propios* | R propios | R propios | Pagar seña | R propios | — | — | — |
| Auditor | R | R | R | R | R | R | R | — |

\* El paciente solo crea/cancela/reprograma sus propios turnos dentro del plazo de cancelación configurable.

## Rutas públicas (sin autenticación)

- Enlace de reserva online (`/reservar/{consultorio}`) — ver disponibilidad y reservar.
- Confirmación / cancelación / reprogramación desde el enlace del recordatorio (token de un solo uso, con vencimiento).
- Pago de seña vía link de Mercado Pago.
- Descarga de comprobante/factura con token.
