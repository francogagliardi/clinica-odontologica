/** Appointment management from the single-use public token (C-07). */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import {
  cancelarTurno,
  confirmarTurno,
  fetchGestion,
  type GestionTurnoResponse,
} from "../features/reserva/api";
import { Button } from "../shared/ui/Button";
import { Card } from "../shared/ui/Card";
import { ErrorBanner } from "../shared/ui/ErrorBanner";
import { EstadoBadge } from "../shared/ui/EstadoBadge";
import { Loading } from "../shared/ui/Loading";
import { PageHeader } from "../shared/ui/PageHeader";

interface Props {
  token: string;
}

interface Fallo {
  mensaje: string;
  status: number | null;
}

export function GestionTurnoPage({ token }: Props): React.JSX.Element {
  const [turno, setTurno] = useState<GestionTurnoResponse | null>(null);
  const [fallo, setFallo] = useState<Fallo | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  useEffect(() => {
    fetchGestion(token)
      .then(setTurno)
      .catch((failure: unknown) => setFallo(asFallo(failure)));
  }, [token]);

  async function accion(confirmar: boolean) {
    setFallo(null);
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
      setFallo(asFallo(failure));
    }
  }

  if (turno === null) {
    return (
      <main>
        <PageHeader title="Mi turno" />
        {fallo !== null ? <ErrorBanner message={fallo.mensaje} /> : null}
        {fallo?.status === 410 ? (
          <p>Pedí un enlace nuevo en la clínica.</p>
        ) : null}
        {mensaje !== null ? <p role="status">{mensaje}</p> : null}
        {fallo === null && mensaje === null ? <Loading /> : null}
      </main>
    );
  }

  return (
    <main>
      <PageHeader title="Mi turno" />
      <Card
        title="Resumen del turno"
        actions={<EstadoBadge estado={turno.estado} />}
      >
        <p>Estado: {turno.estado}</p>
        <p>Inicio: {new Date(turno.inicio).toLocaleString("es-AR")}</p>
        <p>Profesional: {turno.profesional.matricula}</p>
        {turno.prestacion !== null ? (
          <p>Prestación: {turno.prestacion.nombre}</p>
        ) : null}
        <p>Seña: {turno.sena.estado}</p>
        <p>{turno.politica_sena}</p>

        {turno.puede_confirmar ? (
          <Button onClick={() => void accion(true)}>Confirmar turno</Button>
        ) : null}
        {turno.puede_cancelar ? (
          <Button variant="secondary" onClick={() => void accion(false)}>
            Cancelar turno
          </Button>
        ) : null}
      </Card>

      {fallo !== null ? <ErrorBanner message={fallo.mensaje} /> : null}
      {mensaje !== null ? <p role="status">{mensaje}</p> : null}
    </main>
  );
}

function asFallo(failure: unknown): Fallo {
  return failure instanceof ApiError
    ? { mensaje: describeFailure(failure), status: failure.status }
    : { mensaje: String(failure), status: null };
}
