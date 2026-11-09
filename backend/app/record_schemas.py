from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Money = Annotated[Decimal, Field(max_digits=14, decimal_places=2)]
NonnegativeMoney = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
Quantity = Annotated[Decimal, Field(max_digits=14, decimal_places=3)]
NonnegativeQuantity = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class CustomerFields(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    whatsapp: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    customer_type: Literal["retail", "wholesale", "both"] = "retail"
    notes: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def clean_text(self) -> "CustomerFields":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Customer name cannot be blank.")
        if self.email is not None:
            self.email = self.email.strip() or None
        for field in ("phone", "whatsapp", "address"):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, value.strip() or None)
        self.notes = self.notes.strip()
        return self


class OpeningBalanceFields(BaseModel):
    opening_balance: NonnegativeMoney = Decimal("0.00")
    opening_balance_date: date | None = None
    opening_balance_notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_opening_balance(self) -> "OpeningBalanceFields":
        if self.opening_balance_notes is not None:
            self.opening_balance_notes = self.opening_balance_notes.strip()
        if self.opening_balance > 0:
            if self.opening_balance_date is None:
                raise ValueError("An effective date is required for an opening balance.")
            if self.opening_balance_notes is None or not self.opening_balance_notes.strip():
                raise ValueError("Source notes are required for an opening balance.")
            self.opening_balance_notes = self.opening_balance_notes.strip()
        return self


class CustomerCreate(CustomerFields, OpeningBalanceFields):
    model_config = ConfigDict(extra="forbid")


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    whatsapp: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    customer_type: Literal["retail", "wholesale", "both"] | None = None
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None

    @model_validator(mode="after")
    def clean_text(self) -> "CustomerUpdate":
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Customer name cannot be blank.")
        if self.email is not None:
            self.email = self.email.strip() or None
        for field in ("phone", "whatsapp", "address"):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, value.strip() or None)
        if self.notes is not None:
            self.notes = self.notes.strip()
        return self


class OpeningBalanceResponse(BaseModel):
    amount: Decimal
    effective_date: date
    source_notes: str

    model_config = ConfigDict(from_attributes=True)


class OpeningBalanceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    effective_date: date
    source_notes: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def clean_source_notes(self) -> "OpeningBalanceCreate":
        self.source_notes = self.source_notes.strip()
        if not self.source_notes:
            raise ValueError("Source notes are required.")
        return self


class CustomerResponse(BaseModel):
    id: str
    name: str
    phone: str | None
    whatsapp: str | None
    email: EmailStr | None
    address: str | None
    customer_type: str
    notes: str
    is_active: bool
    opening_balances: list[OpeningBalanceResponse]
    opening_balance_total: Decimal
    created_at: datetime


class SupplierFields(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    contact_person: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    notes: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def clean_text(self) -> "SupplierFields":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Supplier name cannot be blank.")
        if self.email is not None:
            self.email = self.email.strip() or None
        for field in ("contact_person", "phone", "address"):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, value.strip() or None)
        self.notes = self.notes.strip()
        return self


class SupplierCreate(SupplierFields, OpeningBalanceFields):
    model_config = ConfigDict(extra="forbid")


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    contact_person: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None

    @model_validator(mode="after")
    def clean_text(self) -> "SupplierUpdate":
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Supplier name cannot be blank.")
        if self.email is not None:
            self.email = self.email.strip() or None
        for field in ("contact_person", "phone", "address"):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, value.strip() or None)
        if self.notes is not None:
            self.notes = self.notes.strip()
        return self


class SupplierResponse(BaseModel):
    id: str
    name: str
    contact_person: str | None
    phone: str | None
    email: EmailStr | None
    address: str | None
    payment_terms_days: int | None
    notes: str
    is_active: bool
    opening_balances: list[OpeningBalanceResponse]
    opening_balance_total: Decimal
    created_at: str


class UnitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,39}$")
    name: str = Field(min_length=1, max_length=80)
    abbreviation: str = Field(min_length=1, max_length=16)
    decimal_places: int = Field(ge=0, le=3)

    @model_validator(mode="after")
    def clean_text(self) -> "UnitCreate":
        self.id = self.id.strip().lower()
        self.name = self.name.strip()
        self.abbreviation = self.abbreviation.strip()
        if not self.name or not self.abbreviation:
            raise ValueError("Unit name and abbreviation cannot be blank.")
        return self


class UnitResponse(BaseModel):
    id: str
    name: str
    abbreviation: str
    decimal_places: int

    model_config = ConfigDict(from_attributes=True)


class UnitConversionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_unit_id: str = Field(min_length=1, max_length=40)
    to_unit_id: str = Field(min_length=1, max_length=40)
    factor: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=6)]


class UnitConversionResponse(BaseModel):
    id: str
    from_unit_id: str
    to_unit_id: str
    factor: Decimal

    model_config = ConfigDict(from_attributes=True)


class ProductCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def clean_text(self) -> "ProductCategoryCreate":
        self.name = self.name.strip()
        self.description = self.description.strip()
        if not self.name:
            raise ValueError("Category name cannot be blank.")
        return self


class ProductCategoryResponse(BaseModel):
    id: str
    name: str
    description: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProductPriceTierInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_type: Literal["retail", "wholesale"]
    minimum_quantity: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
    unit_price: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class ProductFields(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=1, max_length=80)
    barcode: str | None = Field(default=None, max_length=80)
    category_id: str | None = Field(default=None, max_length=36)
    description: str = Field(default="", max_length=5000)
    unit_id: str = Field(min_length=1, max_length=40)
    supplier_id: str | None = Field(default=None, max_length=36)
    purchase_cost: Money
    retail_price: Money
    wholesale_price: Money
    minimum_stock: NonnegativeQuantity = Decimal("0")
    price_tiers: list[ProductPriceTierInput] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def clean_text_and_tiers(self) -> "ProductFields":
        self.name = self.name.strip()
        self.sku = self.sku.strip().upper()
        self.unit_id = self.unit_id.strip()
        self.category_id = _strip_optional(self.category_id)
        self.supplier_id = _strip_optional(self.supplier_id)
        if self.barcode is not None:
            self.barcode = self.barcode.strip() or None
        self.description = self.description.strip()
        if not self.name or not self.sku:
            raise ValueError("Product name and SKU cannot be blank.")
        keys = [(tier.price_type, tier.minimum_quantity) for tier in self.price_tiers]
        if len(set(keys)) != len(keys):
            raise ValueError("Price tiers must have unique quantities for each price type.")
        return self


class ProductCreate(ProductFields):
    model_config = ConfigDict(extra="forbid")

    opening_stock: NonnegativeQuantity = Decimal("0")
    opening_stock_reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def require_opening_reason(self) -> "ProductCreate":
        if self.opening_stock > 0:
            if self.opening_stock_reason is None or not self.opening_stock_reason.strip():
                raise ValueError("A reason is required when recording opening stock.")
            self.opening_stock_reason = self.opening_stock_reason.strip()
        return self


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    barcode: str | None = Field(default=None, max_length=80)
    category_id: str | None = Field(default=None, max_length=36)
    description: str | None = Field(default=None, max_length=5000)
    unit_id: str | None = Field(default=None, min_length=1, max_length=40)
    supplier_id: str | None = Field(default=None, max_length=36)
    purchase_cost: Money | None = None
    retail_price: Money | None = None
    wholesale_price: Money | None = None
    minimum_stock: NonnegativeQuantity | None = None
    is_active: bool | None = None
    price_tiers: list[ProductPriceTierInput] | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def clean_text_and_tiers(self) -> "ProductUpdate":
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Product name cannot be blank.")
        if self.sku is not None:
            self.sku = self.sku.strip().upper()
            if not self.sku:
                raise ValueError("Product SKU cannot be blank.")
        if self.barcode is not None:
            self.barcode = self.barcode.strip() or None
        if self.category_id is not None:
            self.category_id = self.category_id.strip() or None
        if self.supplier_id is not None:
            self.supplier_id = self.supplier_id.strip() or None
        if self.unit_id is not None:
            self.unit_id = self.unit_id.strip()
            if not self.unit_id:
                raise ValueError("Unit ID cannot be blank.")
        if self.description is not None:
            self.description = self.description.strip()
        if self.price_tiers is not None:
            keys = [(tier.price_type, tier.minimum_quantity) for tier in self.price_tiers]
            if len(set(keys)) != len(keys):
                raise ValueError("Price tiers must have unique quantities for each price type.")
        return self


class ProductPriceTierResponse(BaseModel):
    price_type: str
    minimum_quantity: Decimal
    unit_price: Decimal


class ProductResponse(BaseModel):
    id: str
    name: str
    sku: str
    barcode: str | None
    category_id: str | None
    category_name: str | None
    description: str
    unit_id: str
    unit_name: str
    unit_abbreviation: str
    unit_decimal_places: int
    supplier_id: str | None
    supplier_name: str | None
    purchase_cost: Decimal
    retail_price: Decimal
    wholesale_price: Decimal
    minimum_stock: Decimal
    stock_quantity: Decimal
    is_low_stock: bool
    is_active: bool
    price_tiers: list[ProductPriceTierResponse]
    created_at: str


class StockMovementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    movement_type: Literal["adjustment", "damage"]
    quantity_delta: Quantity
    reason: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_movement(self) -> "StockMovementCreate":
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError("A reason is required for a stock movement.")
        if self.quantity_delta == 0:
            raise ValueError("Stock movement quantity cannot be zero.")
        if self.movement_type == "damage" and self.quantity_delta >= 0:
            raise ValueError("Damaged stock must be recorded as a decrease.")
        return self


class StockMovementResponse(BaseModel):
    id: str
    product_id: str
    movement_type: str
    quantity_delta: Decimal
    reason: str
    created_by: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
