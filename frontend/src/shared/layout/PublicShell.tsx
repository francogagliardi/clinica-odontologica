/**
 * Public shell (design.md D5): sober brand header with public links only.
 * It never reads the session nor renders user data.
 */

import type { ReactNode } from "react";

import { Link } from "../navigation";
import { ContentWrapper, SkipLink } from "./SkipLink";

const RESERVAR = { href: "/reservar", label: "Reservar" } as const;
const INGRESAR = { href: "/agenda", label: "Ingresar" } as const;
const PRIVACIDAD = { href: "/privacidad", label: "Privacidad" } as const;

export interface PublicShellProps {
  children: ReactNode;
  pathname?: string;
}

export function PublicShell({
  children,
  pathname = window.location.pathname,
}: PublicShellProps): React.JSX.Element {
  const enlaces =
    pathname === "/"
      ? [RESERVAR, INGRESAR, PRIVACIDAD]
      : [RESERVAR, PRIVACIDAD];

  return (
    <>
      <SkipLink />
      <div className="ds-shell ds-shell--public">
        <header className="ds-public-header">
          <div className="ds-public-header__inner">
            <Link className="ds-brand" to="/">
              Clínica Odontológica
            </Link>
            <nav className="ds-public-nav" aria-label="Navegación pública">
              {enlaces.map((enlace) => (
                <Link key={enlace.href} to={enlace.href}>
                  {enlace.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <ContentWrapper>{children}</ContentWrapper>
      </div>
    </>
  );
}
