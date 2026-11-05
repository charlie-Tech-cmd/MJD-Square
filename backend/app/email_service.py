import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def send_password_reset_email(recipient: str, reset_url: str) -> None:
    if not settings.smtp_host or not settings.mail_from:
        logger.error("Password reset email was not sent: SMTP is not configured.")
        return

    message = EmailMessage()
    message["Subject"] = "Reset your MJD Square password"
    message["From"] = settings.mail_from
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your MJD Square account.\n\n"
        f"Use this link within 30 minutes to choose a new password:\n{reset_url}\n\n"
        "If you did not request this change, you can ignore this email."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            if settings.smtp_use_starttls:
                smtp.starttls()
                smtp.ehlo()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("Password reset email delivery failed.")
