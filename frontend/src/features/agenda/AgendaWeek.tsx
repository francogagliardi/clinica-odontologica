/** Week view: Monday–Sunday columns with hourly drop targets. */

import { BloqueoCard, TurnoCard } from "./components";
import { diasEntre, fechaDe, horaDe, inicioEnHora } from "./calendar";
import type { Bloqueo, Turno } from "./api";

const HORAS = Array.from({ length: 13 }, (_, index) => index + 8);

interface Props {
  desde: string;
  hasta: string;
  turnos: Turno[];
  bloqueos: Bloqueo[];
  esReprogramable: (turno: Turno) => boolean;
  onDragStart: (turno: Turno) => void;
  onDrop: (turno: Turno, inicio: string) => void;
}

export function AgendaWeek({
  desde,
  hasta,
  turnos,
  bloqueos,
  esReprogramable,
  onDragStart,
  onDrop,
}: Props): React.JSX.Element {
  const dias = diasEntre(desde, hasta);
  return (
    <div className="agenda-semana">
      <div className="agenda-semana-encabezado">
        <span />
        {dias.map((dia) => (
          <span key={dia}>{dia.slice(5)}</span>
        ))}
      </div>
      {HORAS.map((hora) => (
        <div key={hora} className="agenda-semana-fila">
          <span className="agenda-hora">{String(hora).padStart(2, "0")}:00</span>
          {dias.map((dia) => {
            const clave = `${dia}-${hora}`;
            const delDia = turnos.filter(
              (turno) =>
                fechaDe(turno.inicio) === dia &&
                Number(horaDe(turno.inicio).slice(0, 2)) === hora,
            );
            const bloqueosDia = bloqueos.filter(
              (bloqueo) =>
                fechaDe(bloqueo.desde) === dia &&
                Number(horaDe(bloqueo.desde).slice(0, 2)) === hora,
            );
            return (
              <div
                key={clave}
                className="agenda-celda"
                aria-label={`Celda ${dia} ${hora}:00`}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const raw = event.dataTransfer.getData("text/turno");
                  if (raw !== "") {
                    onDrop(JSON.parse(raw) as Turno, inicioEnHora(dia, hora));
                  }
                }}
              >
                {delDia.map((turno) => (
                  <TurnoCard
                    key={turno.id}
                    turno={turno}
                    reprogramable={esReprogramable(turno)}
                    onDragStart={onDragStart}
                  />
                ))}
                {bloqueosDia.map((bloqueo) => (
                  <BloqueoCard key={bloqueo.id} bloqueo={bloqueo} />
                ))}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
