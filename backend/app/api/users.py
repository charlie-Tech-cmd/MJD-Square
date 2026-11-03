from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import AuditLog, AuthSession, Role, User
from app.permissions import require_csrf, require_permission
from app.schemas import StaffCreateRequest, StaffResponse
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users and permissions"])


def to_staff_response(user: User) -> StaffResponse:
    created_at = user.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return StaffResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=created_at.isoformat(),
        role={
            "id": user.role.id,
            "name": user.role.name,
            "permissions": [
                {"id": permission.id, "description": permission.description}
                for permission in user.role.permissions
            ],
        },
    )


@router.get("", response_model=list[StaffResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("staff:manage")),
) -> list[StaffResponse]:
    users = db.scalars(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .order_by(User.created_at, User.email)
    ).all()
    return [to_staff_response(user) for user in users]


@router.post("", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("staff:manage")),
    _: User = Depends(require_csrf),
) -> StaffResponse:
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A user with that email already exists."
        )
    staff_role = db.scalar(select(Role).where(Role.name == "Shop staff"))
    if staff_role is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Default staff role has not been initialized.",
        )
    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=staff_role,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email already exists.",
        ) from exc
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="user.create",
            entity_type="user",
            entity_id=user.id,
            details={"role": staff_role.name, "email": email},
        )
    )
    db.commit()
    db.refresh(user)
    return to_staff_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_staff(
    user_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("staff:manage")),
    _: User = Depends(require_csrf),
) -> None:
    user = db.scalar(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    if user is None or user.role.name != "Shop staff":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff account not found."
        )
    if user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You cannot deactivate your own account."
        )
    if not user.is_active:
        return None
    user.is_active = False
    db.query(AuthSession).filter(AuthSession.user_id == user.id).delete(synchronize_session=False)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="user.deactivate",
            entity_type="user",
            entity_id=user.id,
            details={"role": user.role.name},
        )
    )
    db.commit()
    return None
