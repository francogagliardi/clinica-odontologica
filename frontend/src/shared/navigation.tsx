/**
 * Minimal client-side navigation for the SPA (no router, no persistence).
 *
 * `navigate` pushes the pathname and emits a custom event; `usePathname` listens
 * to that event and to `popstate` so back/forward work. `Link` keeps a real
 * `href` for accessibility/SEO and only intercepts plain left clicks on internal
 * paths, so modified clicks and new-tab links behave natively.
 */

import { useEffect, useState } from "react";
import type { AnchorHTMLAttributes, MouseEvent } from "react";

export const NAVIGATE_EVENT = "app:navigate";

interface NavigationState {
  appIndex?: number;
}

function currentAppIndex(): number {
  const state = window.history.state as NavigationState | null;
  const index = state?.appIndex;
  return typeof index === "number" && Number.isFinite(index) ? index : 0;
}

export function navigate(to: string): void {
  if (to === window.location.pathname) {
    return;
  }
  window.history.pushState({ appIndex: currentAppIndex() + 1 }, "", to);
  window.dispatchEvent(new Event(NAVIGATE_EVENT));
}

export function goBack(fallback = "/"): void {
  if (currentAppIndex() > 0) {
    window.history.back();
  } else {
    navigate(fallback);
  }
}

export function usePathname(): string {
  const [pathname, setPathname] = useState(() => window.location.pathname);

  useEffect(() => {
    const sync = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", sync);
    window.addEventListener(NAVIGATE_EVENT, sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener(NAVIGATE_EVENT, sync);
    };
  }, []);

  return pathname;
}

export function isInternalPath(to: string): boolean {
  return to.startsWith("/") && !to.startsWith("//");
}

export interface LinkProps
  extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  to: string;
}

export function Link({
  to,
  onClick,
  target,
  children,
  ...rest
}: LinkProps): React.JSX.Element {
  function handleClick(event: MouseEvent<HTMLAnchorElement>): void {
    onClick?.(event);
    if (event.defaultPrevented) {
      return;
    }
    if (event.button !== 0) {
      return;
    }
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    if (target !== undefined && target !== "" && target !== "_self") {
      return;
    }
    if (!isInternalPath(to)) {
      return;
    }
    event.preventDefault();
    navigate(to);
  }

  return (
    <a {...rest} href={to} target={target} onClick={handleClick}>
      {children}
    </a>
  );
}

export const AppLink = Link;
