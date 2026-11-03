from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Permission, Role, User
from app.permission_catalog import STAFF_CONFIGURABLE_PERMISSION_IDS
from app.permissions import require_csrf, require_permission
from app.schemas import RolePermissionsResponse, RolePermissionsUpdate

router = APIRouter(prefix="/roles", tags=["users and permissions"])


def permission_response(role: Role, permissions: list[Permission]) -> RolePermissionsResponse:
    granted_ids = {permission.id for permission in role.permissions}
    return RolePermissionsResponse(
        role_id=role.id,
        role_name=role.name,
        permissions=[
            {
                "id": permission.id,
                "description": permission.description,
                "granted": permission.id in granted_ids,
            }
            for permission in permissions
        ],
    )


@router.get("/staff/permissions", response_model=RolePermissionsResponse)
def read_staff_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("staff:manage")),
) -> RolePermissionsResponse:
    role = db.scalar(select(Role).where(Role.name == "Shop staff"))
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Default staff role has not been initialized.",
        )
    permissions = db.scalars(
        select(Permission)
        .where(Permission.id.in_(STAFF_CONFIGURABLE_PERMISSION_IDS))
        .order_by(Permission.id)
    ).all()
    return permission_response(role, permissions)


@router.put("/staff/permissions", response_model=RolePermissionsResponse)
def update_staff_permissions(
    payload: RolePermissionsUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("staff:manage")),
    _: User = Depends(require_csrf),
) -> RolePermissionsResponse:
    invalid_ids = set(payload.permission_ids) - STAFF_CONFIGURABLE_PERMISSION_IDS
    if invalid_ids:
        raise HTTPException(
            status_code=422,
            detail="One or more permissions cannot be assigned to shop staff.",
        )
    role = db.scalar(select(Role).where(Role.name == "Shop staff"))
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Default staff role has not been initialized.",
        )
    before = sorted(permission.id for permission in role.permissions)
    selected_permissions = db.scalars(
        select(Permission).where(Permission.id.in_(payload.permission_ids))
    ).all()
    role.permissions = list(selected_permissions)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="role.permissions.update",
            entity_type="role",
            entity_id=role.id,
            details={
                "role": role.name,
                "previous": before,
                "current": sorted(payload.permission_ids),
            },
        )
    )
    db.commit()
    return permission_response(
        role,
        db.scalars(
            select(Permission)
            .where(Permission.id.in_(STAFF_CONFIGURABLE_PERMISSION_IDS))
            .order_by(Permission.id)
        ).all(),
    )
