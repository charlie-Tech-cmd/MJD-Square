import smtplib
from unittest.mock import MagicMock, Mock

import pytest

from app.config import settings
from app.email_service import EmailDeliveryError, send_password_reset_email


def configure_smtp(monkeypatch) -> MagicMock:
    monkeypatch.setattr(settings, "smtp_host", "smtp-relay.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "smtp_password", "smtp-password")
    monkeypatch.setattr(settings, "smtp_use_starttls", True)
    monkeypatch.setattr(settings, "mail_from", "verified@example.com")
    smtp = MagicMock()
    monkeypatch.setattr("app.email_service.smtplib.SMTP", Mock(return_value=smtp))
    smtp.__enter__.return_value = smtp
    smtp.__exit__.return_value = False
    return smtp


def test_password_reset_email_uses_authenticated_starttls_smtp(monkeypatch):
    smtp = configure_smtp(monkeypatch)

    send_password_reset_email("user@example.com", "https://app.example.com/reset")

    assert smtp.ehlo.call_count == 2
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("smtp-user", "smtp-password")
    message = smtp.send_message.call_args.args[0]
    assert message["From"] == "verified@example.com"
    assert message["To"] == "user@example.com"


def test_password_reset_email_surfaces_smtp_delivery_failure(monkeypatch):
    smtp = configure_smtp(monkeypatch)
    smtp.send_message.side_effect = smtplib.SMTPException("delivery rejected")

    with pytest.raises(EmailDeliveryError, match="delivery failed"):
        send_password_reset_email("user@example.com", "https://app.example.com/reset")
