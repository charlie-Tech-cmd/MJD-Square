import json
import secrets

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.db import SessionLocal
from app.whatsapp_service import update_delivery_statuses, valid_webhook_signature

router = APIRouter(tags=["WhatsApp webhooks"])


@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
def verify_whatsapp_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    if not settings.whatsapp_webhook_verify_token or not settings.whatsapp_app_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp webhook verification is not configured.",
        )
    if (
        mode != "subscribe"
        or not token
        or not secrets.compare_digest(token, settings.whatsapp_webhook_verify_token)
        or challenge is None
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook token.")
    return challenge


@router.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request) -> dict[str, int | str]:
    if not settings.whatsapp_app_secret or not settings.whatsapp_webhook_verify_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp webhook verification is not configured.",
        )
    body = await request.body()
    if not valid_webhook_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature.",
        )
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        )
    with SessionLocal() as db:
        updated = update_delivery_statuses(db, payload)
    return {"status": "ok", "updated": updated}
