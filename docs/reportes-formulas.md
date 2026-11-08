# Fórmulas SQL de los reportes (C-15, design D8)

> Fuente de implementación: `backend/app/infrastructure/repositories.py`
> (`ConsultaReportesRepository`) y `backend/app/domain/reportes.py`.
> Los reportes son **solo lectura**: no escriben ni auditan (D10). Los totales se
> calculan en PostgreSQL sobre el rango completo; el detalle se trunca aparte y
> nunca altera los agregados.

## Rango y zona horaria

- `desde`/`hasta` son fechas locales argentinas (UTC-3).
- Columnas `timestamptz` (`turnos.inicio`) usan el intervalo semiabierto
  `[desde 00:00 -03, hasta+1 00:00 -03)` generado por
  `rango_local_a_utc`.
- Columnas `date` (`cobros.fecha_operacion`, `cajas_diarias.fecha`) se comparan
  directo contra las fechas locales.

## Agenda y ocupación

| Métrica | Fórmula SQL |
|---|---|
| `total_turnos` / `por_estado` | `COUNT(*) FILTER (WHERE estado = ...)` agrupado por `estado` |
| `por_profesional` / `por_sillon` | `COUNT(*) GROUP BY profesional_id` / `sillon_id` |
| `minutos_disponibles` | `SUM(EXTRACT(EPOCH FROM (hora_hasta - hora_desde)) / 60)` por cada fecha del rango cuyo `EXTRACT(ISODOW) - 1` esté en `dias_atencion` (`generate_series` + `CROSS JOIN`) |
| `minutos_ocupados` | `SUM(EXTRACT(EPOCH FROM (fin - inicio)) / 60)` de turnos `reservado|confirmado|en_sala|atendido` **no sobreturno** |
| `minutos_sobreturno` | los mismos minutos con `es_sobreturno = true`, informados aparte |
| `ocupacion_porcentaje` | `ROUND(ocupados * 100.0 / NULLIF(disponibles, 0), 2)`; `0.00` y `sin_agenda=true` si `disponibles = 0` |

## Ausentismo

| Métrica | Fórmula |
|---|---|
| `atendidos` / `cancelados` / `ausentes` | `COUNT(*) FILTER (WHERE estado = ...)` |
| `turnos_activos` | `COUNT(*) FILTER (WHERE estado IN ('reservado','confirmado','en_sala'))`, fuera de las tasas |
| `tasa_ausentismo` | `(cancelados + ausentes) / (atendidos + cancelados + ausentes)` |
| `tasa_no_asistencia` | `ausentes / (atendidos + cancelados + ausentes)` |
| `sin_cierres` | denominador `= 0`; ambas tasas `0.00`, sin división por cero |

Redondeo half-up a dos decimales (`0.375 → 0.38`).

## Caja

| Métrica | Fórmula SQL |
|---|---|
| `total_aprobado` | `SUM(monto) FILTER (WHERE estado = 'aprobado')` |
| `total_efectivo` / `total_mercadopago` | el mismo `SUM` con `FILTER (estado = 'aprobado')`, agrupado por `medio` |
| `por_estado` | `COUNT(*) GROUP BY estado` sobre **todos** los cobros del rango |
| `movimientos_por_tipo` | `COUNT(*)`, `SUM(monto)` agrupados por `tipo`/`medio`, unidos a su caja |
| `cajas_del_rango` | filas de `cajas_diarias` tal como quedaron persistidas; una caja abierta informa cierre nulo y **no** se re-arquea |

Para el odontólogo, el alcance propio de caja se aplica por
`turnos.profesional_id` o `presupuestos.profesional_id` asociados al cobro.
Gastos y deudas se informan aparte: nunca se restan de `total_aprobado`.

## Liquidaciones

| Métrica | Fórmula SQL |
|---|---|
| Cabeceras incluidas | `desde <= :hasta AND hasta >= :desde` (cruce inclusivo, no contención) |
| `cantidad_liquidaciones` | `COUNT(*)` por `(obra_social_id, estado)` |
| `total_cobertura` | `SUM(total_cobertura)` de cabeceras congeladas |
| `cantidad_practicas` | `SUM(cantidad_practicas)` de cabeceras |
| Detalle por prestación | `SUM(items_liquidacion.cantidad)` y `SUM(cobertura_item)` agrupados por `prestacion_codigo`, con `items_liquidacion.deleted_at IS NULL` |

Los ítems dados de baja no suman; el total por prestación coincide con la suma
de las cabeceras del rango.

## Cobertura de pruebas (fuente independiente)

`backend/tests/integration/test_reportes_repos.py` define un dataset
determinista (11 turnos, 2 profesionales, 2 sillones, 7 cobros, 4 movimientos,
2 cajas, 2 liquidaciones) y compara cada agregado contra valores escritos a
mano en el test, no contra la misma SQL. `EXPLAIN (ANALYZE, BUFFERS)` se corrió
sobre ese dataset: agenda por estado y cobros usan índices existentes; las
consultas restantes usan los índices de agenda/profesional, caja/fecha,
liquidación/período y el único parcial de ítems.
