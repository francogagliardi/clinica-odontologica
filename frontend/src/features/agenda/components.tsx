/** Visual cards for appointments and blocks (C-08). */

import { Badge } from "../../shared/ui/Badge";
import { EstadoBadge } from "../../shared/ui/EstadoBadge";
import { horaDe } from "./calendar";
import type { Bloqueo, Turno } from "./api";

interface TurnoCardProps {
  turno: Turno;
  reprogramable: boolean;
  onDragStart: (turno: Turno) => void;
}

export function TurnoCard({
  turno,
  reprogramable,
  onDragStart,
}: TurnoCardProps): React.JSX.Element {
  return (
    <div
      className={`turno estado-${turno.estado}${
        turno.es_sobreturno ? " sobreturno" : ""
      }`}
      draggable={reprogramable}
      onDragStart={(event) => {
        event.dataTransfer.setData("text/turno", JSON.stringify(turno));
        onDragStart(turno);
      }}
      aria-label={`Turno ${horaDe(turno.inicio)} ${turno.estado}`}
      style={
        turno.es_sobreturno && turno.color_sobreturno !== null
          ? { borderColor: turno.color_sobreturno }
          : undefined
      }
    >
      <span className="turno-hora">{horaDe(turno.inicio)}</span>
      <EstadoBadge estado={turno.estado} />
      {turno.es_sobreturno ? (
        <Badge tone="warning" className="turno-sobreturno">
          Sobreturno
        </Badge>
      ) : null}
    </div>
  );
}

export function BloqueoCard({ bloqueo }: { bloqueo: Bloqueo }): React.JSX.Element {
  return (
    <div className="bloqueo" aria-label={`Bloqueo ${bloqueo.motivo}`}>
      {bloqueo.motivo}
    </div>
  );
}
