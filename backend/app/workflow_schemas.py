from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.record_schemas import Money

ReminderStatus = Literal[
    "prepared",
    "sent_manually",
    "follow_up_required",
    "promised_payment",
    "disputed",
    "resolved",
]
ReminderChannel = Literal["whatsapp", "phone", "in_person", "other"]


class ReminderActivityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReminderStatus
    channel: ReminderChannel | None = None
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def clean_notes(self) -> "ReminderActivityCreate":
        self.notes = self.notes.strip()
        if self.status == "sent_manually" and self.channel is None:
            raise ValueError("Choose how the reminder was sent.")
        return self


class ReminderActivityResponse(BaseModel):
    id: str
    status: ReminderStatus
    channel: ReminderChannel | None
    notes: str
    actor_name: str | None
    created_at: datetime


class PaymentReminderResponse(BaseModel):
    sale_id: str
    invoice_number: str
    customer_id: str
    customer_name: str
    customer_phone: str | None
    customer_whatsapp: str | None
    sale_date: date
    due_date: date
    total_amount: Money
    amount_paid: Money
    balance_due: Money
    days_overdue: int
    latest_status: ReminderStatus | None
    last_contacted_at: datetime | None
    activities: list[ReminderActivityResponse]


class TransactionHistoryResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, object]
    actor_name: str | None
    created_at: datetime
