# Verificación de escenarios — c-13-caja-cobros-mercadopago

Fecha: 2026-11-07. Backend con PostgreSQL real (base descartable para tests y smoke), proveedor Mercado Pago `test` sin red ni credenciales reales. Frontend sin cambios.

## Resultado global

- **Suite backend completa: 969 passed, 0 failed** (`pytest tests -q`, 51 min 02 s).
- Frontend: **28 passed** (`npm test`) y `npm run typecheck` limpio.
- Migración `0012_caja_cobros` reversible (`upgrade head → downgrade 0011 → upgrade head`).
- Smoke C-13 OK con base descartable y cliente MP compartido.

## Matriz requirement → test

### `caja/cobros` (11 requirements)

| Requirement | Test(s) |
|---|---|
| Alta de cobro en efectivo con conciliación inmediata | `test_cobros_efectivo.py` |
| Seña solo para prestaciones que la requieren | `test_cobros_sena.py` |
| Una sola seña viva por turno | `test_cobros_sena.py` |
| Cobro de tratamiento contra presupuesto aceptado | `test_cobros_tratamiento.py` |
| Preferencia de pago Mercado Pago en sandbox | `test_cobros_mp.py` |
| Webhook de Mercado Pago firmado y público | `test_webhook_mp.py` |
| Conciliación idempotente del pago | `test_webhook_mp.py` |
| Pérdida de seña reflejada desde el turno | `test_sena_perdida.py` |
| Reembolso registrado sin devolución real | `test_cobros_reembolso.py` |
| Acceso a cobros por rol | `test_caja_rbac.py` |
| Auditoría de las escrituras de cobro | `test_caja_auditoria.py` |

### `caja/arqueo` (5 requirements)

| Requirement | Test(s) |
|---|---|
| Caja diaria única por fecha UTC-3 | `test_caja_arqueo.py` |
| Movimientos de ingreso, gasto y deuda | `test_caja_arqueo.py` |
| Arqueo con efectivo esperado | `test_caja_arqueo.py` |
| Cierre con diferencia cero | `test_caja_arqueo.py` |
| Acceso y auditoría de caja | `test_caja_rbac.py`, `test_caja_auditoria.py` |

### `agenda/turnos` (delta, 1 requirement)

| Requirement | Test(s) |
|---|---|
| Pérdida de seña por cancelación tardía y ausentismo | `test_sena_perdida.py` |

### Persistencia, migración y dominio

| Verificación | Test(s) |
|---|---|
| Tablas, CHECKs e índices de cobros/caja/movimientos | `tests/unit/test_models_metadata.py`, `test_caja_migracion.py` |
| Head 0012 y downgrade/upgrade | `test_migration.py`, `tests/test_migrations_env.py` |
| Fecha UTC-3, arqueo y transiciones | `tests/unit/test_caja_dominio.py` |
| Provider MP y firma HMAC | `tests/unit/test_mercadopago_provider.py`, `test_mercadopago_firma.py` |

## SQLSTATE observados

- `23505`: segunda seña viva, `proveedor_pago_id` duplicado, dos movimientos para el mismo cobro, versión duplicada.
- `23514`: monto ≤ 0, tipo/referencias inválidas, caja con apertura negativa, cierre sin snapshot, pieza FDI inválida (C-11).
- `P0001`: `UPDATE`/`DELETE` directo sobre `registro_auditoria`, evoluciones firmadas, odontogramas/hallazgos y consentimientos.
- `55P03`: bloqueo `FOR UPDATE` en cierre concurrente de caja.

## Smoke C-13

Base `clinica_c13_smoke` + `TestClient` con `TestMercadoPagoClient` compartido (sin red):

| Paso | Resultado |
|---|---|
| Login admin | 200 |
| Turno ENDO para seña | 201 |
| Presupuesto CONS aceptado | 200, copago 4.800,00 |
| Abrir caja | 201, fecha 2026-11-07 |
| Cobro efectivo de tratamiento | 201 `aprobado` |
| Seña MP | 201 `pendiente` + link sandbox |
| Webhook aprobado firmado | 200; seña `pagada` |
| Webhook duplicado | 200 sin segundo ingreso |
| Arqueo | efectivo 4.800,00; MP 10.000,00 |
| Cierre cuadrado | 200, diferencia 0,00 |
| Cierre repetido | 409 |
| Limpieza | base descartable eliminada; demo reseedeada en `0012_caja_cobros` |

## Desvíos

- La suite completa comparte base con la demo: al terminar se reseedeó la base y se restauró el head `0012_caja_cobros`.
- El smoke de webhook requiere un `TestMercadoPagoClient` compartido; se hizo in-process con `dependency_overrides`, sin agregar endpoints de prueba a la API.
- La demo canónica no crea profesionales ni turnos; para pruebas manuales de caja hay que crear un profesional/turno o reutilizar los datos de los changes anteriores.
