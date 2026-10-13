/** Fallback for unknown routes: 404 without breaking the SPA. */
export function NotFoundPage(): React.JSX.Element {
  return (
    <main>
      <h1>Página no encontrada</h1>
      <p>404 — la ruta solicitada no existe.</p>
    </main>
  );
}
