/** Presentational table wrapper: scrollable, named and keyboard reachable. */

import type { ReactNode } from "react";

export interface TableProps {
  label: string;
  children: ReactNode;
  className?: string;
}

export function Table({
  label,
  children,
  className,
}: TableProps): React.JSX.Element {
  return (
    <div
      className={["ds-table-scroll", className]
        .filter((value): value is string => value !== undefined && value !== "")
        .join(" ")}
      role="region"
      aria-label={label}
      tabIndex={0}
    >
      <table className="ds-table">{children}</table>
    </div>
  );
}
