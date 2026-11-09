/** Presentational page header: exactly one h1 plus optional actions. */

import type { ReactNode } from "react";

export interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  eyebrow?: string;
  className?: string;
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
  className,
}: PageHeaderProps): React.JSX.Element {
  return (
    <header
      className={["ds-page-header", className]
        .filter((value): value is string => value !== undefined && value !== "")
        .join(" ")}
    >
      {eyebrow === undefined ? null : (
        <p className="ds-page-header__eyebrow">{eyebrow}</p>
      )}
      <div className="ds-page-header__row">
        <div>
          <h1>{title}</h1>
          {description === undefined ? null : (
            <p className="ds-page-header__description">{description}</p>
          )}
        </div>
        {actions === undefined ? null : (
          <div className="ds-page-header__actions">{actions}</div>
        )}
      </div>
    </header>
  );
}
