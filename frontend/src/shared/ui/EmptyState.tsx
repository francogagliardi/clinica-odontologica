/** Presentational empty state: title, explanation and optional action. */

import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  action,
  className,
}: EmptyStateProps): React.JSX.Element {
  return (
    <div
      className={["ds-empty", className]
        .filter((value): value is string => value !== undefined && value !== "")
        .join(" ")}
    >
      <h2 className="ds-empty__title">{title}</h2>
      <p className="ds-empty__description">{description}</p>
      {action === undefined ? null : (
        <div className="ds-empty__action">{action}</div>
      )}
    </div>
  );
}
