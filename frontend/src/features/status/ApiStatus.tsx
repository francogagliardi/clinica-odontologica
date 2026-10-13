import { useEffect, useState } from "react";

import {
  ApiError,
  describeFailure,
  fetchSystemStatus,
  type SystemStatus,
} from "../../shared/api/client";

type LoadState = { kind: "loading" } | { kind: "done"; status: SystemStatus };

/** Backend status panel: parallel health+ready fetch, errors shown verbatim. */
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
    return <p>Consultando estado del backend…</p>;
  }
  const { health, ready } = state.status;
  return (
    <section aria-label="Estado del backend">
      <p>
        API: {health instanceof ApiError ? describeFailure(health) : health.status}
      </p>
      <p>
        Dependencias:{" "}
        {ready instanceof ApiError
          ? describeFailure(ready)
          : `db ${ready.checks.db} · redis ${ready.checks.redis}`}
      </p>
    </section>
  );
}
