/** Users and roles API: access management is decided by the backend (R-07). */

import {
  fetchJson,
  patchJson,
  postJson,
  putJson,
} from "../../shared/api/client";
import { authHeaders } from "../auth/session";

export interface Usuario {
  id: string;
  nombre: string;
  email: string;
  is_active: boolean;
  roles: string[];
}

export interface Rol {
  id: string;
  nombre: string;
}

export interface NuevoUsuario {
  nombre: string;
  email: string;
  password: string;
  roles: string[];
}

export interface CambiosUsuario {
  nombre?: string;
  email?: string;
  activo?: boolean;
}

export function fetchUsuarios(
  incluirInactivos = false,
): Promise<Usuario[]> {
  const path = incluirInactivos
    ? "/usuarios?incluir_inactivos=true"
    : "/usuarios";
  return fetchJson(path, authHeaders()) as Promise<Usuario[]>;
}

export function fetchUsuario(id: string): Promise<Usuario> {
  return fetchJson(`/usuarios/${id}`, authHeaders()) as Promise<Usuario>;
}

export function crearUsuario(payload: NuevoUsuario): Promise<Usuario> {
  return postJson("/usuarios", payload, authHeaders()) as Promise<Usuario>;
}

export function actualizarUsuario(
  id: string,
  cambios: CambiosUsuario,
): Promise<Usuario> {
  return patchJson(
    `/usuarios/${id}`,
    cambios,
    authHeaders(),
  ) as Promise<Usuario>;
}

export function reemplazarRoles(
  id: string,
  roles: string[],
): Promise<Usuario> {
  return putJson(
    `/usuarios/${id}/roles`,
    { roles },
    authHeaders(),
  ) as Promise<Usuario>;
}

export function cambiarPassword(
  id: string,
  password: string,
): Promise<Usuario> {
  return postJson(
    `/usuarios/${id}/password`,
    { password },
    authHeaders(),
  ) as Promise<Usuario>;
}

export function fetchRoles(): Promise<Rol[]> {
  return fetchJson("/roles", authHeaders()) as Promise<Rol[]>;
}
