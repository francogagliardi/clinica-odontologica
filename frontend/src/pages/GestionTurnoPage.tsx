/** Appointment management from the single-use public token (C-07). */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import {
  cancelarTurno,
  confirmarTurno,
  fetchGestion,
  type GestionTurnoResponse,
} from "../features/reserva/api";

interface Props {
  token: string;
}

export function GestionTurnoPage({ token }: Props): React.JSX.Element {
  const [turno, setTurno] = useState<GestionTurnoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  useEffect(() => {
    fetchGestion(token)
      .then(setTurno)
      .catch((failure: unknown) => setError(asMessage(failure)));
  }, [token]);

  async function accion(confirmar: boolean) {
    setError(null);
    try {
      const resultado = confirmar
        ? await confirmarTurno(token)
        : await cancelarTurno(token);
      setMensaje(
        resultado.sena_perdida
          ? `Turno ${resultado.estado}: la seña se pierde por cancelar fuera de plazo.`
          : `Turno ${resultado.estado}.`,
      );
      setTurno(null);
    } catch (failure) {
      setError(asMessage(failure));
    }
  }

  if (turno === null) {
    return (
      <main>
        <h1>Mi turno</h1>
        {error !== null ? <p role="alert">{error}</p> : null}
        {mensaje !== null ? <p role="status">{mensaje}</p> : null}
        {error === null && mensaje === null ? <p>Cargando…</p> : null}
      </main>
    );
  }

  return (
    <main>
      <h1>Mi turno</h1>
      <p>Estado: {turno.estado}</p>
      <p>Inicio: {new Date(turno.inicio).toLocaleString("es-AR")}</p>
      <p>Profesional: {turno.profesional.matricula}</p>
      {turno.prestacion !== null ? (
        <p>Prestación: {turno.prestacion.nombre}</p>
      ) : null}
      <p>Seña: {turno.sena.estado}</p>
      <p>{turno.politica_sena}</p>

      {turno.puede_confirmar ? (
        <button type="button" onClick={() => void accion(true)}>
          Confirmar turno
        </button>
      ) : null}
      {turno.puede_cancelar ? (
        <button type="button" onClick={() => void accion(false)}>
          Cancelar turno
        </button>
      ) : null}

      {error !== null ? <p role="alert">{error}</p> : null}
    </main>
  );
}

function asMessage(failure: unknown): string {
  return failure instanceof ApiError
    ? describeFailure(failure)
    : String(failure);
}
