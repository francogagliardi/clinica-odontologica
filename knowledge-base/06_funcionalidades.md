# Funcionalidades

Organizadas por **épica** y luego por **historia de usuario** (US-NNN). MVP = épicas 1–5 marcadas `v1`; épica 6 = posterior. Fuentes: informe §D (MVP) + checklist de funcionalidades necesarias/opcionales.
Alcance decidido (DD-08): independiente + clínica multi-profesional desde el día uno. ARCA en homologación dentro de v1 (DD-09). Demo con convenio ficticio "OS Demo" (DD-11).

## Épica 1: Agenda y reserva online (v1)

### US-001 — Reserva online 24/7
**Como** paciente **Quiero** reservar un turno desde un enlace público **Para** no depender del horario de recepción.
**Criterios de aceptación**:
- [ ] CA-1: el enlace muestra disponibilidad real por profesional/prestación.
- [ ] CA-2: la reserva crea el turno con duración de la prestación y valida anti-solapamiento.
- [ ] CA-3: el paciente recibe confirmación por WhatsApp con enlace de gestión.
**Reglas relacionadas**: RN-TU-01, RN-TU-02, RN-NO-03.

### US-002 — Agenda multi-profesional / multi-sillón
**Como** recepcionista **Quiero** ver la agenda día/semana por profesional y sillón con bloqueos y sobreturnos **Para** evitar solapamientos.
**Criterios de aceptación**:
- [ ] CA-1: vistas día/semana/mes con código de color por estado.
- [ ] CA-2: bloqueos impiden reservar; sobreturnos con marca visible.
- [ ] CA-3: drag & drop reprograma validando RN-TU-01.
**Reglas relacionadas**: RN-TU-01, RN-TU-06, RN-TU-07.

### US-003 — Lista de espera automática
**Como** paciente en espera **Quiero** que se me ofrezca el hueco liberado **Para** adelantar mi atención.
**Criterios de aceptación**:
- [ ] CA-1: la cancelación dispara la oferta por orden FIFO.
- [ ] CA-2: la oferta por WhatsApp vence en plazo configurable; si vence, pasa al siguiente.
**Reglas relacionadas**: RN-TU-05, RN-NO-02.

## Épica 2: Comunicaciones WhatsApp (v1)

### US-010 — Recordatorios y gestión por WhatsApp
**Como** paciente **Quiero** recibir recordatorios 48/24 h y confirmar/cancelar/reprogramar desde el mensaje **Para** gestionar mi turno sin llamar.
**Criterios de aceptación**:
- [ ] CA-1: envío automático por API oficial de Meta con enlace tokenizado.
- [ ] CA-2: la respuesta actualiza la agenda sin intervención manual.
- [ ] CA-3: WhatsApp incluido en el plan, no como módulo pago aparte (diferenciador).
**Reglas relacionadas**: RN-NO-01, RN-NO-02, RN-NO-03.

## Épica 3: Historia clínica odontológica (v1)

### US-020 — Ficha clínica con odontograma FDI
**Como** odontólogo **Quiero** registrar la atención con evoluciones y odontograma por pieza/cara **Para** tener la historia completa del paciente.
**Criterios de aceptación**:
- [ ] CA-1: odontograma FDI con estados por cara y diagnósticos.
- [ ] CA-2: evoluciones inmutables tras firma, con rectificatoria.
- [ ] CA-3: adjuntos (fotos/documentos) por historia.
**Reglas relacionadas**: RN-CL-01, RN-CL-04.

### US-021 — Presupuesto / plan de tratamiento en consulta
**Como** odontólogo **Quiero** generar el presupuesto en la misma consulta con cobertura calculada **Para** que el paciente decida informado.
**Criterios de aceptación**:
- [ ] CA-1: ítems por prestación/pieza con precio y cobertura/copago.
- [ ] CA-2: estados borrador/aceptado/rechazado/en_curso/finalizado.
- [ ] CA-3: consentimiento con firma para prácticas invasivas.
**Reglas relacionadas**: RN-CL-02, RN-CL-03, RN-OS-02.

## Épica 4: Caja, cobros y facturación (v1)

### US-030 — Caja y señas con Mercado Pago
**Como** recepcionista **Quiero** cobrar y registrar señas vinculadas a la reserva **Para** asegurar asistencia y conciliar.
**Criterios de aceptación**:
- [ ] CA-1: cobro en efectivo y vía Mercado Pago (sandbox en v1) con conciliación.
- [ ] CA-2: seña solo si la prestación la exige (`requiere_seña`); su pérdida sigue la política visible.
- [ ] CA-3: caja diaria con arqueo.
**Reglas relacionadas**: RN-AD-02, RN-AD-03, RN-TU-04, RN-TU-08.

### US-031 — Facturación ARCA y obras sociales
**Como** administrador **Quiero** emitir factura electrónica y liquidar obras sociales **Para** operar sin doble carga.
**Criterios de aceptación**:
- [ ] CA-1: factura B/C con CAE y QR enviada por WhatsApp/email (homologación ARCA en v1 — DD-09).
- [ ] CA-2: validación preventiva de cobertura antes de registrar la práctica (demo contra convenio ficticio "OS Demo" — DD-11).
- [ ] CA-3: liquidación por período con trazabilidad.
**Reglas relacionadas**: RN-AD-01, RN-OS-01, RN-OS-03.

## Épica 5: Roles, reportes y datos (v1)

### US-040 — Roles y permisos + trazabilidad
**Como** administrador **Quiero** gestionar usuarios y roles con auditoría inmutable **Para** controlar accesos.
**Criterios de aceptación**:
- [ ] CA-1: matriz RBAC de `03_actores_y_roles.md` aplicada en backend y UI.
- [ ] CA-2: registro inmutable usuario/IP/dispositivo.
**Reglas relacionadas**: RN-SE-01, RN-SE-02.

### US-041 — Reportes básicos + exportación
**Como** administrador **Quiero** reportes de agenda, ausentismo, caja y exportación total **Para** decidir y no quedar cautivo.
**Criterios de aceptación**:
- [ ] CA-1: reportes agenda/ausentismo/caja/liquidaciones.
- [ ] CA-2: exportación total (PDF + estructurado) sin cargo.
**Reglas relacionadas**: RN-SE-03.

## Épica 6: Etapa posterior (no v1)

US-050 periodontograma e imágenes/RX · US-051 IA (agente de turnos, dictado, resumen) · US-052 portal/app del paciente · US-053 campañas y recupero de inactivos · US-054 multisucursal · US-055 laboratorio e inventario · US-056 API pública e integraciones (Google Calendar, radiología, marketing) · US-057 telemedicina · US-058 modo offline degradado · US-059 planificación 3D. (Sin criterios de aceptación en esta versión; se detallan cuando entren al roadmap.)
