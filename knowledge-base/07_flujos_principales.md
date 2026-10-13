# Flujos Principales

## Flujo 1: Reserva online de turno
**Disparador**: el paciente abre el enlace público. **Actor**: paciente.
**Pasos**:
1. Frontend muestra profesionales, prestaciones y disponibilidad real.
2. Paciente elige horario; API valida anti-solapamiento (RN-TU-01) y crea el turno en estado reservado.
3. API programa recordatorios 48/24 h y envía confirmación por WhatsApp con enlace tokenizado.
4. Si la prestación requiere seña, el flujo deriva al pago (Flujo 4 parcial).
**Casos de error**:
- Horario tomado en concurrente → reintento con disponibilidad actualizada.
- Teléfono inválido → error visible, sin turno creado.

## Flujo 2: Confirmación / cancelación / reprogramación por WhatsApp
**Disparador**: recordatorio programado o mensaje del paciente. **Actor**: paciente (+ bot).
**Pasos**:
1. Bot envía recordatorio con enlace (token un solo uso, con vencimiento).
2. Paciente confirma → turno a confirmado; cancela → turno liberado + dispara lista de espera (RN-TU-05); reprograma → validación RN-TU-01 y nuevo horario.
3. Agenda actualizada sin intervención de recepción.
**Diagrama de secuencia** (ASCII):
```
Paciente → WhatsApp → API → DB (turno + recordatorio)
                         ← actualiza agenda
         ← confirmación por WhatsApp
[si cancela] API → ListaEspera → ofrece hueco al siguiente (FIFO)
```
**Casos de error**:
- Token vencido o fuera de plazo → se deriva a recepción.
- Fallo de envío WhatsApp → reintento + alerta a recepción.

## Flujo 3: Atención con odontograma y presupuesto
**Disparador**: paciente en sillón. **Actor**: odontólogo.
**Pasos**:
1. Odontólogo abre ficha clínica y registra evolución.
2. Actualiza odontograma FDI por pieza/cara con diagnósticos.
3. Genera presupuesto con cobertura/copago calculados (validación RN-OS-01/02).
4. Paciente acepta → plan en curso + consentimiento firmado si aplica.
**Casos de error**:
- Cobertura no validable (servicio externo caído) → presupuesto marcado "cobertura pendiente de verificación", sin bloquear la atención.

## Flujo 4: Cobro con Mercado Pago y factura ARCA
**Disparador**: cobro de seña o tratamiento. **Actor**: recepcionista/paciente.
**Pasos**:
1. Caja registra cobro (efectivo o link MP); webhook MP concilia el pago.
2. Sistema emite comprobante y, si es fiscal, factura B/C con CAE y QR vía ARCA.
3. Factura enviada al paciente por WhatsApp/email; caja y turno actualizados.
**Casos de error**:
- Webhook MP duplicado/tardío → idempotencia por id de pago.
- ARCA fuera de servicio → comprobante interno emitido + factura fiscal encolada para reintento (nunca se pierde el cobro).

## Flujo 5: Lista de espera ante hueco liberado
**Disparador**: cancelación. **Actor**: sistema.
**Pasos**:
1. Hueco liberado → busca entradas compatibles por orden.
2. Ofrece por WhatsApp con vencimiento; si acepta → turno creado; si vence/rechaza → siguiente.
**Casos de error**:
- Nadie acepta → hueco vuelve a disponibilidad pública.
