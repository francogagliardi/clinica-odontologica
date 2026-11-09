/** Raw turno state mapped to a visual tone; never translates the label. */

import { Badge } from "./Badge";
import type { BadgeTone } from "./Badge";

const TONOS: Record<string, BadgeTone> = {
  reservado: "info",
  confirmado: "primary",
  en_sala: "warning",
  atendido: "success",
  cancelado: "danger",
  ausente: "warning",
};

export interface EstadoBadgeProps {
  estado: string;
}

export function EstadoBadge({ estado }: EstadoBadgeProps): React.JSX.Element {
  return <Badge tone={TONOS[estado] ?? "neutral"}>{estado}</Badge>;
}
