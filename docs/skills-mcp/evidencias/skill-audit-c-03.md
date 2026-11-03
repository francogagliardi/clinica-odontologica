# Auditoría de escenarios — `c-03-auth-jwt-rbac`

Fecha: 2026-11-02 · Change: `c-03-auth-jwt-rbac` · Governance: **CRÍTICO**

## Alcance y método

Se aplicó la skill propia del proyecto `spec-scenario-auditor`
(`.agents/skills/spec-scenario-auditor/SKILL.md`) sobre las tres delta specs de
`openspec/changes/c-03-auth-jwt-rbac/specs/`, contrastándolas con la knowledge
base y con la implementación real.

**Limitación declarada:** se intentó delegar la auditoría a un subagente
independiente, pero falló por límite de uso gratuito del proveedor. La auditoría
fue realizada por el mismo agente que implementó el change, en la misma sesión.
Eso reduce la independencia: el valor de esta evidencia está en la matriz de
trazabilidad y en la lista explícita de defectos corregidos, no en una supuesta
revisión ciega. Una segunda pasada humana sigue siendo recomendable antes de
aprobar el change.

## Matriz de trazabilidad

| Requirement | Regla KB | Esperado | Error de negocio | Borde | Veredicto |
|---|---|---|---|---|---|
| Autenticación de credenciales y emisión de access token | DD-07b (`09`, `08` §Flujo JWT), RN-SE-01 (`05`) | sí | sí | sí (email con mayúsculas/espacios) | OK |
| Auditoría de intentos de autenticación | RN-SE-02 (`05`), US-040 CA-2 (`06`) | sí | sí (fallo commiteado antes del 401) | sí (429 no audita) | OK |
| Protección contra fuerza bruta en inicio de sesión | `08` §Seguridad, `CHANGES.md` C-03 | sí | sí | sí (reset y expiración de ventana) | OK |
| Validación de token de sesión Bearer | DD-07b, RN-SE-01 | sí | sí | sí (ausente/Basic, `typ`, `alg=none`, baja con token vigente) | OK |
| Control de acceso estricto por roles (RBAC) | RN-SE-01, `03_actores_y_roles.md` | sí | sí | sí (multi-rol, rol revocado, claim `roles` inyectado) | OK |
| Generación y verificación de tokens opacos públicos | RN-NO-03 (`05`), `08` §Seguridad | sí | sí | sí (vencido, propósito distinto) | OK |
| Consumo atómico de un solo uso | RN-NO-03 | sí | sí | sí (concurrencia) | OK |
| Token almacenado solo como hash | RN-NO-03, R-08 | sí | sí | sí (digest único) | OK |

Total: **29 escenarios** (10 + 10 + 9).

## Huecos detectados en el borrador inicial (y cómo se cerraron)

La primera versión de la auditoría había dictaminado «sin huecos». Era
incorrecta. La revisión real encontró:

1. **El login no se auditaba.** RN-SE-02 y US-040 CA-2 exigen registro
   inmutable de usuario/IP/dispositivo. → Nuevo requirement «Auditoría de
   intentos de autenticación» con 3 escenarios; el fallo se commitea antes del
   401 porque el `UnitOfWork` hace rollback ante excepción.
2. **El token público se guardaba en claro.** Una filtración de base entregaba
   enlaces vivos. → Nuevo requirement «Token almacenado solo como hash» y
   persistencia de SHA-256.
3. **El 410 no era observable.** La spec prometía HTTP 410 pero C-03 no monta
   endpoints públicos: solo existía una excepción interna. → Los escenarios se
   reescribieron en el borde real del servicio (`TokenAlreadyUsedError`) y se
   declaró que el mapeo a HTTP 410 pertenece a C-07/C-09.
4. **Faltaba el escenario de enumeración por tiempo.** → Se agregó la
   comparación bcrypt ficticia y el escenario de cuerpo 401 idéntico.
5. **El email era case-sensitive.** → Escenario de email con mayúsculas y
   espacios + normalización en endpoint y en SQL.
6. **Faltaba el cambio de rol en caliente.** → Escenario de rol revocado con
   token vigente y de claim `roles` inyectado que no autoriza.
7. **Faltaba el propósito del token.** → `expected_tipo` obligatorio en
   verificación y consumo, con `TokenPurposeError`.
8. **Faltaba el borde del 429 no auditado.** → Escenario explícito y aserción
   de que la tabla append-only no crece con reintentos bloqueados.

## Defectos de implementación detectados y corregidos

| # | Defecto (borrador) | Corrección |
|---|---|---|
| 1 | Router `/test-rbac` montado sobre la app real desde el módulo de tests | Endpoints reales `GET /usuarios/me` y `GET /usuarios` (admin) |
| 2 | Throttling en estado global no inyectable | `get_login_limiter` como dependencia; limitador y reloj falsos por test |
| 3 | Email case-sensitive | `normalize_email` + `lower(email)` en la consulta |
| 4 | Sin comparación ficticia (enumeración por tiempo) | `verify_password_with_dummy` |
| 5 | Token público en claro | `token_hash` SHA-256; valor crudo devuelto una sola vez |
| 6 | Mensajes de error incluían el token crudo | Errores sin el valor recibido |
| 7 | Login fallido se perdía por el rollback del UoW | `uow.commit()` explícito antes del 401 |
| 8 | El JWT llevaba `roles` y `email` | Claims mínimos `sub`/`typ`/`iat`/`exp`; autorización desde la base |
| 9 | No se validaba `typ` ni se blindaba `alg=none` | `typ` obligatorio y lista explícita de algoritmos |
| 10 | 429 sin `Retry-After` | Header calculado por el limitador |
| 11 | `usado` y `usado_at` podían divergir | CHECK `(usado) = (usado_at IS NOT NULL)` |
| 12 | Sin prueba de hash en reposo ni de propósito | Tests de digest, ausencia de valor crudo y `TokenPurposeError` |

## Riesgos residuales (fuera de C-03)

- Throttling en memoria = un solo proceso; al escalar debe migrar a Redis.
- Sin refresh token (DD-07b): sesión corta y re-login.
- El 429 no se audita: trade-off para no permitir crecimiento ilimitado de una
  tabla append-only.
- El mapeo HTTP de los errores de token (404/410) se implementa en C-07/C-09.
