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
import { Button } from "../shared/ui/Button";
import { Link } from "../shared/navigation";
import { Card } from "../shared/ui/Card";
import { EmptyState } from "../shared/ui/EmptyState";
import { ErrorBanner } from "../shared/ui/ErrorBanner";
import { Input } from "../shared/ui/Input";
import { Loading } from "../shared/ui/Loading";
import { PageHeader } from "../shared/ui/PageHeader";
import { Select } from "../shared/ui/Select";

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
        <PageHeader title="Reservar turno" />
        {error !== null ? <ErrorBanner message={error} /> : <Loading />}
      </main>
    );
  }

  const hayProfesional = profesionalId !== "";

  return (
    <main>
      <PageHeader
        title={`Reservar turno en ${catalogo.nombre}`}
        description="Elegí profesional, prestación y fecha; después confirmá tus datos."
      />
      <div className="ds-prose">
        <p>{catalogo.politica_cancelacion}</p>
        <p>{catalogo.politica_sena}</p>
        <p>
          <Link to="/privacidad">Política de privacidad</Link>
        </p>
      </div>

      <section aria-label="Datos del turno" className="ds-booking-filters">
        <Select
          label="Profesional"
          value={profesionalId}
          onChange={(event) => {
            setProfesionalId(event.target.value);
            setInicio("");
          }}
        >
          <option value="">Elegí un profesional</option>
          {catalogo.profesionales.map((profesional) => (
            <option key={profesional.id} value={profesional.id}>
              {profesional.matricula} ({profesional.especialidades.join(", ")})
            </option>
          ))}
        </Select>

        <Select
          label="Prestación"
          value={prestacionId}
          onChange={(event) => setPrestacionId(event.target.value)}
        >
          <option value="">Sin prestación</option>
          {catalogo.prestaciones.map((prestacion) => (
            <option key={prestacion.id} value={prestacion.id}>
              {prestacion.nombre} ({prestacion.duracion_min} min)
            </option>
          ))}
        </Select>

        <Input
          label="Fecha"
          type="date"
          value={fecha}
          onChange={(event) => setFecha(event.target.value)}
        />
      </section>

      <section aria-label="Horarios disponibles">
        <h2>Horarios</h2>
        {!hayProfesional ? (
          <p>Elegí un profesional y una fecha para ver los horarios.</p>
        ) : null}
        {hayProfesional && slots.length === 0 ? (
          <EmptyState
            title="No hay horarios disponibles."
            description="Probá con otra fecha o elegí otro profesional."
          />
        ) : null}
        {slots.length > 0 ? (
          <ul className="ds-slot-grid" aria-label="Horarios disponibles">
            {slots.map((slot) => {
              const hora = slot.inicio.slice(11, 16);
              const elegido = inicio === slot.inicio;
              return (
                <li key={slot.inicio}>
                  <Button
                    variant={elegido ? "primary" : "secondary"}
                    size="sm"
                    aria-pressed={elegido}
                    onClick={() => setInicio(slot.inicio)}
                  >
                    {hora}
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : null}
      </section>

      <Card title="Tus datos" description="No pedimos aceptación de la política.">
        <form onSubmit={reservar} className="ds-form-grid">
          <Input
            label="Nombre"
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
            required
          />
          <Input
            label="Apellido"
            value={apellido}
            onChange={(event) => setApellido(event.target.value)}
            required
          />
          <Input
            label="DNI"
            value={dni}
            onChange={(event) => setDni(event.target.value)}
            required
          />
          <Input
            label="Teléfono WhatsApp"
            type="tel"
            value={telefono}
            onChange={(event) => setTelefono(event.target.value)}
            required
          />
          <Button
            type="submit"
            className="ds-form-grid__full"
            disabled={inicio === ""}
          >
            Reservar
          </Button>
        </form>
      </Card>

      {error !== null ? <ErrorBanner message={error} /> : null}

      {reserva !== null ? (
        <Card title="Turno reservado">
          <p>Estado: {reserva.estado}</p>
          <p>Seña: {reserva.sena.estado}</p>
          <p>
            <a href={reserva.gestion_url}>Gestionar mi turno</a>
          </p>
        </Card>
      ) : null}
    </main>
  );
}

function asMessage(failure: unknown): string {
  return failure instanceof ApiError
    ? describeFailure(failure)
    : String(failure);
}
