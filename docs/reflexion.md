# Reflexión — Metodología I
**Tecnicatura Universitaria en Programación**
**Integrante:** Franco Nicolás Gagliardi
**Fecha:** 13/10/2026

## 1. Qué del Discovery estaba mal o sin respaldo y cómo lo detectamos

En el Discovery investigué 18 sistemas para consultorios odontológicos y armé el informe que está en `docs/discovery/informe-discovery.md`. Después hice una auditoría de fuentes que quedó en `docs/discovery/verificacion-fuentes.md`.

Lo que hice fue simple: abrí 7 páginas reales (sitios oficiales, páginas de precios, centros de ayuda, marketplace y reseñas verificadas) y comparé una por una las 52 afirmaciones del informe contra lo que cada página mostraba. Si no estaba, lo marqué como "No evidenciado". El resultado fue 40 confirmadas, 4 parciales y 8 sin respaldo.

Ahí aparecieron los errores. Con DentalCore el informe decía "No evidenciado" en tres cosas que su propia página sí muestra: que maneja varias sucursales, que guarda auditoría sin cambios y que exporta en PDF y HL7. Con AgendaPro los números estaban viejos: el informe citaba más de 20.000 cuando la página actual dice más de 30.000, el dato de 135.000 profesionales no apareció por ningún lado, y la comisión de Mercado Pago no estaba en la dirección citada. También el informe decía que nadie documentaba la exportación de datos, pero los términos de Dentidesk sí lo hacen (Excel, 30 días). Y la página de Dentidesk en Capterra tiene 0 reseñas, así que solo sirve como referencia de precio. Dos páginas me bloquearon la lectura directa (Capterra devolvía error 403) y las resolví con búsqueda marcada como alternativa.

## 2. Dónde usamos Ajustar, qué estaba mal y qué pasaba si seguíamos de largo

Usé "Ajustar" tres veces. La primera fue sobre el informe: apliqué 12 correcciones (P1 a P12) antes de generar el PDF final, y con eso el puntaje de DentalCore pasó de 4,58 a 4,63. La segunda fue en la base de conocimiento: al principio decía algo genérico como "FastAPI + SPA + PostgreSQL", y lo reemplacé por mi decisión exacta de stack (JWT, SQLAlchemy, Redis solo para colas, Docker, React con TypeScript y Vite). La tercera fue durante el C-01: al probar todo junto con Docker apareció un error real, las migraciones se rompían porque el código de arranque usaba una dirección de base de datos distinta a la que necesitaba, y lo arreglé antes de cerrar.

Si en esos momentos hubiera apretado "Continuar" sin revisar, entregaba un PDF con datos falsos, construía el código sobre un stack vago, y llegaba a la demo con las migraciones rotas.

## 3. Diferencia entre implementar con especificación aprobada vs pedir código suelto

El C-01 lo propuse primero: escribí la propuesta, el diseño, 4 mini-especificaciones y 10 tareas, las revisé y las aprobé yo, y recién después se implementó con pruebas (17 de backend y 7 de frontend, todas en verde).

Si en cambio hubiera pedido "haceme la base" sin nada previo, me habría llegado un código sin ancla, sin pruebas y hasta con secretos escritos a mano en el código. Con la especificación aprobada yo sabía qué se iba a hacer antes de hacerlo, y después pude comprobar que andaba.

## 4. Qué parte de la fundación aportó más y cuál menos al ciclo OPSX

Para mí lo que más valor aportó fue la base de conocimiento con las decisiones (DD) y las reglas de negocio (RN), junto con las 13 reglas duras (R-01 a R-13). Las cumplí en cada paso: no subí secretos, usé Redis solo para colas y no permití turnos superpuestos.

Lo que menos se notó en el día a día fue la instalación del registro de skills: era necesaria para que todo funcione, pero no se ve. El roadmap también me sirvió como mapa, pero al final es solo un índice.

## 5. Reparto del trabajo

Este es un proyecto individual. Yo, Franco Nicolás Gagliardi, hice todas las etapas: el resumen de investigación, la verificación de fuentes, las decisiones de stack y reglas, la revisión de los documentos, el Docker Desktop, las pruebas y las subidas.
