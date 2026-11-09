/** Public privacy policy page: versioned text, hash and no acceptance step. */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import {
  fetchPrivacidad,
  type PoliticaPrivacidad,
} from "../features/privacidad/api";

function asMessage(failure: unknown): string {
  return failure instanceof ApiError
    ? describeFailure(failure)
    : String(failure);
}

export function PrivacidadPage(): React.JSX.Element {
  const [politica, setPolitica] = useState<PoliticaPrivacidad | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let activo = true;
    fetchPrivacidad()
      .then((respuesta) => {
        if (activo) {
          setPolitica(respuesta);
        }
      })
      .catch((failure: unknown) => {
        if (activo) {
          setError(asMessage(failure));
        }
      });
    return () => {
      activo = false;
    };
  }, []);

  if (politica === null) {
    return (
      <main>
        <h1>Política de privacidad</h1>
        {error !== null ? <p role="alert">{error}</p> : <p>Cargando…</p>}
      </main>
    );
  }

  return (
    <main>
      <h1>Política de privacidad</h1>
      <p>Versión: {politica.version}</p>
      <p>Vigente desde: {politica.vigente_desde}</p>
      <p>{politica.texto}</p>
      <p>Hash SHA-256: {politica.hash}</p>
      <p>
        <a href="/reservar">Volver a reservar</a>
      </p>
    </main>
  );
}
