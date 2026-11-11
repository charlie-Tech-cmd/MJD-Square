from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Customer, CustomerOpeningBalance, User
from app.permissions import require_csrf, require_permission
from app.record_schemas import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    OpeningBalanceCreate,
    OpeningBalanceResponse,
)

router = APIRouter(prefix="/customers", tags=["customers"])


def customer_response(
    customer: Customer, opening_balances: list[CustomerOpeningBalance]
) -> CustomerResponse:
    return CustomerResponse(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        whatsapp=customer.whatsapp,
        whatsapp_receipt_opted_in=customer.whatsapp_receipt_opted_in,
        whatsapp_receipt_consent_at=customer.whatsapp_receipt_consent_at,
        email=customer.email,
        address=customer.address,
        customer_type=customer.customer_type,
        notes=customer.notes,
        is_active=customer.is_active,
        opening_balances=[
            OpeningBalanceResponse.model_validate(balance) for balance in opening_balances
        ],
        opening_balance_total=sum(
            (balance.amount for balance in opening_balances), Decimal("0.00")
        ),
        created_at=customer.created_at.isoformat(),
    )


def load_opening_balances(
    db: Session, customer_ids: list[str]
) -> dict[str, list[CustomerOpeningBalance]]:
    if not customer_ids:
        return {}
    balances = db.scalars(
        select(CustomerOpeningBalance)
        .where(CustomerOpeningBalance.customer_id.in_(customer_ids))
        .order_by(CustomerOpeningBalance.effective_date, CustomerOpeningBalance.created_at)
    ).all()
    result: dict[str, list[CustomerOpeningBalance]] = {}
    for balance in balances:
        result.setdefault(balance.customer_id, []).append(balance)
    return result


def record_opening_balance(
    db: Session,
    customer: Customer,
    amount: Decimal,
    effective_date: date,
    source_notes: str,
    actor: User,
) -> CustomerOpeningBalance:
    balance = CustomerOpeningBalance(
        customer_id=customer.id,
        amount=amount,
        effective_date=effective_date,
        source_notes=source_notes,
        created_by=actor.id,
    )
    db.add(balance)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="customer.opening_balance",
            entity_type="customer",
            entity_id=customer.id,
            details={"amount": str(amount), "effective_date": effective_date.isoformat()},
        )
    )
    return balance


def require_opening_balance_permission(actor: User) -> None:
    if "customers:opening_balance" not in {permission.id for permission in actor.role.permissions}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to record customer opening balances.",
        )


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("customers:read")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[CustomerResponse]:
    customers = db.scalars(
        select(Customer).order_by(Customer.name, Customer.id).limit(limit).offset(offset)
    ).all()
    balances = load_opening_balances(db, [customer.id for customer in customers])
    return [customer_response(customer, balances.get(customer.id, [])) for customer in customers]


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:manage")),
    _: User = Depends(require_csrf),
) -> CustomerResponse:
    if payload.opening_balance > 0:
        require_opening_balance_permission(actor)
    customer = Customer(
        name=payload.name,
        phone=payload.phone,
        whatsapp=payload.whatsapp,
        whatsapp_receipt_opted_in=payload.whatsapp_receipt_opted_in,
        whatsapp_receipt_consent_at=(
            datetime.now(UTC) if payload.whatsapp_receipt_opted_in else None
        ),
        email=str(payload.email) if payload.email else None,
        address=payload.address,
        customer_type=payload.customer_type,
        notes=payload.notes,
    )
    db.add(customer)
    try:
        db.flush()
        if payload.opening_balance > 0:
            balance = record_opening_balance(
                db,
                customer,
                payload.opening_balance,
                payload.opening_balance_date,
                payload.opening_balance_notes,
                actor,
            )
            balances = [balance]
        else:
            balances = []
        db.add(
            AuditLog(
                actor_user_id=actor.id,
                action="customer.create",
                entity_type="customer",
                entity_id=customer.id,
                details={
                    "customer_type": customer.customer_type,
                    "whatsapp_receipt_opted_in": customer.whatsapp_receipt_opted_in,
                },
            )
        )
        db.commit()
        db.refresh(customer)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer could not be created because a record constraint was violated.",
        ) from exc
    return customer_response(customer, balances)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:manage")),
    _: User = Depends(require_csrf),
) -> CustomerResponse:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    changes = payload.model_dump(exclude_unset=True)
    for required in ("name", "customer_type", "whatsapp_receipt_opted_in"):
        if required in changes and changes[required] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{required} cannot be null.",
            )
    if "whatsapp" in changes and changes["whatsapp"] != customer.whatsapp:
        if "whatsapp_receipt_opted_in" not in changes:
            changes["whatsapp_receipt_opted_in"] = False
    if changes.get("whatsapp_receipt_opted_in"):
        whatsapp_number = changes.get("whatsapp", customer.whatsapp)
        if not whatsapp_number:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A WhatsApp number is required for receipt opt-in.",
            )
        if not customer.whatsapp_receipt_opted_in or (
            "whatsapp" in changes and changes["whatsapp"] != customer.whatsapp
        ):
            customer.whatsapp_receipt_consent_at = datetime.now(UTC)
    elif changes.get("whatsapp_receipt_opted_in") is False:
        customer.whatsapp_receipt_consent_at = None
    for field, value in changes.items():
        if field == "whatsapp_receipt_opted_in":
            customer.whatsapp_receipt_opted_in = value
            continue
        if field == "email":
            value = str(value) if value else None
        setattr(customer, field, value)
    if changes:
        db.add(
            AuditLog(
                actor_user_id=actor.id,
                action="customer.update",
                entity_type="customer",
                entity_id=customer.id,
                details={"fields": sorted(changes)},
            )
        )
    db.commit()
    db.refresh(customer)
    balances = load_opening_balances(db, [customer.id]).get(customer.id, [])
    return customer_response(customer, balances)


@router.post(
    "/{customer_id}/opening-balances",
    response_model=OpeningBalanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_customer_opening_balance(
    customer_id: str,
    payload: OpeningBalanceCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:opening_balance")),
    _: User = Depends(require_csrf),
) -> OpeningBalanceResponse:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    balance = record_opening_balance(
        db, customer, payload.amount, payload.effective_date, payload.source_notes, actor
    )
    db.commit()
    db.refresh(balance)
    return OpeningBalanceResponse.model_validate(balance)
