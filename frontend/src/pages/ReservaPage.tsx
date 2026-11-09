/** Public booking page (C-07): catalogue, real slots and reservation form. */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import {
  fetchCatalogo,
  fetchDisponibilidad,
  crearReserva,
  type CatalogoPublico,
  type ReservaResponse,
  type SlotPublico,
} from "../features/reserva/api";

const FECHA_INICIAL = "2026-11-09";

export function ReservaPage(): React.JSX.Element {
  const [catalogo, setCatalogo] = useState<CatalogoPublico | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [profesionalId, setProfesionalId] = useState("");
  const [prestacionId, setPrestacionId] = useState("");
  const [fecha, setFecha] = useState(FECHA_INICIAL);
  const [slots, setSlots] = useState<SlotPublico[]>([]);
  const [inicio, setInicio] = useState("");
  const [nombre, setNombre] = useState("");
  const [apellido, setApellido] = useState("");
  const [dni, setDni] = useState("");
  const [telefono, setTelefono] = useState("");
  const [reserva, setReserva] = useState<ReservaResponse | null>(null);

  useEffect(() => {
    fetchCatalogo()
      .then(setCatalogo)
      .catch((failure: unknown) => setError(asMessage(failure)));
  }, []);

  useEffect(() => {
    if (profesionalId === "" || fecha === "") {
      setSlots([]);
      return;
    }
    fetchDisponibilidad(profesionalId, prestacionId || null, fecha)
      .then(setSlots)
      .catch((failure: unknown) => {
        setSlots([]);
        setError(asMessage(failure));
      });
  }, [profesionalId, prestacionId, fecha]);

  async function reservar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const creada = await crearReserva({
        nombre,
        apellido,
        dni,
        telefono,
        profesional_id: profesionalId,
        prestacion_id: prestacionId || null,
        inicio,
      });
      setReserva(creada);
    } catch (failure) {
      setError(asMessage(failure));
    }
  }

  if (catalogo === null) {
    return (
      <main>
        <h1>Reservar turno</h1>
        {error !== null ? <p role="alert">{error}</p> : <p>Cargando…</p>}
      </main>
    );
  }

  return (
    <main>
      <h1>Reservar turno en {catalogo.nombre}</h1>
      <p>{catalogo.politica_cancelacion}</p>
      <p>{catalogo.politica_sena}</p>
      <p>
        <a href="/privacidad">Política de privacidad</a>
      </p>

      <label>
        Profesional
        <select
          value={profesionalId}
          onChange={(event) => setProfesionalId(event.target.value)}
        >
          <option value="">Elegí un profesional</option>
          {catalogo.profesionales.map((profesional) => (
            <option key={profesional.id} value={profesional.id}>
              {profesional.matricula} ({profesional.especialidades.join(", ")})
            </option>
          ))}
        </select>
      </label>

      <label>
        Prestación
        <select
          value={prestacionId}
          onChange={(event) => setPrestacionId(event.target.value)}
        >
          <option value="">Sin prestación</option>
          {catalogo.prestaciones.map((prestacion) => (
            <option key={prestacion.id} value={prestacion.id}>
              {prestacion.nombre} ({prestacion.duracion_min} min)
            </option>
          ))}
        </select>
      </label>

      <label>
        Fecha
        <input
          type="date"
          value={fecha}
          onChange={(event) => setFecha(event.target.value)}
        />
      </label>

      <section aria-label="Horarios disponibles">
        <h2>Horarios</h2>
        {slots.length === 0 ? <p>No hay horarios disponibles.</p> : null}
        <ul>
          {slots.map((slot) => (
            <li key={slot.inicio}>
              <button
                type="button"
                aria-pressed={inicio === slot.inicio}
                onClick={() => setInicio(slot.inicio)}
              >
                {slot.inicio.slice(11, 16)}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <form onSubmit={reservar}>
        <label>
          Nombre
          <input
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
            required
          />
        </label>
        <label>
          Apellido
          <input
            value={apellido}
            onChange={(event) => setApellido(event.target.value)}
            required
          />
        </label>
        <label>
          DNI
          <input
            value={dni}
            onChange={(event) => setDni(event.target.value)}
            required
          />
        </label>
        <label>
          Teléfono WhatsApp
          <input
            value={telefono}
            onChange={(event) => setTelefono(event.target.value)}
            required
          />
        </label>
        <button type="submit" disabled={inicio === ""}>
          Reservar
        </button>
      </form>

      {error !== null ? <p role="alert">{error}</p> : null}

      {reserva !== null ? (
        <section aria-label="Reserva confirmada">
          <h2>Turno reservado</h2>
          <p>Estado: {reserva.estado}</p>
          <p>Seña: {reserva.sena.estado}</p>
          <a href={reserva.gestion_url}>Gestionar mi turno</a>
        </section>
      ) : null}
    </main>
  );
}

function asMessage(failure: unknown): string {
  return failure instanceof ApiError
    ? describeFailure(failure)
    : String(failure);
}
