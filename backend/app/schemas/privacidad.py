"""Public privacy-policy response (C-16, design D7)."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class PoliticaPrivacidadResponse(BaseModel):
    """Only the public text, its version and its digest: no PII, no secrets."""

    model_config = ConfigDict(extra="forbid")

    version: str
    vigente_desde: date
    texto: str
    hash: str
    alcance_legal_validado: bool = False
