# Verificación de fuentes — Informe Discovery (auditoría, sin correcciones al informe)

**Fecha de verificación**: 2026-10-13 (en vivo, misma fecha de consulta declarada en el informe).
**Informe auditado**: `docs/discovery/informe-discovery.md` (secciones A–D, 18 sistemas, tabla comparativa, matriz ponderada).
**Alcance**: auditoría exclusivamente — no se modificó el informe, el `.docx` ni el archivo de estado. Las correcciones propuestas quedan listadas para una futura corrida "Ajustar".
**Método**: obtención en vivo de cada URL elegida mediante WebFetch el 2026-10-13. Cuando la obtención directa fue bloqueada o vacía, se usó respaldo por búsqueda web, marcado explícitamente como *respaldo (fallback)*.
**Convención de veredictos**: CONFIRMADO (la afirmación está en la URL, con cita); PARCIAL (coincidencia incompleta o matizada); NO RESPALDADO (afirmación no hallada en la URL, o rótulo "No evidenciado" del informe refutado por evidencia existente en la URL).

## Fuentes verificadas (7 URL, 5 tipos exigidos + 2 de refuerzo)

| # | URL | Tipo | Estado de obtención |
|---|---|------|---------------------|
| F1 | https://dentalcore.app/ | (a) sitio oficial del proveedor | OK directo |
| F2 | https://agendapro.com/ar/planes | (b) página de precios/planes | OK directo |
| F3a | https://web.dentaltec.com.ar/software-odontologos-argentina | (a/c) sitio oficial + guía pública | OK directo |
| F3b | https://web.dentaltec.com.ar/preguntas-frecuentes | (c) centro de ayuda / documentación pública | OK directo |
| F4 | https://app.dentidesk.com/terminos.php | (c) documentación pública contractual | OK directo |
| F5 | https://www.capterra.co.cr/software/196361/dentalink | (d) marketplace confiable | Bloqueado (403) → respaldo por búsqueda |
| F6 | https://www.capterra.cl/software/184029/dentidesk | (e) reseñas verificadas | Bloqueado (403) → respaldo por búsqueda |
| F7 | https://reservo.cl/homepage/ar/dental/ | (a) sitio oficial, refuerzo de alta ponderación | Vacío en obtención → respaldo por búsqueda |

Nota: F2 se complementó con https://pro.doctoralia.com/ar/precio (tipo b, OK directo) como segundo punto de control de precios. F3a/F3b pertenecen al mismo proveedor y cuentan como una fuente de tipo (c).

---

## F1. DentalCore — sitio oficial (OK directo, 16 afirmaciones controladas)

Afirmaciones de precio y pago:
- C1. "Un solo plan USD 50/mes (2 usuarios incl.; +USD 10/usuario)" — **CONFIRMADO**. Cita: "USD 50 por mes con 2 usuarios incluidos, y USD 10 por cada persona que sumes".
- C2. "Pago en ARS vía Mercado Pago" — **CONFIRMADO**. Cita: "En Argentina los ves y los pagás en pesos, con Mercado Pago o transferencia".
- C11. "Reserva con QR/link de Mercado Pago" — **CONFIRMADO**. Cita: "El paciente paga con QR o link de Mercado Pago (Argentina, México, Chile, Colombia, Perú y Uruguay)".

Afirmaciones funcionales:
- C3. "Confirmación por WhatsApp con enlace; recordatorios 48/24 h con plazo configurable" — **CONFIRMADO**. Cita: "48 h y 24 h antes del turno, con un link para confirmar o cancelar con un toque, dentro del plazo de cancelación que fijás vos. Si cancela, el horario se libera en la agenda".
- C4. "Factura electrónica ARCA (B/C con CAE y QR enviada por WhatsApp/email)" — **CONFIRMADO**. Cita: "Cada cobro emite su Factura C o B con tu CUIT, CAE y QR, y le llega al paciente por WhatsApp o email".
- C5. "17 motores de reglas (CDSS) con fuente citada" — **CONFIRMADO**. Cita: "17 motores clínicos que cruzan los datos del paciente con reglas basadas en literatura" (Bagán, Neville, IADT, EFP, NICE NG12 citadas en página).
- C6. "Opera en 8 países LatAm (afirmación comercial, sin cifra de clientes)" — **CONFIRMADO**, y el informe lo califica correctamente como afirmación. Cita: listado Argentina, México, Chile, Colombia, Perú, Ecuador, Uruguay y Paraguay.
- C7. "Asistente de voz para mover turnos y dictar evolución" — **CONFIRMADO** (sección "Decile Sani y soltá el mouse").
- C8. "Videoconsultas" — **CONFIRMADO** ("La videoconsulta es un turno más de tu agenda"; USD 0,50 por videoconsulta, dato no recogido en el informe pero sin contradicción).
- C9. "Sala de espera" — **CONFIRMADO** ("Agenda multi-doctor", "Sala de espera").
- C10. "Inventario por lote" — **CONFIRMADO** ("Stock por lote").

Rótulos "No evidenciado" del informe refutados o matizados por el sitio en vivo:
- C12. "Sucursales: No evidenciado" — **NO RESPALDADO** (el rótulo es falso). El sitio declara "Varias clínicas, una cuenta".
- C13. "Auditoría: No evidenciado" — **NO RESPALDADO**. El sitio declara "Historia clínica con auditoría de accesos… registro que no se puede editar ni borrar" (usuario, IP, dispositivo).
- C14. "Exportación: No evidenciado" — **NO RESPALDADO**. El sitio declara "Exportás la clínica entera —cada historia en PDF y en HL7 FHIR, con sus imágenes— aunque la cuenta esté suspendida… 90 días para bajarla".
- C15. "Política de privacidad/respaldo/trazabilidad y adecuación a Ley 25.326/26.529: No evidenciado" — **PARCIAL** (el rótulo es excesivo). Evidencia existente: página /privacy enlazada; "copias cifradas (AES-256-GCM)… últimos 8… prueba mensual de restauración"; "pensada para ayudarte a cumplir la ley de datos personales (Ley 25.326)"; mención de Ley 26.529 en evoluciones. No se revisó el texto íntegro de la política.
- C16. "API pública: No evidenciado" — **PARCIAL**. Existe "acceso externo con llave de solo lectura… en HL7 FHIR" revocable; no equivale a API pública documentada, pero merece mención.

Balance F1: 11 CONFIRMADO · 2 PARCIAL · 3 NO RESPALDADO.

## F2. AgendaPro — página de precios AR (OK directo, 10 afirmaciones; apoyo en Doctoralia precios OK directo)

- C1. "Rango $13.900 (1 prof.) a $314.900 ARS/mes IVA incl." — **CONFIRMADO**. Cita: plan Individual "$13.900 ARS/mes (IVA incluido)"; plan Pro "$314.900 ARS/mes (IVA incluido)".
- C2. "WhatsApp desde +$7.900/mes (50 mensajes)" — **CONFIRMADO**. Cita: "Desde $ 7.900 / mes ARS IVA incluido — 50 mensajes mensuales".
- C3. "Asistente 'Charly' extra" — **CONFIRMADO**. Cita: "Charly… Desde $31.900 / mes ARS IVA incluido".
- C4. "Facturación ARCA: No evidenciada (explícitamente ausente)" — **CONFIRMADO** (el rótulo es correcto). Cita: "Facturación electrónica — Próximamente".
- C5. "Fichas clínicas personalizables (Premium/Pro)" — **CONFIRMADO** (tabla comparativa de planes).
- C6. "Sin odontograma (según tercero ArgenSalud 2026-04-24)" — **PARCIAL**. La página de planes no menciona odontograma (silencio compatible), sin verificación independiente en esta auditoría.
- C7. "+20.000 negocios / +135.000 profesionales (afirmaciones comerciales)" — **NO RESPALDADO** en esta URL. La página en vivo declara "+30.000 negocios en Latinoamérica"; la cifra de profesionales no aparece. Requiere corrección de cifras.
- C8. "Comisión Mercado Pago 2 % (1 % en Pro, +IVA)" — **NO RESPALDADO** en esta URL (no figura en la página de planes; requiere otra fuente o rótulo).
- C9. "Cobro de señas con Mercado Pago" — **NO RESPALDADO** en esta URL (no figura; requiere otra fuente o rótulo).
- C10. "Prueba gratis (duración no especificada)" — **CONFIRMADO** (botones "Prueba Gratis" sin duración declarada).

Control cruzado tipo (b): Doctoralia PRO (OK directo) — "Starter $25.000 / Plus $35.000 / VIP $55.000 ARS/mes facturado anualmente; HCE recién en Plus/VIP; lista de espera solo VIP; sin odontograma ni ARCA/MP visibles" — **CONFIRMADO** en todos sus puntos; refuerza la ficha 16 del informe.

Balance F2: 6 CONFIRMADO · 1 PARCIAL · 3 NO RESPALDADO.

## F3. DentalTec — guía + FAQ públicas (OK directo, 10 afirmaciones)

- C1. "Validación preventiva en tiempo real contra 15+ obras sociales" — **CONFIRMADO**. Cita FAQ: "verifica automáticamente… estado del afiliado, nomenclador vigente, topes y frecuencias… antes de que la práctica se registre".
- C2. "64 % menos débitos (cifra del proveedor)" — **CONFIRMADO**, con atribución correcta en el informe. Cita: "reducción del 64 % en débitos, medida en producción real".
- C3. "40 % menos ausentismo, 98 % entrega (WhatsApp)" — **CONFIRMADO**. Cita: "40 % de reducción en ausentismo y 98 % de tasa de entrega".
- C4. "Facturación con integración ARCA" — **CONFIRMADO**. Cita: "Se integra directamente con ARCA (ex AFIP)".
- C5. "Packs WhatsApp desde USD 9/50 mensajes" — **CONFIRMADO**. Cita: "packs de mensajería arrancan desde USD $9 por 50 mensajes".
- C6. "Tracción institucional: CORA, San Juan, Mendoza, Entre Ríos, Santiago del Estero" — **CONFIRMADO** (nombres idénticos en guía y FAQ).
- C7. "Soporte 24/7 (afirmado)" — **CONFIRMADO**. Cita: "soporte técnico real 24/7".
- C8. "+2.000 profesionales, 5/5 (30 reseñas)" — **CONFIRMADO** como afirmación del proveedor, correctamente atribuida en el informe.
- C9. "Costo por odontólogo no publicado" — **CONFIRMADO** (el FAQ habla de costo "que se justifica" sin cifra base).
- C10. "Odontograma digital (afirmado)" — **CONFIRMADO**. Cita: "odontograma digital… integrado con la historia clínica… CIE-10".

Balance F3: 10 CONFIRMADO · 0 PARCIAL · 0 NO RESPALDADO. Es la ficha con respaldo más sólido.

## F4. Dentidesk — términos contractuales públicos (OK directo, 6 afirmaciones)

- C1. "Trial 15 días" — **CONFIRMADO**. Cita cl. 2.2: "versión gratuita por 15 días".
- C2. "Recargo 30 % por reactivación tras inactividad" — **CONFIRMADO**. Cita cl. 9.4.
- C3. "WhatsApp automático 'próximo', no disponible; acceso actual manual" — **CONFIRMADO**. Cita cl. 4.8: "mensajes predefinidos requieren intervención manual del operador"; el blog oficial (2026-08-13) declara "WhatsApp automático… próximas alternativas".
- C4. Brecha (g) del informe: "exportación… nadie la documenta" — **NO RESPALDADO** (el rótulo es falso para Dentidesk). Citas: cl. 2.8/7.5–7.6 (exportación Excel, ventana de 30 días post-término, posible cargo administrativo).
- C5. "Seguridad normativa argentina: No evidenciada" — **CONFIRMADO** (los términos invocan exclusivamente leyes chilenas 19.628/20.584/21.719).
- C6. "Facturación SII chileno; ARCA/Mercado Pago: No evidenciado" — **CONFIRMADO** (sitio oficial: integración SII; sin mención ARCA/MP).

Balance F4: 5 CONFIRMADO · 0 PARCIAL · 1 NO RESPALDADO.

## F5. Dentalink en Capterra — marketplace (respaldo por búsqueda; directo 403, 3 afirmaciones)

- C1. "Referencia Capterra USD 29/mes" — **CONFIRMADO** (respaldo). Cita indexada: "Starting Price US$29.00" (hasta "Per User / month" según edición regional).
- C2. "Sin contratos mínimos" — **CONFIRMADO** (respaldo, página oficial de planes): "Sin contratos o plazos mínimos de uso".
- C3. "Confirmaciones/recordatorios WhatsApp; Contact Center IA adicional" — **PARCIAL**. La oferta actual del proveedor lo declara, pero una reseña Capterra verificada (2022) pedía recordatorios WhatsApp automáticos entonces ausentes ("Me gustaría que existiera… por whatsapp… de forma automática"). Requiere matiz temporal y verificación con demo.

Balance F5: 2 CONFIRMADO · 1 PARCIAL · 0 NO RESPALDADO.

## F6. Dentidesk en Capterra — reseñas (respaldo por búsqueda; directo 403, 2 afirmaciones)

- C1. "Referencia Capterra USD 50" — **CONFIRMADO** (respaldo). Cita indexada: "Precio inicial US$ 50,00".
- C2. Citada como fuente "de precio base y reseñas" — **NO RESPALDADO** en cuanto a reseñas: la ficha indexada indica "Basado en 0 opiniones". Debe citarse solo como referencia de precio.

Balance F6: 1 CONFIRMADO · 0 PARCIAL · 1 NO RESPALDADO.

## F7. Reservo AR — sitio oficial (respaldo por búsqueda; obtención directa vacía, 5 afirmaciones + 1 pendiente)

- C1. "Facturación con integración ARCA (página AR)" — **CONFIRMADO** (respaldo). Cita indexada: "facturar con la integración ARCA"; centro de ayuda y blog ARCA dedicados.
- C2. "Mercado Pago" — **CONFIRMADO** (respaldo). Cita: "Recibí pagos online con Mercado Pago"; tutorial oficial de integración MP-AR.
- C3. "Odontograma digital y fichas" — **CONFIRMADO** (respaldo). Cita: "odontograma claro, ordenado y fácil de actualizar".
- C4. "+15 países / +12 años (afirmación comercial)" — **CONFIRMADO** como afirmación correctamente atribuida (respaldo).
- C5. "Desde $30.000 ARS/mes (tercero reservo.cl/blog, 2026-07-12)" — **CONFIRMADO** en atribución y cifra (respaldo): tabla comparativa del blog indica "$30.000 ARS/mes" para Reservo.
- Pendiente (sin veredicto, fuera de evidencia reunida): "cobro por sillón" y "certificación Fonasa/CENS en Chile" no aparecieron en los fragmentos de respaldo; no se refutan, quedan para verificación con demo.

Balance F7: 5 CONFIRMADO · 0 PARCIAL · 0 NO RESPALDADO (+1 pendiente).

---

## Tabla consolidada de hallazgos

| # | Fuente | Afirmación del informe | Veredicto | Evidencia / cita o "no hallado" |
|---|---|---|---|---|
| H1 | DentalCore (F1) | Sucursales: "No evidenciado" | NO RESPALDADO | Refutado: "Varias clínicas, una cuenta" (dentalcore.app, en vivo) |
| H2 | DentalCore (F1) | Auditoría: "No evidenciado" | NO RESPALDADO | Refutado: "auditoría de accesos… no se puede editar ni borrar" (IP, dispositivo) |
| H3 | DentalCore (F1) | Exportación: "No evidenciado" | NO RESPALDADO | Refutado: "Exportás la clínica entera —PDF y HL7 FHIR… 90 días" |
| H4 | DentalCore (F1) | Privacidad/respaldo/Ley 25.326: "No evidenciado" | PARCIAL | Existe: /privacy, backups AES-256 ×8 con prueba mensual, mención Ley 25.326; política íntegra no revisada |
| H5 | DentalCore (F1) | API pública: "No evidenciado" | PARCIAL | Existe llave solo-lectura HL7 FHIR revocable; no es API pública documentada |
| H6 | AgendaPro (F2) | +20.000 negocios / +135.000 profesionales | NO RESPALDADO | Página en vivo: "+30.000 negocios"; 135.000 no hallado en la URL |
| H7 | AgendaPro (F2) | Comisión MP 2 % (1 % Pro +IVA) | NO RESPALDADO | No hallado en /ar/planes; requiere otra fuente o rótulo |
| H8 | AgendaPro (F2) | Señas con Mercado Pago | NO RESPALDADO | No hallado en /ar/planes; requiere otra fuente o rótulo |
| H9 | Dentidesk (F4) | Brecha (g): "nadie documenta exportación" | NO RESPALDADO | Refutado: términos cl. 2.8/7.5–7.6 (Excel, 30 días, posible cargo) |
| H10 | Dentidesk (F6) | Capterra como fuente "de precio y reseñas" | NO RESPALDADO | "Basado en 0 opiniones"; vale solo como referencia de precio USD 50 |
| H11 | Dentalink (F5) | WhatsApp automático vigente | PARCIAL | Reseña 2022 pedía WhatsApp automático; oferta actual declara Contact Center IA — matiz temporal pendiente de demo |
| H12 | General | Riesgos: "Origen de Dentiqa…" + "marked" | Observación | Dentiqa solo aparece en tabla de tercero; corregir redacción ("marcado") y alcance |
| H13 | General | ClinIA: "costo por usuario $0" (tabla, fila 4) | Pendiente | Fuera de las 5 fuentes de esta auditoría; verificar en Ajustar |
| H14 | General | Reservo: sillón / Fonasa-CENS | Pendiente | Sin veredicto (fragmentos de respaldo insuficientes); verificar con demo |

Totales: 52 controles afirmación-evidencia → 40 CONFIRMADO · 4 PARCIAL · 8 NO RESPALDADO. Hallazgos que exigen corrección (H1–H12): 12. Pendientes de demo (H13–H14): 2.

## Propuesta de correcciones para la corrida "Ajustar" (afirmación exacta → corrección propuesta)

- P1. Ficha 1: "sucursales/auditoría/exportación: No evidenciado" → "Sucursales: evidenciado parcial ('Varias clínicas, una cuenta'); auditoría: evidenciada (registro inmutable con usuario, IP y dispositivo); exportación: evidenciada (PDF + HL7 FHIR, ventana de 90 días post-baja)".
- P2. Ficha 1: "política de privacidad/respaldo/trazabilidad y adecuación a Ley 25.326/26.529: No evidenciado" → "Respaldo (AES-256, 8 copias, prueba mensual), trazabilidad (auditoría de accesos) y mención orientativa a Ley 25.326 evidenciados en sitio/FAQ; política de privacidad publicada (contenido íntegro no revisado); adecuación a Ley 26.529: No evidenciada".
- P3. Ficha 1: "Google Calendar/API pública/AFIP-firma digital: No evidenciado" → "Google Calendar: No evidenciado; API pública documentada: No evidenciada (existe llave de solo lectura HL7 FHIR revocable); firma digital AFIP: No evidenciada".
- P4. Ficha 13: "+20.000 negocios / +135.000 profesionales" → "+30.000 negocios (página de planes, 2026-10-13); 135.000 profesionales: No evidenciado en la URL citada (mantener solo si se aporta fuente)".
- P5. Ficha 13: "comisión 2 % (1 % en Pro, +IVA)" → "No evidenciado en /ar/planes (aportar URL o rotular 'No evidenciado')".
- P6. Ficha 13: "cobro de señas con Mercado Pago" → "No evidenciado en /ar/planes (aportar URL o rotular 'No evidenciado')".
- P7. Sección C, brecha (g): "nadie la documenta (Dentidesk incluso penaliza la reactivación)" → "Dentidesk documenta exportación (Excel, 30 días post-término, posible cargo administrativo) y penaliza la reactivación (+30 %); en el resto de los proveedores: No evidenciado".
- P8. Anexo de fuentes: "Capterra (referencias de precio base y reseñas)" → "Capterra: Dentalink USD 29/mes (2 reseñas verificadas, 2022); Dentidesk USD 50 (0 reseñas: solo referencia de precio)".
- P9. Ficha 14 (Dentalink): "confirmaciones/recordatorios WhatsApp… Contact Center con IA 24/7 (adicional)" → agregar "oferta vigente del proveedor; reseña Capterra 2022 señalaba ausencia de WhatsApp automático — confirmar alcance actual con demo".
- P10. Sección 10 (Riesgos): "Origen de Dentiqa y detalle de DentalTec/Benty no verificados en fuente oficial: marked como evidencia parcial" → "Dentiqa aparece solo vía comparativa de tercero (reservo.cl/blog); sus datos son evidencia de tercero, no oficial. DentalTec y Benty: verificados en sitio oficial salvo puntos marcados 'No evidenciado'".
- P11 (opcional, con demo): reconsiderar Seguridad 3,5 de DentalCore a la luz de la evidencia (backups, auditoría, 2FA para recetar, controles ISO 27001 declarados sin certificación) y verificar "costo por usuario $0" de ClinIA.
- P12 (higiene): tabla comparativa fila 12 "USD 149,9" → normalizar formato ("USD 149,90") manteniendo la nota de ambigüedad, correctamente marcada.

## Limitaciones de esta auditoría

- Tres URL no admitieron obtención directa (Reservo: página vacía; Capterra ×2: 403) y se resolvieron con respaldo de búsqueda, de menor fuerza probatoria.
- No se verificaron las 18 fichas en profundidad: el diseño fue 5 fuentes + barrido de tabla para huecos sin marcar.
- Los precios en ARS son volátiles; las cifras rigen a fecha de verificación.
- Las cifras de adopción y eficacia declaradas por proveedores (2.000+ profesionales, 64 %, 40 %, 98 %) se confirman como *declaraciones publicadas*, no como hechos auditados.

## Conclusión y recomendación

El informe sale bien parado en lo central: precios publicados, integraciones ARCA/Mercado Pago/WhatsApp y cláusulas contractuales verificadas coinciden con lo declarado, y el uso del rótulo "No evidenciado" es en general disciplinado. No obstante, existen 8 afirmaciones NO RESPALDADAS —incluido un bloque de tres rótulos "No evidenciado" refutados por el propio sitio de DentalCore— que impiden un aprobado limpio. **Acción recomendada: corrida "Ajustar" aplicando P1–P12**, tras la cual el informe quedará en condiciones de alimentar la reflexión del curso con trazabilidad completa.
