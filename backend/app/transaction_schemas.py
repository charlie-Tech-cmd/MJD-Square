import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.record_schemas import Money, NonnegativeMoney, Quantity

PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class SaleLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=36)
    quantity: PositiveQuantity


class SaleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = Field(default=None, max_length=36)
    sale_type: Literal["retail", "wholesale"] = "retail"
    sale_date: date
    due_date: date | None = None
    lines: list[SaleLineCreate] = Field(min_length=1, max_length=100)
    payment_amount: NonnegativeMoney = Decimal("0.00")
    payment_method: str | None = Field(default=None, max_length=40)
    payment_reference: str | None = Field(default=None, max_length=100)
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_sale(self) -> "SaleCreate":
        if self.due_date is not None and self.due_date < self.sale_date:
            raise ValueError("The invoice due date cannot be before the sale date.")
        if len({line.product_id for line in self.lines}) != len(self.lines):
            raise ValueError("A product can only appear once on a sale.")
        if self.payment_amount > 0 and not (self.payment_method or "").strip():
            raise ValueError("Choose a payment method when recording a payment.")
        if self.payment_method is not None:
            self.payment_method = self.payment_method.strip() or None
        if self.payment_reference is not None:
            self.payment_reference = self.payment_reference.strip() or None
        self.notes = self.notes.strip()
        return self


class PurchaseLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=36)
    quantity: PositiveQuantity
    unit_cost: NonnegativeMoney


class PurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: str | None = Field(default=None, max_length=36)
    supplier_reference: str | None = Field(default=None, max_length=100)
    purchase_date: date
    lines: list[PurchaseLineCreate] = Field(min_length=1, max_length=100)
    payment_amount: NonnegativeMoney = Decimal("0.00")
    payment_method: str | None = Field(default=None, max_length=40)
    payment_reference: str | None = Field(default=None, max_length=100)
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_purchase(self) -> "PurchaseCreate":
        if len({line.product_id for line in self.lines}) != len(self.lines):
            raise ValueError("A product can only appear once on a purchase.")
        if self.payment_amount > 0 and not (self.payment_method or "").strip():
            raise ValueError("Choose a payment method when recording a payment.")
        if self.payment_method is not None:
            self.payment_method = self.payment_method.strip() or None
        if self.payment_reference is not None:
            self.payment_reference = self.payment_reference.strip() or None
        if self.supplier_reference is not None:
            self.supplier_reference = self.supplier_reference.strip() or None
        self.notes = self.notes.strip()
        return self


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: PositiveMoney
    method: str = Field(min_length=1, max_length=40)
    reference: str | None = Field(default=None, max_length=100)
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def clean_text(self) -> "PaymentCreate":
        self.method = self.method.strip()
        if not self.method:
            raise ValueError("Choose a payment method.")
        if self.reference is not None:
            self.reference = self.reference.strip() or None
        self.notes = self.notes.strip()
        return self


class PaymentEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    uploaded_at: datetime


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amount: Money
    method: str
    reference: str | None
    notes: str
    received_at: datetime
    receipts: list[PaymentEvidenceResponse] = Field(default_factory=list)
    whatsapp_receipt_status: str | None = None


class AccountPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amount: Money
    method: str
    reference: str | None
    notes: str
    received_at: datetime
    receipts: list[PaymentEvidenceResponse] = Field(default_factory=list)
    whatsapp_receipt_status: str | None = None


class AccountPaymentHistoryResponse(AccountPaymentResponse):
    account_type: Literal["customer", "supplier"]
    account_name: str


class ManualPaymentReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payer_name: str = Field(min_length=1, max_length=160)
    payer_phone: str | None = Field(default=None, max_length=40)
    purpose: str = Field(min_length=1, max_length=240)
    amount: PositiveMoney
    payment_method: str = Field(min_length=1, max_length=40)
    paid_on: date

    @model_validator(mode="after")
    def clean_required_text(self) -> "ManualPaymentReceiptCreate":
        for field in ("payer_name", "purpose", "payment_method"):
            value = getattr(self, field).strip()
            if not value:
                raise ValueError(f"{field.replace('_', ' ').capitalize()} cannot be blank.")
            setattr(self, field, value)
        if self.payer_phone is not None:
            self.payer_phone = self.payer_phone.strip() or None
        return self

    @field_validator("payer_phone")
    @classmethod
    def validate_payer_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = re.sub(r"[\s()-]", "", value)
        if not value:
            return None
        if not re.fullmatch(r"\+?[1-9]\d{7,14}", value):
            raise ValueError("Enter a phone number with its country code, such as +2348012345678.")
        return value


class ManualPaymentReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    receipt_number: str
    business_name: str
    currency: str
    payer_name: str
    payer_phone: str | None
    purpose: str
    amount: Money
    payment_method: str
    paid_on: date
    created_at: datetime


class ManualPaymentReceiptListResponse(BaseModel):
    receipts: list[ManualPaymentReceiptResponse]
    business_name: str
    currency: str
    payment_methods: list[str]


class SaleLineResponse(BaseModel):
    product_id: str
    product_name: str
    sku: str
    unit_name: str
    quantity: Quantity
    unit_price: Money
    line_total: Money


class SaleResponse(BaseModel):
    id: str
    invoice_number: str
    customer_id: str | None
    customer_name: str | None
    sale_type: str
    sale_date: date
    due_date: date
    lines: list[SaleLineResponse]
    total_amount: Money
    amount_paid: Money
    balance_due: Money
    payments: list[PaymentResponse]
    notes: str
    created_at: datetime


class PurchaseLineResponse(BaseModel):
    product_id: str
    product_name: str
    sku: str
    unit_name: str
    quantity: Quantity
    unit_cost: Money
    line_total: Money


class PurchaseResponse(BaseModel):
    id: str
    purchase_number: str
    supplier_id: str | None
    supplier_name: str | None
    supplier_reference: str | None
    purchase_date: date
    lines: list[PurchaseLineResponse]
    total_amount: Money
    amount_paid: Money
    balance_due: Money
    payments: list[PaymentResponse]
    notes: str
    created_at: datetime


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)
    amount: PositiveMoney
    expense_date: date
    method: str = Field(min_length=1, max_length=40)
    reference: str | None = Field(default=None, max_length=100)
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def clean_text(self) -> "ExpenseCreate":
        for field in ("category", "description", "method"):
            value = getattr(self, field).strip()
            if not value:
                raise ValueError(f"{field.replace('_', ' ').capitalize()} cannot be blank.")
            setattr(self, field, value)
        if self.reference is not None:
            self.reference = self.reference.strip() or None
        self.notes = self.notes.strip()
        return self


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: str
    description: str
    amount: Money
    expense_date: date
    method: str
    reference: str | None
    notes: str
    created_at: datetime
