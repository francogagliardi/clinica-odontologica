"""Environment-only configuration with fail-fast on missing secrets (R-08).

All values come from environment variables documented in .env.example.
Secrets have NO hardcoded defaults: a missing secret fails startup naming
the variable instead of falling back to something insecure.

Note on `extra="ignore"`: unlike the RORO boundary schemas (extra="forbid"
per R-01), the settings model must ignore unrelated host env vars — with
`extra="forbid"` any unrelated variable (PATH, HOME, ...) would crash the
process. Unknown *fields* still cannot be set programmatically.
"""

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read exclusively from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    whatsapp_api_token: str
    whatsapp_phone_id: str
    mp_access_token: str
    arca_cuit: str
    arca_cert: str
    arca_key: str
    app_base_url: str = "http://127.0.0.1:8080"


def load_settings() -> Settings:
    """Build Settings, failing fast with the missing UPPER-CASE var name."""
    try:
        return Settings()
    except ValidationError as exc:
        missing = sorted(
            {
                str(location[0]).upper()
                for error in exc.errors()
                if error.get("type") == "missing"
                for location in [error.get("loc", ())]
                if location
            }
        )
        names = ", ".join(missing) if missing else "configuration"
        raise RuntimeError(
            f"Missing required environment variable(s): {names}. "
            "Copy backend/.env.example to backend/.env and fill it in."
        ) from exc
