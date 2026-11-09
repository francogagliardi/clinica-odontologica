/** Public privacy policy API (C-16). Anonymous, read-only, no auth header. */

import { fetchJson } from "../../shared/api/client";

export interface PoliticaPrivacidad {
  version: string;
  vigente_desde: string;
  texto: string;
  hash: string;
  alcance_legal_validado: boolean;
}

export function fetchPrivacidad(version?: string): Promise<PoliticaPrivacidad> {
  const path =
    version === undefined
      ? "/privacidad"
      : `/privacidad/${encodeURIComponent(version)}`;
  return fetchJson(path) as Promise<PoliticaPrivacidad>;
}
