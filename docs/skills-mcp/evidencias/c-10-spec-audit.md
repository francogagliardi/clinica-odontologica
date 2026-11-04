# Auditoría de escenarios — c-10-lista-espera-automatica

Fecha: 2026-11-04. Auditoría con `spec-scenario-auditor` (tarea 0.1) sobre las cinco
deltas del change: `agenda/lista-espera` (30 escenarios), `comunicaciones/ofertas-hueco`
(25), `agenda/turnos` (8), `agenda/reserva-publica` (6) y `agenda/recursos-agendables`
(13). Contrastadas contra RN-TU-05 (`05_reglas_de_negocio.md:11`), RN-TU-01 (`:7`),
RN-NO-02/RN-NO-03 (`:39–40`), Flujo 5 (`07_flujos_principales.md` §Flujo 5),
`04_modelo_de_datos.md:55–57` §EntradaListaEspera y `design.md` D1–D13.

## Matriz de trazabilidad

| Requirement | Regla KB | Escenario esperado | Error de negocio | Borde | Veredicto |
|---|---|---|---|---|---|
| `agenda/lista-espera` · Alta de entrada en la lista de espera | RN-TU-05 (`05_reglas_de_negocio.md:11`), US-003/CA-1, `04_modelo_de_datos.md:55–57` | sí (201 + `orden` creciente) | sí (409 duplicado; 404 recurso inactivo/ajeno) | sí (422 campo extra/servidor) | OK |
| `agenda/lista-espera` · Baja de una entrada pendiente | RN-TU-05, RN-SE-02, `04_modelo_de_datos.md:55–57` | sí (200, sale del FIFO) | sí (409 `ofrecido`; 404 inexistente/ajeno) | sí (baja lógica + entrada dada de baja no recibe ofertas) | OK |
| `agenda/lista-espera` · Selección FIFO con compatibilidad | RN-TU-05, Flujo 5 paso 1, US-003/CA-1 | sí (menor `orden` gana) | sí (incompatible por profesional se saltea) | sí (entrada sin profesional; sin candidatas) | OK |
| `agenda/lista-espera` · Oferta con vencimiento y rotación | US-003/CA-2, Flujo 5 paso 2, RN-TU-05, R-06 | sí (rota al siguiente) | sí (hueco ya ocupado al rotar) | sí (vencimiento en el borde exacto; última entrada) | OK |
| `agenda/lista-espera` · Conversión a turno sin solapamiento | RN-TU-01 (`:7`), RN-TU-05, RN-NO-02, R-10 | sí (200 + turno en recursos retenidos) | sí (retención vencida + horario tomado → 409) | sí (dos aceptaciones concurrentes; reserva pública simultánea) | OK |
| `agenda/lista-espera` · Retención atómica del hueco ofrecido | RN-TU-05, RN-TU-01, Flujo 5 | sí (cancelación retiene; aceptación libera; rechazo libera) | sí (en `agenda/turnos` §Reservas bloqueadas: alta/reprogramación 409) | sí (dos cancelaciones no duplican; retención vencida sin barrido; nadie acepta) | OK (error de negocio delegado a la delta de turnos, verificada en task 3.1) |
| `agenda/lista-espera` · Acceso a la lista de espera por rol | RN-SE-01 (`:44`), `03_actores_y_roles.md` §RBAC, R-03 | sí (recepción 201/200/200) | sí (odontólogo 403; asistente/auditor 403 escritura) | sí (sin token 401; consultorio ajeno 404) | OK |
| `comunicaciones/ofertas-hueco` · Mensaje de oferta con la plantilla existente | RN-NO-01/RN-NO-02 (`:38–39`), US-003/CA-2, R-06/R-12 | sí (mensaje `pendiente` + `whatsapp:send`) | sí (Redis caído no rompe la cancelación) | sí (`turno_id` nulo; reintento no duplica) | OK |
| `comunicaciones/ofertas-hueco` · Token de oferta de propósito propio | RN-NO-03 (`:40`), `03_actores_y_roles.md` §Rutas públicas | sí (solo hash, tipo `oferta_hueco`) | sí (vencido, otro propósito, entrada no ofrecida → 410) | sí (token reutilizado = reintento idempotente → 410) | OK |
| `comunicaciones/ofertas-hueco` · Consulta pública de la oferta | RN-NO-03, US-003, R-03 | sí (200 con prestación/profesional/inicio/vence) | sí (vencida → 410; sin datos sensibles) | sí (consultar dos veces no consume) | OK |
| `comunicaciones/ofertas-hueco` · Aceptación de la oferta por enlace | RN-TU-01/05, RN-NO-02/03, Flujo 5 paso 2 | sí (200 + turno en sillón retenido) | sí (retención vencida y tomada → 409; aceptar vencida → 410) | sí (dos aceptaciones concurrentes: una 200, otra 410) | OK |
| `comunicaciones/ofertas-hueco` · Rechazo de la oferta por enlace | US-003/CA-2, Flujo 5 paso 2, RN-TU-05 | sí (200 + siguiente retiene) | sí (rechazo de convertida → 410) | sí (sin siguiente: vuelve a disponibilidad; rechazo repetido) | OK |
| `comunicaciones/ofertas-hueco` · Aceptación o rechazo por respuesta de WhatsApp | RN-NO-02 (`:39`), `comunicaciones/whatsapp-webhook`, R-12 | sí (aceptar crea turno; rechazar rota) | sí (acción no aplicable → `aplicado=false, derivado=true`) | sí (evento duplicado del proveedor) | OK |
| `agenda/turnos` · Reservas bloqueadas por retenciones de lista de espera | RN-TU-05/01/06 (`:7,11,12`), Flujo 5, R-10 | sí (conversión libera y el turno bloquea) | sí (alta, reprogramación, reserva pública y sobreturno → 409) | sí (vencida sin barrido 201; otro recurso 201; consecutivo en el borde 201) | OK |
| `agenda/reserva-publica` · Disponibilidad pública real (MODIFIED) | US-001/CA-1, RN-TU-05/01/02/07, RN-NO-03 | sí (slots con duración real; retención vigente oculta) | sí (recurso inexistente/inactivo 404) | sí (fecha inválida 422; día sin atención; retención vencida no oculta) | OK |
| `agenda/recursos-agendables` · Disponibilidad base por profesional (MODIFIED) | RN-TU-01/02/05/07, US-001/CA-1, Flujo 1 | sí (consecutivos, duración, retención vigente oculta) | sí (404 profesional/prestación; 422 borde) | sí (día sin atención; último slot incompleto; otro profesional; retención vencida) | OK |

## Huecos detectados

Ninguno bloqueante. Dos observaciones de cobertura, ya resueltas por el diseño:

- **`agenda/lista-espera` · Retención atómica** no repite el 409 de alta/reprogramación:
  ese error de negocio vive en `agenda/turnos` §Reservas bloqueadas (delta MODIFIED) y
  se verifica en la tarea 3.1. Duplicarlo en dos deltas crearía dos fuentes de verdad
  para el mismo borde.
- **`comunicaciones/ofertas-hueco` · Token** clasifica «token reutilizado» como borde
  (reintento idempotente) y no como error: es el mismo comportamiento observable que el
  checklist de idempotencia de la skill. Las tres clases quedan cubiertas sin agregar
  escenarios.

## Escenarios no verificables

Ninguno. Todos los `THEN` son observables en HTTP (status + body), en PostgreSQL
(fila/estado/exclusion constraint) o en la cola (`whatsapp:send`). Los de la cola se
verifican con el Redis de prueba o el doble de `get_redis`.

## Escenarios sin tarea de verificación

Ninguno: `tasks.md` asigna 2.1/2.3 (alta, baja, RBAC), 3.1 (retención, disponibilidad,
409), 4.1 (FIFO y hueco liberado), 5.1 (mensaje, token, consulta), 6.1 (vencimiento y
rechazo), 7.1 (aceptación y conversión) y 8.1 (webhook) a cada bloque de escenarios.

## Deriva de dominio (KB vs spec)

- **Retención fuera de `ofrecido`**: la KB (`04_modelo_de_datos.md:55–57`) define
  atributos y el orden FIFO, pero no dice si una entrada `vencido`/`convertido` conserva
  las columnas `oferta_*`. El change adopta el invariante más estricto (solo `ofrecido`
  retiene; las demás las anulan) para que «retención» y «estado» no puedan divergir.
  No contradice la KB y queda registrado en `design.md` D2/D7.
- **TTL global vs por consultorio**: la KB no exige granularidad; el change usa variable
  global con default 30 min y lo deja como pregunta abierta en `design.md` §Open
  Questions. Sin deriva.
- **Sin autogestión pública de la lista**: US-003 no la exige en v1; el change la deja
  fuera de alcance explícitamente. Sin deriva.

## Veredicto

**LISTO PARA APPLY** — las cinco deltas cubren esperado, error de negocio y borde por
requirement, con trazabilidad a RN-TU-05/RN-TU-01/RN-NO-02/RN-NO-03 y Flujo 5, y
`openspec validate c-10-lista-espera-automatica --strict` pasa sin errores.
