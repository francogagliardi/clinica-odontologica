"""Anonymous privacy-policy publication (C-16, design D7).

Two public GET routes with no database access: the current version and an
exact version lookup. Publishing the policy does not register acceptance and
does not change the public booking contract.

Revision ID: none (domain content, not a migration).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import reject_unexpected_query
from app.domain.privacidad import (
    PoliticaPrivacidad,
    hash_politica,
    politica_actual,
    politica_por_version,
)
from app.schemas.privacidad import PoliticaPrivacidadResponse

router = APIRouter(prefix="/privacidad", tags=["privacidad"])

_VERSION_DESCONOCIDA = "Versión de política de privacidad no encontrada"


def _to_response(politica: PoliticaPrivacidad) -> PoliticaPrivacidadResponse:
    return PoliticaPrivacidadResponse(
        version=politica.version,
        vigente_desde=politica.vigente_desde,
        texto=politica.texto,
        hash=hash_politica(politica.texto),
        alcance_legal_validado=False,
    )


@router.get(
    "",
    response_model=PoliticaPrivacidadResponse,
    summary="Política de privacidad vigente (pública)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_privacidad() -> PoliticaPrivacidadResponse:
    return _to_response(politica_actual())


@router.get(
    "/{version}",
    response_model=PoliticaPrivacidadResponse,
    summary="Política de privacidad por versión exacta (pública)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_privacidad_version(
    version: str,
) -> PoliticaPrivacidadResponse:
    politica = politica_por_version(version)
    if politica is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_VERSION_DESCONOCIDA,
        )
    return _to_response(politica)
