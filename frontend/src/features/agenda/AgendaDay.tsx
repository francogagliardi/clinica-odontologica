/** Day view: one column with hourly drop targets. */

import { BloqueoCard, TurnoCard } from "./components";
import { fechaDe, horaDe, inicioEnHora } from "./calendar";
import type { Bloqueo, Turno } from "./api";

const HORAS = Array.from({ length: 13 }, (_, index) => index + 8); // 08–20

interface Props {
  fecha: string;
  turnos: Turno[];
  bloqueos: Bloqueo[];
  esReprogramable: (turno: Turno) => boolean;
  onDragStart: (turno: Turno) => void;
  onDrop: (turno: Turno, inicio: string) => void;
}

export function AgendaDay({
  fecha,
  turnos,
  bloqueos,
  esReprogramable,
  onDragStart,
  onDrop,
}: Props): React.JSX.Element {
  return (
    <div className="agenda-dia">
      {HORAS.map((hora) => {
        const delDia = turnos.filter(
          (turno) =>
            fechaDe(turno.inicio) === fecha &&
            Number(horaDe(turno.inicio).slice(0, 2)) === hora,
        );
        const bloqueosHora = bloqueos.filter(
          (bloqueo) =>
            fechaDe(bloqueo.desde) === fecha &&
            Number(horaDe(bloqueo.desde).slice(0, 2)) === hora,
        );
        return (
          <div
            key={hora}
            className="agenda-fila"
            data-hora={hora}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const turno = event.dataTransfer.getData("text/turno");
              if (turno !== "") {
                onDrop(JSON.parse(turno) as Turno, inicioEnHora(fecha, hora));
              }
            }}
          >
            <span className="agenda-hora">{String(hora).padStart(2, "0")}:00</span>
            <div className="agenda-celda">
              {delDia.map((turno) => (
                <TurnoCard
                  key={turno.id}
                  turno={turno}
                  reprogramable={esReprogramable(turno)}
                  onDragStart={(item) => {
                    onDragStart(item);
                  }}
                />
              ))}
              {bloqueosHora.map((bloqueo) => (
                <BloqueoCard key={bloqueo.id} bloqueo={bloqueo} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
