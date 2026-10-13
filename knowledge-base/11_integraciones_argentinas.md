# Integraciones Argentinas (WhatsApp · Mercado Pago · ARCA · Cobertura)

> Archivo extra del dominio (permitido por la skill: prefijo `1X_`). Operativiza la fila "Obligatorias v1" del Discovery con riesgos y estrategia sandbox.

## WhatsApp Business API (oficial Meta) — obligatoria v1

- Uso: recordatorios 48/24 h, confirmación/cancelación/reprogramación, lista de espera, envío de facturas (Flujos 2, 4, 5).
- Async con Redis (DD-07c): los envíos se encolan en Redis (`whatsapp:send`) desde la API y los consumen workers en 2.º plano con reintento exponencial; la programación 48/24 h vive en colas diferidas de Redis (`recordatorios:due`); estado de cada mensaje persistido en PostgreSQL (`MensajeWhatsApp`), nunca solo en Redis.
- Exigencias: número + plantillas aprobadas + ventana de 24 h; costo por mensaje (los competidores lo cobran aparte: AgendaPro +$7.900/mes, DentalTec packs USD 9/50 — nuestro diferencial es incluirlo, DD-03).
- v1 universitaria: capa de prueba / número de test; plantillas mínimas (recordatorio, confirmación, oferta de hueco).
- Riesgo: aprobación de plantillas y costos fuera de control del proyecto (riesgo Discovery).

## Mercado Pago — obligatoria v1

- Uso: señas vinculadas a reserva, cobro de tratamientos, conciliación automática (US-030, Flujo 4).
- Async con Redis (DD-07c): la conciliación diferida y los reintentos de cobro corren como jobs en 2.º plano; los webhooks se acusan de inmediato y se procesan idempotentemente vía worker.
- v1 universitaria: **modo sandbox** (credenciales TEST), webhooks idempotentes en URL pública (túnel o demo local).
- Riesgo: comisiones y condiciones pueden cambiar; no asumir valores del benchmark sin fuente (verificación: comisión 2 % NO RESPALDADA en /ar/planes).

## Facturación ARCA (ex AFIP) — obligatoria v1 (alcance según P-03)

- Uso: factura electrónica B/C con CAE y QR por cada cobro fiscal (RN-AD-01, US-031, Flujo 4).
- Async con Redis (DD-07c): la emisión fiscal va a cola `arca:emitir` con reintentos; el cobro nunca se bloquea por ARCA (Flujo 4 degradado).
- v1 universitaria: **ambiente de homologación** (CUIT/CERT/KEY de prueba); si P-03 resuelve "comprobante interno", ARCA pasa a etapa posterior con cola de reintentos ya diseñada.
- Riesgo: alta de certificados y homologación dependen de terceros; el diseño con cola evita que bloquee los cobros.

## Verificación de cobertura (PUCO / obras sociales) — deseable

- Uso: validación preventiva antes de registrar la práctica (RN-OS-01; diferencial tipo DentalTec/ClinIA).
- v1: cálculo local de cobertura/copago por convenio cargado (RN-OS-02) contra el convenio ficticio "OS Demo" (DD-11); conexión PUCO real solo si hay acceso; 1 obra social real en segunda iteración.
- Riesgo: sin API accesible se opera con convenios manuales; no bloquear el MVP por esto (SU-03).

## Estrategia común v1

Sandbox/homologación/prueba para las tres obligatorias; credenciales solo en variables de entorno (`08_arquitectura_propuesta.md`); reintentos con colas Redis para ARCA (`arca:emitir`) y WhatsApp (`whatsapp:send`); programación de recordatorios en Redis (`recordatorios:due`); webhooks idempotentes para MP (ack inmediato + worker); spike temprano de cada integración para validar SU-03 antes del desarrollo core.
