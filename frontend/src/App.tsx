import { HomePage } from "./pages/HomePage";
import { AgendaPage } from "./pages/AgendaPage";
import { GestionTurnoPage } from "./pages/GestionTurnoPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ReservaPage } from "./pages/ReservaPage";

const GESTION_PREFIX = "/reservar/gestion/";

/** Minimal pathname router (no business logic in the client, R-07). */
export function App(): React.JSX.Element {
  const pathname = window.location.pathname;
  if (pathname.startsWith(GESTION_PREFIX)) {
    return <GestionTurnoPage token={pathname.slice(GESTION_PREFIX.length)} />;
  }
  if (pathname === "/agenda") {
    return <AgendaPage />;
  }
  if (pathname === "/reservar") {
    return <ReservaPage />;
  }
  if (pathname === "/") {
    return <HomePage />;
  }
  return <NotFoundPage />;
}
