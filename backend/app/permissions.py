from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import AuthSession, Permission, Role, User
from app.security import token_digest

SESSION_COOKIE = "mjd_session"
CSRF_COOKIE = "mjd_csrf"
CSRF_COOKIE_PATH = "/"
SESSION_HOURS = 12


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")

    auth_session = db.scalar(
        select(AuthSession)
        .options(
            selectinload(AuthSession.user).joinedload(User.role).selectinload(Role.permissions)
        )
        .where(AuthSession.token_hash == token_digest(token))
    )
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid.")

    now = auth_session.expires_at
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    if now <= datetime.now(UTC):
        db.delete(auth_session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")
    if not auth_session.user.is_active:
        db.delete(auth_session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive.")
    return auth_session.user


def require_permission(permission: str) -> Callable[..., User]:
    def check_permission(user: User = Depends(get_current_user)) -> User:
        granted = {item.id for item in user.role.permissions}
        if permission not in granted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return check_permission


def require_csrf(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    header_token = request.headers.get("X-CSRF-Token", "")
    if not cookie_token or not secrets_compare(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token is missing or invalid.",
        )
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.token_hash == token_digest(request.cookies.get(SESSION_COOKIE, "")),
        )
    )
    if auth_session is None or token_digest(cookie_token) != auth_session.csrf_token_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token is missing or invalid.",
        )
    return user


def secrets_compare(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


def list_permissions(user: User) -> list[Permission]:
    return sorted(user.role.permissions, key=lambda permission: permission.id)
