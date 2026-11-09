/** Functional audit viewer: filters, paginated table and no write surface.
 *
 * The screen is read-only: every 401/403/404/422 is presented verbatim and no
 * local rule filters the rows.
 */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import { LoginForm } from "../features/auth/LoginForm";
import { useSession } from "../features/auth/session";
import {
  fetchAuditoria,
  type AuditoriaResponse,
  type FiltrosAuditoria,
} from "../features/auditoria/api";
import { Button } from "../shared/ui/Button";
import { Card } from "../shared/ui/Card";
import { EmptyState } from "../shared/ui/EmptyState";
import { ErrorBanner } from "../shared/ui/ErrorBanner";
import { Input } from "../shared/ui/Input";
import { Loading } from "../shared/ui/Loading";
import { PageHeader } from "../shared/ui/PageHeader";
import { Select } from "../shared/ui/Select";
import { Table } from "../shared/ui/Table";

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
      <PageHeader
        title="Auditoría"
        description="Historial de solo lectura con usuario, IP y dispositivo."
      />

      {error !== null ? <ErrorBanner message={error} /> : null}
      {cargando ? <Loading /> : null}

      {puedeLeer ? (
        <>
          <Card title="Filtros">
            <form onSubmit={buscar} className="ds-filter-grid">
              <Input
                label="Usuario (id)"
                value={filtros.usuarioId ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, usuarioId: event.target.value })
                }
              />
              <Input
                label="Entidad"
                value={filtros.entidad ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, entidad: event.target.value })
                }
              />
              <Input
                label="Acción"
                value={filtros.accion ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, accion: event.target.value })
                }
              />
              <Input
                label="Desde"
                type="date"
                value={filtros.desde ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, desde: event.target.value })
                }
              />
              <Input
                label="Hasta"
                type="date"
                value={filtros.hasta ?? ""}
                onChange={(event) =>
                  setFiltros({ ...filtros, hasta: event.target.value })
                }
              />
              <Select
                label="Límite"
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
              </Select>
              <Button type="submit">Buscar</Button>
            </form>
          </Card>

          {datos !== null ? (
            <>
              <p>Total: {total}</p>
              {datos.filas.length === 0 ? (
                <EmptyState
                  title="Sin registros"
                  description="No hay eventos para los filtros elegidos."
                />
              ) : (
                <Table label="Auditoría">
                  <thead>
                    <tr>
                      <th scope="col">Usuario</th>
                      <th scope="col">Email</th>
                      <th scope="col">Acción</th>
                      <th scope="col">Entidad</th>
                      <th scope="col">Entidad ID</th>
                      <th scope="col">IP</th>
                      <th scope="col">Dispositivo</th>
                      <th scope="col">Fecha</th>
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
                </Table>
              )}
              <div className="ds-pagination">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - limite))}
                >
                  Anterior
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={offset + limite >= total}
                  onClick={() => setOffset(offset + limite)}
                >
                  Siguiente
                </Button>
              </div>
            </>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
