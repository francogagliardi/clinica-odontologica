/** Backoffice agenda: day/week/month views with drag & drop reprogramming. */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import { LoginForm } from "../features/auth/LoginForm";
import { useSession } from "../features/auth/session";
import {
  fetchBloqueos,
  fetchProfesionales,
  fetchSillones,
  fetchTurnos,
  reprogramarTurno,
  type Bloqueo,
  type Profesional,
  type Sillon,
  type Turno,
} from "../features/agenda/api";
import { AgendaDay } from "../features/agenda/AgendaDay";
import { AgendaMonth } from "../features/agenda/AgendaMonth";
import { AgendaWeek } from "../features/agenda/AgendaWeek";
import {
  hoyISO,
  mover,
  rango,
  type Vista,
} from "../features/agenda/calendar";
import { puedeReprogramar } from "../features/agenda/permissions";
import { Button } from "../shared/ui/Button";
import { EmptyState } from "../shared/ui/EmptyState";
import { ErrorBanner } from "../shared/ui/ErrorBanner";
import { Input } from "../shared/ui/Input";
import { Loading } from "../shared/ui/Loading";
import { PageHeader } from "../shared/ui/PageHeader";
import { Select } from "../shared/ui/Select";

export function AgendaPage(): React.JSX.Element {
  const session = useSession();
  const [vista, setVista] = useState<Vista>("dia");
  const [fecha, setFecha] = useState(hoyISO());
  const [profesionalId, setProfesionalId] = useState("");
  const [sillonId, setSillonId] = useState("");
  const [profesionales, setProfesionales] = useState<Profesional[]>([]);
  const [sillones, setSillones] = useState<Sillon[]>([]);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [bloqueos, setBloqueos] = useState<Bloqueo[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { desde, hasta } = rango(vista, fecha);

  useEffect(() => {
    if (session === null) {
      return;
    }
    Promise.all([fetchProfesionales(), fetchSillones()])
      .then(([listaProfesionales, listaSillones]) => {
        setProfesionales(listaProfesionales);
        setSillones(listaSillones);
      })
      .catch((failure: unknown) => setError(asMessage(failure)));
  }, [session]);

  useEffect(() => {
    if (session === null) {
      return;
    }
    setCargando(true);
    setError(null);
    Promise.all([
      fetchTurnos(desde, hasta, profesionalId || null, sillonId || null),
      fetchBloqueos(desde, hasta),
    ])
      .then(([listaTurnos, listaBloqueos]) => {
        setTurnos(listaTurnos);
        setBloqueos(listaBloqueos);
      })
      .catch((failure: unknown) => {
        setTurnos([]);
        setBloqueos([]);
        setError(asMessage(failure));
      })
      .finally(() => setCargando(false));
  }, [session, desde, hasta, profesionalId, sillonId]);

  if (session === null) {
    return <LoginForm />;
  }

  const bloqueosVisibles = bloqueos.filter((bloqueo) => {
    if (profesionalId !== "" && bloqueo.profesional_id === profesionalId) {
      return true;
    }
    if (sillonId !== "" && bloqueo.sillon_id === sillonId) {
      return true;
    }
    return profesionalId === "" && sillonId === "";
  });

  const esReprogramable = (turno: Turno): boolean =>
    puedeReprogramar(turno, session, profesionales);

  async function reprogramar(turno: Turno, inicio: string): Promise<void> {
    setError(null);
    try {
      await reprogramarTurno(turno.id, inicio);
      const [listaTurnos, listaBloqueos] = await Promise.all([
        fetchTurnos(desde, hasta, profesionalId || null, sillonId || null),
        fetchBloqueos(desde, hasta),
      ]);
      setTurnos(listaTurnos);
      setBloqueos(listaBloqueos);
    } catch (failure) {
      setError(asMessage(failure));
    }
  }

  return (
    <main>
      <PageHeader
        title="Agenda"
        description="Turnos y bloqueos por profesional y sillón."
      />

      <div className="agenda-toolbar" role="group" aria-label="Filtros de agenda">
        <Select
          label="Vista"
          value={vista}
          onChange={(event) => setVista(event.target.value as Vista)}
        >
          <option value="dia">Día</option>
          <option value="semana">Semana</option>
          <option value="mes">Mes</option>
        </Select>
        <Input
          label="Fecha"
          type="date"
          value={fecha}
          onChange={(event) => setFecha(event.target.value)}
        />
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setFecha(mover(vista, fecha, -1))}
        >
          Anterior
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setFecha(mover(vista, fecha, 1))}
        >
          Siguiente
        </Button>
        <Select
          label="Profesional"
          value={profesionalId}
          onChange={(event) => setProfesionalId(event.target.value)}
        >
          <option value="">Todos</option>
          {profesionales.map((profesional) => (
            <option key={profesional.id} value={profesional.id}>
              {profesional.matricula}
            </option>
          ))}
        </Select>
        <Select
          label="Sillón"
          value={sillonId}
          onChange={(event) => setSillonId(event.target.value)}
        >
          <option value="">Todos</option>
          {sillones.map((sillon) => (
            <option key={sillon.id} value={sillon.id}>
              {sillon.nombre}
            </option>
          ))}
        </Select>
      </div>

      {error !== null ? <ErrorBanner message={error} /> : null}
      {cargando ? <Loading /> : null}
      {!cargando && turnos.length === 0 && error === null ? (
        <EmptyState
          title="Sin turnos para este rango."
          description="Probá con otra fecha, profesional o sillón."
        />
      ) : null}

      <div
        className="agenda-scroll"
        role="region"
        aria-label="Grilla de agenda"
        tabIndex={0}
      >
        {vista === "dia" ? (
          <AgendaDay
            fecha={fecha}
            turnos={turnos}
            bloqueos={bloqueosVisibles}
            esReprogramable={esReprogramable}
            onDragStart={() => undefined}
            onDrop={(turno, inicio) => void reprogramar(turno, inicio)}
          />
        ) : null}
        {vista === "semana" ? (
          <AgendaWeek
            desde={desde}
            hasta={hasta}
            turnos={turnos}
            bloqueos={bloqueosVisibles}
            esReprogramable={esReprogramable}
            onDragStart={() => undefined}
            onDrop={(turno, inicio) => void reprogramar(turno, inicio)}
          />
        ) : null}
        {vista === "mes" ? (
          <AgendaMonth
            desde={desde}
            hasta={hasta}
            turnos={turnos}
            esReprogramable={esReprogramable}
            onDragStart={() => undefined}
            onDrop={(turno, inicio) => void reprogramar(turno, inicio)}
          />
        ) : null}
      </div>
    </main>
  );
}

function asMessage(failure: unknown): string {
  return failure instanceof ApiError
    ? describeFailure(failure)
    : String(failure);
}
