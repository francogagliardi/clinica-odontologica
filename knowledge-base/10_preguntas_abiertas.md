# Preguntas Abiertas

> Incluye las 6 preguntas del Discovery + incertidumbres de inferencia Mode A (regla low-confidence del state-contract: lo no inferible con confianza se marca y se sigue, sin bloquear).

## Inconsistencias detectadas

### IN-01 — Cifras comerciales sin auditoría en el benchmark
**Documento A dice**: el informe usa cifras de proveedores (64 % menos débitos, 40 % ausentismo, +500 clínicas, +2.000 profesionales) como evidencia comparativa.
**La verificación dice** (`verificacion-fuentes.md`): son declaraciones publicadas correctamente atribuidas, no hechos auditados; 8 afirmaciones NO RESPALDADAS + 4 PARCIALES (P1–P12).
**Impacto**: el roadmap no debe dimensionar beneficios (p. ej. "reduce ausentismo 40 %") como garantizados.
**Resolución propuesta**: mantener las cifras solo como referencia atribuida; medir con datos propios.

### IN-02 — Precios ARS volátiles y benchmark incompleto
**Informe dice**: 9 de 12 regionales sin precios; tabla con valores a fecha 2026-10-13.
**Verificación dice**: AgendaPro declara +30.000 negocios (no +20.000); comisiones/señas MP no halladas en /ar/planes; Dentidesk Capterra sin reseñas (solo precio).
**Impacto**: el pricing propio no puede fijarse solo con este benchmark.
**Resolución propuesta**: verificar con demo los 5 priorizados (DentalCore, Reservo AR, Benty, ClinIA, DentalTec) antes de fijar precio.

## Respuestas del usuario (2026-10-13, cierra fase kb-creator)

| ID | Respuesta | Estado |
|---|---|---|
| P-01 | (b) independiente + clínica multi-profesional desde el día uno | ✅ Respondida — SU-02 pasa a confirmada |
| P-02 | (a) seña opcional por prestación | ✅ Respondida — ver RN-TU-08 |
| P-03 | (a) factura ARCA real en homologación en v1 | ✅ Respondida — ver DD-09 |
| P-04 | (c) convenio ficticio propio para la demo, 1 real como segunda iteración | ✅ Respondida — ver seed en `04_modelo_de_datos.md` |
| P-05 | (a)/(b) ambas aceptables; default demo local, decisión final pendiente de constraints de entrega | 🟡 Parcialmente abierta |
| P-06 | (a) FastAPI + SPA + PostgreSQL, refinada 2026-10-13 a stack exacto (DD-07a–DD-07e) | ✅ Respondida — ver DD-07 |
| P-07 | Confirmada por implicación (stack web elegido ⇒ `web_app`) | ✅ Cerrada |
| P-08 | Confirmada por P-01(b) (`public_multi_user`; multi-tenant posterior) | ✅ Cerrada |

## Preguntas abiertas (priorizadas)

| Prioridad | Pregunta | Bloquea | Decisor |
|---|---|---|---|
| Alta | P-01 ✅ Respondida (b: independiente + multi-profesional — DD-08) | Diseño de agenda/RBAC | Equipo |
| Alta | P-02 ✅ Respondida (a: opcional por prestación — RN-TU-08) | RN-TU-04, US-030 | Equipo |
| Alta | P-03 ✅ Respondida (a: ARCA homologación en v1 — DD-09) | US-031, arquitectura fiscal | Equipo |
| Alta | P-04 ✅ Respondida (c: convenio ficticio "OS Demo" — DD-11) | Seed data, RN-OS-01 | Equipo |
| Alta | P-05 ¿Hospedaje en nube con costo o demo local para la entrega? | Despliegue, env vars | Cátedra / equipo |
| Alta | P-06 ✅ Respondida ((a) FastAPI + SPA + PostgreSQL, refinada a stack exacto DD-07a–DD-07e) | Todo el roadmap técnico | Equipo |
| Media | P-07 **[DISCOVERY]** `system_type` asumido `web_app` SaaS: ¿se confirma frente a app móvil nativa o desktop? Recomendación: sí, web_app (16/18 competidores). | 02, 08 | Equipo |
| Media | P-08 **[DISCOVERY]** `scale` asumido `public_multi_user` (equipo clínico + reserva pública; multi-tenant posterior): ¿se confirma? | 03, 04 | Equipo |
| Media | P-09 Verificar con demo los 5 competidores priorizados y confirmar precios/condiciones vigentes | Pricing (DD-06) | Equipo |
| Baja | P-10 ¿Portal del paciente con cuentas o solo enlaces tokenizados en v1? | US-052 vs RN-NO-03 | Equipo |
| Baja | P-11 Alcance legal (Ley 25.326 / 26.529) con asesoramiento: ¿qué exige la cátedra demostrar? | RN-SE-04 | Cátedra |
