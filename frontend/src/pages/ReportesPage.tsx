/** Functional reports page: four boards, filters and patient/clinic export. */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import { LoginForm } from "../features/auth/LoginForm";
import { logout, useSession } from "../features/auth/session";
import {
  crearExportacion,
  descargarExportacion,
  fetchAgenda,
  fetchAusentismo,
  fetchCaja,
  fetchExportacion,
  fetchLiquidaciones,
  type Exportacion,
  type Fila,
  type ReporteAgenda,
  type ReporteAusentismo,
  type ReporteCaja,
  type ReporteLiquidaciones,
} from "../features/reportes/api";
import { hoyISO } from "../features/agenda/calendar";

interface Reportes {
  agenda: ReporteAgenda;
  ausentismo: ReporteAusentismo;
  caja: ReporteCaja;
  liquidaciones: ReporteLiquidaciones;
}

function asMessage(failure: unknown): string {
  return failure instanceof ApiError
    ? describeFailure(failure)
    : String(failure);
}

function TablaDetalle({ filas }: { filas: Fila[] }): React.JSX.Element {
  if (filas.length === 0) {
    return <p>Sin detalle para el rango.</p>;
  }
  const columnas = Array.from(
    new Set(filas.flatMap((fila) => Object.keys(fila))),
  );
  return (
    <table>
      <thead>
        <tr>
          {columnas.map((columna) => (
            <th key={columna}>{columna}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {filas.map((fila, indice) => (
          <tr key={String(fila.turno_id ?? fila.cobro_id ?? fila.liquidacion_id ?? indice)}>
            {columnas.map((columna) => (
              <td key={columna}>{String(fila[columna] ?? "")}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ReportesPage(): React.JSX.Element {
  const session = useSession();
  const [desde, setDesde] = useState(hoyISO());
  const [hasta, setHasta] = useState(hoyISO());
  const [limite, setLimite] = useState(500);
  const [profesionalId, setProfesionalId] = useState("");
  const [reportes, setReportes] = useState<Reportes | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pacienteId, setPacienteId] = useState("");
  const [exportacion, setExportacion] = useState<Exportacion | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (session === null) {
      return;
    }
    let activo = true;
    setCargando(true);
    setError(null);
    const filtros = {
      desde,
      hasta,
      limite,
      profesionalId: profesionalId === "" ? null : profesionalId,
    };
    Promise.all([
      fetchAgenda(filtros),
      fetchAusentismo(filtros),
      fetchCaja(filtros),
      fetchLiquidaciones(filtros),
    ])
      .then(([agenda, ausentismo, caja, liquidaciones]) => {
        if (activo) {
          setReportes({ agenda, ausentismo, caja, liquidaciones });
        }
      })
      .catch((failure: unknown) => {
        if (activo) {
          setError(asMessage(failure));
        }
      })
      .finally(() => {
        if (activo) {
          setCargando(false);
        }
      });
    return () => {
      activo = false;
    };
  }, [session, desde, hasta, limite, profesionalId]);

  useEffect(() => {
    if (
      exportacion === null ||
      (exportacion.estado !== "pendiente" &&
        exportacion.estado !== "generando")
    ) {
      return;
    }
    const id = exportacion.id;
    const timer = window.setInterval(() => {
      void fetchExportacion(id)
        .then((actual) => setExportacion(actual))
        .catch((failure: unknown) => setExportError(asMessage(failure)));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [exportacion]);

  if (session === null) {
    return <LoginForm />;
  }

  const esAdmin = session.usuario.roles.includes("administrador");

  async function exportar(alcance: "paciente" | "consultorio"): Promise<void> {
    setExportError(null);
    try {
      const creada = await crearExportacion(
        alcance,
        pacienteId === "" ? null : pacienteId,
      );
      setExportacion(creada);
    } catch (failure) {
      setExportError(asMessage(failure));
    }
  }

  async function descargar(): Promise<void> {
    if (exportacion === null) {
      return;
    }
    setExportError(null);
    try {
      const blob = await descargarExportacion(exportacion.id);
      const enlace = document.createElement("a");
      const url = URL.createObjectURL(blob);
      enlace.href = url;
      enlace.download = `exportacion-${exportacion.id}.zip`;
      enlace.click();
      URL.revokeObjectURL(url);
    } catch (failure) {
      setExportError(asMessage(failure));
    }
  }

  return (
    <main>
      <h1>Reportes</h1>
      <button type="button" onClick={logout}>
        Salir
      </button>

      <div className="reportes-filtros">
        <label>
          Desde
          <input
            type="date"
            value={desde}
            onChange={(event) => setDesde(event.target.value)}
          />
        </label>
        <label>
          Hasta
          <input
            type="date"
            value={hasta}
            onChange={(event) => setHasta(event.target.value)}
          />
        </label>
        <label>
          Límite
          <select
            value={limite}
            onChange={(event) => setLimite(Number(event.target.value))}
          >
            <option value={100}>100</option>
            <option value={500}>500</option>
            <option value={1000}>1000</option>
          </select>
        </label>
        <label>
          Profesional (id, opcional)
          <input
            value={profesionalId}
            onChange={(event) => setProfesionalId(event.target.value)}
          />
        </label>
      </div>

      {error !== null ? <p role="alert">{error}</p> : null}
      {cargando ? <p>Cargando…</p> : null}

      {reportes !== null ? (
        <>
          <section aria-label="Agenda">
            <h2>Agenda</h2>
            <p>Turnos totales: {reportes.agenda.total_turnos}</p>
            <p>Cancelaciones: {reportes.agenda.cancelaciones}</p>
            <p>
              Ocupación: {reportes.agenda.ocupacion_porcentaje} % (
              {reportes.agenda.minutos_ocupados}/{""}
              {reportes.agenda.minutos_disponibles} min)
            </p>
            <p>
              Detalle: {reportes.agenda.total_detalle}
              {reportes.agenda.detalle_truncado ? " (truncado)" : ""}
            </p>
            <TablaDetalle filas={reportes.agenda.detalle} />
          </section>

          <section aria-label="Ausentismo">
            <h2>Ausentismo</h2>
            <p>Atendidos: {reportes.ausentismo.atendidos}</p>
            <p>Cancelados: {reportes.ausentismo.cancelados}</p>
            <p>Ausentes: {reportes.ausentismo.ausentes}</p>
            <p>Tasa de ausentismo: {reportes.ausentismo.tasa_ausentismo}</p>
            <p>
              Tasa de no asistencia:{" "}
              {reportes.ausentismo.tasa_no_asistencia}
            </p>
            <TablaDetalle filas={reportes.ausentismo.detalle} />
          </section>

          <section aria-label="Caja">
            <h2>Caja</h2>
            <p>Total aprobado: {reportes.caja.total_aprobado}</p>
            <p>Efectivo: {reportes.caja.total_efectivo}</p>
            <p>Mercado Pago: {reportes.caja.total_mercadopago}</p>
            <p>Gastos: {reportes.caja.total_gastos}</p>
            <p>Deudas: {reportes.caja.total_deudas}</p>
            <h3>Cajas</h3>
            <TablaDetalle filas={reportes.caja.cajas} />
            <h3>Movimientos</h3>
            <TablaDetalle filas={reportes.caja.movimientos} />
            <TablaDetalle filas={reportes.caja.detalle} />
          </section>

          <section aria-label="Liquidaciones">
            <h2>Liquidaciones</h2>
            <p>
              Liquidaciones: {reportes.liquidaciones.cantidad_liquidaciones}
            </p>
            <p>Cobertura: {reportes.liquidaciones.total_cobertura}</p>
            <p>Prácticas: {reportes.liquidaciones.cantidad_practicas}</p>
            <h3>Por prestación</h3>
            <TablaDetalle filas={reportes.liquidaciones.por_prestacion} />
            <TablaDetalle filas={reportes.liquidaciones.detalle} />
          </section>
        </>
      ) : null}

      <section aria-label="Exportar">
        <h2>Exportar datos</h2>
        <label>
          Paciente (id)
          <input
            value={pacienteId}
            onChange={(event) => setPacienteId(event.target.value)}
          />
        </label>
        <button
          type="button"
          onClick={() => void exportar("paciente")}
          disabled={pacienteId === ""}
        >
          Exportar paciente
        </button>
        {esAdmin ? (
          <button type="button" onClick={() => void exportar("consultorio")}>
            Exportar consultorio
          </button>
        ) : null}
        {exportError !== null ? <p role="alert">{exportError}</p> : null}
        {exportacion !== null ? (
          <div>
            <p>Estado: {exportacion.estado}</p>
            {exportacion.ultimo_error !== null ? (
              <p role="alert">{exportacion.ultimo_error}</p>
            ) : null}
            <button
              type="button"
              onClick={() => void descargar()}
              disabled={exportacion.estado !== "lista"}
            >
              Descargar ZIP
            </button>
          </div>
        ) : null}
      </section>
    </main>
  );
}
