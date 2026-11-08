# Proposal

## Why

C-13 ya registra y concilia cobros, pero hoy un cobro aprobado no produce ningún comprobante: no hay factura fiscal, no hay respaldo interno cuando ARCA falla y la clínica no puede reclamar a una obra social. Sin comprobante se incumple RN-AD-01 y sin validación/liquidación no se puede operar con cobertura (US-031, Flujo 4, DD-04/DD-09/DD-11).

## What Changes

- Nuevo modelo `Comprobante` (uno por cobro aprobado): numeración interna propia, `tipo B|C`, `ambiente='homologacion'`, `estado pendiente|emitido|fallido`, CAE, vencimiento de CAE, punto de venta/número fiscal, QR, importe, snapshot del receptor, payload/respuesta del proveedor y control de reintentos.
- Hook de emisión: al aprobarse un cobro (efectivo al crear o Mercado Pago al conciliar) se crea el comprobante **en la misma transacción**; un cobro no aprobado nunca tiene comprobante.
- Fallback interno: si ARCA no está disponible, el comprobante interno queda emitido con su número propio y el cobro no se bloquea; la factura fiscal queda `pendiente` y encolada en `arca:emitir` para reintento.
- Proveedor ARCA abstraído: `ArcaClient` + `TestArcaClient` (`ARCA_PROVIDER=test`), CAE/QR simulados deterministas por clave de idempotencia, fallo inyectable, sin red ni certificados reales (R-12).
- Worker `arca:emitir`: claim atómico, reintentos exponenciales, tope de intentos, barrido de comprobantes vencidos (PostgreSQL es la fuente de verdad; Redis solo acelera), idempotencia fiscal y reintento manual.
- QR fiscal con formato AFIP (`https://www.afip.gob.ar/fe/qr/?p=<base64url(JSON)>`) y QR interno equivalente; ambos son strings verificables por test.
- Validación preventiva de cobertura contra el convenio local de "OS Demo": `cubierta|no_cubierta|pendiente_verificacion`, cobertura y copago calculados con el precio base; es consultiva y **no bloquea** la atención (Flujo 3).
- Liquidación de obras sociales por período (UTC-3): cabecera `borrador|cerrada` con `desde/hasta`, ítems trazables a `ItemPresupuesto`, `Presupuesto` y `Cobro`, total de cobertura y cierre inmutable.
- Endpoints nuevos: `/comprobantes` (consulta, reintento, envío), `/obras-sociales/cobertura` y `/obras-sociales/liquidaciones` (crear, listar, ficha, editar observaciones, cerrar, borrar borrador).
- Migración `0013_facturacion_arca` (`down_revision='0012_caja_cobros'`); el "008b" del roadmap está desactualizado.
- Sin UI en este change; la superficie es la API y el comprobante se consulta por sus endpoints.

## Capabilities

### New Capabilities

- `fiscal/comprobantes-arca`: comprobante único por cobro aprobado, emisión fiscal en homologación con CAE/QR, fallback interno, worker `arca:emitir` con reintentos e idempotencia, envío simulado y RBAC/auditoría.
- `comercial/liquidaciones-obras-sociales`: validación preventiva de cobertura y liquidación de obras sociales por período con trazabilidad de prácticas incluidas.

### Modified Capabilities

<!-- Ninguna: C-14 agrega endpoints y tablas nuevas sin cambiar el contrato observable de las specs archivadas. -->

## Impact

- **Backend**: modelos `app/models/fiscal.py` y `app/models/liquidaciones.py`; dominio `app/domain/fiscal.py` y `app/domain/liquidaciones.py`; servicios `app/application/comprobantes.py`, `app/application/cobertura.py` y `app/application/liquidaciones.py`; proveedor `app/infrastructure/arca.py`; routers `app/api/comprobantes.py`, `app/api/cobertura.py` y `app/api/liquidaciones.py`; hooks en `app/application/cobros.py`; worker `app/workers/__main__.py`; repos y `UnitOfWork`.
- **Migración**: `backend/alembic/versions/0013_facturacion_arca.py` (`comprobantes`, `comprobantes_envios`, `secuencias_comprobantes`, `liquidaciones_obras_sociales`, `items_liquidacion`; índices únicos parciales y constraint de exclusión de períodos).
- **Configuración**: `ARCA_PROVIDER=test`, `ARCA_PUNTO_VENTA`, `ARCA_CONDICION_EMISOR`, `ARCA_MAX_INTENTOS` y `ARCA_WORKER_INTERVAL_SECONDS`; `ARCA_CUIT/CERT/KEY` quedan declarados pero no se usan en v1.
- **Base de datos**: PostgreSQL sigue siendo la fuente de verdad de comprobantes, jobs y liquidaciones; Redis solo transporta ids de job.
- **Fuera de alcance**: certificados/red reales de ARCA, notas de crédito, topes/frecuencias/nomenclador real, envío real de email, UI fiscal y cualquier costo real de terceros (R-12).
