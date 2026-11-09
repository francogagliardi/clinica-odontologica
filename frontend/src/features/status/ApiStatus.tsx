import { useEffect, useState } from "react";

import {
  ApiError,
  describeFailure,
  fetchSystemStatus,
  type SystemStatus,
} from "../../shared/api/client";
import { Badge } from "../../shared/ui/Badge";
import type { BadgeTone } from "../../shared/ui/Badge";
import { Card } from "../../shared/ui/Card";
import { Loading } from "../../shared/ui/Loading";

type LoadState = { kind: "loading" } | { kind: "done"; status: SystemStatus };

interface FilaEstado {
  label: string;
  tone: BadgeTone;
  texto: string;
}

function fila(label: string, ok: boolean): FilaEstado {
  return ok
    ? { label, tone: "success", texto: "Operativo" }
    : { label, tone: "danger", texto: "Con error" };
}

/** Backend status panel: three named rows, text + tone, errors verbatim. */
export function ApiStatus(): React.JSX.Element {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchSystemStatus().then(
      (status) => {
        if (!cancelled) {
          setState({ kind: "done", status });
        }
      },
      () => {
        if (!cancelled) {
          setState({
            kind: "done",
            status: {
              health: new ApiError(0, "unexpected client failure"),
              ready: new ApiError(0, "unexpected client failure"),
            },
          });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <Card title="Estado del sistema">
        <Loading label="Consultando estado del backend…" />
      </Card>
    );
  }

  const { health, ready } = state.status;
  const healthError = health instanceof ApiError ? describeFailure(health) : null;
  const readyError = ready instanceof ApiError ? describeFailure(ready) : null;
  const dbUp = !(ready instanceof ApiError) && ready.checks.db === "up";
  const redisUp = !(ready instanceof ApiError) && ready.checks.redis === "up";
  const filas: FilaEstado[] = [
    fila("API", healthError === null),
    fila("Base de datos", dbUp),
    fila("Redis", redisUp),
  ];

  return (
    <Card title="Estado del sistema">
      <div className="ds-status" aria-live="polite">
        <ul className="ds-status__list">
          {filas.map((item) => (
            <li
              key={item.label}
              className="ds-status__row"
              role="group"
              aria-label={item.label}
            >
              <span className="ds-status__label">{item.label}</span>
              <Badge tone={item.tone}>{item.texto}</Badge>
            </li>
          ))}
        </ul>
        {healthError === null ? null : (
          <p className="ds-status__error ds-mono">{healthError}</p>
        )}
        {readyError === null ? null : (
          <p className="ds-status__error ds-mono">{readyError}</p>
        )}
      </div>
    </Card>
  );
}
