/** Presentational button: anchor when `href` is given, native button otherwise. */

import type { ReactNode } from "react";

import { Link } from "../navigation";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

interface ButtonBaseProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  children: ReactNode;
  onClick?: () => void;
  "aria-label"?: string;
  "aria-expanded"?: boolean;
  "aria-controls"?: string;
  "aria-pressed"?: boolean;
  "aria-current"?:
    | "page"
    | "step"
    | "location"
    | "date"
    | "time"
    | true
    | false;
}

export type ButtonProps =
  | (ButtonBaseProps & { href: string; disabled?: never; type?: never })
  | (ButtonBaseProps & {
      href?: undefined;
      disabled?: boolean;
      type?: "button" | "submit" | "reset";
    });

export function Button(props: ButtonProps): React.JSX.Element {
  const classes = [
    "ds-button",
    `ds-button--${props.variant ?? "primary"}`,
    `ds-button--${props.size ?? "md"}`,
    props.className,
  ]
    .filter((value): value is string => value !== undefined && value !== "")
    .join(" ");

  const aria = {
    "aria-label": props["aria-label"],
    "aria-expanded": props["aria-expanded"],
    "aria-controls": props["aria-controls"],
    "aria-pressed": props["aria-pressed"],
    "aria-current": props["aria-current"],
  };

  if (props.href !== undefined) {
    return (
      <Link
        className={classes}
        to={props.href}
        onClick={props.onClick}
        {...aria}
      >
        {props.children}
      </Link>
    );
  }

  return (
    <button
      className={classes}
      type={props.type ?? "button"}
      disabled={props.disabled}
      onClick={props.onClick}
      {...aria}
    >
      {props.children}
    </button>
  );
}
