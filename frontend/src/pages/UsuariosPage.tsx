/** Functional access-management page: list, create, roles and account state.
 *
 * No design system (C-17) and no business rules in the client: every 403/409/422
 * is shown verbatim from the API and the UI only hides what the API already
 * forbids (R-07).
 */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import { LoginForm } from "../features/auth/LoginForm";
import { logout, useSession } from "../features/auth/session";
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
    Promise.all([fetchUsuarios(incluirInactivos), fetchRoles()])
      .then(([lista, catalogo]) => {
        if (activo) {
          setUsuarios(lista);
          setRoles(catalogo);
        }
      })
      .catch((failure: unknown) => {
        if (activo) {
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
      <h1>Usuarios</h1>
      <button type="button" onClick={logout}>
        Salir
      </button>

      {error !== null ? <p role="alert">{error}</p> : null}
      {cargando ? <p>Cargando…</p> : null}

      {esAdmin ? (
        <>
          <section aria-label="Alta de usuario">
            <h2>Nuevo usuario</h2>
            <form onSubmit={crear}>
              <label>
                Nombre
                <input
                  value={alta.nombre}
                  onChange={(event) =>
                    setAlta({ ...alta, nombre: event.target.value })
                  }
                />
              </label>
              <label>
                Email
                <input
                  value={alta.email}
                  onChange={(event) =>
                    setAlta({ ...alta, email: event.target.value })
                  }
                />
              </label>
              <label>
                Contraseña
                <input
                  type="password"
                  value={alta.password}
                  onChange={(event) =>
                    setAlta({ ...alta, password: event.target.value })
                  }
                />
              </label>
              <fieldset>
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
              <button type="submit">Crear usuario</button>
            </form>
          </section>

          <label>
            <input
              type="checkbox"
              checked={incluirInactivos}
              onChange={(event) =>
                setIncluirInactivos(event.target.checked)
              }
            />
            Incluir inactivos
          </label>

          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Email</th>
                <th>Estado</th>
                <th>Roles</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((usuario) => (
                <tr key={usuario.id}>
                  <td>{usuario.nombre}</td>
                  <td>{usuario.email}</td>
                  <td>{usuario.is_active ? "activo" : "inactivo"}</td>
                  <td>{usuario.roles.join(", ")}</td>
                  <td>
                    <fieldset>
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
                    <button
                      type="button"
                      onClick={() => void guardarRoles(usuario)}
                    >
                      Guardar roles
                    </button>
                    <button
                      type="button"
                      onClick={() => void alternarEstado(usuario)}
                    >
                      {usuario.is_active ? "Desactivar" : "Activar"}
                    </button>
                    <label>
                      Nueva contraseña
                      <input
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
                    </label>
                    <button
                      type="button"
                      onClick={() => void guardarPassword(usuario)}
                    >
                      Cambiar contraseña
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </main>
  );
}
