# ENTREGA — TPI Metodología I

## Integrantes

| Integrante | Participación |
|---|---|
| Franco Nicolás Gagliardi | Fundación, los 17 changes del roadmap, skill propia, integración del MCP, pruebas, sistema de diseño y documentación |

Equipo individual (la consigna admite hasta tres integrantes). Materia: Metodología I.

## Video

👉 Ver video explicativo y demostración: `https://...` (se publica junto con la entrega).

## Repositorio

https://github.com/francogagliardi/clinica-odontologica

- Roadmap completo: `C-01` a `C-17`, archivados en `openspec/changes/archive/`.
- Artefactos SDD de cada change: `proposal.md`, `design.md`, specs con escenarios y `tasks.md` con su verificación.
- Skill propia: `.agents/skills/spec-scenario-auditor/SKILL.md`, registrada en `.atl/skill-registry.md`.
- Guía reproducible del MCP: `docs/skills-mcp/mcp.md`.
- Documentación del sistema de diseño: `docs/design-system.md`.
- Runbook de demo local: `docs/demo.md`.

## Alcance presentado

- **17 changes completos, probados y archivados**, muy por encima del mínimo de dos por integrante.
- **1341 tests de backend y 199 de frontend** en verde, más typecheck y build.
- Sistema levantado con Docker Compose: API, frontend, PostgreSQL, Redis y cuatro workers.
- Datos ficticios e integraciones en modo de prueba: WhatsApp en capa de prueba, Mercado Pago en sandbox y ARCA en homologación.
- Fuera del alcance del TPI: épica 6 (US-050–US-059), posterior al MVP.

## Commit de entrega

El último commit de `main` incluye este documento y el estado final del repositorio. El historial completo del proceso está en `git log`.

## Documentos de la entrega

- Ficha de investigación de skill y MCP: [`docs/skills-mcp/investigacion.md`](docs/skills-mcp/investigacion.md)
- Informe de aplicación: [`docs/skills-mcp/aplicacion.md`](docs/skills-mcp/aplicacion.md)
- Evidencias: [`docs/skills-mcp/evidencias/`](docs/skills-mcp/evidencias/)
- Guía del MCP: [`docs/skills-mcp/mcp.md`](docs/skills-mcp/mcp.md)
- Sistema de diseño: [`docs/design-system.md`](docs/design-system.md)

## Datos y credenciales

Todas las evidencias usan la base demo del Compose con datos ficticios. El repositorio no contiene contraseñas, tokens ni datos de pacientes: en la documentación y la configuración de ejemplo la credencial aparece como `CAMBIAR_PASSWORD`.
