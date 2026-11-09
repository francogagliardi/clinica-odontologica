import { usePathname } from "./shared/navigation";
import { BackofficeShell } from "./shared/layout/BackofficeShell";
import { PublicShell } from "./shared/layout/PublicShell";
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

const BACKOFFICE_PATHS: ReadonlySet<string> = new Set([
  "/agenda",
  "/reportes",
  "/usuarios",
  "/auditoria",
]);

/**
 * Minimal pathname router (no business logic in the client, R-07).
 * The shell is chosen here; every page keeps rendering its own <main>.
 */
export function App(): React.JSX.Element {
  const pathname = usePathname();
  const page = renderPage(pathname);

  if (BACKOFFICE_PATHS.has(pathname)) {
    return (
      <BackofficeShell pathname={pathname}>{page}</BackofficeShell>
    );
  }
  return <PublicShell pathname={pathname}>{page}</PublicShell>;
}

function renderPage(pathname: string): React.JSX.Element {
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
