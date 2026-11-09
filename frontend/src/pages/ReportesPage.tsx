/** Functional reports page: four boards, filters and patient/clinic export. */

import { useEffect, useState } from "react";

import { ApiError, describeFailure } from "../shared/api/client";
import { LoginForm } from "../features/auth/LoginForm";
import { useSession } from "../features/auth/session";
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
import { Button } from "../shared/ui/Button";
import { Card } from "../shared/ui/Card";
import { ErrorBanner } from "../shared/ui/ErrorBanner";
import { Input } from "../shared/ui/Input";
import { Loading } from "../shared/ui/Loading";
import { PageHeader } from "../shared/ui/PageHeader";
import { Select } from "../shared/ui/Select";
import { Table } from "../shared/ui/Table";

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

function TablaDetalle({
  filas,
  label,
}: {
  filas: Fila[];
  label: string;
}): React.JSX.Element {
  if (filas.length === 0) {
    return <p>Sin detalle para el rango.</p>;
  }
  const columnas = Array.from(
    new Set(filas.flatMap((fila) => Object.keys(fila))),
  );
  return (
    <Table label={label}>
      <thead>
        <tr>
          {columnas.map((columna) => (
            <th key={columna} scope="col">
              {columna}
            </th>
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
    </Table>
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
  const enCurso =
    exportacion !== null &&
    (exportacion.estado === "pendiente" || exportacion.estado === "generando");

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
      <PageHeader
        title="Reportes"
        description="Cuatro tableros de solo lectura con exportación de datos."
      />

      <div
        className="reportes-filtros"
        role="group"
        aria-label="Filtros de reportes"
      >
        <Input
          label="Desde"
          type="date"
          value={desde}
          onChange={(event) => setDesde(event.target.value)}
        />
        <Input
          label="Hasta"
          type="date"
          value={hasta}
          onChange={(event) => setHasta(event.target.value)}
        />
        <Select
          label="Límite"
          value={limite}
          onChange={(event) => setLimite(Number(event.target.value))}
        >
          <option value={100}>100</option>
          <option value={500}>500</option>
          <option value={1000}>1000</option>
        </Select>
        <Input
          label="Profesional (id, opcional)"
          value={profesionalId}
          onChange={(event) => setProfesionalId(event.target.value)}
        />
      </div>

      {error !== null ? <ErrorBanner message={error} /> : null}
      {cargando ? <Loading /> : null}

      {reportes !== null ? (
        <>
          <Card title="Agenda">
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
            <TablaDetalle
              filas={reportes.agenda.detalle}
              label="Detalle de agenda"
            />
          </Card>

          <Card title="Ausentismo">
            <p>Atendidos: {reportes.ausentismo.atendidos}</p>
            <p>Cancelados: {reportes.ausentismo.cancelados}</p>
            <p>Ausentes: {reportes.ausentismo.ausentes}</p>
            <p>Tasa de ausentismo: {reportes.ausentismo.tasa_ausentismo}</p>
            <p>
              Tasa de no asistencia:{" "}
              {reportes.ausentismo.tasa_no_asistencia}
            </p>
            <TablaDetalle
              filas={reportes.ausentismo.detalle}
              label="Detalle de ausentismo"
            />
          </Card>

          <Card title="Caja">
            <p>Total aprobado: {reportes.caja.total_aprobado}</p>
            <p>Efectivo: {reportes.caja.total_efectivo}</p>
            <p>Mercado Pago: {reportes.caja.total_mercadopago}</p>
            <p>Gastos: {reportes.caja.total_gastos}</p>
            <p>Deudas: {reportes.caja.total_deudas}</p>
            <h3>Cajas</h3>
            <TablaDetalle filas={reportes.caja.cajas} label="Cajas" />
            <h3>Movimientos</h3>
            <TablaDetalle
              filas={reportes.caja.movimientos}
              label="Movimientos de caja"
            />
            <TablaDetalle
              filas={reportes.caja.detalle}
              label="Detalle de caja"
            />
          </Card>

          <Card title="Liquidaciones">
            <p>
              Liquidaciones: {reportes.liquidaciones.cantidad_liquidaciones}
            </p>
            <p>Cobertura: {reportes.liquidaciones.total_cobertura}</p>
            <p>Prácticas: {reportes.liquidaciones.cantidad_practicas}</p>
            <h3>Por prestación</h3>
            <TablaDetalle
              filas={reportes.liquidaciones.por_prestacion}
              label="Liquidaciones por prestación"
            />
            <TablaDetalle
              filas={reportes.liquidaciones.detalle}
              label="Detalle de liquidaciones"
            />
          </Card>
        </>
      ) : null}

      <Card title="Exportar datos" className="ds-print-hidden">
        <Input
          label="Paciente (id)"
          value={pacienteId}
          onChange={(event) => setPacienteId(event.target.value)}
        />
        <div className="ds-card__actions">
          <Button
            variant="secondary"
            onClick={() => void exportar("paciente")}
            disabled={pacienteId === ""}
          >
            Exportar paciente
          </Button>
          {esAdmin ? (
            <Button
              variant="secondary"
              onClick={() => void exportar("consultorio")}
            >
              Exportar consultorio
            </Button>
          ) : null}
        </div>
        {exportError !== null ? <ErrorBanner message={exportError} /> : null}
        {exportacion !== null ? (
          <>
            <p>Estado: {exportacion.estado}</p>
            {enCurso ? (
              <Loading
                label={
                  exportacion.estado === "pendiente"
                    ? "Exportación pendiente…"
                    : "Generando exportación…"
                }
              />
            ) : null}
            {exportacion.ultimo_error !== null ? (
              <ErrorBanner message={exportacion.ultimo_error} />
            ) : null}
            <Button
              onClick={() => void descargar()}
              disabled={exportacion.estado !== "lista"}
            >
              Descargar ZIP
            </Button>
          </>
        ) : null}
      </Card>
    </main>
  );
}
