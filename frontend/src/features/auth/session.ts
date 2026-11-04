/** In-memory backoffice session (R-03: never localStorage/cookies). */

import { useEffect, useState } from "react";

import { postJson } from "../../shared/api/client";

export interface UsuarioAuth {
  id: string;
  nombre: string;
  email: string;
  roles: string[];
}

export interface Session {
  token: string;
  usuario: UsuarioAuth;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  usuario: UsuarioAuth;
}

let current: Session | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) {
    listener();
  }
}

export function getSession(): Session | null {
  return current;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function authHeaders(): Record<string, string> {
  return current === null
    ? {}
    : { Authorization: `Bearer ${current.token}` };
}

export async function login(email: string, password: string): Promise<Session> {
  const response = (await postJson("/usuarios/login", {
    email,
    password,
  })) as LoginResponse;
  current = { token: response.access_token, usuario: response.usuario };
  emit();
  return current;
}

export function logout(): void {
  current = null;
  emit();
}

export function useSession(): Session | null {
  const [session, setSession] = useState<Session | null>(current);
  useEffect(() => subscribe(() => setSession(current)), []);
  return session;
}
