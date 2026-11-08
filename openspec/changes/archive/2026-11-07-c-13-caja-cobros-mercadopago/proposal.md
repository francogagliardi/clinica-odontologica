# Proposal

## Why

La clínica cobra señas y tratamientos, pero hoy no tiene dónde registrarlos: C-06/C-07 dejan el turno con `sena_estado` y C-12 cierra el presupuesto con un copago, sin un hecho económico que los concilie. Sin cobros ni caja diaria no se puede asegurar la asistencia, conciliar Mercado Pago ni cerrar el día con arqueo (US-030, Flujo 4, RN-AD-02/03/04).

## What Changes

- Nuevo modelo `Cobro` (paciente, turno o presupuesto opcional, tipo `sena|tratamiento|otro`, monto ARS, medio `efectivo|mercadopago`, estado `pendiente|aprobado|rechazado|reembolsado|perdido`, `proveedor_pago_id` único, `fecha_operacion` en UTC-3).
- Seña solo si la prestación del turno tiene `requiere_sena=true` y por el `monto_sena` exacto (RN-TU-08); al aprobarse concilia `Turno.sena_estado='pagada'` (RN-AD-02).
- Pérdida de seña: `Turno.sena_estado` sigue siendo la fuente de verdad; el `Cobro` de seña se refleja como `perdido` cuando el turno pasa a pérdida por cancelación tardía o ausentismo (RN-TU-04), sin reimplementar la regla en caja.
- Mercado Pago **sandbox**: preferencia/link de pago mediante proveedor abstraído (`MP_PROVIDER=test`, sin llamadas ni costos reales), webhook público con firma HMAC, ack inmediato e idempotencia por `proveedor_pago_id`. El procesamiento del webhook es sincrónico y transaccional: no se agrega una cuarta cola Redis (R-06 mantiene `whatsapp:send`, `recordatorios:due`, `arca:emitir`).
- Caja diaria con movimientos: `CajaDiaria` (fecha UTC-3, apertura, cierre) y `MovimientoCaja` (`ingreso|gasto|deuda`, con vínculo opcional al cobro). El arqueo suma ingresos/gastos/deudas y exige que el efectivo contado coincida con el sistema; diferencia ≠ 0 → 409 y no se cierra (RN-AD-03).
- Endpoints `/cobros` (alta, listado/ficha, reembolso) y `/caja` (abrir, movimientos, consultar, cerrar/arqueo), más `POST /webhooks/mercadopago` público.
- Reembolso en v1: solo registra el estado `reembolsado` y auditoría; no hay devolución real a Mercado Pago ni movimiento automático de caja.
- Migración `0012_caja_cobros` (el `008a` del roadmap está desactualizado; el head real es `0011_presupuestos`).
- Sin UI en este change: la superficie pública de pago es el checkout hospedado de Mercado Pago; la SPA de caja queda para un change posterior.

## Capabilities

### New Capabilities

- `caja/cobros`: alta y consulta de cobros, seña condicionada por prestación, cobro de tratamiento contra presupuesto, preferencia MP sandbox, webhook firmado e idempotente, conciliación con turno/presupuesto, pérdida y reembolso, RBAC y auditoría.
- `caja/arqueo`: caja diaria por fecha UTC-3, movimientos de ingreso/gasto/deuda, totales del día, arqueo y cierre con diferencia cero.

### Modified Capabilities

- `agenda/turnos`: el paso a `cancelado` desde el backoffice aplica la misma política de plazo que la ruta pública y el paso a `ausente` marca pérdida de seña cuando la prestación la requiere (RN-TU-04). El estado sigue viviendo en `Turno.sena_estado`.

## Impact

- **Backend**: modelos `app/models/caja.py`; dominio `app/domain/caja.py`; servicios `app/application/cobros.py` y `app/application/caja.py`; proveedor `app/infrastructure/mercadopago.py`; routers `app/api/cobros.py`, `app/api/caja.py` y `app/api/webhooks.py`; repos y `UnitOfWork`; hooks de seña en `app/api/publico.py` y `app/api/turnos.py`.
- **Migración**: `backend/alembic/versions/0012_caja_cobros.py` (`cobros`, `cajas_diarias`, `movimientos_caja`, índices únicos parciales).
- **Configuración**: `MP_PROVIDER=test` y `MP_WEBHOOK_SECRET` en `Settings`, `.env.example` y entorno de tests; `MP_ACCESS_TOKEN` existente queda sin uso real en v1.
- **Base de datos**: PostgreSQL sigue siendo la única fuente de verdad de caja; Redis no se usa para conciliar pagos.
- **Fuera de alcance**: emisión fiscal ARCA (C-14), devoluciones reales, liquidación de obras sociales, UI de caja y cualquier cobro con credenciales/costos reales (R-12).
