/**
 * Backoffice shell (design.md D5): topbar, protected rail, session and Salir.
 * Without a session it renders only the brand: no protected links are offered.
 */

import { useState } from "react";
import type { ReactNode } from "react";

import { logout, useSession } from "../../features/auth/session";
import { Link } from "../navigation";
import { Button } from "../ui/Button";
import { ContentWrapper, SkipLink } from "./SkipLink";

const MODULOS = [
  { href: "/agenda", label: "Agenda" },
  { href: "/reportes", label: "Reportes" },
  { href: "/usuarios", label: "Usuarios" },
  { href: "/auditoria", label: "Auditoría" },
] as const;

const NAV_ID = "backoffice-nav";

export interface BackofficeShellProps {
  children: ReactNode;
  pathname?: string;
}

export function BackofficeShell({
  children,
  pathname = window.location.pathname,
}: BackofficeShellProps): React.JSX.Element {
  const session = useSession();
  const [abierto, setAbierto] = useState(false);

  return (
    <>
      <SkipLink />
      <div
        className={`ds-shell ds-shell--backoffice${
          session === null ? " ds-shell--signed-out" : ""
        }`}
      >
        <header className="ds-topbar">
          <Link className="ds-brand" to="/">
            Clínica Odontológica
          </Link>
          {session === null ? null : (
            <Button
              variant="secondary"
              size="sm"
              className="ds-menu-button"
              aria-expanded={abierto}
              aria-controls={NAV_ID}
              onClick={() => setAbierto(!abierto)}
            >
              Menú
            </Button>
          )}
        </header>

        {session === null ? null : (
          <aside className={`ds-rail${abierto ? " ds-rail--open" : ""}`}>
            <nav
              id={NAV_ID}
              className="ds-rail__nav"
              aria-label="Navegación principal"
            >
              {MODULOS.map((modulo) => (
                <Link
                  key={modulo.href}
                  className="ds-rail__link"
                  to={modulo.href}
                  aria-current={pathname === modulo.href ? "page" : undefined}
                  onClick={() => setAbierto(false)}
                >
                  {modulo.label}
                </Link>
              ))}
            </nav>
            <div className="ds-rail__session">
              <p>{session.usuario.nombre}</p>
              <p>{session.usuario.email}</p>
              <Button variant="ghost" size="sm" onClick={logout}>
                Salir
              </Button>
            </div>
          </aside>
        )}

        <ContentWrapper>{children}</ContentWrapper>
      </div>
    </>
  );
}
