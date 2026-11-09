/** Public privacy policy page: centered reading column, versioned text and hash. */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import {
  fetchPrivacidad,
  type PoliticaPrivacidad,
} from "../features/privacidad/api";
import { goBack } from "../shared/navigation";
import { Button } from "../shared/ui/Button";
import { ErrorBanner } from "../shared/ui/ErrorBanner";
import { Loading } from "../shared/ui/Loading";
import { PageHeader } from "../shared/ui/PageHeader";

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
      <main className="ds-reading">
        <PageHeader
          title="Política de privacidad"
          actions={
            <Button variant="ghost" onClick={() => goBack("/")}>
              Volver
            </Button>
          }
        />
        {error !== null ? <ErrorBanner message={error} /> : <Loading />}
      </main>
    );
  }

  return (
    <main className="ds-reading">
      <PageHeader
        title="Política de privacidad"
        description="Texto informativo versionado; no se pide aceptación para reservar."
        actions={
          <Button variant="ghost" onClick={() => goBack("/")}>
            Volver
          </Button>
        }
      />
      <article className="ds-prose" aria-label="Política de privacidad">
        <dl className="ds-meta">
          <dt>Versión</dt>
          <dd>{politica.version}</dd>
          <dt>Vigente desde</dt>
          <dd>{politica.vigente_desde}</dd>
        </dl>
        <p>{politica.texto}</p>
        <p className="ds-mono">Hash SHA-256: {politica.hash}</p>
        <p>
          <Button href="/reservar">Reservar turno</Button>
        </p>
      </article>
    </main>
  );
}

function asMessage(failure: unknown): string {
  return failure instanceof ApiError
    ? describeFailure(failure)
    : String(failure);
}
