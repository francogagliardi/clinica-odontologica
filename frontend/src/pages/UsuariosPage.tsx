/** Functional access-management page: list, create, roles and account state.
 *
 * No business rules in the client: every 403/409/422 is shown verbatim from the
 * API and the UI only hides what the API already forbids (R-07).
 */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import { LoginForm } from "../features/auth/LoginForm";
import { useSession } from "../features/auth/session";
import {
  actualizarUsuario,
  cambiarPassword,
  crearUsuario,
  fetchRoles,
  fetchUsuarios,
  reemplazarRoles,
  type Rol,
  type Usuario,
} from "../features/usuarios/api";
import { Badge } from "../shared/ui/Badge";
import { Button } from "../shared/ui/Button";
import { Card } from "../shared/ui/Card";
import { EmptyState } from "../shared/ui/EmptyState";
import { ErrorBanner } from "../shared/ui/ErrorBanner";
import { Input } from "../shared/ui/Input";
import { Loading } from "../shared/ui/Loading";
import { PageHeader } from "../shared/ui/PageHeader";
import { Table } from "../shared/ui/Table";

interface FormularioAlta {
  nombre: string;
  email: string;
  password: string;
  roles: string[];
}

const ALTA_VACIA: FormularioAlta = {
  nombre: "",
  email: "",
  password: "",
  roles: [],
};

function asMessage(failure: unknown): string {
  return failure instanceof ApiError
    ? describeFailure(failure)
    : String(failure);
}

export function UsuariosPage(): React.JSX.Element {
  const session = useSession();
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [roles, setRoles] = useState<Rol[]>([]);
  const [incluirInactivos, setIncluirInactivos] = useState(false);
  const [refresco, setRefresco] = useState(0);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sinPermiso, setSinPermiso] = useState(false);
  const [alta, setAlta] = useState<FormularioAlta>(ALTA_VACIA);
  const [rolesEditados, setRolesEditados] = useState<
    Record<string, string[]>
  >({});
  const [passwords, setPasswords] = useState<Record<string, string>>({});

  useEffect(() => {
    if (session === null) {
      return;
    }
    let activo = true;
    setCargando(true);
    setError(null);
    setSinPermiso(false);
    Promise.all([fetchUsuarios(incluirInactivos), fetchRoles()])
      .then(([lista, catalogo]) => {
        if (activo) {
          setUsuarios(lista);
          setRoles(catalogo);
        }
      })
      .catch((failure: unknown) => {
        if (activo) {
          setSinPermiso(
            failure instanceof ApiError &&
              (failure.status === 401 || failure.status === 403),
          );
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
  }, [session, incluirInactivos, refresco]);

  if (session === null) {
    return <LoginForm />;
  }

  const esAdmin = session.usuario.roles.includes("administrador");

  async function ejecutar(accion: () => Promise<unknown>): Promise<void> {
    setError(null);
    try {
      await accion();
      setRefresco((valor) => valor + 1);
    } catch (failure) {
      setError(asMessage(failure));
    }
  }

  function rolesDe(usuario: Usuario): string[] {
    return rolesEditados[usuario.id] ?? usuario.roles;
  }

  function alternarRol(usuario: Usuario, nombre: string): void {
    const actuales = rolesDe(usuario);
    const siguientes = actuales.includes(nombre)
      ? actuales.filter((rol) => rol !== nombre)
      : [...actuales, nombre];
    setRolesEditados({ ...rolesEditados, [usuario.id]: siguientes });
  }

  function alternarRolAlta(nombre: string): void {
    const siguientes = alta.roles.includes(nombre)
      ? alta.roles.filter((rol) => rol !== nombre)
      : [...alta.roles, nombre];
    setAlta({ ...alta, roles: siguientes });
  }

  async function crear(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await ejecutar(async () => {
      await crearUsuario(alta);
      setAlta(ALTA_VACIA);
    });
  }

  async function guardarRoles(usuario: Usuario): Promise<void> {
    await ejecutar(() => reemplazarRoles(usuario.id, rolesDe(usuario)));
  }

  async function alternarEstado(usuario: Usuario): Promise<void> {
    await ejecutar(() =>
      actualizarUsuario(usuario.id, { activo: !usuario.is_active }),
    );
  }

  async function guardarPassword(usuario: Usuario): Promise<void> {
    const password = passwords[usuario.id] ?? "";
    await ejecutar(async () => {
      await cambiarPassword(usuario.id, password);
      setPasswords({ ...passwords, [usuario.id]: "" });
    });
  }

  return (
    <main>
      <PageHeader
        title="Usuarios"
        description="Altas, roles y estado de las cuentas del consultorio."
      />

      {error !== null ? <ErrorBanner message={error} /> : null}
      {cargando ? <Loading /> : null}

      {esAdmin && !sinPermiso ? (
        <Card title="Nuevo usuario">
          <form onSubmit={crear} className="ds-form-grid">
            <Input
              label="Nombre"
              value={alta.nombre}
              onChange={(event) =>
                setAlta({ ...alta, nombre: event.target.value })
              }
            />
            <Input
              label="Email"
              type="email"
              value={alta.email}
              onChange={(event) =>
                setAlta({ ...alta, email: event.target.value })
              }
            />
            <Input
              label="Contraseña"
              type="password"
              value={alta.password}
              onChange={(event) =>
                setAlta({ ...alta, password: event.target.value })
              }
            />
            <fieldset className="ds-roles ds-form-grid__full">
              <legend>Roles</legend>
              {roles.map((rol) => (
                <label key={rol.id}>
                  <input
                    type="checkbox"
                    aria-label={`Rol ${rol.nombre}`}
                    checked={alta.roles.includes(rol.nombre)}
                    onChange={() => alternarRolAlta(rol.nombre)}
                  />
                  {rol.nombre}
                </label>
              ))}
            </fieldset>
            <Button
              type="submit"
              className="ds-form-grid__full"
            >
              Crear usuario
            </Button>
          </form>
        </Card>
      ) : null}

      {!sinPermiso && !cargando ? (
        <label className="ds-check">
          <input
            type="checkbox"
            checked={incluirInactivos}
            onChange={(event) => setIncluirInactivos(event.target.checked)}
          />
          Incluir inactivos
        </label>
      ) : null}

      {!sinPermiso &&
      !cargando &&
      error === null &&
      usuarios.length === 0 ? (
        <EmptyState
          title="Sin usuarios"
          description="No hay cuentas para mostrar con este filtro."
        />
      ) : null}

      {!sinPermiso && usuarios.length > 0 ? (
        <Table label="Usuarios">
          <thead>
            <tr>
              <th scope="col">Nombre</th>
              <th scope="col">Email</th>
              <th scope="col">Estado</th>
              <th scope="col">Roles</th>
              <th scope="col">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {usuarios.map((usuario) => (
              <tr key={usuario.id}>
                <td>{usuario.nombre}</td>
                <td>{usuario.email}</td>
                <td>
                  <Badge tone={usuario.is_active ? "success" : "neutral"}>
                    {usuario.is_active ? "activo" : "inactivo"}
                  </Badge>
                </td>
                <td>{usuario.roles.join(", ")}</td>
                <td>
                  <div
                    className="ds-actions"
                    role="group"
                    aria-label={`Acciones para ${usuario.email}`}
                  >
                    <fieldset className="ds-roles">
                      <legend>Roles de {usuario.email}</legend>
                      {roles.map((rol) => (
                        <label key={rol.id}>
                          <input
                            type="checkbox"
                            aria-label={`${usuario.email} ${rol.nombre}`}
                            checked={rolesDe(usuario).includes(rol.nombre)}
                            onChange={() => alternarRol(usuario, rol.nombre)}
                          />
                          {rol.nombre}
                        </label>
                      ))}
                    </fieldset>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void guardarRoles(usuario)}
                    >
                      Guardar roles
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void alternarEstado(usuario)}
                    >
                      {usuario.is_active ? "Desactivar" : "Activar"}
                    </Button>
                    <Input
                      label="Nueva contraseña"
                      type="password"
                      aria-label={`Contraseña de ${usuario.email}`}
                      value={passwords[usuario.id] ?? ""}
                      onChange={(event) =>
                        setPasswords({
                          ...passwords,
                          [usuario.id]: event.target.value,
                        })
                      }
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void guardarPassword(usuario)}
                    >
                      Cambiar contraseña
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : null}
    </main>
  );
}
