import hashlib
import hmac
import json
import logging
import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    AccountPayment,
    BusinessSettings,
    Customer,
    Payment,
    Supplier,
    WhatsAppReceipt,
)

logger = logging.getLogger(__name__)


def whatsapp_sender_configured() -> bool:
    return all(
        (
            settings.whatsapp_access_token,
            settings.whatsapp_phone_number_id,
            settings.whatsapp_api_version,
            settings.whatsapp_receipt_template,
        )
    )


def normalize_whatsapp_number(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("0"):
        digits = f"234{digits[1:]}"
    if not 8 <= len(digits) <= 15:
        return None
    return digits


def prepare_payment_receipt(
    db: Session,
    payment: Payment | AccountPayment,
    recipient: Customer | Supplier | None,
    transaction_reference: str,
    balance_due: Decimal,
    payment_direction: str = "received",
) -> WhatsAppReceipt | None:
    if recipient is None:
        return None
    business_settings = db.get(BusinessSettings, 1)
    phone = recipient.whatsapp or ""
    normalized_number = normalize_whatsapp_number(phone) if phone else None
    if not recipient.whatsapp_receipt_opted_in:
        status = "not_opted_in"
    elif not phone:
        status = "no_number"
    elif normalized_number is None:
        status = "invalid_number"
    elif not whatsapp_sender_configured():
        status = "not_configured"
    else:
        status = "pending"
    receipt = WhatsAppReceipt(
        payment=payment if isinstance(payment, Payment) else None,
        account_payment=payment if isinstance(payment, AccountPayment) else None,
        recipient_name=recipient.name,
        recipient_kind="customer" if isinstance(recipient, Customer) else "supplier",
        payment_direction=payment_direction,
        phone=normalized_number or phone,
        amount=payment.amount,
        method=payment.method,
        reference=payment.reference,
        transaction_reference=transaction_reference,
        balance_due=balance_due,
        currency=business_settings.currency if business_settings else "NGN",
        received_at=payment.received_at,
        status=status,
    )
    db.add(receipt)
    return receipt


def _template_parameters(
    receipt: WhatsAppReceipt, business_name: str, timezone: str
) -> list[str]:
    timestamp = receipt.received_at
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    localized_time = timestamp.astimezone(ZoneInfo(timezone)).strftime("%d %b %Y, %H:%M")
    receipt_number = f"RCP-{receipt.id.replace('-', '').upper()}"
    return [
        receipt.recipient_name,
        business_name,
        (
            "payment received by MJD Square from you"
            if receipt.payment_direction == "received"
            else "payment made by MJD Square to you"
        ),
        receipt_number,
        receipt.transaction_reference,
        f"{receipt.currency} {receipt.amount:.2f}",
        receipt.method,
        receipt.reference or "Not provided",
        localized_time,
        f"{receipt.currency} {receipt.balance_due:.2f}",
        "This is a manual payment record, not independent bank confirmation.",
    ]


def send_payment_receipt(db: Session, receipt: WhatsAppReceipt | None) -> None:
    if receipt is None or receipt.status != "pending":
        return
    if not whatsapp_sender_configured():
        receipt.status = "not_configured"
        db.commit()
        return
    business_settings = db.get(BusinessSettings, 1)
    business_name = business_settings.business_name if business_settings else "MJD Square"
    timezone = business_settings.timezone if business_settings else "Africa/Lagos"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": receipt.phone,
        "type": "template",
        "template": {
            "name": settings.whatsapp_receipt_template,
            "language": {"code": settings.whatsapp_receipt_template_language},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": value}
                        for value in _template_parameters(receipt, business_name, timezone)
                    ],
                }
            ],
        },
    }
    try:
        request = Request(
            (
                f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
                f"{settings.whatsapp_phone_number_id}/messages"
            ),
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {settings.whatsapp_access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            response_data = json.loads(response.read())
        message_id = response_data["messages"][0]["id"]
        if not isinstance(message_id, str) or not message_id:
            raise ValueError("WhatsApp returned an invalid message identifier.")
    except HTTPError as exc:
        receipt.status = "failed"
        receipt.failure_reason = f"WhatsApp API rejected the receipt (HTTP {exc.code})."
        logger.warning("WhatsApp API rejected payment receipt %s (HTTP %s).", receipt.id, exc.code)
    except (URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        receipt.status = "failed"
        receipt.failure_reason = "WhatsApp API request failed or returned an invalid response."
        logger.warning("WhatsApp delivery failed for payment receipt %s: %s", receipt.id, exc)
    else:
        receipt.status = "accepted"
        receipt.provider_message_id = message_id
        receipt.accepted_at = datetime.now(UTC)
        receipt.failure_reason = None
    db.commit()


def valid_webhook_signature(payload: bytes, signature: str | None) -> bool:
    if not settings.whatsapp_app_secret or not signature:
        return False
    expected = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def update_delivery_statuses(db: Session, payload: dict) -> int:
    updated = 0
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        return updated
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value", {})
            if not isinstance(value, dict):
                continue
            statuses = value.get("statuses", [])
            if not isinstance(statuses, list):
                continue
            for delivery in statuses:
                if not isinstance(delivery, dict):
                    continue
                message_id = delivery.get("id")
                provider_status = delivery.get("status")
                if (
                    not isinstance(message_id, str)
                    or not isinstance(provider_status, str)
                    or provider_status
                    not in {
                        "sent",
                        "delivered",
                        "read",
                        "failed",
                    }
                ):
                    continue
                receipt = db.scalar(
                    select(WhatsAppReceipt).where(
                        WhatsAppReceipt.provider_message_id == message_id
                    )
                )
                if receipt is None or receipt.status in {"read", "delivered", "failed"}:
                    continue
                if provider_status == "failed":
                    receipt.status = "failed"
                    receipt.failure_reason = "WhatsApp reports that the receipt was not delivered."
                else:
                    receipt.status = provider_status
                    timestamp = delivery.get("timestamp")
                    try:
                        occurred_at = datetime.fromtimestamp(int(timestamp), UTC)
                    except (TypeError, ValueError, OSError):
                        occurred_at = datetime.now(UTC)
                    if provider_status == "sent":
                        receipt.sent_at = occurred_at
                    elif provider_status == "delivered":
                        receipt.delivered_at = occurred_at
                    elif provider_status == "read":
                        receipt.delivered_at = receipt.delivered_at or occurred_at
                        receipt.read_at = occurred_at
                    receipt.failure_reason = None
                updated += 1
    if updated:
        db.commit()
    return updated
