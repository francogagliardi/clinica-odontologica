/** Presentational pill badge: tone is visual only, text stays verbatim. */

import type { ReactNode } from "react";

export type BadgeTone =
  | "neutral"
  | "primary"
  | "success"
  | "warning"
  | "danger"
  | "info";

export interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
}

export function Badge({
  tone = "neutral",
  children,
  className,
}: BadgeProps): React.JSX.Element {
  return (
    <span
      className={["ds-badge", `ds-badge--${tone}`, className]
        .filter((value): value is string => value !== undefined && value !== "")
        .join(" ")}
    >
      {children}
    </span>
  );
}
