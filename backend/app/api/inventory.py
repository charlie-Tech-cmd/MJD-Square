from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import (
    AuditLog,
    InventoryBalance,
    Product,
    ProductCategory,
    ProductPriceTier,
    StockMovement,
    Supplier,
    UnitConversion,
    UnitOfMeasure,
    User,
    utc_now,
)
from app.permissions import require_csrf, require_permission
from app.record_schemas import (
    ProductCategoryCreate,
    ProductCategoryResponse,
    ProductCreate,
    ProductPriceTierInput,
    ProductPriceTierResponse,
    ProductResponse,
    ProductUpdate,
    StockMovementCreate,
    StockMovementResponse,
    UnitConversionCreate,
    UnitConversionResponse,
    UnitCreate,
    UnitResponse,
)

router = APIRouter(tags=["products and inventory"])


def product_query():
    return select(Product).options(
        selectinload(Product.price_tiers),
        selectinload(Product.inventory_balance),
    )


def get_product_or_404(db: Session, product_id: str) -> Product:
    product = db.scalar(product_query().where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product


def product_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        name=product.name,
        sku=product.sku,
        barcode=product.barcode,
        category_id=product.category_id,
        category_name=product.category.name if product.category else None,
        description=product.description,
        unit_id=product.unit_id,
        unit_name=product.unit.name,
        unit_abbreviation=product.unit.abbreviation,
        unit_decimal_places=product.unit.decimal_places,
        supplier_id=product.supplier_id,
        supplier_name=product.supplier.name if product.supplier else None,
        purchase_cost=product.purchase_cost,
        retail_price=product.retail_price,
        wholesale_price=product.wholesale_price,
        minimum_stock=product.minimum_stock,
        stock_quantity=(
            product.inventory_balance.quantity if product.inventory_balance else Decimal("0")
        ),
        is_low_stock=(
            product.minimum_stock > 0
            and (
                product.inventory_balance is None
                or product.inventory_balance.quantity <= product.minimum_stock
            )
        ),
        is_active=product.is_active,
        price_tiers=[
            ProductPriceTierResponse(
                price_type=tier.price_type,
                minimum_quantity=tier.minimum_quantity,
                unit_price=tier.unit_price,
            )
            for tier in product.price_tiers
        ],
        created_at=product.created_at.isoformat(),
    )


def validate_references(
    db: Session,
    unit_id: str | None,
    category_id: str | None,
    supplier_id: str | None,
) -> None:
    if unit_id is not None and db.get(UnitOfMeasure, unit_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select a valid unit of measure.",
        )
    if category_id is not None and db.get(ProductCategory, category_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select a valid product category.",
        )
    if supplier_id is not None and db.get(Supplier, supplier_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select a valid supplier.",
        )


def set_price_tiers(product: Product, tiers: list[ProductPriceTierInput]) -> None:
    product.price_tiers = [
        ProductPriceTier(
            price_type=tier.price_type,
            minimum_quantity=tier.minimum_quantity,
            unit_price=tier.unit_price,
        )
        for tier in tiers
    ]


def quantity_matches_unit(quantity: Decimal, unit: UnitOfMeasure) -> bool:
    precision = Decimal(1).scaleb(-unit.decimal_places)
    return quantity == quantity.quantize(precision)


def add_stock_movement(
    db: Session,
    product: Product,
    quantity_delta: Decimal,
    movement_type: str,
    reason: str,
    actor: User,
) -> StockMovement:
    if not quantity_matches_unit(abs(quantity_delta), product.unit):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This unit supports at most {product.unit.decimal_places} decimal places.",
        )
    balance = db.scalar(
        select(InventoryBalance).where(InventoryBalance.product_id == product.id).with_for_update()
    )
    if balance is None:
        balance = InventoryBalance(product_id=product.id, quantity=Decimal("0"))
        db.add(balance)
        db.flush()
    updated_quantity = balance.quantity + quantity_delta
    if updated_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The movement would reduce stock below zero.",
        )
    balance.quantity = updated_quantity
    balance.updated_at = utc_now()
    movement = StockMovement(
        product_id=product.id,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        reason=reason,
        created_by=actor.id,
    )
    db.add(movement)
    return movement


@router.get("/units", response_model=list[UnitResponse])
def list_units(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:read")),
) -> list[UnitOfMeasure]:
    return db.scalars(select(UnitOfMeasure).order_by(UnitOfMeasure.name)).all()


@router.post("/units", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
def create_unit(
    payload: UnitCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory:manage")),
    _: User = Depends(require_csrf),
) -> UnitOfMeasure:
    unit = UnitOfMeasure(
        id=payload.id,
        name=payload.name,
        abbreviation=payload.abbreviation,
        decimal_places=payload.decimal_places,
    )
    db.add(unit)
    try:
        db.add(
            AuditLog(
                actor_user_id=actor.id,
                action="unit.create",
                entity_type="unit_of_measure",
                entity_id=unit.id,
                details={},
            )
        )
        db.commit()
        db.refresh(unit)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A unit with that identifier, name, or abbreviation already exists.",
        ) from exc
    return unit


@router.get("/unit-conversions", response_model=list[UnitConversionResponse])
def list_unit_conversions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:read")),
) -> list[UnitConversion]:
    return db.scalars(
        select(UnitConversion).order_by(UnitConversion.from_unit_id, UnitConversion.to_unit_id)
    ).all()


@router.post(
    "/unit-conversions",
    response_model=UnitConversionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_unit_conversion(
    payload: UnitConversionCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory:manage")),
    _: User = Depends(require_csrf),
) -> UnitConversion:
    if payload.from_unit_id == payload.to_unit_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A unit conversion must use two different units.",
        )
    validate_references(db, payload.from_unit_id, None, None)
    validate_references(db, payload.to_unit_id, None, None)
    conversion = UnitConversion(
        from_unit_id=payload.from_unit_id,
        to_unit_id=payload.to_unit_id,
        factor=payload.factor,
    )
    db.add(conversion)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="unit_conversion.create",
            entity_type="unit_conversion",
            entity_id=conversion.id,
            details={
                "from_unit_id": payload.from_unit_id,
                "to_unit_id": payload.to_unit_id,
                "factor": str(payload.factor),
            },
        )
    )
    try:
        db.commit()
        db.refresh(conversion)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That unit conversion already exists.",
        ) from exc
    return conversion


@router.get("/product-categories", response_model=list[ProductCategoryResponse])
def list_product_categories(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:read")),
) -> list[ProductCategory]:
    return db.scalars(select(ProductCategory).order_by(ProductCategory.name)).all()


@router.post(
    "/product-categories",
    response_model=ProductCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product_category(
    payload: ProductCategoryCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory:manage")),
    _: User = Depends(require_csrf),
) -> ProductCategory:
    category = ProductCategory(name=payload.name, description=payload.description)
    db.add(category)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="product_category.create",
            entity_type="product_category",
            entity_id=category.id,
            details={"name": category.name},
        )
    )
    try:
        db.commit()
        db.refresh(category)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product category with that name already exists.",
        ) from exc
    return category


@router.get("/products", response_model=list[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:read")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ProductResponse]:
    products = db.scalars(
        product_query().order_by(Product.name, Product.id).limit(limit).offset(offset)
    ).all()
    return [product_response(product) for product in products]


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory:manage")),
    _: User = Depends(require_csrf),
) -> ProductResponse:
    validate_references(db, payload.unit_id, payload.category_id, payload.supplier_id)
    unit = db.get(UnitOfMeasure, payload.unit_id)
    if unit is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select a valid unit of measure.",
        )
    quantities = [payload.minimum_stock, payload.opening_stock]
    quantities.extend(tier.minimum_quantity for tier in payload.price_tiers)
    if any(not quantity_matches_unit(quantity, unit) for quantity in quantities):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This unit supports at most {unit.decimal_places} decimal places.",
        )
    product = Product(
        name=payload.name,
        sku=payload.sku.upper(),
        barcode=payload.barcode,
        category_id=payload.category_id,
        description=payload.description,
        unit_id=payload.unit_id,
        supplier_id=payload.supplier_id,
        purchase_cost=payload.purchase_cost,
        retail_price=payload.retail_price,
        wholesale_price=payload.wholesale_price,
        minimum_stock=payload.minimum_stock,
    )
    set_price_tiers(product, payload.price_tiers)
    db.add(product)
    try:
        db.flush()
        db.add(InventoryBalance(product_id=product.id, quantity=payload.opening_stock))
        if payload.opening_stock > 0:
            db.add(
                StockMovement(
                    product_id=product.id,
                    movement_type="opening",
                    quantity_delta=payload.opening_stock,
                    reason=payload.opening_stock_reason,
                    created_by=actor.id,
                )
            )
        db.add(
            AuditLog(
                actor_user_id=actor.id,
                action="product.create",
                entity_type="product",
                entity_id=product.id,
                details={"sku": product.sku},
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with that SKU or barcode already exists.",
        ) from exc
    return product_response(get_product_or_404(db, product.id))


@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory:manage")),
    _: User = Depends(require_csrf),
) -> ProductResponse:
    product = db.scalar(product_query().where(Product.id == product_id).with_for_update())
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    changes = payload.model_dump(exclude_unset=True, exclude={"price_tiers"})
    for required in (
        "name",
        "sku",
        "description",
        "unit_id",
        "purchase_cost",
        "retail_price",
        "wholesale_price",
        "minimum_stock",
    ):
        if required in changes and changes[required] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{required} cannot be null.",
            )
    validate_references(
        db,
        changes.get("unit_id"),
        changes.get("category_id"),
        changes.get("supplier_id"),
    )
    tier_inputs = payload.price_tiers if "price_tiers" in payload.model_fields_set else None
    if "price_tiers" in payload.model_fields_set and payload.price_tiers is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="price_tiers cannot be null.",
        )
    if "unit_id" in changes and changes["unit_id"] != product.unit_id:
        movement_exists = db.scalar(
            select(StockMovement.id).where(StockMovement.product_id == product.id).limit(1)
        )
        if movement_exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product's unit cannot be changed after stock movements are recorded.",
            )
        if changes["unit_id"] is not None:
            new_unit = db.get(UnitOfMeasure, changes["unit_id"])
            if new_unit is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Select a valid unit of measure.",
                )
    effective_unit = (
        db.get(UnitOfMeasure, changes["unit_id"])
        if changes.get("unit_id") is not None
        else product.unit
    )
    if effective_unit is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select a valid unit of measure.",
        )
    effective_minimum_stock = changes.get("minimum_stock", product.minimum_stock)
    if not quantity_matches_unit(effective_minimum_stock, effective_unit):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This unit supports at most {effective_unit.decimal_places} decimal places.",
        )
    effective_tiers = tier_inputs if tier_inputs is not None else product.price_tiers
    if any(
        not quantity_matches_unit(tier.minimum_quantity, effective_unit) for tier in effective_tiers
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This unit supports at most {effective_unit.decimal_places} decimal places.",
        )
    if tier_inputs is not None:
        set_price_tiers(product, tier_inputs)
    for field, value in changes.items():
        if field == "sku" and value is not None:
            value = value.strip().upper()
        elif field in {"name", "description"} and value is not None:
            value = value.strip()
            if field == "name" and not value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Product name cannot be blank.",
                )
        elif field == "barcode" and value is not None:
            value = value.strip() or None
        setattr(product, field, value)
    if changes or tier_inputs is not None:
        db.add(
            AuditLog(
                actor_user_id=actor.id,
                action="product.update",
                entity_type="product",
                entity_id=product.id,
                details={
                    "fields": sorted(
                        [*changes, *(["price_tiers"] if tier_inputs is not None else [])]
                    )
                },
            )
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with that SKU or barcode already exists.",
        ) from exc
    return product_response(get_product_or_404(db, product.id))


@router.get("/products/{product_id}/stock-movements", response_model=list[StockMovementResponse])
def list_stock_movements(
    product_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:read")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[StockMovement]:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return db.scalars(
        select(StockMovement)
        .where(StockMovement.product_id == product_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id)
        .limit(limit)
        .offset(offset)
    ).all()


@router.post(
    "/products/{product_id}/stock-movements",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stock_movement(
    product_id: str,
    payload: StockMovementCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("inventory:manage")),
    _: User = Depends(require_csrf),
) -> StockMovement:
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    movement = add_stock_movement(
        db,
        product,
        payload.quantity_delta,
        payload.movement_type,
        payload.reason,
        actor,
    )
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="inventory.stock_movement",
            entity_type="product",
            entity_id=product.id,
            details={
                "movement_type": payload.movement_type,
                "quantity_delta": str(payload.quantity_delta),
                "reason": payload.reason,
            },
        )
    )
    db.commit()
    db.refresh(movement)
    return movement
