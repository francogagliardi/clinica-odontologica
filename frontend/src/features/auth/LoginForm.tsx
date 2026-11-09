/** Backoffice login form: token stays in memory (R-03). */

import { useId, useState } from "react";

import { ApiError, describeFailure } from "../../shared/api/client";
import { Button } from "../../shared/ui/Button";
import { Card } from "../../shared/ui/Card";
import { ErrorBanner } from "../../shared/ui/ErrorBanner";
import { Input } from "../../shared/ui/Input";
import { PageHeader } from "../../shared/ui/PageHeader";
import { login } from "./session";

export function LoginForm(): React.JSX.Element {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const errorId = useId();

  async function enviar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await login(email, password);
    } catch (failure) {
      setError(
        failure instanceof ApiError ? describeFailure(failure) : String(failure),
      );
    }
  }

  return (
    <main className="ds-auth">
      <div className="ds-auth__panel">
        <PageHeader
          title="Backoffice"
          description="Ingresá con tu cuenta del consultorio."
        />
        <Card title="Acceso del equipo">
          <form onSubmit={enviar} className="ds-auth__form">
            <Input
              label="Email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              aria-invalid={error === null ? undefined : true}
              aria-describedby={error === null ? undefined : errorId}
            />
            <Input
              label="Contraseña"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              aria-invalid={error === null ? undefined : true}
              aria-describedby={error === null ? undefined : errorId}
            />
            <Button type="submit">Ingresar</Button>
          </form>
          {error !== null ? (
            <ErrorBanner id={errorId} message={error} />
          ) : null}
        </Card>
      </div>
    </main>
  );
}
