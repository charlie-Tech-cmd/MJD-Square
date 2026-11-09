from collections import defaultdict
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import (
    AuditLog,
    BusinessSettings,
    Customer,
    Payment,
    ReminderActivity,
    Sale,
    User,
    utc_now,
)
from app.permissions import require_csrf, require_permission
from app.workflow_schemas import (
    PaymentReminderResponse,
    ReminderActivityCreate,
    ReminderActivityResponse,
    TransactionHistoryResponse,
)

router = APIRouter(tags=["business workflows"])


def reminder_activity_response(activity: ReminderActivity) -> ReminderActivityResponse:
    return ReminderActivityResponse(
        id=activity.id,
        status=activity.status,
        channel=activity.channel,
        notes=activity.notes,
        actor_name=activity.actor.full_name if activity.actor else None,
        created_at=activity.created_at,
    )


@router.get("/payment-reminders", response_model=list[PaymentReminderResponse])
def list_payment_reminders(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("customers:read")),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[PaymentReminderResponse]:
    paid_by_sale = (
        select(Payment.sale_id.label("sale_id"), func.sum(Payment.amount).label("amount_paid"))
        .where(Payment.sale_id.is_not(None))
        .group_by(Payment.sale_id)
        .subquery()
    )
    paid_amount = func.coalesce(paid_by_sale.c.amount_paid, 0)
    records = db.execute(
        select(Sale, Customer, paid_amount)
        .join(Customer, Sale.customer_id == Customer.id)
        .outerjoin(paid_by_sale, Sale.id == paid_by_sale.c.sale_id)
        .where(Sale.total_amount > paid_amount)
        .order_by(Sale.due_date.asc(), Sale.created_at.desc())
        .limit(limit)
    ).all()
    if not records:
        return []

    sale_ids = [sale.id for sale, _, _ in records]
    activity_rows = db.scalars(
        select(ReminderActivity)
        .where(ReminderActivity.sale_id.in_(sale_ids))
        .options(joinedload(ReminderActivity.actor))
        .order_by(ReminderActivity.created_at.desc(), ReminderActivity.id.desc())
    ).all()
    activities_by_sale: dict[str, list[ReminderActivity]] = defaultdict(list)
    for activity in activity_rows:
        activities_by_sale[activity.sale_id].append(activity)

    business_settings = db.get(BusinessSettings, 1)
    business_timezone = ZoneInfo(
        business_settings.timezone if business_settings else "Africa/Lagos"
    )
    today = utc_now().astimezone(business_timezone).date()
    reminders: list[PaymentReminderResponse] = []
    for sale, customer, amount_paid in records:
        activities = activities_by_sale[sale.id]
        latest_status = activities[0].status if activities else None
        last_contacted_at = next(
            (
                activity.created_at
                for activity in activities
                if activity.status == "sent_manually"
            ),
            None,
        )
        reminders.append(
            PaymentReminderResponse(
                sale_id=sale.id,
                invoice_number=sale.invoice_number,
                customer_id=customer.id,
                customer_name=customer.name,
                customer_phone=customer.phone,
                customer_whatsapp=customer.whatsapp,
                sale_date=sale.sale_date,
                due_date=sale.due_date,
                total_amount=sale.total_amount,
                amount_paid=amount_paid,
                balance_due=sale.total_amount - amount_paid,
                days_overdue=max((today - sale.due_date).days, 0),
                latest_status=latest_status,
                last_contacted_at=last_contacted_at,
                activities=[reminder_activity_response(activity) for activity in activities],
            )
        )
    return reminders


@router.post(
    "/sales/{sale_id}/reminder-activities",
    response_model=ReminderActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reminder_activity(
    sale_id: str,
    payload: ReminderActivityCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customers:manage")),
    _: User = Depends(require_csrf),
) -> ReminderActivityResponse:
    sale = db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    paid_amount = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.sale_id == sale.id)
    )
    if payload.status == "resolved" and paid_amount < sale.total_amount:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invoice can only be marked resolved after it is fully paid.",
        )
    if payload.status != "resolved" and paid_amount >= sale.total_amount:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A reminder cannot be recorded for a fully paid invoice.",
        )
    activity = ReminderActivity(
        sale_id=sale.id,
        status=payload.status,
        channel=payload.channel,
        notes=payload.notes,
        created_by=actor.id,
    )
    db.add(activity)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="payment_reminder.activity",
            entity_type="sale",
            entity_id=sale.id,
            details={
                "invoice_number": sale.invoice_number,
                "status": payload.status,
                "channel": payload.channel,
                "notes": payload.notes,
            },
        )
    )
    db.commit()
    db.refresh(activity)
    return reminder_activity_response(activity)


@router.get("/transaction-history", response_model=list[TransactionHistoryResponse])
def list_transaction_history(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit:read")),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=120),
) -> list[TransactionHistoryResponse]:
    statement = select(AuditLog).options(joinedload(AuditLog.actor))
    if q and q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                AuditLog.action.ilike(term),
                AuditLog.entity_type.ilike(term),
                AuditLog.entity_id.ilike(term),
                cast(AuditLog.details, String).ilike(term),
            )
        )
    entries = db.scalars(
        statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        TransactionHistoryResponse(
            id=entry.id,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            details=entry.details,
            actor_name=entry.actor.full_name if entry.actor else None,
            created_at=entry.created_at,
        )
        for entry in entries
    ]
