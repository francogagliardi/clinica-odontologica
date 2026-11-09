import { Button } from "../shared/ui/Button";
import { PageHeader } from "../shared/ui/PageHeader";

/** Fallback for unknown routes: public 404 without protected navigation. */
export function NotFoundPage(): React.JSX.Element {
  return (
    <main>
      <PageHeader
        title="Página no encontrada"
        description="404 — la ruta solicitada no existe."
      />
      <p>
        <Button href="/reservar" variant="secondary">
          Reservar un turno
        </Button>
      </p>
    </main>
  );
}
