import re
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
    owner_setup_token: str | None = None
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
    s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "S3_ENDPOINT_URL",
            "B2_S3_ENDPOINT_URL",
            "BACKBLAZE_S3_ENDPOINT_URL",
        ),
    )
    s3_region: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_REGION", "B2_REGION", "BACKBLAZE_REGION"),
    )
    s3_bucket: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_BUCKET", "B2_BUCKET", "BACKBLAZE_BUCKET"),
    )
    s3_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "S3_ACCESS_KEY_ID",
            "B2_APPLICATION_KEY_ID",
            "BACKBLAZE_APPLICATION_KEY_ID",
        ),
    )
    s3_secret_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "S3_SECRET_ACCESS_KEY",
            "B2_APPLICATION_KEY",
            "BACKBLAZE_APPLICATION_KEY",
        ),
    )
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_api_version: str | None = None
    whatsapp_receipt_template: str | None = None
    whatsapp_receipt_template_language: str = "en"
    whatsapp_app_secret: str | None = None
    whatsapp_webhook_verify_token: str | None = None

    @field_validator("app_env")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env == "production":
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production.")
            if not self.owner_setup_token or len(self.owner_setup_token) < 32:
                raise ValueError(
                    "Production requires OWNER_SETUP_TOKEN with at least 32 characters."
                )
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Production must use PostgreSQL.")
            if not self.smtp_host or not self.mail_from or not self.smtp_use_starttls:
                raise ValueError("Production requires SMTP with STARTTLS and a sender address.")
            if not self.smtp_username or not self.smtp_password:
                raise ValueError("Production requires authenticated SMTP credentials.")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("Production FRONTEND_URL must use HTTPS.")
            if not all(
                (
                    self.s3_region,
                    self.s3_bucket,
                    self.s3_access_key_id,
                    self.s3_secret_access_key,
                )
            ):
                raise ValueError(
                    "Production requires configured private S3-compatible receipt storage."
                )
            if self.s3_endpoint_url:
                try:
                    endpoint = urlsplit(self.s3_endpoint_url)
                    endpoint.port
                except ValueError as exc:
                    raise ValueError("S3_ENDPOINT_URL must be a valid HTTPS endpoint.") from exc
                if (
                    endpoint.scheme != "https"
                    or not endpoint.hostname
                    or endpoint.username is not None
                    or endpoint.password is not None
                    or endpoint.query
                    or endpoint.fragment
                ):
                    raise ValueError(
                        "Production S3_ENDPOINT_URL must use HTTPS without credentials."
                    )

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
        s3_credentials = (self.s3_access_key_id, self.s3_secret_access_key)
        if bool(s3_credentials[0]) != bool(s3_credentials[1]):
            raise ValueError(
                "S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY must be configured together."
            )
        whatsapp_sender_settings = (
            self.whatsapp_access_token,
            self.whatsapp_phone_number_id,
            self.whatsapp_api_version,
            self.whatsapp_receipt_template,
        )
        if any(whatsapp_sender_settings) and not all(whatsapp_sender_settings):
            raise ValueError(
                "WhatsApp sender requires access token, phone number ID, API version, "
                "and receipt template."
            )
        if self.whatsapp_api_version and not re.fullmatch(r"v\d+\.\d+", self.whatsapp_api_version):
            raise ValueError("WHATSAPP_API_VERSION must look like vNN.N.")
        if self.whatsapp_phone_number_id and not self.whatsapp_phone_number_id.isdigit():
            raise ValueError("WHATSAPP_PHONE_NUMBER_ID must contain only digits.")
        if self.whatsapp_receipt_template and not re.fullmatch(
            r"[a-z0-9_]+", self.whatsapp_receipt_template
        ):
            raise ValueError("WHATSAPP_RECEIPT_TEMPLATE must be a lowercase template name.")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{2,20}", self.whatsapp_receipt_template_language):
            raise ValueError("WHATSAPP_RECEIPT_TEMPLATE_LANGUAGE is invalid.")
        webhook_settings = (self.whatsapp_app_secret, self.whatsapp_webhook_verify_token)
        if bool(webhook_settings[0]) != bool(webhook_settings[1]):
            raise ValueError(
                "WhatsApp app secret and webhook verify token must be configured together."
            )
        if not 1 <= self.smtp_port <= 65535:
            raise ValueError("SMTP_PORT must be between 1 and 65535.")
        if self.app_env != "development" and self.database_url.startswith("sqlite"):
            raise ValueError("SQLite is only supported for local development.")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
