# Visión y Objetivos

**Proyecto**: Sistema de gestión odontológica con turnos y agenda (mercado argentino).
**Contexto**: Proyecto universitario — Metodología I, integrante Franco Nicolás Gagliardi.
**Fuentes**: `docs/discovery/informe-discovery.md` (18 sistemas, matriz ponderada líder DentalCore 4,63), `docs/discovery/verificacion-fuentes.md` (auditoría 40 CONFIRMADO / 4 PARCIAL / 8 NO RESPALDADO, P1–P12), sección `discovery` de `.active-orchestrator-state.json`.

## Propósito del sistema

Centralizar en una única plataforma SaaS la agenda, la historia clínica odontológica y la administración de consultorios y clínicas dentales argentinas, eliminando la gestión manual por WhatsApp/papel/planillas que hoy genera dobles reservas, ausentismo sin recupero, confirmaciones manuales y débitos evitables de obras sociales.

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|---|---|---|
| Odontólogo independiente | Gestionar su agenda, historia clínica y cobro sin carga administrativa | Presupuestos en consulta, cobro directo con Mercado Pago, recordatorios automáticos |
| Recepcionista / administrativo | Operar la agenda diaria sin solapamientos ni llamadas manuales | Confirmar turnos, gestionar caja, señas y facturación |
| Administrador de clínica | Explotar múltiples profesionales, sillones y (a futuro) sucursales con datos | Liquidaciones, reportes, roles, recupero de ausentes/inactivos |
| Paciente | Reservar y gestionar sus turnos online 24/7 | Confirmar/cancelar/reprogramar desde el recordatorio, pagar señas, ver presupuestos |
| Roles secundarios (asistente, laboratorio, auditor/obra social) | Trazabilidad de su parte del flujo | Órdenes de laboratorio, auditoría de cobertura |

## Alcance v1 (MVP)

Imprescindibles (del informe §D + checklist Discovery):

- Agenda diaria/semanal multi-profesional y multi-sillón con duraciones variables, bloqueos, sobreturnos y prevención de solapamientos.
- Reserva online 24/7 con enlace público.
- Confirmación / cancelación / reprogramación por WhatsApp con recordatorios automáticos.
- Lista de espera automática sobre huecos liberados.
- Ficha clínica + odontograma FDI + presupuestos / planes de tratamiento.
- Caja, cobros y señas con Mercado Pago; facturación ARCA.
- Obras sociales básicas con validación de cobertura.
- Roles y permisos.
- Reportes básicos.

Diferenciadores del MVP (oportunidades detectadas §C):

- Precio ARS publicado + prueba gratuita.
- WhatsApp incluido en el plan (no como extra con costo aparte).
- Validación preventiva de obras sociales antes de confirmar el plan.
- Consentimiento informado con firma + trazabilidad desde el día uno.
- Exportación total de datos sin cautividad ni penalizaciones.

## Fuera de alcance (etapas posteriores)

Periodontograma e imágenes/RX; IA conversacional, dictado y resumen clínico; portal/app del paciente y app móvil; campañas y recupero de inactivos; multisucursal; laboratorio e inventario; API pública e integraciones (Google Calendar, radiología, marketing); telemedicina/videoconsulta; modo offline; planificación 3D. Detalle completo en `06_funcionalidades.md` y `10_preguntas_abiertas.md`.

## Métricas de éxito

- Cero turnos superpuestos por profesional/sillón en operación normal.
- Reducción medible del ausentismo vía recordatorios/confirmación (los proveedores declaran ~40 %; validar con datos propios, no asumir la cifra).
- Tiempo administrativo de confirmación manual tendiendo a cero.
- Todo cobro con comprobante emitido; débitos de obras sociales reducidos vía validación preventiva.
- MVP demostrable con datos ficticios (restricción universitaria).
