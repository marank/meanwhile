from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./calendar.db"
    secret_key: str = "dev-change-me-in-production-needs-32-bytes"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    allow_registration: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]

    caldav_path: str = "/caldav"
    ics_path: str = "/ics"


settings = Settings()
