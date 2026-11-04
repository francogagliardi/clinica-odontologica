/** Backoffice login form: token stays in memory (R-03). */

import { useState } from "react";

import { ApiError, describeFailure } from "../../shared/api/client";
import { login } from "./session";

export function LoginForm(): React.JSX.Element {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

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
    <main>
      <h1>Backoffice</h1>
      <form onSubmit={enviar}>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <button type="submit">Ingresar</button>
      </form>
      {error !== null ? <p role="alert">{error}</p> : null}
    </main>
  );
}
