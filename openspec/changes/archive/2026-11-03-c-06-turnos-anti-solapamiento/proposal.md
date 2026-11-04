# Proposal

## Why

C-04 dejó la oferta (profesionales, sillones, prestaciones y bloqueos) y C-05 la demanda (pacientes y cobertura), pero el sistema todavía no puede **reservar nada**: no existe el `Turno`. Sin turnos no hay agenda real, no se puede cumplir el heart del sistema —evitar solapamientos (RN-TU-01)— y C-07/C-08/C-09/C-13 no tienen qué reservar, mostrar ni cobrar.

C-06 es el JOIN del GATE 3 y el núcleo del MVP: crea el turno con garantía transaccional anti-solapamiento por profesional **y** por sillón, aplica bloqueos y la máquina de estados, y convierte la disponibilidad base de C-04 en disponibilidad real.

## What Changes

- Agrega el modelo `Turno` y la migración `0006_turnos_anti_solapamiento`:
  - Paciente, profesional, sillón y prestación; `inicio`/`fin`; estado (`reservado`, `confirmado`, `en_sala`, `atendido`, `cancelado`, `ausente`); origen (`recepcion`, `online`, `whatsapp`); marca de sobreturno con color; `token_publico` único opcional.
  - `fin` se deriva de la duración de la prestación o de la duración base del profesional (RN-TU-02).
  - Garantía anti-solapamiento en PostgreSQL con extensión `btree_gist` y constraints de exclusión para turnos normales, más validación en la aplicación para devolver 409 con detalle y para cubrir sobreturnos (RN-TU-01/RN-TU-06).
  - Índices `(profesional_id, inicio)`, `(sillon_id, inicio)`, `estado` y `token_publico`.
- Agrega `consultorios.plazo_cancelacion_horas` (default 24) para RN-TU-03.
- Expone endpoints con RBAC (RN-SE-01):
  - `POST /turnos`: alta con validación de solapamiento, bloqueos y coherencia de recursos.
  - `GET /turnos` por rango de fechas y filtros de profesional/sillón/estado; `GET /turnos/{id}`.
  - `PATCH /turnos/{id}/estado`: máquina de estados validada.
  - `PATCH /turnos/{id}/reprogramar`: nueva fecha/recursos con la misma validación transaccional.
- Extiende la disponibilidad de C-04 para descontar turnos activos y bloqueos, devolviendo solo huecos realmente libres.
- Valida en el borde y en la base: fin posterior a inicio, duración coherente, sobreturno con color obligatorio, estados y orígenes válidos, recursos activos y pertenecientes al consultorio, bloqueo que impide la reserva.
- Agrega suite unitaria (máquina de estados, cálculo de fin) e integración (concurrencia real, 409/422/404, bloqueos, sobreturnos, reprogramación y RBAC).

## Capabilities

### New Capabilities
- `agenda/turnos`: alta, consulta, reprogramación, cancelación por estado y garantía anti-solapamiento por profesional y sillón.

### Modified Capabilities
- `agenda/recursos-agendables`: la disponibilidad deja de ser «base» y descuenta turnos activos además de bloqueos.

## Impact

- **Backend**:
  - `app/models/agenda.py` (`Turno`) o módulo `app/models/turnos.py`, `app/models/__init__.py`.
  - `app/models/security.py` (`Consultorio.plazo_cancelacion_horas`) y migración `0006`.
  - `app/domain/agenda.py` (fin del turno, solapamiento y disponibilidad real).
  - `app/infrastructure/repositories.py` y `app/infrastructure/uow.py` (`TurnoRepository`).
  - `app/schemas/turnos.py`, `app/api/turnos.py`, ajuste de `app/api/profesionales.py` (disponibilidad real) y `app/main.py`.
  - Tests unitarios e integración; actualización de tests que asumen el head `0005`.
- **Base de datos**: extensión `btree_gist` y constraints de exclusión; requieren un usuario con permiso para crear extensiones (el `clinica` del Compose lo tiene).
- **API Surface**: `/turnos`, `/turnos/{id}`, `/turnos/{id}/estado`, `/turnos/{id}/reprogramar` y `GET /profesionales/{id}/disponibilidad` enriquecido.
- **Riesgos y mitigaciones**:
  - **Solapamiento silencioso**: se ataca en dos capas (constraint de exclusión + validación), con prueba de concurrencia real; un fallo de la app no puede dejar dos turnos normales en el mismo slot.
  - **Sobreturnos**: son la única excepción y llevan marca y color obligatorios; nunca se crean por error de validación.
  - **Seña**: `seña_id` se difiere a C-13 para no crear una FK a una tabla inexistente; RN-TU-04 se implementa cuando exista el cobro.
  - **Lista de espera**: la liberación por cancelación se notifica en C-10; C-06 solo deja el turno cancelado.
  - **Zona horaria**: se mantiene el offset fijo `UTC-3` de C-04.
