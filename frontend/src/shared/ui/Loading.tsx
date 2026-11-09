/** Presentational loading indicator: one polite status region. */

export interface LoadingProps {
  label?: string;
  className?: string;
}

export function Loading({
  label = "Cargando…",
  className,
}: LoadingProps): React.JSX.Element {
  return (
    <p
      role="status"
      aria-live="polite"
      className={["ds-loading", className]
        .filter((value): value is string => value !== undefined && value !== "")
        .join(" ")}
    >
      {label}
    </p>
  );
}
