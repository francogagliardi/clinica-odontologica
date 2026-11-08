# Proposal

## Why

La clínica ya agenda, atiende, cobra, factura y liquida, pero no puede mirar esos datos en conjunto ni sacarlos del sistema: no hay reportes de agenda/ausentismo/caja/liquidaciones y no existe forma de exportar el historial completo de un paciente o del consultorio. Sin eso se incumplen US-041 y RN-SE-03, y el antídoto contra la cautividad que declara DD-05 queda como promesa sin producto.

## What Changes

- Reportes de solo lectura bajo `/reportes`, con rango obligatorio en UTC-3 (máximo 62 días, misma convención que `GET /turnos`) y filtros por profesional, sillón, obra social y estado:
  - **Agenda**: turnos por rango/estado/profesional/sillón, ocupación en minutos contra la agenda configurada y cancelaciones.
  - **Ausentismo**: atendidos vs cancelados/ausentes, tasa de ausentismo y detalle por turno.
  - **Caja**: cobros por medio y estado (efectivo vs Mercado Pago), movimientos, cajas/arqueos y cierres.
  - **Liquidaciones**: por obra social, período y estado, con cobertura total y prácticas por prestación.
- Todos los totales se calculan en SQL (`SUM`/`COUNT`/`FILTER`) y se devuelven con el rango y la zona horaria usados; el cliente solo presenta.
- Exportación total en **ZIP** con `exportacion.pdf`, `datos.json`, `manifiesto.json` y `csv/<entidad>.csv` para alcance `paciente` o `consultorio`, siempre disponible y sin cargos ni ventanas (RN-SE-03/DD-05).
- La exportación incluye pacientes, turnos, historia/evoluciones, odontograma/hallazgos, adjuntos, consentimientos, presupuestos/ítems, cobros, caja, comprobantes, liquidaciones, recordatorios/mensajes, lista de espera, catálogo usado y auditoría. Excluye secretos y credenciales: `hash_password`, tokens de enlace público, tokens de un solo uso, secretos de webhooks, payloads/respuestas de proveedores y `link_pago`.
- Exportación como **job durable**: `POST /exportaciones` responde 202, la fila `exportaciones` es la fuente de verdad y el worker `reportes` genera el artefacto; `GET /exportaciones/{id}` informa estado y `GET /exportaciones/{id}/archivo` entrega el ZIP cuando está listo. Redis solo acelera; un barrido de pendientes reintenta sin cola.
- Nueva cola reservada `reportes:generar` (cuarta) y modo `python -m app.workers reportes`; `platform/job-queues` se modifica en consecuencia.
- Migración `0014_reportes` (`down_revision='0013_facturacion_arca'`): tabla `exportaciones` con estado, scope, artefacto, intentos y claim. No altera tablas existentes.
- UI funcional `features/reportes` en `/reportes`: tableros de los cuatro reportes, filtros y botón de exportación con sondeo de estado. Sin sistema de diseño: la capa visual es C-17.
- Nuevas variables de entorno para límites de exportación y ritmo del worker; dependencia nueva `fpdf2` (Python puro) solo para el PDF.

## Capabilities

### New Capabilities

- `reportes/reportes`: consultas agregadas de agenda, ausentismo, caja y liquidaciones, con filtros acotados, totales calculados en SQL y acceso por rol.
- `reportes/exportacion`: exportación total por paciente o consultorio en PDF + estructurado, generada por un job durable, con RBAC, auditoría y exclusiones de secretos.

### Modified Capabilities

- `platform/job-queues`: el contrato de nombres reservados pasa de tres a cuatro colas al incorporar `reportes:generar`; se mantiene la regla Redis-solo-jobs.

## Impact

- **Backend**: modelos `app/models/reportes.py`; dominio `app/domain/reportes.py`; servicios `app/application/reportes.py` y `app/application/exportaciones.py`; routers `app/api/reportes.py` y `app/api/exportaciones.py`; constructor de PDF/ZIP en `app/infrastructure/exportacion.py`; worker `app/workers/__main__.py`; repos y `UnitOfWork`.
- **Migración**: `backend/alembic/versions/0014_reportes.py` (tabla `exportaciones`, índices de estado/próximo intento y de scope por consultorio).
- **Configuración**: `EXPORTACION_MAX_FILAS`, `EXPORTACION_MAX_BYTES`, `EXPORTACION_MAX_INTENTOS`, `REPORTES_WORKER_INTERVAL_SECONDS`; `.env.example` y entorno de tests.
- **Dependencias**: `fpdf2` pineada en `backend/requirements.txt` (sin librerías de sistema); `zipfile`/`csv`/`json` de la biblioteca estándar.
- **Frontend**: `features/reportes/api.ts`, `pages/ReportesPage.tsx`, ruta `/reportes` en `App.tsx` y pruebas Vitest.
- **Base de datos**: PostgreSQL sigue siendo la fuente de verdad de exportaciones y jobs; Redis solo transporta ids.
- **Fuera de alcance**: diseño visual (C-17), reportes programados o envío por email/WhatsApp, BI/consultas ad-hoc, exportación incremental, retención punitiva o cobro por exportar, y cualquier servicio externo de generación de PDF (R-12).
