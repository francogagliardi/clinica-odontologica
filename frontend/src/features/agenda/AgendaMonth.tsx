/** Month view: compact grid with one chip per appointment. */

import { TurnoCard } from "./components";
import { diasEntre, fechaDe, inicioEnDia } from "./calendar";
import type { Turno } from "./api";

interface Props {
  desde: string;
  hasta: string;
  turnos: Turno[];
  esReprogramable: (turno: Turno) => boolean;
  onDragStart: (turno: Turno) => void;
  onDrop: (turno: Turno, inicio: string) => void;
}

export function AgendaMonth({
  desde,
  hasta,
  turnos,
  esReprogramable,
  onDragStart,
  onDrop,
}: Props): React.JSX.Element {
  return (
    <div className="agenda-mes">
      {diasEntre(desde, hasta).map((dia) => {
        const delDia = turnos.filter(
          (turno) => fechaDe(turno.inicio) === dia,
        );
        return (
          <div
            key={dia}
            className="agenda-mes-dia"
            aria-label={`Día ${dia}`}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const raw = event.dataTransfer.getData("text/turno");
              if (raw !== "") {
                const turno = JSON.parse(raw) as Turno;
                onDrop(turno, inicioEnDia(dia, turno.inicio));
              }
            }}
          >
            <strong>{dia.slice(8)}</strong>
            {delDia.map((turno) => (
              <TurnoCard
                key={turno.id}
                turno={turno}
                reprogramable={esReprogramable(turno)}
                onDragStart={onDragStart}
              />
            ))}
          </div>
        );
      })}
    </div>
  );
}
