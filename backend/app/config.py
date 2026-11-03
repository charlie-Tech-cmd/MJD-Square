from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
LOCAL_DATABASE_PATH = ROOT_DIR / "backend" / "data" / "mjd_square.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = f"sqlite:///{LOCAL_DATABASE_PATH.as_posix()}"
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:5173"

    @field_validator("app_env")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env == "production":
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production.")
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Production must use PostgreSQL.")
        elif self.app_env != "development" and self.database_url.startswith("sqlite"):
            raise ValueError("SQLite is only supported for local development.")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
