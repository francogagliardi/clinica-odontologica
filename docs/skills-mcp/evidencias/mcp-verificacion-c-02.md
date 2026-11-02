# Evidencia MCP — verificación del esquema de C-02 (2026-11-01)

Mismo servidor MCP de la ficha (`Postgres MCP Pro`, `--access-mode=restricted`), ahora
consultado **después** de aplicar la migración `0002_core_models_seguridad` y correr el
seed demo. Sirve para cerrar el círculo abierto en `mcp-sesion-cliente.md`: allí el MCP
mostró la base vacía (`0001_base`); acá muestra el esquema que el change creó.

Base: Compose local (`clinica`), datos ficticios. Sin datos de pacientes.

## 1. Columnas por tabla

```sql
select table_name, column_name, data_type
from information_schema.columns
where table_schema='public'
  and table_name in ('consultorios','roles','usuarios','usuario_roles','registro_auditoria')
order by table_name, ordinal_position;
```

Resultado (resumido): `consultorios`, `roles` y `usuarios` exponen
`is_active/created_at/updated_at/deleted_at` (baja lógica), `usuario_roles` solo
`usuario_id` + `rol_id`, y `registro_auditoria` **no** tiene columnas de modificación
(`updated_at`, `deleted_at` ausentes), tal como exige RN-SE-02.

## 2. Conteos y versión aplicada

```sql
select (select count(*) from roles) as roles,
       (select count(*) from consultorios) as consultorios,
       (select count(*) from usuarios) as usuarios,
       (select count(*) from usuario_roles) as links,
       (select count(*) from registro_auditoria) as auditoria,
       (select version_num from alembic_version) as version;
```

```
roles=5  consultorios=1  usuarios=1  links=1  auditoria=0  version=0002_core_models_seguridad
```

Los 5 roles son los del seed (`administrador`, `odontologo`, `recepcionista`,
`asistente`, `auditor`), más el consultorio demo y el administrador con su vínculo.

## 3. Índices: unicidad solo sobre filas activas

```sql
select indexname, indexdef from pg_indexes where schemaname='public' order by indexname;
```

Fragmento relevante:

```
CREATE UNIQUE INDEX uq_consultorios_slug_activo ON public.consultorios USING btree (slug) WHERE (deleted_at IS NULL)
CREATE UNIQUE INDEX uq_roles_nombre_activo      ON public.roles       USING btree (nombre) WHERE (deleted_at IS NULL)
CREATE UNIQUE INDEX uq_usuarios_email_activo    ON public.usuarios    USING btree (email)  WHERE (deleted_at IS NULL)
CREATE UNIQUE INDEX pk_usuario_roles            ON public.usuario_roles USING btree (usuario_id, rol_id)
```

Confirma que la unicidad es **parcial**: un valor dado de baja lógica deja de bloquear
su reutilización.

## 4. Triggers de auditoría

```sql
select tgname from pg_trigger where not tgisinternal order by tgname;
```

```
trg_registro_auditoria_sin_truncate
trg_registro_auditoria_sin_update_delete
```

Dos triggers: el de fila bloquea `UPDATE`/`DELETE` y el de sentencia bloquea
`TRUNCATE` (PostgreSQL no dispara triggers de fila en un vaciado masivo).

## Qué aportó esta consulta

- Cerró la verificación de la migración **desde afuera del código**: el esquema real
  coincide con lo que declaran los modelos y las specs.
- Detectó que el nombre del CHECK quedaba duplicado (`ck_consultorios_ck_...`) porque
  la convención de nombres de SQLAlchemy ya agrega `ck_<tabla>_`: se corrigió la
  migración para pasar el nombre corto y el test de paridad ORM↔esquema lo verifica.
- Dejó evidencia de que la herramienta MCP sirve tanto para el diseño (antes del
  change) como para la verificación (después), que es el uso previsto en `AGENTS.md`.
