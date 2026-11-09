from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
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
    frontend_url: str = "http://localhost:5173"
    smtp_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SMTP_HOST",
            "BREVO_SMTP_HOST",
        ),
    )
    smtp_port: int = Field(
        default=587,
        validation_alias=AliasChoices(
            "SMTP_PORT",
            "BREVO_SMTP_PORT",
        ),
    )
    smtp_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SMTP_USERNAME",
            "BREVO_SMTP_USERNAME",
            "BREVO_SMTP_USER",
        ),
    )
    smtp_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SMTP_PASSWORD",
            "BREVO_SMTP_PASSWORD",
        ),
    )
    smtp_use_starttls: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "SMTP_USE_STARTTLS",
            "BREVO_SMTP_USE_STARTTLS",
        ),
    )
    mail_from: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "MAIL_FROM",
            "BREVO_MAIL_FROM",
            "BREVO_SENDER_EMAIL",
        ),
    )

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
            if not self.smtp_host or not self.mail_from or not self.smtp_use_starttls:
                raise ValueError("Production requires SMTP with STARTTLS and a sender address.")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("Production FRONTEND_URL must use HTTPS.")

            origins = [origin.strip() for origin in self.cors_origins.split(",")]

            if not origins or any(not origin for origin in origins):
                raise ValueError("Production CORS_ORIGINS must contain valid HTTPS origins.")

            for origin in origins:
                try:
                    parsed = urlsplit(origin)
                    parsed.port
                except ValueError as exc:
                    raise ValueError(
                        "Production CORS_ORIGINS contains an invalid origin."
                    ) from exc

                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or "*" in parsed.netloc
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.path
                    or parsed.query
                    or parsed.fragment
                    or any(character.isspace() for character in origin)
                ):
                    raise ValueError(
                        "Production CORS_ORIGINS must contain explicit HTTPS origins "
                        "without wildcards, credentials, paths, queries, or fragments."
                    )

        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together.")
        if not 1 <= self.smtp_port <= 65535:
            raise ValueError("SMTP_PORT must be between 1 and 65535.")
        if self.app_env != "development" and self.database_url.startswith("sqlite"):
            raise ValueError("SQLite is only supported for local development.")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
