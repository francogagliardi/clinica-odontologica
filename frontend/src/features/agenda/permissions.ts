/** Visual permissions: the API remains the authority (RN-SE-01). */

import type { Session } from "../auth/session";
import type { Profesional, Turno } from "./api";

export function puedeReprogramar(
  turno: Turno,
  session: Session | null,
  profesionales: Profesional[],
): boolean {
  if (session === null) {
    return false;
  }
  const roles = session.usuario.roles;
  if (roles.includes("administrador") || roles.includes("recepcionista")) {
    return true;
  }
  if (roles.includes("odontologo")) {
    const profesional = profesionales.find(
      (item) => item.id === turno.profesional_id,
    );
    return profesional?.usuario_id === session.usuario.id;
  }
  return false;
}
