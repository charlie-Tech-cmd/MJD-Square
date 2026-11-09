from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Supplier, SupplierOpeningBalance, User
from app.permissions import require_csrf, require_permission
from app.record_schemas import (
    OpeningBalanceCreate,
    OpeningBalanceResponse,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def supplier_response(
    supplier: Supplier, opening_balances: list[SupplierOpeningBalance]
) -> SupplierResponse:
    return SupplierResponse(
        id=supplier.id,
        name=supplier.name,
        contact_person=supplier.contact_person,
        phone=supplier.phone,
        email=supplier.email,
        address=supplier.address,
        payment_terms_days=supplier.payment_terms_days,
        notes=supplier.notes,
        is_active=supplier.is_active,
        opening_balances=[
            OpeningBalanceResponse.model_validate(balance) for balance in opening_balances
        ],
        opening_balance_total=sum(
            (balance.amount for balance in opening_balances), Decimal("0.00")
        ),
        created_at=supplier.created_at.isoformat(),
    )


def load_opening_balances(
    db: Session, supplier_ids: list[str]
) -> dict[str, list[SupplierOpeningBalance]]:
    if not supplier_ids:
        return {}
    balances = db.scalars(
        select(SupplierOpeningBalance)
        .where(SupplierOpeningBalance.supplier_id.in_(supplier_ids))
        .order_by(SupplierOpeningBalance.effective_date, SupplierOpeningBalance.created_at)
    ).all()
    result: dict[str, list[SupplierOpeningBalance]] = {}
    for balance in balances:
        result.setdefault(balance.supplier_id, []).append(balance)
    return result


def record_opening_balance(
    db: Session,
    supplier: Supplier,
    amount: Decimal,
    effective_date: date,
    source_notes: str,
    actor: User,
) -> SupplierOpeningBalance:
    balance = SupplierOpeningBalance(
        supplier_id=supplier.id,
        amount=amount,
        effective_date=effective_date,
        source_notes=source_notes,
        created_by=actor.id,
    )
    db.add(balance)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="supplier.opening_balance",
            entity_type="supplier",
            entity_id=supplier.id,
            details={"amount": str(amount), "effective_date": effective_date.isoformat()},
        )
    )
    return balance


def require_opening_balance_permission(actor: User) -> None:
    if "suppliers:opening_balance" not in {permission.id for permission in actor.role.permissions}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to record supplier opening balances.",
        )


@router.get("", response_model=list[SupplierResponse])
def list_suppliers(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("suppliers:read")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SupplierResponse]:
    suppliers = db.scalars(
        select(Supplier).order_by(Supplier.name, Supplier.id).limit(limit).offset(offset)
    ).all()
    balances = load_opening_balances(db, [supplier.id for supplier in suppliers])
    return [supplier_response(supplier, balances.get(supplier.id, [])) for supplier in suppliers]


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("suppliers:manage")),
    _: User = Depends(require_csrf),
) -> SupplierResponse:
    if payload.opening_balance > 0:
        require_opening_balance_permission(actor)
    supplier = Supplier(
        name=payload.name,
        contact_person=payload.contact_person,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        address=payload.address,
        payment_terms_days=payload.payment_terms_days,
        notes=payload.notes,
    )
    db.add(supplier)
    try:
        db.flush()
        if payload.opening_balance > 0:
            balance = record_opening_balance(
                db,
                supplier,
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
                action="supplier.create",
                entity_type="supplier",
                entity_id=supplier.id,
                details={},
            )
        )
        db.commit()
        db.refresh(supplier)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Supplier could not be created because a record constraint was violated.",
        ) from exc
    return supplier_response(supplier, balances)


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: str,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("suppliers:manage")),
    _: User = Depends(require_csrf),
) -> SupplierResponse:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name cannot be null.",
        )
    for field, value in changes.items():
        if field == "email":
            value = str(value) if value else None
        setattr(supplier, field, value)
    if changes:
        db.add(
            AuditLog(
                actor_user_id=actor.id,
                action="supplier.update",
                entity_type="supplier",
                entity_id=supplier.id,
                details={"fields": sorted(changes)},
            )
        )
    db.commit()
    db.refresh(supplier)
    balances = load_opening_balances(db, [supplier.id]).get(supplier.id, [])
    return supplier_response(supplier, balances)


@router.post(
    "/{supplier_id}/opening-balances",
    response_model=OpeningBalanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_supplier_opening_balance(
    supplier_id: str,
    payload: OpeningBalanceCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("suppliers:opening_balance")),
    _: User = Depends(require_csrf),
) -> OpeningBalanceResponse:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
    balance = record_opening_balance(
        db, supplier, payload.amount, payload.effective_date, payload.source_notes, actor
    )
    db.commit()
    db.refresh(balance)
    return OpeningBalanceResponse.model_validate(balance)
