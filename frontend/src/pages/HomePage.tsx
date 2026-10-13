import { ApiStatus } from "../features/status/ApiStatus";

/** Backoffice placeholder (agenda/administración llegan en C-07/C-08). */
export function HomePage(): React.JSX.Element {
  return (
    <main>
      <h1>Backoffice — Clínica Odontológica</h1>
      <p>Gestión interna: agenda, pacientes y caja (en construcción).</p>
      <ApiStatus />
    </main>
  );
}
