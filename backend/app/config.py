from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-change-me-in-production-needs-32-bytes"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite:///./calendar.db"
    secret_key: str = _DEV_SECRET
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    allow_registration: bool = True
    admin_email: str | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    base_url: str | None = None

    caldav_path: str = "/caldav"
    ics_path: str = "/ics"

    @model_validator(mode="after")
    def _require_secret_key(self) -> "Settings":
        if self.environment != "development" and self.secret_key == _DEV_SECRET:
            raise ValueError(
                "SECRET_KEY must be set to a non-default value outside development"
            )
        return self


settings = Settings()
