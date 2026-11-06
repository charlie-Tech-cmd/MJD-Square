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
        smtp_use_starttls=True,
        mail_from="noreply@example.com",
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


def test_development_preserves_localhost_http_origin():
    configured = Settings(
        _env_file=None,
        app_env="development",
        cors_origins="http://localhost:5173",
    )

    assert configured.allowed_origins == ["http://localhost:5173"]
