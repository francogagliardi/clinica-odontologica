"""Unit of work: one transaction per use case (R-04).

The repository layer never commits; this context manager commits on success
and rolls back on any exception, leaving the session reusable.
"""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.repositories import (
    AuditoriaRepository,
    BloqueoRepository,
    ConsultorioRepository,
    ListaEsperaRepository,
    MensajeWhatsAppRepository,
    ObraSocialRepository,
    PacienteRepository,
    PrestacionRepository,
    ProfesionalRepository,
    ProfesionalSillonRepository,
    RecordatorioRepository,
    RolRepository,
    SillonRepository,
    TurnoRepository,
    UsuarioRepository,
)


class UnitOfWork:
    """Groups repositories over a single session and owns the transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "UnitOfWork":
        self._session = self._session_factory()
        self.consultorios = ConsultorioRepository(self._session)
        self.roles = RolRepository(self._session)
        self.usuarios = UsuarioRepository(self._session)
        self.auditoria = AuditoriaRepository(self._session)
        self.profesionales = ProfesionalRepository(self._session)
        self.sillones = SillonRepository(self._session)
        self.profesionales_sillones = ProfesionalSillonRepository(self._session)
        self.prestaciones = PrestacionRepository(self._session)
        self.bloqueos = BloqueoRepository(self._session)
        self.obras_sociales = ObraSocialRepository(self._session)
        self.pacientes = PacienteRepository(self._session)
        self.turnos = TurnoRepository(self._session)
        self.recordatorios = RecordatorioRepository(self._session)
        self.mensajes = MensajeWhatsAppRepository(self._session)
        self.lista_espera = ListaEsperaRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        """Commit mid-use-case.

        Only for facts that must survive even when the request ends in an
        error response (e.g. the append-only login audit before a 401).
        """
        if self._session is None:
            raise RuntimeError("UnitOfWork no está abierto")
        await self._session.commit()

    @property
    def session(self) -> AsyncSession:
        """Raw session for cases the repositories do not cover yet."""
        if self._session is None:
            raise RuntimeError("UnitOfWork no está abierto")
        return self._session
