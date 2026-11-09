import { HomePage } from "./pages/HomePage";
import { AgendaPage } from "./pages/AgendaPage";
import { AuditoriaPage } from "./pages/AuditoriaPage";
import { GestionTurnoPage } from "./pages/GestionTurnoPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PrivacidadPage } from "./pages/PrivacidadPage";
import { ReportesPage } from "./pages/ReportesPage";
import { ReservaPage } from "./pages/ReservaPage";
import { UsuariosPage } from "./pages/UsuariosPage";

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
  if (pathname === "/reportes") {
    return <ReportesPage />;
  }
  if (pathname === "/usuarios") {
    return <UsuariosPage />;
  }
  if (pathname === "/auditoria") {
    return <AuditoriaPage />;
  }
  if (pathname === "/privacidad") {
    return <PrivacidadPage />;
  }
  if (pathname === "/reservar") {
    return <ReservaPage />;
  }
  if (pathname === "/") {
    return <HomePage />;
  }
  return <NotFoundPage />;
}
