/** Presentational error banner: server messages stay verbatim. */

import type { ReactNode } from "react";

export interface ErrorBannerProps {
  message: string;
  title?: string;
  action?: ReactNode;
  className?: string;
  id?: string;
}

export function ErrorBanner({
  message,
  title,
  action,
  className,
  id,
}: ErrorBannerProps): React.JSX.Element {
  return (
    <div
      id={id}
      role="alert"
      className={["ds-error-banner", className]
        .filter((value): value is string => value !== undefined && value !== "")
        .join(" ")}
    >
      {title === undefined ? null : (
        <p className="ds-error-banner__title">{title}</p>
      )}
      <p className="ds-error-banner__message">{message}</p>
      {action === undefined ? null : <div>{action}</div>}
    </div>
  );
}
