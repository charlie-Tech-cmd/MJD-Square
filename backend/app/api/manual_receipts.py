from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, BusinessSettings, ManualPaymentReceipt, User
from app.permissions import require_csrf, require_permission
from app.transaction_schemas import (
    ManualPaymentReceiptCreate,
    ManualPaymentReceiptListResponse,
    ManualPaymentReceiptResponse,
)

router = APIRouter(prefix="/manual-receipts", tags=["manual receipts"])


def get_business_settings(db: Session) -> BusinessSettings:
    settings = db.get(BusinessSettings, 1)
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Business settings have not been initialized.",
        )
    return settings


@router.get("", response_model=ManualPaymentReceiptListResponse)
def list_manual_receipts(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("payments:read")),
) -> ManualPaymentReceiptListResponse:
    settings = get_business_settings(db)
    receipts = db.scalars(
        select(ManualPaymentReceipt)
        .order_by(
            ManualPaymentReceipt.paid_on.desc(),
            ManualPaymentReceipt.created_at.desc(),
        )
        .limit(limit)
    ).all()
    return ManualPaymentReceiptListResponse(
        receipts=receipts,
        business_name=settings.business_name,
        currency=settings.currency,
        payment_methods=settings.payment_methods,
    )


@router.post(
    "",
    response_model=ManualPaymentReceiptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_receipt(
    payload: ManualPaymentReceiptCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payments:create")),
    _: User = Depends(require_csrf),
) -> ManualPaymentReceipt:
    settings = get_business_settings(db)
    payment_method = next(
        (
            configured
            for configured in settings.payment_methods
            if configured.casefold() == payload.payment_method.casefold()
        ),
        None,
    )
    if payment_method is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Choose a payment method configured in business settings.",
        )

    receipt_id = str(uuid4())
    receipt_number = f"MJD-{payload.paid_on:%Y%m%d}-{receipt_id[:12].upper()}"
    receipt = ManualPaymentReceipt(
        id=receipt_id,
        receipt_number=receipt_number,
        business_name=settings.business_name,
        currency=settings.currency,
        payer_name=payload.payer_name,
        payer_phone=payload.payer_phone,
        purpose=payload.purpose,
        amount=payload.amount,
        payment_method=payment_method,
        paid_on=payload.paid_on,
        created_by=user.id,
    )
    db.add(receipt)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="manual_payment_receipt.create",
            entity_type="manual_payment_receipt",
            entity_id=receipt_id,
            details={
                "receipt_number": receipt_number,
                "amount": str(payload.amount),
                "currency": settings.currency,
            },
        )
    )
    db.commit()
    db.refresh(receipt)
    return receipt
