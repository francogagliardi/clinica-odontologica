import { ApiStatus } from "../features/status/ApiStatus";
import { Button } from "../shared/ui/Button";

/** Public landing: centered hero with the two entries and the status panel. */
export function HomePage(): React.JSX.Element {
  return (
    <main className="ds-home">
      <div className="ds-home__inner">
        <p className="ds-home__eyebrow">Turnos online</p>
        <h1>Clínica Odontológica</h1>
        <p className="ds-home__description">
          Reservá un turno como paciente o ingresá al backoffice del equipo.
        </p>
        <nav className="ds-home__actions" aria-label="Accesos de la portada">
          <Button href="/reservar">Reservar turno</Button>
          <Button href="/agenda" variant="secondary">
            Ingresar al backoffice
          </Button>
        </nav>
        <div className="ds-home__status">
          <ApiStatus />
        </div>
      </div>
    </main>
  );
}
