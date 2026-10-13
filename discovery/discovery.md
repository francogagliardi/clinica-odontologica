# Discovery — Sistema de gestión odontológica con turnos y agenda (mercado argentino)

**Fecha de elaboración**: 2026-10-13
**Fuentes investigadas**: 18 sistemas (11 de origen argentino, 5 regionales con presencia en Argentina, 2 internacionales de referencia). Todas las fuentes se consultaron el 2026-10-13 salvo indicación contraria. Lista completa de URLs y fechas en el anexo "Fuentes consultadas".
**Método**: investigación web verificable (sitios oficiales, páginas de precios, centros de ayuda, comparativas de terceros y marketplaces de reseñas). No se inventó ninguna funcionalidad: lo no demostrado públicamente se consigna como "No evidenciado". Se distingue entre funcionalidad comprobada y afirmación comercial del proveedor.
**Nota de gobernanza**: la skill `discovery-research` prevé una Q&A interactiva y un gate de confirmación antes de escribir. En esta corrida el brief del usuario (fase Discovery despachada por el orquestador) constituye el contenido de la fase en sí: los 11 puntos del checklist se derivan del brief y de la evidencia relevada, y se documenta aquí directamente por instrucción explícita del orquestador.

## 1. Problema que resuelve

Los consultorios y clínicas odontológicas de Argentina gestionan turnos y agenda con WhatsApp manual, papel o planillas, lo que genera dobles reservas, ausentismo sin recupero, tiempo administrativo perdido en confirmaciones y facturación a obras sociales con débitos evitables. El producto a desarrollar debe centralizar agenda, historia clínica odontológica y administración adaptada a la realidad argentina (obras sociales, ARCA, Mercado Pago, WhatsApp como canal dominante).

## 2. Usuarios / roles

- **Odontólogo independiente**: agenda propia, historia clínica, presupuestos y cobro directo.
- **Recepcionista / administrativo**: carga y confirma turnos, gestiona caja, señas y facturación.
- **Administrador de clínica**: múltiples profesionales, sillones/boxes, sucursales, liquidaciones, reportes y roles.
- **Paciente**: reserva online 24/7, confirma/cancela/reprograma, recibe recordatorios, paga señas, accede a presupuestos y documentos.
- **Roles secundarios**: asistente, laboratorio (órdenes de trabajo), auditor/obra social (trazabilidad).

## 3. Casos de uso

1. Como paciente, quiero reservar un turno online 24/7 (web, enlace, redes, WhatsApp) para no depender del horario de recepción.
2. Como recepcionista, quiero ver la agenda diaria/semanal por profesional y sillón, con bloqueos y sobreturnos, para evitar solapamientos.
3. Como paciente, quiero confirmar, cancelar o reprogramar mi turno desde el recordatorio para liberar el horario a tiempo.
4. Como odontólogo, quiero registrar la atención en ficha clínica con odontograma y generar el presupuesto/plan de tratamiento en la misma consulta.
5. Como administrador, quiero cobrar (caja, Mercado Pago, seña), facturar (ARCA/obras sociales) y liquidar profesionales sin doble carga.
6. Como administrador, quiero recuperar pacientes ausentes e inactivos con recordatorios y campañas automáticas.

## 4. Competidores / soluciones existentes

Informe completo de mercado, secciones A–D.

### A. Tabla comparativa (ordenada por relevancia para Argentina)

| # | Producto (empresa, país) | Segmento | Modalidad | Precio publicado (moneda, fecha consulta) |
|---|---|---|---|---|
| 1 | DentalCore (Argentina) — dentalcore.app | Independiente, consultorio, clínica | SaaS nube | USD 50/mes (2 usuarios incl.; +USD 10/usuario). Pago en ARS vía Mercado Pago |
| 2 | Reservo (Chile, página AR) — reservo.cl/homepage/ar/dental | Independiente, clínica | SaaS nube | No publica en sitio oficial; tercero (reservo.cl/blog, 2026-07-12) indica desde $30.000 ARS/mes |
| 3 | Benty (Argentina) — benty.com.ar | Independiente, clínica | SaaS nube | No publica; 1 mes bonificado |
| 4 | OdontoClinIA / ClinIA (Argentina) — clinia.com.ar/odontologia | Consultorio, clínica PyME, hospital público, cadena | SaaS web | Cotización por institución; costo por usuario declarado $0 |
| 5 | DentalTec (Argentina) — web.dentaltec.com.ar | Independiente, círculos/federaciones, instituciones | SaaS 100% web | No publica plan base; packs WhatsApp desde USD 9/50 mensajes |
| 6 | Dentalist (Argentina) — dentalist.com.ar | Independiente, consultorio, clínica | SaaS navegador | USD 35/mes (200 pacientes, 1 profesional); 60 días de prueba |
| 7 | FLAP (Argentina) — flap.com.ar/odontologos | Independiente, clínica | SaaS nube | No publica (capacitación inicial sin cargo) |
| 8 | DentalCor (Argentina, Córdoba) — dentalcorsoftware.com.ar | Consultorio, clínica | SaaS nube | No publica; afirma +500 clínicas |
| 9 | Denteo (Argentina) — denteo.com.ar | Consultorio, clínica, laboratorio | SaaS nube + app Android | No publica |
| 10 | Odontias (Argentina) — odontias.com.ar | Independiente, clínica | SaaS nube + PWA | $19.000 / $29.000 / $45.000 ARS/mes; cobro vía Mercado Pago |
| 11 | DenPro (Argentina) — denpro.ar | Independiente, clínica | SaaS nube | $19.900 (Basic) / $29.900 (Team) ARS/mes; prueba 30 días |
| 12 | Odontoly (Argentina) — odontoly.com | Independiente, consultorio | Híbrida (local-first + remoto) | USD 149,9 (alcance exacto ambiguo en sitio); activación acompañada |
| 13 | AgendaPro (Chile, opera AR) — agendapro.com/ar | Multirrubro (incluye dental) | SaaS nube | $13.900 (1 prof.) a $314.900 ARS/mes IVA incl.; WhatsApp desde +$7.900/mes |
| 14 | Dentalink (Chile) — softwaredentalink.com | Consultorio, clínica, cadena | SaaS nube | Cotización (LatAm); referencia Capterra USD 29/mes |
| 15 | Dentidesk (Chile) — dentidesk.com | Clínica pequeña y grande | SaaS nube (+ local declarado) | Cotización; referencia Capterra USD 50; trial 15 días |
| 16 | Doctoralia PRO (España/Grupo Docplanner, opera AR) — pro.doctoralia.com/ar | Independiente, centro médico | SaaS + directorio | $25.000 / $35.000 / $55.000 ARS/mes facturado anualmente |
| 17 | tab32 (EE. UU., referencia) — tab32.com | Consultorio, grupos/DSO | SaaS nube | USD 125/mes año 1 (hasta 3 prestadores), USD 225 desde año 2 |
| 18 | Open Dental (EE. UU., referencia) — opendental.com | Cualquier tamaño | Servidor local autohospedado | USD 199/mes (12 meses) luego USD 149; hasta 3 prestadores |

#### Fichas por sistema (todo lo no demostrado: "No evidenciado")

**1. DentalCore (Argentina, dentalcore.app).** Segmento: independiente a clínica. SaaS. Agenda visual con drag & drop, sala de espera, confirmación por WhatsApp con enlace (el paciente confirma/cancela y la agenda se actualiza sola), recordatorios 48/24 h con plazo de cancelación configurable. Turnos digitales: reserva con QR/link de Mercado Pago; videoconsultas. Automatización: mensajes automáticos (confirmaciones, recordatorios, post-operatorios, controles, cumpleaños) vía ventana oficial de Meta; asistente de voz para mover turnos y dictar evolución. Clínica: historia clínica, odontograma y periodontograma, módulos por especialidad, recetas, consentimientos, derivaciones, órdenes de laboratorio, inventario por lote; diferencial comprobado: 17 motores de reglas de apoyo a la decisión clínica (CDSS) con fuente citada. Administración: caja diaria con arqueo, deudores, Mercado Pago con conciliación automática, factura electrónica ARCA (B/C con CAE y QR enviada por WhatsApp/email), cobertura y copago en el plan, liquidación de obras sociales por período. Integraciones: WhatsApp Business (API oficial Meta), Mercado Pago, ARCA; Google Calendar/API pública/AFIP-firma digital: No evidenciado. Operación: multiusuario pago por persona; sucursales/auditoría/exportación: No evidenciado. Seguridad: control de acceso por usuario; política de privacidad/respaldo/trazabilidad y adecuación a Ley 25.326/26.529: No evidenciado. Comercial: un solo plan USD 50/mes, pago en pesos en AR. Fortalezas: único con CDSS + ARCA + Mercado Pago + WhatsApp oficial integrados. Limitación: sin precio por agenda/sucursal publicado ni evidencia de adopción masiva. Adopción: opera en 8 países LatAm (afirmación comercial, sin cifra de clientes publicada).

**2. Reservo (Chile, con página y operación argentina, reservo.cl/homepage/ar/dental).** Segmento: independientes y centros. SaaS. Agenda online 24/7 multi-dispositivo, reserva web y Facebook, confirmación y recordatorio por correo y WhatsApp; odontograma digital y fichas clínicas y faciales; presupuestos; telemedicina; cobros online con seña al reservar; facturación con integración ARCA (página AR) y comprobantes de pago; cálculo de comisiones; control de sesiones; CRM, giftcards, estadísticas, registro financiero. Cobro por sillón simultáneo (no por profesional). Integraciones: Mercado Pago y ARCA (página AR); certificada Fonasa/CENS en Chile; Google Calendar/API: No evidenciado. Operación: +15 países LatAm, +12 años (afirmación comercial). Seguridad/adecuación normativa argentina: No evidenciado. Comercial: sin precio en sitio oficial ("conocé sin costo"); tercero verificable indica desde $30.000 ARS/mes. Fortaleza: la regional con mejor adaptación AR comprobada (ARCA + Mercado Pago + odontograma + telemedicina). Limitación: precios no publicados; profundidad clínica (periodontograma, imágenes) No evidenciada.

**3. Benty (Argentina, benty.com.ar).** Segmento: independiente a clínica. SaaS online. Agenda por profesionales, espacios y disponibilidad; reserva online con actualización de datos por el paciente; recordatorios/confirmación por WhatsApp; historia clínica con evoluciones, odontograma visual por pieza, planes de tratamiento con presupuestos y seguimiento, órdenes de laboratorio (envío-recepción-pago), recetas digitales y electrónicas, facturación electrónica integrada, liquidaciones del staff por actividad, roles y permisos, licencias del personal. Administración de obras sociales y stock: afirmado por tercero (reservo.cl/blog), No evidenciado en sitio oficial. Integraciones: WhatsApp; ARCA: afirmado por tercero, detalle No evidenciado; Mercado Pago/API/Google Calendar: No evidenciado. Seguridad: trazabilidad declarada como intención de diseño; adecuación legal: el sitio aclara que el alcance legal depende de cada organización (honestidad destacable, no cumplimiento demostrado). Comercial: precio a cotizar según profesionales; 1 mes bonificado. Fortaleza: cobertura funcional integral AR con laboratorio y liquidaciones. Limitación: sin precios ni evidencia de adopción publicados.

**4. OdontoClinIA / ClinIA (Argentina, clinia.com.ar/odontologia).** Segmento: consultorio, clínica PyME, hospitales/centros municipales, cadenas. Web SaaS. Agenda por profesional/especialidad/sillón; asistente de IA por WhatsApp que reserva contra agenda real, recuerda, cancela, reprograma y deriva a humano; turnero web y app de pacientes. Clínica: odontograma FDI 52 piezas por cara con dentición según edad, diagnósticos CIE-10, prácticas de nomenclador con estados, plan con importe estimado, periodontograma: No evidenciado; historia clínica con IA de resumen; adjuntos. Recetario electrónico inscripto ReNaPDiS N.º 248 (verificable en listado oficial; alcance limitado al recetario), recetas HL7 FHIR. Administración: facturación electrónica ARCA, verificación de cobertura vía API PUCO, integración RENAPER declarada; Mercado Pago/obras sociales-liquidación detalle: No evidenciado. Integraciones: WhatsApp IA, PUCO, RENAPER, ARCA. Operación: multisucursal con dashboard único; roles: No evidenciado en detalle. Seguridad: sin política publicada; adecuación normativa general: No evidenciada (solo recetario registrado). Comercial: cotización por institución. Fortaleza: única con IA conversacional de turnos + PUCO + ReNaPDiS verificable. Limitación: sin precios; foco institucional, posible exceso para independientes.

**5. DentalTec (Argentina, web.dentaltec.com.ar).** Segmento: odontólogos e instituciones (CORA, círculos de San Juan, Mendoza, Entre Ríos, Santiago del Estero — afirmación comercial con nombres concretos). Web SaaS. Agenda con recordatorios WhatsApp (40% menos ausentismo, 98% entrega — cifras del proveedor, sin auditoría independiente). Diferencial comprobado en su FAQ: validación preventiva de prácticas en tiempo real contra 15+ obras sociales vía web services (64% menos débitos — cifra del proveedor); gestión jerárquica círculos/federaciones/CORA; facturación con integración ARCA y planillas automáticas. Odontograma digital: afirmado. Soporte 24/7: afirmado. Integraciones: obras sociales, ARCA, WhatsApp (packs desde USD 9/50 mensajes). Reserva online 24/7/lista de espera/periodontograma/Mercado Pago/API: No evidenciado. Seguridad normativa: No evidenciada. Comercial: costo por odontólogo no publicado. Fortaleza: el único con validación de obras sociales en tiempo real y tracción institucional verificable por nombres. Limitación: sin precios; sin evidencia de reserva online ni half clínico profundo.

**6. Dentalist (Argentina, dentalist.com.ar).** Segmento: independiente a clínica. SaaS en navegador (sin instalación). Agenda inteligente con horarios propios, Google Calendar (sincronización declarada), calendarios por sede, pantalla de llamado para sala de espera; turnos online desde landing propia con dominio propio y SEO; recordatorios automáticos por email (WhatsApp: No evidenciado). Portal del paciente (turnos, recetas, presupuestos, documentos); recetas con firma digital; presupuestos y cobros por secciones con saldo; finanzas y cobranzas; campañas e insights con IA y Meta Ads (afirmación comercial). Diferencial: Studio 3D en navegador y cefalometría con IA (CBCT local, sin subida a nube). Administración: reportes financieros; Mercado Pago/ARCA/obras sociales: No evidenciado. Seguridad: No evidenciada. Comercial: USD 35/mes (hasta 200 pacientes, 1 profesional + 2 asistentes), 60 días de prueba sin tarjeta; Studio 3D +USD 99/mes. Fortaleza: mejor experiencia de paciente y marketing + 3D; trial generoso. Limitación: sin WhatsApp ni facturación argentina evidenciados; precios en USD.

**7. FLAP (Argentina, flap.com.ar/odontologos).** Segmento: independiente a clínica. SaaS. Agenda multi-profesional con especialidades, box, duración y disponibilidad propias; bloqueos, estados de turno/seña/cobro; autoasignación por carga diaria/semanal (diferencial comprobado); reserva 24/7 desde página web; avisos por email incluidos y WhatsApp en paquetes adicionales; señas y cobros con Mercado Pago vinculados a la reserva; historia clínica con evoluciones, odontograma digital FDI con superficies y eventos; prestaciones con tiempos/precios/especialidades; analíticas de agenda; equipo y permisos; sucursales según configuración. Facturación ARCA/obras sociales/API/Google Calendar: No evidenciado. Seguridad: No evidenciada. Comercial: sin precios; configuración y capacitación inicial sin cargo; demo con datos ficticios. Fortaleza: agenda multi-recurso más sofisticada (autoasignación) + señas MP. Limitación: WhatsApp como costo extra; sin facturación argentina evidenciada.

**8. DentalCor (Argentina, Córdoba, dentalcorsoftware.com.ar).** Segmento: consultorio/clínica. Nube. Agenda multi-profesional con vistas día/semana/mes, código de color por doctor, notificaciones al agendar/cancelar; recordatorios WhatsApp y email; historia clínica con archivos, odontograma, presupuestos en PDF; finanzas en tiempo real (ingresos, gastos, deudas, reportes). +500 clínicas (afirmación comercial sin fuente). Facturación ARCA/obras sociales/Mercado Pago/API/roles: No evidenciado. Seguridad: SSL declarado; adecuación normativa: No evidenciada. Comercial: sin precios; soporte 24/7 declarado. Fortaleza: propuesta integral simple con tracción declarada local. Limitación: casi sin detalle técnico verificable; sin precios.

**9. Denteo (Argentina, denteo.com.ar).** Segmento: consultorio, clínica, laboratorio dental. Nube + app nativa Android (iOS pendiente). Agenda visual con estados; historia clínica con odontograma; presupuestos; facturación electrónica ARCA; WhatsApp con plantillas aprobadas y recordatorios; turnos: reserva online No evidenciada en detalle. Administración: facturación ARCA, caja: detalle No evidenciado; Mercado Pago/obras sociales: No evidenciado. Seguridad: disponibilidad objetivo 99,9% (ver estado — enlace declarado); normativa: No evidenciada. Comercial: sin precios. Fortaleza: ARCA + WhatsApp + app Android + módulo laboratorio (poco común). Limitación: sin precios ni detalle de agenda/turnos digitales.

**10. Odontias (Argentina, odontias.com.ar).** Segmento: independiente a clínica. Nube + PWA con biometría. Agenda con intervalos 15–60 min, detección de solapamientos, sobreturnos paralelos con color, asignación de sillones/consultorios; confirmación/cancelación automática con asistente IA por WhatsApp 24/7 (WAHA + n8n declarados); recordatorios por email; odontograma anatómico FDI; galería clínica/radiografías HD; historial y evoluciones; caja diaria ARS con balances en PDF y flujo 6 meses; facturación por profesional; precios en pesos con débito Mercado Pago. Reserva online 24/7/lista de espera/obras sociales/ARCA/API: No evidenciado. Seguridad: No evidenciada. Comercial: $19.000/$29.000/$45.000 ARS/mes, 1–3 profesionales, 150–600 pacientes. Fortaleza: precios ARS publicados más accesibles + IA WhatsApp con stack declarado + PWA biométrica. Limitación: sin facturación electrónica ni integraciones locales evidenciadas.

**11. DenPro (Argentina, denpro.ar).** Segmento: independiente/clínica. Nube. Turnos, historias clínicas, notas de tratamiento, odontograma y facturación (declarados); +50 consultorios (afirmación comercial). Detalle de agenda/recordatorios/WhatsApp/Mercado Pago/ARCA/obras sociales/API/seguridad: No evidenciado (sitio escueto; menciona compatibilidad GDPR, no normativa argentina). Comercial: $19.900/$29.900 ARS/mes, anual −15%, trial 30 días. Fortaleza: precio ARS claro y bajo. Limitación: el sitio demuestra pocas funcionalidades; todo lo específico es No evidenciado.

**12. Odontoly (Argentina, odontoly.com).** Segmento: consultorio independiente. Híbrida local-first (la base vive en la PC principal; remoto vía navegador con PC encendida; sin app móvil nativa). Agenda con turnos/tareas/solicitudes de reserva online vía enlace (con confirmación del equipo, sin bot); historia clínica, evoluciones, odontograma, archivos/fotos/RX, presupuestos con impresión; caja ARS/USD con cotización manual, gastos, deudas, resumen del día; 2 usuarios con permisos, 4 dispositivos; funciona con cortes (sesión vigente). WhatsApp/Mercado Pago/ARCA/obras sociales/API: No evidenciado (IA y web completa declarados como futuros, honestamente). Seguridad: datos locales (menor exposición, mayor riesgo de pérdida sin respaldo declarado). Comercial: USD 149,9 (el sitio no aclara si es mensual/único — ambiguo), sin permanencia ni cobro automático. Fortaleza: modelo local-first con caja bimoneda, honesto sobre su roadmap. Limitación: sin nube real ni automatizaciones; precio ambiguo.

**13. AgendaPro (Chile, fuerte operación AR, agendapro.com/ar).** Multirrubro con vertical dental/salud. SaaS. Agenda online 24/7 configurable, marketplace, recordatorios WhatsApp/SMS/email (WhatsApp extra desde $7.900/mes, 50 mensajes), cobro de señas con Mercado Pago (comisión 2%, 1% en Pro, +IVA), comisiones por dentista, inventario, fichas clínicas personalizables (Premium/Pro, sin odontograma — comparativa ArgenSalud 2026-04-24), asistente "Charly" extra, API y analytics (Pro). +20.000 negocios / +135.000 profesionales (afirmaciones comerciales). Facturación ARCA/obras sociales/odontograma: No evidenciado (explícitamente ausente según tercero). Seguridad normativa salud: No evidenciada. Comercial: $13.900–$314.900 ARS/mes IVA incluido + extras; prueba gratis (duración no especificada). Fortaleza: escala regional, marketplace, caja/inventario. Limitación: generalista sin odontograma ni facturación argentina; WhatsApp y bot con costo aparte.

**14. Dentalink (Chile, LatAm + España, softwaredentalink.com).** Consultorio a cadena. Nube (Chrome recomendado). Agenda con agendamiento online 24/7, confirmaciones/recordatorios WhatsApp y email, Contact Center con IA 24/7 (adicional), tareas automáticas de citas/recaptura/morosidad (Titanium); historia clínica, odontograma y periodontograma, ortodoncia, estética facial, telemedicina (adicional), imágenes, videos 3D, consentimientos, firma (adicional), notas/resumen clínico con IA, análisis RX y simulador de sonrisa; caja, pagos online y en cuotas, convenios, gastos, inventario, laboratorio, liquidaciones, +50 reportes Excel; multisucursal, usuarios/roles ilimitados, chat interno. Facturación electrónica: solo VeriFactu España evidenciada; ARCA/Mercado Pago/PUCO/obras sociales argentinas: No evidenciado. Seguridad: "altos estándares" (genérico); normativa argentina: No evidenciada. Comercial: cotización por tamaño; referencia Capterra USD 29/mes; sin contratos mínimos. Fortaleza: suite clínica + IA más madura de LatAm, multicentro real. Limitación: sin localización argentina evidenciada ni precios públicos.

**15. Dentidesk (Chile, LatAm, dentidesk.com).** Clínicas. Nube. Agenda personalizable con agendamiento online embebible, confirmación/anulación por correo (WhatsApp automático: declarado como "próximo", no disponible); historiales, fichas por especialidad (ortodoncia, endodoncia, periodoncia, cirugía ortognática, disfunción), odontograma con nomenclatura chilena/internacional/universal, presupuestos por pieza, convenios con descuentos, recetas/interconsultas/derivaciones, laboratorio, radiología, insumos/stock, +20 reportes, multisucursal, API de horarios, roles con restricción a asistentes. Facturación integrada al SII chileno y Alegra/DGII; ARCA/Mercado Pago: No evidenciado. Términos: trial 15 días, precios por país en web (no verificados para AR), recargo 30% por reactivación tras inactividad (cláusula contractual pública). Seguridad normativa argentina: No evidenciada. Comercial: cotización; referencia USD 50. Fortaleza: profundidad de fichas por especialidad + integraciones fiscales chilenas. Limitación: sin WhatsApp automático, sin localización AR, sin precios públicos.

**16. Doctoralia PRO (Grupo Docplanner, opera AR, pro.doctoralia.com/ar).** Independiente/centro. SaaS + directorio (+110.000 profesionales verificados en app AR). Reserva online multicanal 24/7 (perfil, web, Google, redes), sincronización Google/Outlook, recordatorios email/push (Starter) y SMS (Plus), lista de espera y operaciones masivas (VIP), videoconsulta (Plus), HCE con episodios clínicos (Plus/VIP, sin odontograma evidenciado), chat seguro, informes, campañas SMS. Cobro al reservar/Mercado Pago/ARCA/obras sociales/API: No evidenciado en AR. Seguridad normativa argentina: No evidenciada. Comercial: $25.000/$35.000/$55.000 ARS/mes con pago anual por adelantado (≈$300.000/año el Starter); perfil gratuito solo visibilidad. Fortaleza: captación de pacientes nuevos (directorio) + lista de espera. Limitación: HCE recién en Plus, sin odontograma, pago anual anticipado, sin facturación argentina.

**17. tab32 (EE. UU., referencia internacional, tab32.com).** Consultorio a DSO. Nube (Google Cloud). Agenda con reserva online, lista ASAP/espera, drag & drop; odontograma y periodontograma, imágenes/RX, dictado por voz con IA, verificación de seguros en tiempo real, claims ($0,20) y adjuntos ($0,50), formularios digitales, SMS bidireccional,Arrange/recalls, analítica, multisede centralizada, API y data warehouse. HIPAA + SOC 2 (declarado en sitio). Localización argentina (ARCA/MP/obras sociales/WhatsApp/español): No evidenciada; opera solo en EE. UU. Comercial: USD 125/mes año 1, USD 225 desde año 2, trial 14 días. Valor como referencia: UX moderna, precios publicados, IA de voz, open data. No apto directo para AR sin localización total.

**18. Open Dental (EE. UU., referencia internacional, opendental.com).** Cualquier tamaño. Servidor local autohospedado (no es nube; el hosting/IT lo pone la clínica). Agenda, odontograma, imágenes, eServices pagos (recordatorios, reserva online, formularios), código abierto, +50 reportes. Precio publicado: USD 199/mes (12 meses) luego USD 149 + módulos (texting, eClipboard). HIPAA declarado. Localización argentina: No evidenciada. Valor como referencia: costo piso del mercado, código abierto (auditable, exportable), comunidad grande. No apto directo: requiere servidor, inglés, sin ARCA/MP/WhatsApp.

### B. Matriz de puntuación ponderada (0–5 por criterio)

Pesos: Turnos y automatización 25% · Clínica odontológica 20% · Integraciones locales y WhatsApp 15% · Administración/cobros/facturación 15% · Experiencia del paciente 10% · Seguridad/exportación/trazabilidad 10% · Precio y adopción 5%.

| # | Sistema | Tur/Aut 25% | Clínica 20% | Integ 15% | Admin 15% | ExpPx 10% | Seg 10% | Precio 5% | **Total** |
|---|---|---|---|---|---|---|---|---|---|
| 1 | DentalCore | 4,5 | 5,0 | 5,0 | 5,0 | 4,0 | 3,5 | 4,0 | **4,58** |
| 2 | Reservo | 4,5 | 4,0 | 4,5 | 3,5 | 4,0 | 3,0 | 4,0 | **4,03** |
| 3 | Benty | 4,0 | 4,0 | 4,0 | 4,0 | 4,0 | 3,0 | 3,0 | **3,85** |
| 4 | Dentalink | 4,5 | 4,5 | 2,0 | 4,0 | 4,0 | 3,5 | 2,0 | **3,78** |
| 5 | Dentalist | 4,0 | 4,5 | 2,5 | 3,5 | 4,5 | 3,0 | 4,0 | **3,75** |
| 6 | ClinIA | 4,0 | 4,0 | 4,0 | 3,5 | 3,0 | 3,5 | 2,5 | **3,70** |
| 7 | DentalTec | 3,5 | 3,5 | 4,5 | 4,5 | 3,0 | 3,0 | 3,0 | **3,68** |
| 8 | FLAP | 4,5 | 3,5 | 3,5 | 3,5 | 4,0 | 2,5 | 2,5 | **3,65** |
| 9 | tab32 (ref) | 4,0 | 4,5 | 1,0 | 4,0 | 4,0 | 4,0 | 2,0 | **3,55** |
| 10 | DentalCor | 4,0 | 3,5 | 3,5 | 3,5 | 3,5 | 2,5 | 2,5 | **3,48** |
| 11 | Denteo | 3,5 | 3,5 | 4,0 | 3,5 | 3,0 | 2,5 | 2,5 | **3,38** |
| 12 | Odontias | 3,5 | 3,5 | 3,0 | 3,5 | 3,0 | 2,5 | 4,5 | **3,33** |
| 13 | Dentidesk | 3,5 | 4,5 | 1,5 | 4,0 | 3,0 | 3,0 | 2,0 | **3,30** |
| 14 | AgendaPro | 4,5 | 1,5 | 2,5 | 3,5 | 4,0 | 2,5 | 3,5 | **3,15** |
| 15 | DenPro | 3,5 | 3,0 | 2,0 | 3,0 | 3,0 | 2,5 | 4,5 | **3,00** |
| 16 | Open Dental (ref) | 3,0 | 4,0 | 1,0 | 3,5 | 2,5 | 3,5 | 3,5 | **3,00** |
| 17 | Doctoralia | 4,0 | 2,0 | 2,0 | 2,0 | 5,0 | 3,0 | 3,0 | **2,95** |
| 18 | Odontoly | 3,0 | 3,5 | 1,5 | 3,5 | 3,0 | 2,5 | 3,0 | **2,90** |

Criterio aplicado: 5 = evidenciado y superior; 4 = evidenciado y sólido; 3 = parcial o afirmado sin detalle; 2 = débil/ausente; 1 = no apto para Argentina. Los puntajes de integraciones/seguridad castigan sistemáticamente lo "No evidenciado".

### C. Análisis competitivo

**Funcionalidades estándar de mercado** (las tiene casi todos; no diferenciarse aquí es quedar fuera): agenda visual diaria/semanal multi-profesional; reserva online 24/7 con enlace; recordatorios y confirmación (email como mínimo); historia clínica digital con adjuntos; odontograma con notación FDI; presupuestos/planes de tratamiento; caja y control de pagos; reportes básicos; roles y permisos; prueba gratuita o demo.

**Diferenciadores reales** (pocos los tienen, y están evidenciados): apoyo a la decisión clínica con reglas citadas (solo DentalCore); validación de obras sociales en tiempo real + gestión jerárquica de círculos (solo DentalTec); verificación de cobertura PUCO + recetario ReNaPDiS registrado (solo ClinIA); facturación ARCA integrada (DentalCore, Benty, Denteo, Reservo-AR); cobro con Mercado Pago vinculado a la reserva (FLAP, DentalCore, Reservo-AR, Odontias para el abono); asistente de IA por WhatsApp que opera la agenda (ClinIA, Odontias, Dentalink-Contact Center); autoasignación de turnos por carga (FLAP); planificación 3D/cefalometría con IA (Dentalist); cobro por sillón en lugar de por profesional (Reservo); modelo local-first con caja bimoneda ARS/USD (Odontoly); open data/API real (tab32).

**Vacíos frecuentes del mercado argentino**: (a) precios no publicados — 9 de los 12 sistemas argentinos/regionales exigen cotización, lo que frena la adopción por independientes; (b) WhatsApp como costo extra o ausente, pese a ser el canal dominante; (c) facturación ARCA y Mercado Pago ausentes en la mitad de los locales; (d) gestión de obras sociales/prepagas con nomencladores y liquidación por convenio, casi inexistente fuera de DentalTec/DentalCore; (e) lista de espera y recuperación de ausentes/inactivos, poco evidenciados; (f) cumplimiento normativo demostrable (Ley 25.326 de datos personales, Ley 26.529 de HCE, consentimiento informado con firma): ningún proveedor publica política verificable; (g) exportación de datos y salida sin cautividad: nadie la documenta (Dentidesk incluso penaliza la reactivación); (h) periodontograma, imágenes/RX y laboratorio, cobertura desigual; (i) offline ante cortes de internet: solo Odontoly lo contempla.

**Oportunidades de innovación para un producto nuevo**: precio ARS publicado y transparente con prueba gratuita; WhatsApp nativo incluido (no como extra) con confirmación/cancelación/reprogramación y lista de espera automática; ARCA + Mercado Pago + obras sociales con validación preventiva en un mismo flujo; trazabilidad y consentimiento con firma desde el día uno con política de privacidad publicada; exportación total de datos y ausencia de penalizaciones (antídoto contra la cautividad); agenda multi-sillón con prevención de solapamientos y sobreturnos; portal del paciente simple; analítica de ausentismo y recupero; modo degradado ante cortes.

### D. Recomendación final

**Cinco competidores prioritarios para analizar mediante demo**: 1) DentalCore — el rival funcional más completo (CDSS + ARCA + MP + WhatsApp oficial); 2) Reservo (versión AR) — la regional mejor localizada (sillón, ARCA, MP); 3) Benty — integral argentino con laboratorio y liquidaciones; 4) ClinIA — referencia en IA conversacional, PUCO y compliance de recetario; 5) DentalTec — referencia en obras sociales y tracción institucional (CORA/círculos). Suplente: Dentalink (benchmark regional de suite + IA, sin localización AR).

**Tres productos de referencia para experiencia de usuario**: 1) tab32 — agenda, dictado por voz y reserva online modernas con precios transparentes (referencia de UX, no de localización); 2) Dentalist — portal del paciente, landing con dominio propio y reserva sobre disponibilidad real; 3) FLAP — agenda multi-profesional con estados de turno/seña/cobro visibles y autoasignación.

**MVP sugerido**:
- *Imprescindibles*: agenda diaria/semanal multi-profesional y multi-sillón con duraciones variables, bloqueos, sobreturnos y prevención de solapamientos; reserva online 24/7 con enlace; confirmación/cancelación/reprogramación por WhatsApp con recordatorios automáticos; ficha clínica + odontograma FDI + presupuestos/planes; caja, cobros, señas con Mercado Pago y facturación ARCA; roles y permisos; reportes básicos.
- *Diferenciadores del MVP*: precio ARS publicado + prueba gratuita; WhatsApp incluido (no extra) con lista de espera automática; validación preventiva de obras sociales; consentimiento informado con firma y trazabilidad; exportación total de datos.
- *Para etapas posteriores*: periodontograma e imágenes/RX; IA conversacional y dictado clínico; portal del paciente y app móvil; campañas y recupero de inactivos; multisucursal; laboratorio e inventario; API pública e integraciones (Google Calendar, radiología, marketing); modo offline.

## 5. Funcionalidades necesarias

Reserva online 24/7; agenda multi-profesional/multi-sillón con bloqueos, sobreturnos y anti-solapamiento; confirmación/cancelación/reprogramación y recordatorios por WhatsApp; lista de espera; ficha clínica con odontograma FDI y presupuestos; caja/Mercado Pago/señas; facturación ARCA; obras sociales básicas; roles y permisos; reportes.

## 6. Funcionalidades opcionales

Periodontograma e imágenes; IA (agente de turnos, dictado, resumen clínico); portal/app del paciente; campañas y recupero; multisucursal; laboratorio/inventario; API e integraciones; telemedicina/videoconsulta; modo offline; planificación 3D.

## 7. Reglas de negocio

No a dos turnos superpuestos por profesional/sillón; duraciones variables por prestación; plazo de cancelación configurable con liberación automática del horario; la cancelación tardía puede perder la seña; lista de espera que ofrece el hueco liberado por orden; cobertura/copago de obra social calculado antes de confirmar el plan; todo cobro emite comprobante; trazabilidad de quién registró/qué/cuándo.

## 8. Integraciones

Obligatorias v1: WhatsApp Business API oficial, Mercado Pago, facturación ARCA. Deseables: PUCO/verificación de cobertura, Google Calendar, sitio web propio. Futuras: API pública, AFIP/ARCA ampliado, radiología/imágenes, firma digital avanzada, herramientas de marketing/Meta Ads.

## 9. Restricciones

Proyecto universitario (Metodología I): alcance acotado, sin presupuesto para licencias pagas de terceros en v1; mercado objetivo Argentina (precios ARS, normativa local); priorizar integraciones con capa gratuita o sandbox (WhatsApp prueba, Mercado Pago sandbox); el MVP debe ser demostrable con datos ficticios.

## 10. Riesgos

- Supuesto sin probar: que los odontólogos independientes paguen por software cuando WhatsApp + papel "les alcanza" — validar con usuarios reales.
- La mitad de la evidencia proviene de afirmaciones comerciales sin auditoría (cifras de adopción, % de reducción de ausentismo/débitos).
- 9 de 12 proveedores regionales no publican precios: el benchmark de pricing es incompleto y volátil (puede cambiar sin aviso).
- Integraciones críticas (WhatsApp Business API, ARCA, Mercado Pago) dependen de aprobaciones y costos de terceros fuera de control del proyecto.
- Cumplimiento normativo (datos de salud, HCE): ningún competidor lo demuestra; el riesgo legal debe validarse con asesoramiento, no con este informe.
- Origen de Dentiqa y detalle de DentalTec/Benty no verificados en fuente oficial: marked como evidencia parcial.

## 11. Preguntas abiertas

- ¿Alcance v1: solo odontólogo independiente o también clínica multi-profesional desde el día uno?
- ¿Reserva con seña obligatoria u opcional por prestación?
- ¿Facturación ARCA real en v1 o comprobante interno con ARCA en etapa posterior?
- ¿Qué obra social/nomenclador se usa para el caso de prueba del MVP?
- ¿Hospedaje en la nube con costo o demo local para la entrega universitaria?
- Verificar con demo los 5 competidores priorizados y confirmar precios/condiciones vigentes antes de fijar el pricing del producto.

## Fuentes consultadas (URL + fecha)

- https://dentalcore.app/ — 2026-10-13
- https://www.dentalist.com.ar/ — 2026-10-13
- https://dentalcorsoftware.com.ar/ — 2026-10-13
- https://flap.com.ar/odontologos — 2026-10-13
- https://odontoly.com/ — 2026-10-13
- https://odontias.com.ar/ — 2026-10-13
- https://www.denteo.com.ar/ — 2026-10-13
- https://www.clinia.com.ar/odontologia — 2026-10-13
- https://web.dentaltec.com.ar/software-odontologos-argentina y /preguntas-frecuentes — 2026-10-13
- https://www.denpro.ar/ — 2026-10-13
- https://benty.com.ar/ (+ /funcionalidades/odontograma, /historia-clinica, /facturas-electronicas) — 2026-10-13
- https://agendapro.com/ar/planes y /ar/dental/software-odontologico — 2026-10-13
- https://www.softwaredentalink.com/es/planes y /funcionalidades — 2026-10-13
- https://www.dentidesk.com/ (+ /dentidesk/feature) y https://app.dentidesk.com/terminos.php — 2026-10-13
- https://pro.doctoralia.com/ar/precio y /ar/agenda-doctoralia-para-especialistas — 2026-10-13
- https://reservo.cl/homepage/ar/dental/ y https://reservo.cl/homepage/cl/dental/ — 2026-10-13
- https://reservo.cl/blog/profesionales/dental/guia-para-elegir-el-mejor-software-dental-en-argentina/ — 2026-10-13 (tercero: precios y funcionalidades Benty/Dentiqa/Reservo/MednIA/CalDoc)
- https://tab32.com/pricing/ — 2026-10-13
- https://operatory.app/best-cloud-based-dental-practice-management-software-2026/ — 2026-10-13 (tercero: precios Open Dental/CareStack/Curve/Dentrix)
- https://turnoapp.com.ar/blog/alternativa-a-agendapro — 2026-10-13 (tercero: precios AgendaPro AR verificados 2026-09-19)
- https://www.medicai.com.ar/blog/cuanto-cuesta-software-medico-argentina — 2026-10-13 (tercero: precios Doctoralia/Kandu/Doclify)
- https://www.argensalud.com/blog/comparativa-argensalud-y-agendapro/ — 2026-10-13 (tercero: AgendaPro sin odontograma/ARCA)
- https://www.capterra.co.cr/software/196361/dentalink y https://www.capterra.cl/software/184029/dentidesk — 2026-10-13 (referencias de precio base y reseñas)
