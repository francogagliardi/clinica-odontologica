/** Skip link and the `#contenido` wrapper shared by both shells (D8). */

import type { ReactNode } from "react";

export function SkipLink(): React.JSX.Element {
  return (
    <a className="ds-skip" href="#contenido">
      Saltar al contenido
    </a>
  );
}

export interface ContentWrapperProps {
  children: ReactNode;
}

export function ContentWrapper({
  children,
}: ContentWrapperProps): React.JSX.Element {
  return (
    <div id="contenido" className="ds-content" tabIndex={-1}>
      {children}
    </div>
  );
}
