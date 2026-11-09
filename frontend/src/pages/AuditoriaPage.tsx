/** Functional audit viewer: filters, paginated table and no write surface.
 *
 * The screen is read-only (C-17 keeps visual design out of scope); every
 * 401/403/404/422 is presented verbatim and no local rule filters the rows.
 */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import { LoginForm } from "../features/auth/LoginForm";
import { logout, useSession } from "../features/auth/session";
import {
  fetchAuditoria,
  type AuditoriaResponse,
  type FiltrosAuditoria,
} from "../features/auditoria/api";

const FILTROS_VACIOS: FiltrosAuditoria = {
  usuarioId: "",
  entidad: "",
  accion: "",
  desde: "",
  hasta: "",
  limite: 100,
  offset: 0,
};

function asMessage(failure: unknown): string {
  return failure instanceof ApiError
    ? describeFailure(failure)
    : String(failure);
}

export function AuditoriaPage(): React.JSX.Element {
  const session = useSession();
  const [filtros, setFiltros] = useState<FiltrosAuditoria>(FILTROS_VACIOS);
  const [aplicados, setAplicados] =
    useState<FiltrosAuditoria>(FILTROS_VACIOS);
  const [offset, setOffset] = useState(0);
  const [datos, setDatos] = useState<AuditoriaResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session === null) {
      return;
    }
    let activo = true;
    setCargando(true);
    setError(null);
    fetchAuditoria({ ...aplicados, offset })
      .then((respuesta) => {
        if (activo) {
          setDatos(respuesta);
        }
      })
      .catch((failure: unknown) => {
        if (activo) {
          setDatos(null);
          setError(asMessage(failure));
        }
      })
      .finally(() => {
        if (activo) {
          setCargando(false);
        }
      });
    return () => {
      activo = false;
    };
  }, [session, aplicados, offset]);

  if (session === null) {
    return <LoginForm />;
  }

  const puedeLeer =
    session.usuario.roles.includes("administrador") ||
    session.usuario.roles.includes("auditor");

  function buscar(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setOffset(0);
    setAplicados({ ...filtros, offset: 0 });
  }

  const total = datos?.total ?? 0;
  const limite = datos?.limite ?? aplicados.limite;

  return (
    <main>
      <h1>Auditoría</h1>
      <button type="button" onClick={logout}>
        Salir
      </button>

      {error !== null ? <p role="alert">{error}</p> : null}
      {cargando ? <p>Cargando…</p> : null}

      {puedeLeer ? (
        <>
          <form onSubmit={buscar}>
            <label>
              Usuario (id)
              <input
                value={filtros.usuarioId ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, usuarioId: event.target.value })
                }
              />
            </label>
            <label>
              Entidad
              <input
                value={filtros.entidad ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, entidad: event.target.value })
                }
              />
            </label>
            <label>
              Acción
              <input
                value={filtros.accion ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, accion: event.target.value })
                }
              />
            </label>
            <label>
              Desde
              <input
                type="date"
                value={filtros.desde ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, desde: event.target.value })
                }
              />
            </label>
            <label>
              Hasta
              <input
                type="date"
                value={filtros.hasta ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, hasta: event.target.value })
                }
              />
            </label>
            <label>
              Límite
              <select
                value={filtros.limite}
                onChange={(event) =>
                  setFiltros({
                    ...filtros,
                    limite: Number(event.target.value),
                  })
                }
              >
                <option value={100}>100</option>
                <option value={500}>500</option>
              </select>
            </label>
            <button type="submit">Buscar</button>
          </form>

          {datos !== null ? (
            <>
              <p>Total: {total}</p>
              <table>
                <thead>
                  <tr>
                    <th>Usuario</th>
                    <th>Email</th>
                    <th>Acción</th>
                    <th>Entidad</th>
                    <th>Entidad ID</th>
                    <th>IP</th>
                    <th>Dispositivo</th>
                    <th>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.filas.map((fila) => (
                    <tr key={fila.id}>
                      <td>{fila.usuario_id ?? "sistema"}</td>
                      <td>{fila.usuario_email ?? ""}</td>
                      <td>{fila.accion}</td>
                      <td>{fila.entidad}</td>
                      <td>{fila.entidad_id}</td>
                      <td>{fila.ip ?? ""}</td>
                      <td>{fila.dispositivo ?? ""}</td>
                      <td>{fila.timestamp}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div>
                <button
                  type="button"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - limite))}
                >
                  Anterior
                </button>
                <button
                  type="button"
                  disabled={offset + limite >= total}
                  onClick={() => setOffset(offset + limite)}
                >
                  Siguiente
                </button>
              </div>
            </>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
