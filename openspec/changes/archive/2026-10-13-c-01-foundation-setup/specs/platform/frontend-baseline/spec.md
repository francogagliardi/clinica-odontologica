# Spec Delta

## Purpose

Establece el shell SPA React+TypeScript+Vite servido por Compose, con estructura features/shared/pages lista para agenda backoffice y reserva pública.

## ADDED Requirements

### Requirement: Shell SPA Vite servido y enrutable

El frontend SHALL compilar con Vite en modo estricto TypeScript (sin `any`), servirse vía Compose y renderizar placeholders enrutable de backoffice (`/`) y reserva pública (`/reservar`), sin lógica de negocio en el cliente.

#### Scenario: Build y rutas placeholder

- **WHEN** se ejecuta el build de producción y se sirve el bundle
- **THEN** `/` renderiza el placeholder backoffice, `/reservar` el placeholder de reserva pública, y rutas desconocidas muestran 404 sin romper la SPA

### Requirement: Configuración del cliente por entorno

La URL base de la API SHALL provenir de variable de entorno documentada en `frontend/.env.example` (p. ej. `VITE_API_BASE_URL`), con fetches paralelos donde haya independencia y errores de API solo presentados (toda validación vive en el backend).

#### Scenario: API base configurable

- **WHEN** se cambia `VITE_API_BASE_URL` y se reconstruye
- **THEN** todas las llamadas usan la nueva base sin editar código, y un fallo `409/422` de la API se muestra tal cual sin reinterpretación local

### Requirement: Convenciones de componentes y rendimiento

Los componentes SHALL usar `PascalCase`, no definir componentes dentro de componentes, importar directo desde módulos (sin barrel files) y paralelizar fetches independientes con `Promise.all`.

#### Scenario: Revisión estática de convenciones

- **WHEN** se audita `frontend/src` sobre el checkout fresco
- **THEN** no hay `any` explícito, no hay componentes anidados, no hay imports desde barrel files y los fetches independientes usan `Promise.all`
