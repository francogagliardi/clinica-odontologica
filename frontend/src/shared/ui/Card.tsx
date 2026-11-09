/** Presentational card: bordered surface, no shadow, one optional heading. */

import { createElement, useId } from "react";
import type { ReactNode } from "react";

export type CardHeadingLevel = 2 | 3 | 4;

export interface CardProps {
  title?: string;
  description?: string;
  actions?: ReactNode;
  headingLevel?: CardHeadingLevel;
  children?: ReactNode;
  className?: string;
}

export function Card({
  title,
  description,
  actions,
  headingLevel = 2,
  children,
  className,
}: CardProps): React.JSX.Element {
  const titleId = useId();
  const hasHeader =
    title !== undefined || description !== undefined || actions !== undefined;

  return (
    <section
      className={["ds-card", className]
        .filter((value): value is string => value !== undefined && value !== "")
        .join(" ")}
      aria-labelledby={title === undefined ? undefined : titleId}
    >
      {hasHeader ? (
        <header className="ds-card__header">
          <div>
            {title === undefined
              ? null
              : createElement(
                  `h${headingLevel}`,
                  { id: titleId, className: "ds-card__title" },
                  title,
                )}
            {description === undefined ? null : (
              <p className="ds-card__description">{description}</p>
            )}
          </div>
          {actions === undefined ? null : (
            <div className="ds-card__actions">{actions}</div>
          )}
        </header>
      ) : null}
      {children === undefined ? null : (
        <div className="ds-card__body">{children}</div>
      )}
    </section>
  );
}
