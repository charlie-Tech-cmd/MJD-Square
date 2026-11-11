import hashlib
import logging
import re
import unicodedata
from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    AccountPayment,
    AuditLog,
    Customer,
    Payment,
    PaymentEvidence,
    Supplier,
    User,
)
from app.permissions import require_csrf, require_permission
from app.receipt_storage import (
    ReceiptStorageError,
    local_receipt_path,
    receipt_download_url,
    remove_receipt,
    store_receipt,
)
from app.transaction_schemas import (
    AccountPaymentHistoryResponse,
    AccountPaymentResponse,
    PaymentEvidenceResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["payment evidence"])
MAX_RECEIPT_BYTES = 10 * 1024 * 1024
DOWNLOAD_CONTENT_TYPES = {
    b"%PDF-": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def require_entity_read(actor: User, permission: str) -> None:
    if permission not in {item.id for item in actor.role.permissions}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this payment record.",
        )


def require_owner(actor: User) -> None:
    if actor.role.name != "Owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Owners can remove payment receipts.",
        )


def detect_content_type(content: bytes) -> str | None:
    for signature, content_type in DOWNLOAD_CONTENT_TYPES.items():
        if content.startswith(signature):
            return content_type
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def safe_filename(value: str | None, content_type: str) -> str:
    filename = unicodedata.normalize("NFKC", value or "")
    filename = PurePosixPath(filename.replace("\\", "/")).name
    filename = "".join(
        character
        for character in filename
        if character.isalnum() or character in " ._()-"
    ).strip(" .")
    filename = re.sub(r"\s+", " ", filename)[:255].strip(" .")
    if filename:
        return filename
    extension = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }[content_type]
    return f"payment-evidence{extension}"


def invoice_payment(db: Session, payment_id: str) -> tuple[Payment, str]:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    if payment.sale_id is not None:
        return payment, "sales:read"
    return payment, "purchases:read"


def account_payment(db: Session, payment_id: str) -> tuple[AccountPayment, str]:
    payment = db.get(AccountPayment, payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account payment not found."
        )
    if payment.customer_id is not None:
        return payment, "customers:read"
    return payment, "suppliers:read"


def persist_receipt(
    *,
    file: UploadFile,
    payment: Payment | None,
    account_payment: AccountPayment | None,
    actor: User,
    db: Session,
) -> PaymentEvidenceResponse:
    content = file.file.read(MAX_RECEIPT_BYTES + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected receipt file is empty.",
        )
    if len(content) > MAX_RECEIPT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Receipt files must be 10 MB or smaller.",
        )
    content_type = detect_content_type(content)
    if content_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a PDF, JPEG, PNG, or WebP payment receipt.",
        )

    receipt_id = str(uuid4())
    if (payment is None) == (account_payment is None):
        raise RuntimeError("Payment evidence must belong to exactly one payment record.")
    payment_id = payment.id if payment is not None else account_payment.id
    object_prefix = "payments" if payment is not None else "account-payments"
    object_key = f"mjd-square/{object_prefix}/{payment_id}/receipts/{receipt_id}"
    filename = safe_filename(file.filename, content_type)
    try:
        store_receipt(object_key, content, content_type)
    except ReceiptStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    receipt = PaymentEvidence(
        id=receipt_id,
        payment_id=payment.id if payment is not None else None,
        account_payment_id=account_payment.id if account_payment is not None else None,
        object_key=object_key,
        filename=filename,
        content_type=content_type,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        uploaded_by_id=actor.id,
    )
    db.add(receipt)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="payment.evidence.upload",
            entity_type="payment_evidence",
            entity_id=receipt_id,
            details={
                "payment_id": payment_id,
                "payment_type": object_prefix,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(content),
                "sha256": receipt.sha256,
            },
        )
    )
    try:
        db.commit()
        db.refresh(receipt)
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            remove_receipt(object_key)
        except ReceiptStorageError:
            logger.exception("A payment receipt object may be orphaned after a database error.")
        logger.exception("Unable to save payment receipt metadata.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The receipt file was uploaded but its payment record could not be saved.",
        ) from exc
    return PaymentEvidenceResponse.model_validate(receipt)


@router.post(
    "/payments/{payment_id}/receipts",
    response_model=PaymentEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_invoice_payment_receipt(
    payment_id: str,
    file: UploadFile = File(),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payments:create")),
    _: User = Depends(require_csrf),
) -> PaymentEvidenceResponse:
    payment, permission = invoice_payment(db, payment_id)
    require_entity_read(actor, permission)
    return persist_receipt(file=file, payment=payment, account_payment=None, actor=actor, db=db)


@router.post(
    "/account-payments/{payment_id}/receipts",
    response_model=PaymentEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_account_payment_receipt(
    payment_id: str,
    file: UploadFile = File(),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payments:create")),
    _: User = Depends(require_csrf),
) -> PaymentEvidenceResponse:
    payment, permission = account_payment(db, payment_id)
    require_entity_read(actor, permission)
    return persist_receipt(
        file=file, payment=None, account_payment=payment, actor=actor, db=db
    )


@router.get(
    "/payment-receipts/{receipt_id}/download",
    include_in_schema=False,
)
def download_payment_receipt(
    receipt_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payments:read")),
) -> Response:
    receipt = db.get(PaymentEvidence, receipt_id)
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment receipt not found."
        )
    if receipt.payment_id is not None:
        _, permission = invoice_payment(db, receipt.payment_id)
    elif receipt.account_payment_id is not None:
        _, permission = account_payment(db, receipt.account_payment_id)
    else:
        logger.error("Payment receipt %s has no associated payment record.", receipt_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This payment receipt is not linked to a payment record.",
        )
    require_entity_read(actor, permission)
    try:
        path = local_receipt_path(receipt.object_key)
        if path is not None:
            return FileResponse(
                path,
                media_type=receipt.content_type,
                filename=receipt.filename,
                headers={
                    "Cache-Control": "private, no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
        url = receipt_download_url(receipt.object_key, receipt.filename, receipt.content_type)
    except ReceiptStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.delete("/payment-receipts/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment_receipt(
    receipt_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payments:read")),
    _: User = Depends(require_csrf),
) -> Response:
    require_owner(actor)
    receipt = db.get(PaymentEvidence, receipt_id)
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment receipt not found."
        )
    if receipt.payment_id is not None:
        payment, payment_type = invoice_payment(db, receipt.payment_id)
        payment_id = payment.id
    elif receipt.account_payment_id is not None:
        payment, payment_type = account_payment(db, receipt.account_payment_id)
        payment_id = payment.id
    else:
        logger.error("Payment receipt %s has no associated payment record.", receipt_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This payment receipt is not linked to a payment record.",
        )

    try:
        remove_receipt(receipt.object_key)
    except ReceiptStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="payment.evidence.delete",
            entity_type="payment_evidence",
            entity_id=receipt.id,
            details={
                "payment_id": payment_id,
                "payment_type": payment_type,
                "filename": receipt.filename,
                "content_type": receipt.content_type,
                "size_bytes": receipt.size_bytes,
                "sha256": receipt.sha256,
            },
        )
    )
    db.delete(receipt)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Unable to save payment receipt removal metadata.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The receipt file was removed but its audit record could not be saved.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/account-payments", response_model=list[AccountPaymentHistoryResponse])
def list_account_payments(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payments:read")),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[AccountPaymentHistoryResponse]:
    permissions = {item.id for item in actor.role.permissions}
    account_filters = []
    if "customers:read" in permissions:
        account_filters.append(AccountPayment.customer_id.is_not(None))
    if "suppliers:read" in permissions:
        account_filters.append(AccountPayment.supplier_id.is_not(None))
    if not account_filters:
        return []

    rows = db.execute(
        select(AccountPayment, Customer.name, Supplier.name)
        .outerjoin(Customer, AccountPayment.customer_id == Customer.id)
        .outerjoin(Supplier, AccountPayment.supplier_id == Supplier.id)
        .where(or_(*account_filters))
        .order_by(AccountPayment.received_at.desc(), AccountPayment.id)
        .limit(limit)
    ).all()
    return [
        AccountPaymentHistoryResponse(
            **AccountPaymentResponse.model_validate(payment).model_dump(),
            account_type="customer" if payment.customer_id else "supplier",
            account_name=customer_name or supplier_name or "Inactive account",
        )
        for payment, customer_name, supplier_name in rows
    ]
