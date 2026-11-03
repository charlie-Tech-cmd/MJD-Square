from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, BusinessSettings, User
from app.permissions import require_csrf, require_permission
from app.schemas import BusinessSettingsResponse, BusinessSettingsUpdate

router = APIRouter(prefix="/settings", tags=["business settings"])


@router.get("", response_model=BusinessSettingsResponse)
def read_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:read")),
) -> BusinessSettings:
    settings = db.get(BusinessSettings, 1)
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Business settings have not been initialized.",
        )
    return settings


@router.put("", response_model=BusinessSettingsResponse)
def update_settings(
    payload: BusinessSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
    _: User = Depends(require_csrf),
) -> BusinessSettings:
    settings = db.get(BusinessSettings, 1)
    if settings is None:
        settings = BusinessSettings(id=1)
        db.add(settings)
    settings.business_name = payload.business_name
    settings.currency = payload.currency
    settings.timezone = payload.timezone
    settings.payment_methods = payload.payment_methods
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="settings.update",
            entity_type="business_settings",
            entity_id="1",
            details={
                "business_name": payload.business_name,
                "currency": payload.currency,
                "timezone": payload.timezone,
                "payment_methods": payload.payment_methods,
            },
        )
    )
    db.commit()
    db.refresh(settings)
    return settings
