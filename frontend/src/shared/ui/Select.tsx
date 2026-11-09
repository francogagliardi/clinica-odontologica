/** Presentational select: same labelling rules as Input. */

import { useId } from "react";

export interface SelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  label: string;
  hint?: string;
  error?: string;
  id?: string;
}

export function Select({
  label,
  hint,
  error,
  id,
  className,
  "aria-invalid": ariaInvalid,
  "aria-describedby": describedByProp,
  children,
  ...control
}: SelectProps): React.JSX.Element {
  const generated = useId();
  const controlId = id ?? `ds-select-${generated}`;
  const hintId = hint === undefined ? undefined : `${controlId}-hint`;
  const errorId = error === undefined ? undefined : `${controlId}-error`;
  const describedBy = [describedByProp, hintId, errorId]
    .filter((value): value is string => value !== undefined && value !== "")
    .join(" ");

  return (
    <div
      className={["ds-field", className]
        .filter((value): value is string => value !== undefined && value !== "")
        .join(" ")}
    >
      <label className="ds-field__label" htmlFor={controlId}>
        {label}
      </label>
      <select
        {...control}
        id={controlId}
        className="ds-field__control"
        aria-invalid={error === undefined ? ariaInvalid : true}
        aria-describedby={describedBy === "" ? undefined : describedBy}
      >
        {children}
      </select>
      {hint === undefined ? null : (
        <p id={hintId} className="ds-field__hint">
          {hint}
        </p>
      )}
      {error === undefined ? null : (
        <p id={errorId} className="ds-field__error">
          {error}
        </p>
      )}
    </div>
  );
}
