# Reglas de Negocio

Cada regla tiene código único `RN-{DOMINIO}-{NN}`. Fuente primaria: informe-discovery §7 + checklist `reglas_de_negocio` del estado Discovery; justificación de mercado en §C del informe.

## Dominio: Turnos y agenda (RN-TU)

- **RN-TU-01**: Prohibido el solapamiento de turnos por profesional y por sillón — todo alta/reprogramación valida disponibilidad transaccionalmente antes de confirmar.
- **RN-TU-02**: La duración del turno deriva de la prestación (duraciones variables); el alta sin prestación usa la duración base del profesional.
- **RN-TU-03**: Plazo de cancelación configurable por consultorio (p. ej. 24 h); dentro del plazo la cancelación es libre, fuera de plazo puede perder la seña (RN-TU-04).
- **RN-TU-04**: La cancelación tardía o el ausentismo pueden implicar pérdida de la seña; la regla por prestación (`requiere_seña`) debe ser visible al reservar.
- **RN-TU-05**: Todo hueco liberado por cancelación se ofrece automáticamente a la lista de espera por orden FIFO (filtrando por prestación/profesional compatible).
- **RN-TU-06**: Sobreturnos permitidos solo con marca explícita y color diferenciado; nunca como solapamiento silencioso.
- **RN-TU-07**: Bloqueos (licencias, feriados, administrativos) impiden reservas en el rango afectado.
- **RN-TU-08**: La seña es opcional por prestación (DD-10): solo exigible si `requiere_seña=true` en la prestación; el flujo de reserva la solicita únicamente en ese caso y la política de pérdida (RN-TU-04) se muestra antes de confirmar.

## Dominio: Clínica (RN-CL)

- **RN-CL-01**: El odontograma usa notación FDI (piezas 11–48 permanentes, 51–85 temporarias) con registro por cara.
- **RN-CL-02**: El presupuesto/plan de tratamiento se genera en la misma consulta y calcula cobertura y copago de la obra social antes de confirmarse.
- **RN-CL-03**: Consentimiento informado con firma requerido para prácticas invasivas; versionado del texto.
- **RN-CL-04**: Evoluciones firmadas inmutables: solo se corrigen con nueva evolución rectificatoria (trazabilidad RN-SE-02).

## Dominio: Administración y cobros (RN-AD)

- **RN-AD-01**: Todo cobro (incluida seña) emite comprobante; factura electrónica ARCA B/C con CAE y QR cuando el comprobante es fiscal.
- **RN-AD-02**: La seña vinculada a la reserva se concilia con el turno; su pérdida sigue RN-TU-04.
- **RN-AD-03**: Caja diaria con arqueo: ingresos, gastos y deudas del día deben cerrar antes del cierre.
- **RN-AD-04**: Precios en ARS; si se exhibe otra moneda, la cotización de referencia es visible (práctica honesta tipo caja bimoneda).

## Dominio: Obras sociales (RN-OS)

- **RN-OS-01**: Validación preventiva de cobertura (afiliado, nomenclador vigente, topes/frecuencias) antes de registrar la práctica, para evitar débitos.
- **RN-OS-02**: Cobertura/copago calculados por ítem del presupuesto antes de la aceptación del paciente.
- **RN-OS-03**: Liquidación de obras sociales por período con trazabilidad de prácticas incluidas.

## Dominio: Comunicaciones (RN-NO)

- **RN-NO-01**: Recordatorios automáticos 48 h y 24 h antes del turno por WhatsApp oficial, con enlace de confirmación/cancelación/reprogramación.
- **RN-NO-02**: La respuesta del paciente (confirma/cancela/reprograma) actualiza la agenda sin intervención manual; la cancelación dispara RN-TU-05.
- **RN-NO-03**: Los enlaces públicos usan token de un solo uso con vencimiento y respetan el plazo de cancelación (RN-TU-03).

## Dominio: Excepciones globales

- **RN-SE-01**: Roles y permisos estrictos según matriz de `03_actores_y_roles.md`; el paciente solo opera sus propios turnos/datos.
- **RN-SE-02**: Trazabilidad total: quién registró/qué/cuándo (usuario, IP, dispositivo) en registro inmutable.
- **RN-SE-03**: Exportación total de datos del paciente/consultorio disponible en todo momento (PDF + formato estructurado); sin ventanas de retención punitivas ni cargos de salida.
- **RN-SE-04**: Datos de salud: sin cumplimiento normativo demostrable por ningún competidor (verificación F1–F7), el sistema publica su política de privacidad y valida el alcance legal con asesoramiento, no con el informe.
