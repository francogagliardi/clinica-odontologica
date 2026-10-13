import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ReservaPage } from "./pages/ReservaPage";

/** Minimal pathname router (no business logic in the client, R-07). */
export function App(): React.JSX.Element {
  const pathname = window.location.pathname;
  if (pathname === "/reservar") {
    return <ReservaPage />;
  }
  if (pathname === "/") {
    return <HomePage />;
  }
  return <NotFoundPage />;
}
