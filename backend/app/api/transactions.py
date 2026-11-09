from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import (
    AccountPayment,
    AuditLog,
    BusinessSettings,
    Customer,
    CustomerOpeningBalance,
    Expense,
    InventoryBalance,
    Payment,
    Product,
    Purchase,
    PurchaseLine,
    Sale,
    SaleLine,
    StockMovement,
    Supplier,
    SupplierOpeningBalance,
    User,
    utc_now,
)
from app.permissions import require_csrf, require_permission
from app.transaction_schemas import (
    AccountPaymentResponse,
    ExpenseCreate,
    ExpenseResponse,
    PaymentCreate,
    PaymentResponse,
    PurchaseCreate,
    PurchaseLineResponse,
    PurchaseResponse,
    SaleCreate,
    SaleLineResponse,
    SaleResponse,
)

router = APIRouter(tags=["transactions"])
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def quantity_matches_unit(quantity: Decimal, unit) -> bool:
    precision = Decimal(1).scaleb(-unit.decimal_places)
    return quantity == quantity.quantize(precision)


def payment_total(payments: list[Payment]) -> Decimal:
    return sum((payment.amount for payment in payments), ZERO)


def sale_query():
    return select(Sale).options(selectinload(Sale.lines), selectinload(Sale.payments))


def purchase_query():
    return select(Purchase).options(selectinload(Purchase.lines), selectinload(Purchase.payments))


def sale_response(sale: Sale) -> SaleResponse:
    paid = payment_total(sale.payments)
    return SaleResponse(
        id=sale.id,
        invoice_number=sale.invoice_number,
        customer_id=sale.customer_id,
        customer_name=sale.customer.name if sale.customer else None,
        sale_type=sale.sale_type,
        sale_date=sale.sale_date,
        due_date=sale.due_date,
        lines=[
            SaleLineResponse(
                product_id=line.product_id,
                product_name=line.product_name,
                sku=line.sku,
                unit_name=line.unit_name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.line_total,
            )
            for line in sale.lines
        ],
        total_amount=sale.total_amount,
        amount_paid=paid,
        balance_due=sale.total_amount - paid,
        payments=[PaymentResponse.model_validate(payment) for payment in sale.payments],
        notes=sale.notes,
        created_at=sale.created_at,
    )


def purchase_response(purchase: Purchase) -> PurchaseResponse:
    paid = payment_total(purchase.payments)
    return PurchaseResponse(
        id=purchase.id,
        purchase_number=purchase.purchase_number,
        supplier_id=purchase.supplier_id,
        supplier_name=purchase.supplier.name if purchase.supplier else None,
        supplier_reference=purchase.supplier_reference,
        purchase_date=purchase.purchase_date,
        lines=[
            PurchaseLineResponse(
                product_id=line.product_id,
                product_name=line.product_name,
                sku=line.sku,
                unit_name=line.unit_name,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                line_total=line.line_total,
            )
            for line in purchase.lines
        ],
        total_amount=purchase.total_amount,
        amount_paid=paid,
        balance_due=purchase.total_amount - paid,
        payments=[PaymentResponse.model_validate(payment) for payment in purchase.payments],
        notes=purchase.notes,
        created_at=purchase.created_at,
    )


def require_payment_permission(actor: User) -> None:
    if "payments:create" not in {permission.id for permission in actor.role.permissions}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to record payments.",
        )


def validate_method(db: Session, method: str) -> None:
    business_settings = db.get(BusinessSettings, 1)
    methods = business_settings.payment_methods if business_settings else []
    if method not in methods:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Choose a payment method configured in business settings.",
        )


def get_products(
    db: Session,
    product_ids: list[str],
) -> dict[str, Product]:
    products = db.scalars(
        select(Product)
        .where(Product.id.in_(product_ids))
        .options(selectinload(Product.price_tiers), selectinload(Product.inventory_balance))
    ).all()
    result = {product.id: product for product in products}
    if len(result) != len(product_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more selected products could not be found.",
        )
    inactive = [product.name for product in products if not product.is_active]
    if inactive:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Inactive products cannot be transacted: {', '.join(inactive)}.",
        )
    return result


def lock_balances(db: Session, product_ids: list[str]) -> dict[str, InventoryBalance]:
    balances = db.scalars(
        select(InventoryBalance)
        .where(InventoryBalance.product_id.in_(product_ids))
        .order_by(InventoryBalance.product_id)
        .with_for_update()
    ).all()
    return {balance.product_id: balance for balance in balances}


def add_payment(
    db: Session,
    actor: User,
    amount: Decimal,
    method: str,
    sale: Sale | None = None,
    purchase: Purchase | None = None,
    reference: str | None = None,
    notes: str = "",
) -> Payment:
    validate_method(db, method)
    payment = Payment(
        sale_id=sale.id if sale else None,
        purchase_id=purchase.id if purchase else None,
        amount=amount,
        method=method,
        reference=reference,
        notes=notes,
        created_by=actor.id,
    )
    db.add(payment)
    return payment


def add_payment_audit(
    db: Session, actor: User, payment: Payment, entity_type: str, entity_id: str
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action=f"{entity_type}.payment",
            entity_type=entity_type,
            entity_id=entity_id,
            details={"amount": str(payment.amount), "method": payment.method},
        )
    )


def add_account_payment(
    db: Session,
    actor: User,
    payload: PaymentCreate,
    *,
    customer_id: str | None = None,
    supplier_id: str | None = None,
) -> AccountPayment:
    validate_method(db, payload.method)
    payment = AccountPayment(
        customer_id=customer_id,
        supplier_id=supplier_id,
        amount=payload.amount,
        method=payload.method,
        reference=payload.reference,
        notes=payload.notes,
        created_by=actor.id,
    )
    db.add(payment)
    return payment


@router.get("/sales", response_model=list[SaleResponse])
def list_sales(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales:read")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SaleResponse]:
    sales = db.scalars(
        sale_query()
        .order_by(Sale.sale_date.desc(), Sale.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [sale_response(sale) for sale in sales]


@router.get("/sales/{sale_id}", response_model=SaleResponse)
def get_sale(
    sale_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales:read")),
) -> SaleResponse:
    sale = db.scalar(sale_query().where(Sale.id == sale_id))
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found.")
    return sale_response(sale)


@router.post("/sales", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale(
    payload: SaleCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales:create")),
    _: User = Depends(require_csrf),
) -> SaleResponse:
    if payload.payment_amount > 0:
        require_payment_permission(actor)
        validate_method(db, payload.payment_method)
    if payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if customer is None or not customer.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Select an active customer.",
            )
        if payload.sale_type == "wholesale" and customer.customer_type == "retail":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This customer is configured for retail sales only.",
            )

    product_ids = sorted(line.product_id for line in payload.lines)
    products = get_products(db, product_ids)
    balances = lock_balances(db, product_ids)
    lines: list[SaleLine] = []
    total = ZERO
    for item in payload.lines:
        product = products[item.product_id]
        if not quantity_matches_unit(item.quantity, product.unit):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{product.name} supports at most {product.unit.decimal_places} decimal places."
                ),
            )
        available = balances[product.id].quantity if product.id in balances else ZERO
        if available < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient stock for {product.name}; available: {available}.",
            )
        unit_price = (
            product.retail_price if payload.sale_type == "retail" else product.wholesale_price
        )
        eligible_tiers = [
            tier
            for tier in product.price_tiers
            if tier.price_type == payload.sale_type and item.quantity >= tier.minimum_quantity
        ]
        if eligible_tiers:
            unit_price = max(eligible_tiers, key=lambda tier: tier.minimum_quantity).unit_price
        line_total = (item.quantity * unit_price).quantize(CENT)
        total += line_total
        lines.append(
            SaleLine(
                product_id=product.id,
                product_name=product.name,
                sku=product.sku,
                unit_name=product.unit.name,
                quantity=item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
    total = total.quantize(CENT)
    if total <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A sale total must be greater than zero.",
        )
    if payload.payment_amount > total:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The payment cannot exceed the sale total.",
        )
    sale_id = str(uuid4())
    sale = Sale(
        id=sale_id,
        invoice_number=f"INV-{sale_id[:8].upper()}",
        customer_id=payload.customer_id,
        sale_type=payload.sale_type,
        sale_date=payload.sale_date,
        due_date=payload.due_date or payload.sale_date,
        total_amount=total,
        notes=payload.notes,
        created_by=actor.id,
        lines=lines,
    )
    db.add(sale)
    for item in payload.lines:
        balance = balances.get(item.product_id)
        if balance is None:
            balance = InventoryBalance(
                product_id=item.product_id,
                quantity=Decimal("0"),
            )
            db.add(balance)
            balances[item.product_id] = balance
        balance.quantity -= item.quantity
        balance.updated_at = utc_now()
        db.add(
            StockMovement(
                product_id=item.product_id,
                movement_type="sale",
                quantity_delta=-item.quantity,
                reason=f"Sale {sale.invoice_number}",
                created_by=actor.id,
            )
        )
    if payload.payment_amount > 0:
        payment = add_payment(
            db,
            actor,
            payload.payment_amount,
            payload.payment_method,
            sale=sale,
            reference=payload.payment_reference,
        )
        add_payment_audit(db, actor, payment, "sale", sale.id)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="sale.create",
            entity_type="sale",
            entity_id=sale.id,
            details={
                "invoice_number": sale.invoice_number,
                "total_amount": str(total),
                "customer_id": sale.customer_id,
            },
        )
    )
    try:
        db.commit()
        sale = db.scalar(sale_query().where(Sale.id == sale.id))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The sale could not be recorded because a record constraint was violated.",
        ) from exc
    return sale_response(sale)


@router.post(
    "/sales/{sale_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_sale_payment(
    sale_id: str,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payments:create")),
    _: User = Depends(require_csrf),
) -> PaymentResponse:
    sale = db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found.")
    if sale.customer_id is not None:
        db.scalar(select(Customer.id).where(Customer.id == sale.customer_id).with_for_update())
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.sale_id == sale.id)
    )
    if payload.amount > sale.total_amount - paid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The payment exceeds the outstanding invoice balance.",
        )
    payment = add_payment(
        db,
        actor,
        payload.amount,
        payload.method,
        sale=sale,
        reference=payload.reference,
        notes=payload.notes,
    )
    add_payment_audit(db, actor, payment, "sale", sale.id)
    try:
        db.commit()
        db.refresh(payment)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The payment could not be recorded.",
        ) from exc
    return PaymentResponse.model_validate(payment)


@router.get("/purchases", response_model=list[PurchaseResponse])
def list_purchases(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchases:read")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[PurchaseResponse]:
    purchases = db.scalars(
        purchase_query()
        .order_by(Purchase.purchase_date.desc(), Purchase.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [purchase_response(purchase) for purchase in purchases]


@router.post("/purchases", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
def create_purchase(
    payload: PurchaseCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("purchases:create")),
    _: User = Depends(require_csrf),
) -> PurchaseResponse:
    if payload.payment_amount > 0:
        require_payment_permission(actor)
        validate_method(db, payload.payment_method)
    if payload.supplier_id is not None:
        supplier = db.get(Supplier, payload.supplier_id)
        if supplier is None or not supplier.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Select an active supplier.",
            )

    product_ids = sorted(line.product_id for line in payload.lines)
    products = get_products(db, product_ids)
    balances = lock_balances(db, product_ids)
    purchase_lines: list[PurchaseLine] = []
    total = ZERO
    for item in payload.lines:
        product = products[item.product_id]
        if not quantity_matches_unit(item.quantity, product.unit):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{product.name} supports at most {product.unit.decimal_places} decimal places."
                ),
            )
        line_total = (item.quantity * item.unit_cost).quantize(CENT)
        total += line_total
        purchase_lines.append(
            PurchaseLine(
                product_id=product.id,
                product_name=product.name,
                sku=product.sku,
                unit_name=product.unit.name,
                quantity=item.quantity,
                unit_cost=item.unit_cost,
                line_total=line_total,
            )
        )
    total = total.quantize(CENT)
    if total <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A purchase total must be greater than zero.",
        )
    if payload.payment_amount > total:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The payment cannot exceed the purchase total.",
        )
    purchase_id = str(uuid4())
    purchase = Purchase(
        id=purchase_id,
        purchase_number=f"PUR-{purchase_id[:8].upper()}",
        supplier_id=payload.supplier_id,
        supplier_reference=payload.supplier_reference,
        purchase_date=payload.purchase_date,
        total_amount=total,
        notes=payload.notes,
        created_by=actor.id,
        lines=purchase_lines,
    )
    db.add(purchase)
    for item in payload.lines:
        product = products[item.product_id]
        balance = balances.get(item.product_id)
        if balance is None:
            balance = InventoryBalance(
                product_id=item.product_id,
                quantity=Decimal("0"),
            )
            db.add(balance)
            balances[item.product_id] = balance
        balance.quantity += item.quantity
        balance.updated_at = utc_now()
        product.purchase_cost = item.unit_cost
        db.add(
            StockMovement(
                product_id=item.product_id,
                movement_type="purchase",
                quantity_delta=item.quantity,
                reason=f"Purchase {purchase.purchase_number}",
                created_by=actor.id,
            )
        )
    if payload.payment_amount > 0:
        payment = add_payment(
            db,
            actor,
            payload.payment_amount,
            payload.payment_method,
            purchase=purchase,
            reference=payload.payment_reference,
        )
        add_payment_audit(db, actor, payment, "purchase", purchase.id)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="purchase.create",
            entity_type="purchase",
            entity_id=purchase.id,
            details={
                "purchase_number": purchase.purchase_number,
                "total_amount": str(total),
                "supplier_id": purchase.supplier_id,
            },
        )
    )
    try:
        db.commit()
        purchase = db.scalar(purchase_query().where(Purchase.id == purchase.id))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The purchase could not be recorded because a record constraint was violated.",
        ) from exc
    return purchase_response(purchase)


@router.post(
    "/purchases/{purchase_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_purchase_payment(
    purchase_id: str,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payments:create")),
    _: User = Depends(require_csrf),
) -> PaymentResponse:
    purchase = db.scalar(select(Purchase).where(Purchase.id == purchase_id).with_for_update())
    if purchase is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase not found.")
    if purchase.supplier_id is not None:
        db.scalar(select(Supplier.id).where(Supplier.id == purchase.supplier_id).with_for_update())
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.purchase_id == purchase.id)
    )
    if payload.amount > purchase.total_amount - paid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The payment exceeds the outstanding purchase balance.",
        )
    payment = add_payment(
        db,
        actor,
        payload.amount,
        payload.method,
        purchase=purchase,
        reference=payload.reference,
        notes=payload.notes,
    )
    add_payment_audit(db, actor, payment, "purchase", purchase.id)
    try:
        db.commit()
        db.refresh(payment)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The payment could not be recorded.",
        ) from exc
    return PaymentResponse.model_validate(payment)


@router.post(
    "/customers/{customer_id}/payments",
    response_model=AccountPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_customer_account_payment(
    customer_id: str,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payments:create")),
    _: User = Depends(require_csrf),
) -> AccountPaymentResponse:
    customer = db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    opening_balance = db.scalar(
        select(func.coalesce(func.sum(CustomerOpeningBalance.amount), 0)).where(
            CustomerOpeningBalance.customer_id == customer.id
        )
    )
    sales_total = db.scalar(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(Sale.customer_id == customer.id)
    )
    invoice_payments = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Sale, Payment.sale_id == Sale.id)
        .where(Sale.customer_id == customer.id)
    )
    account_payments = db.scalar(
        select(func.coalesce(func.sum(AccountPayment.amount), 0)).where(
            AccountPayment.customer_id == customer.id
        )
    )
    outstanding = opening_balance + sales_total - invoice_payments - account_payments
    if outstanding <= 0 or payload.amount > outstanding:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The payment exceeds the customer's outstanding balance.",
        )
    payment = add_account_payment(db, actor, payload, customer_id=customer.id)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="customer.account_payment",
            entity_type="customer",
            entity_id=customer.id,
            details={"amount": str(payment.amount), "method": payment.method},
        )
    )
    db.commit()
    db.refresh(payment)
    return AccountPaymentResponse.model_validate(payment)


@router.post(
    "/suppliers/{supplier_id}/payments",
    response_model=AccountPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_supplier_account_payment(
    supplier_id: str,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payments:create")),
    _: User = Depends(require_csrf),
) -> AccountPaymentResponse:
    supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id).with_for_update())
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
    opening_balance = db.scalar(
        select(func.coalesce(func.sum(SupplierOpeningBalance.amount), 0)).where(
            SupplierOpeningBalance.supplier_id == supplier.id
        )
    )
    purchases_total = db.scalar(
        select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
            Purchase.supplier_id == supplier.id
        )
    )
    invoice_payments = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Purchase, Payment.purchase_id == Purchase.id)
        .where(Purchase.supplier_id == supplier.id)
    )
    account_payments = db.scalar(
        select(func.coalesce(func.sum(AccountPayment.amount), 0)).where(
            AccountPayment.supplier_id == supplier.id
        )
    )
    outstanding = opening_balance + purchases_total - invoice_payments - account_payments
    if outstanding <= 0 or payload.amount > outstanding:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The payment exceeds the supplier's outstanding balance.",
        )
    payment = add_account_payment(db, actor, payload, supplier_id=supplier.id)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="supplier.account_payment",
            entity_type="supplier",
            entity_id=supplier.id,
            details={"amount": str(payment.amount), "method": payment.method},
        )
    )
    db.commit()
    db.refresh(payment)
    return AccountPaymentResponse.model_validate(payment)


@router.get("/expenses", response_model=list[ExpenseResponse])
def list_expenses(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("expenses:read")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ExpenseResponse]:
    return db.scalars(
        select(Expense)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()


@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("expenses:create")),
    _: User = Depends(require_csrf),
) -> ExpenseResponse:
    validate_method(db, payload.method)
    expense = Expense(
        id=str(uuid4()),
        category=payload.category,
        description=payload.description,
        amount=payload.amount,
        expense_date=payload.expense_date,
        method=payload.method,
        reference=payload.reference,
        notes=payload.notes,
        created_by=actor.id,
    )
    db.add(expense)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="expense.create",
            entity_type="expense",
            entity_id=expense.id,
            details={"amount": str(expense.amount), "category": expense.category},
        )
    )
    db.commit()
    db.refresh(expense)
    return ExpenseResponse.model_validate(expense)


@router.get("/reports/summary")
def report_summary(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
) -> dict[str, object]:
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The start date must be on or before the end date.",
        )
    sales_total = db.scalar(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
            Sale.sale_date.between(from_date, to_date)
        )
    )
    purchases_total = db.scalar(
        select(func.coalesce(func.sum(Purchase.total_amount), 0)).where(
            Purchase.purchase_date.between(from_date, to_date)
        )
    )
    expenses_total = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.expense_date.between(from_date, to_date)
        )
    )
    payments_received = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.sale_id.is_not(None),
            func.date(Payment.received_at).between(from_date, to_date),
        )
    )
    payments_received += db.scalar(
        select(func.coalesce(func.sum(AccountPayment.amount), 0)).where(
            AccountPayment.customer_id.is_not(None),
            func.date(AccountPayment.received_at).between(from_date, to_date),
        )
    )
    payments_made = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.purchase_id.is_not(None),
            func.date(Payment.received_at).between(from_date, to_date),
        )
    )
    payments_made += db.scalar(
        select(func.coalesce(func.sum(AccountPayment.amount), 0)).where(
            AccountPayment.supplier_id.is_not(None),
            func.date(AccountPayment.received_at).between(from_date, to_date),
        )
    )
    low_stock_count = db.scalar(
        select(func.count())
        .select_from(InventoryBalance)
        .join(Product, Product.id == InventoryBalance.product_id)
        .where(
            Product.is_active.is_(True),
            Product.minimum_stock > 0,
            InventoryBalance.quantity <= Product.minimum_stock,
        )
    )
    return {
        "from_date": from_date,
        "to_date": to_date,
        "sales_total": str(sales_total),
        "payments_received": str(payments_received),
        "purchases_total": str(purchases_total),
        "payments_made": str(payments_made),
        "expenses_total": str(expenses_total),
        "low_stock_count": low_stock_count,
    }


@router.get("/reports/outstanding")
def report_outstanding(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
) -> dict[str, list[dict[str, object]]]:
    customer_records = db.execute(
        select(Customer.id, Customer.name)
        .where(Customer.is_active.is_(True))
        .order_by(Customer.name, Customer.id)
    ).all()
    customer_openings = dict(
        db.execute(
            select(
                CustomerOpeningBalance.customer_id, func.sum(CustomerOpeningBalance.amount)
            ).group_by(CustomerOpeningBalance.customer_id)
        ).all()
    )
    customer_sales = dict(
        db.execute(
            select(Sale.customer_id, func.sum(Sale.total_amount))
            .where(Sale.customer_id.is_not(None))
            .group_by(Sale.customer_id)
        ).all()
    )
    customer_payments = dict(
        db.execute(
            select(Sale.customer_id, func.sum(Payment.amount))
            .join(Sale, Payment.sale_id == Sale.id)
            .where(Sale.customer_id.is_not(None))
            .group_by(Sale.customer_id)
        ).all()
    )
    customer_account_payments = dict(
        db.execute(
            select(AccountPayment.customer_id, func.sum(AccountPayment.amount))
            .where(AccountPayment.customer_id.is_not(None))
            .group_by(AccountPayment.customer_id)
        ).all()
    )
    customers = []
    for customer_id, name in customer_records:
        balance = (
            customer_openings.get(customer_id, ZERO)
            + customer_sales.get(customer_id, ZERO)
            - customer_payments.get(customer_id, ZERO)
            - customer_account_payments.get(customer_id, ZERO)
        )
        if balance > 0:
            customers.append({"id": customer_id, "name": name, "balance_due": balance})

    supplier_records = db.execute(
        select(Supplier.id, Supplier.name)
        .where(Supplier.is_active.is_(True))
        .order_by(Supplier.name, Supplier.id)
    ).all()
    supplier_openings = dict(
        db.execute(
            select(
                SupplierOpeningBalance.supplier_id, func.sum(SupplierOpeningBalance.amount)
            ).group_by(SupplierOpeningBalance.supplier_id)
        ).all()
    )
    supplier_purchases = dict(
        db.execute(
            select(Purchase.supplier_id, func.sum(Purchase.total_amount))
            .where(Purchase.supplier_id.is_not(None))
            .group_by(Purchase.supplier_id)
        ).all()
    )
    supplier_payments = dict(
        db.execute(
            select(Purchase.supplier_id, func.sum(Payment.amount))
            .join(Purchase, Payment.purchase_id == Purchase.id)
            .where(Purchase.supplier_id.is_not(None))
            .group_by(Purchase.supplier_id)
        ).all()
    )
    supplier_account_payments = dict(
        db.execute(
            select(AccountPayment.supplier_id, func.sum(AccountPayment.amount))
            .where(AccountPayment.supplier_id.is_not(None))
            .group_by(AccountPayment.supplier_id)
        ).all()
    )
    suppliers = []
    for supplier_id, name in supplier_records:
        balance = (
            supplier_openings.get(supplier_id, ZERO)
            + supplier_purchases.get(supplier_id, ZERO)
            - supplier_payments.get(supplier_id, ZERO)
            - supplier_account_payments.get(supplier_id, ZERO)
        )
        if balance > 0:
            suppliers.append({"id": supplier_id, "name": name, "balance_due": balance})
    return {"customer_balances": customers, "supplier_balances": suppliers}
