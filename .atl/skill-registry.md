# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Writing, reviewing, or refactoring React/Next.js code; React components, Next.js pages, data fetching, bundle optimization, performance improvements | vercel-react-best-practices | C:\Users\Franco Gagliardi\.agents\skills\vercel-react-best-practices\SKILL.md |
| BEFORE writing or changing anything in Postgres (tables, columns, schema, migrations, RLS, indexes, triggers, functions, cron/queues, pgvector, restores); diagnosing slow queries, high CPU, timeouts, EXPLAIN plans, connection exhaustion, locking, bloat, row-visibility leaks | supabase-postgres-best-practices | C:\Users\Franco Gagliardi\.agents\skills\supabase-postgres-best-practices\SKILL.md |
| Building features or fixing bugs test-first; "red-green-refactor"; integration tests | tdd | C:\Users\Franco Gagliardi\.agents\skills\tdd\SKILL.md |
| Implementing auth systems, securing APIs, OAuth2/social login, RBAC, session management, SSO/multi-tenancy, debugging auth issues | auth-implementation-patterns | C:\Users\Franco Gagliardi\.agents\skills\auth-implementation-patterns\SKILL.md |
| FastAPI/Python backend work: APIs, async operations, routers, Pydantic schemas, SQLAlchemy, background workers | fastapi-python | C:\Users\Franco Gagliardi\.agents\skills\fastapi-python\SKILL.md |
| Creating or reviewing Dockerfiles/Compose services, container security, networking, volumes, multi-service orchestration, installer harnesses | docker-patterns | C:\Users\Franco Gagliardi\.agents\skills\docker-patterns\SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### vercel-react-best-practices
- Parallelize independent fetches with Promise.all — never waterfall awaits; start promises early, await late; check cheap sync conditions before awaiting
- Import directly from modules, never barrel files; dynamic-import heavy components; defer third-party scripts past hydration; preload on hover/focus
- Never define components inside components; hoist static JSX out; extract expensive work into memoized components
- Prefer ternary over && for conditionals; use startTransition/useDeferredValue for non-urgent updates to keep inputs responsive
- Derive state during render, never in effects; use primitive effect deps; functional setState for stable callbacks; lazy useState init for expensive values
- Batch DOM/CSS changes via classes or cssText; use Set/Map for O(1) lookups; hoist RegExp out of loops; early returns
- Gotcha: server-/Next.js-only rules (RSC cache, after(), next/dynamic) do NOT apply to this Vite SPA — apply client/bundle/rerender/js rules only

### supabase-postgres-best-practices
- Load BEFORE any schema/migration/index/RLS/query change — even one-column or single-query edits
- Missing/partial indexes first for slow queries; verify with EXPLAIN (ANALYZE, BUFFERS) before and after
- Design schemas with correct types, constraints, FKs; prefer declarative migrations; never ad-hoc DDL on live data without a migration
- RLS: enable on every user-facing table, write policies per role, add tests proving no rows leak to the wrong user/tenant
- Keep transactions short with correct isolation; avoid lock escalation and bloat on hot tables (turnos, caja, auditoria append-only)
- Pool connections (transaction mode); diagnose high CPU/timeouts via pg_stat_statements, never guess
- Gotcha: applies to Postgres anywhere (not only Supabase); covers pg_cron/pgmq jobs, pgvector, triggers/functions, pg_restore

### tdd
- Red before green: write one failing test first, then minimal code to pass; no speculative features
- One vertical slice per cycle (one seam → one test → one implementation); never write all tests up front (horizontal slicing)
- Test only at pre-agreed seams (public boundaries); confirm seams with user before writing any test
- Tests assert behavior through public interfaces — never internals, private methods, or side channels (e.g. querying the DB behind the API)
- Expected values from an independent source of truth (literals, worked examples, spec) — never recompute the way the code does; no tautological assertions/snapshots
- Name tests in domain language (check GLOSSARY.md/ADRs); refactoring belongs to the review stage, not the red → green loop

### auth-implementation-patterns
- Prefer JWT Bearer stateless auth for the API + RBAC (odontologo, recepcionista, admin, paciente); enforce server-side on every route, never client-only checks
- Short-lived access tokens (15–30 min) with refresh rotation; validate expiry server-side; rotate JWT/session secrets regularly
- Store JWT in httpOnly + secure + sameSite cookies, never localStorage (XSS); hash passwords with bcrypt/argon2
- Rate-limit all auth endpoints (brute force); validate email format and password strength; secure password-reset tokens with expiry
- Log auth security events (logins, failures); add CSRF protection for cookie/session flows; always HTTPS
- Project wiring: expose auth as FastAPI dependencies (current-user + role guards, e.g. api/deps.py, RN-SE-02)

### fastapi-python
- Routers + Pydantic v2 models for all I/O (RORO: receive object, return object); type-hint every signature; never raw dicts at boundaries
- async def for all DB/API I/O; never block the event loop; use SQLAlchemy 2.0 async patterns
- Dependency injection for shared concerns (auth user, DB session); lifespan context managers for startup/shutdown
- Guard clauses + early returns at entry; happy path last; no unnecessary else; HTTPException with specific status codes for expected errors
- Pydantic BaseModel consistently for validation; middleware for logging/error monitoring; cache hot reads with Redis/in-memory; lazy-load large datasets
- Naming: snake_case files/dirs (routers/user_routes.py); descriptive booleans (is_active, has_permission); exported router first, then sub-routes/utils/types

### docker-patterns
- Compose stack api/frontend/db/redis with service-name DNS (db, redis); gate startup with healthchecks + depends_on conditions; named volumes (pgdata/redisdata) for persistence
- Multi-stage Dockerfiles (deps → dev → build → production); pin base images by version/digest, never :latest; lean production stage running as non-root user
- Dev: bind-mount source for hot reload + anonymous volumes protecting container deps; dev-only settings in override files; prod via explicit -f compose file
- Secrets via env_file/.env (gitignored) or Docker secrets — never bake secrets into image layers; keep a .dockerignore (node_modules, .git, .env, dist, coverage)
- Harden compose: no-new-privileges, read_only + tmpfs where possible, cap_drop ALL; bind dev ports to 127.0.0.1, omit ports in prod
- Gotcha: Linux containers do NOT validate macOS/Windows behavior — keep a native CI matrix; one process per container; never store data without volumes

## Project Conventions

No convention files found (no AGENTS.md / CLAUDE.md / .cursorrules / GEMINI.md / copilot-instructions.md in project root). The conventions section is intentionally empty — it will be populated when AGENTS.md/CLAUDE.md is generated in the next foundation phase.

| File | Path | Notes |
|------|------|-------|
| (none) | — | No convention files in project root yet |
