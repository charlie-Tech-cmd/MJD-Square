import pytest
from pydantic import ValidationError

from app.config import Settings


def production_settings(cors_origins: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql://user:password@localhost/mjd_square",
        cookie_secure=True,
        cors_origins=cors_origins,
        frontend_url="https://app.example.com",
        smtp_host="smtp.example.com",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
        smtp_use_starttls=True,
        mail_from="noreply@example.com",
        s3_region="auto",
        s3_bucket="payment-evidence",
        s3_access_key_id="test-access-key",
        s3_secret_access_key="test-secret-key",
    )


def test_production_accepts_explicit_https_origins():
    configured = production_settings(
        "https://app.example.com, https://admin.example.com"
    )

    assert configured.allowed_origins == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


@pytest.mark.parametrize(
    "origins",
    [
        "*",
        "https://*",
        "https://*.example.com",
        "http://app.example.com",
        "https://app.example.com/dashboard",
        "https://app.example.com?debug=true",
        "https://user:password@app.example.com",
        "https://app.example.com#section",
        "https://app.example.com:invalid",
        "not-a-valid-origin",
        "",
        "https://app.example.com,",
    ],
)
def test_production_rejects_invalid_cors_origins(origins):
    with pytest.raises(ValidationError):
        production_settings(origins)


def test_production_requires_receipt_storage():
    with pytest.raises(ValidationError, match="private S3-compatible receipt storage"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://user:password@localhost/mjd_square",
            cookie_secure=True,
            cors_origins="https://app.example.com",
            frontend_url="https://app.example.com",
            smtp_host="smtp.example.com",
            smtp_username="smtp-user",
            smtp_password="smtp-password",
            smtp_use_starttls=True,
            mail_from="noreply@example.com",
        )


def test_production_requires_authenticated_smtp():
    with pytest.raises(ValidationError, match="authenticated SMTP credentials"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql://localhost/mjd_square",
            cookie_secure=True,
            cors_origins="https://app.example.com",
            frontend_url="https://app.example.com",
            smtp_host="smtp.example.com",
            smtp_use_starttls=True,
            mail_from="noreply@example.com",
            s3_region="auto",
            s3_bucket="payment-evidence",
            s3_access_key_id="test-access-key",
            s3_secret_access_key="test-secret-key",
        )


def test_production_rejects_insecure_receipt_storage_endpoint():
    with pytest.raises(ValidationError, match="S3_ENDPOINT_URL must use HTTPS"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql://localhost/mjd_square",
            cookie_secure=True,
            cors_origins="https://app.example.com",
            frontend_url="https://app.example.com",
            smtp_host="smtp.example.com",
            smtp_username="smtp-user",
            smtp_password="smtp-password",
            smtp_use_starttls=True,
            mail_from="noreply@example.com",
            s3_region="auto",
            s3_bucket="payment-evidence",
            s3_access_key_id="test-access-key",
            s3_secret_access_key="test-secret-key",
            s3_endpoint_url="http://storage.example.com",
        )


def test_development_preserves_localhost_http_origin():
    configured = Settings(
        _env_file=None,
        app_env="development",
        cors_origins="http://localhost:5173",
    )

    assert configured.allowed_origins == ["http://localhost:5173"]


def test_whatsapp_sender_settings_must_be_complete():
    with pytest.raises(ValidationError, match="WhatsApp sender requires"):
        Settings(_env_file=None, whatsapp_access_token="token")


def test_whatsapp_webhook_secrets_must_be_configured_together():
    with pytest.raises(ValidationError, match="must be configured together"):
        Settings(_env_file=None, whatsapp_app_secret="secret")
