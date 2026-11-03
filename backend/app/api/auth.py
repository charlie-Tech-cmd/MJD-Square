from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import AuditLog, AuthSession, LoginAttempt, User, utc_now
from app.permissions import (
    CSRF_COOKIE,
    CSRF_COOKIE_PATH,
    SESSION_COOKIE,
    SESSION_HOURS,
    get_current_user,
    require_csrf,
)
from app.schemas import LoginRequest, PasswordChangeRequest, UserResponse
from app.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
COOKIE_PATH = "/api/v1"


def get_client_ip(request: Request) -> str:
    if request.client:
        return request.client.host[:64]
    return "unknown"


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    email = str(payload.email).lower()
    client_ip = get_client_ip(request)
    cutoff = utc_now() - LOCKOUT_WINDOW
    failed_attempts = (
        db.scalar(
            select(func.count(LoginAttempt.id)).where(
                LoginAttempt.email == email,
                LoginAttempt.client_ip == client_ip,
                LoginAttempt.succeeded.is_(False),
                LoginAttempt.occurred_at >= cutoff,
            )
        )
        or 0
    )
    ip_attempts = (
        db.scalar(
            select(func.count(LoginAttempt.id)).where(
                LoginAttempt.client_ip == client_ip,
                LoginAttempt.succeeded.is_(False),
                LoginAttempt.occurred_at >= cutoff,
            )
        )
        or 0
    )
    if failed_attempts >= MAX_FAILED_ATTEMPTS or ip_attempts >= 20:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Try again in 15 minutes.",
        )

    user = db.scalar(select(User).where(User.email == email))
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    valid_password = verify_password(payload.password, password_hash)
    if not valid_password or user is None or not user.is_active:
        db.add(
            LoginAttempt(
                email=email,
                client_ip=client_ip,
                succeeded=False,
                occurred_at=utc_now(),
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
        )

    session_token = new_token()
    csrf_token = new_token()
    auth_session = AuthSession(
        token_hash=token_digest(session_token),
        csrf_token_hash=token_digest(csrf_token),
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=SESSION_HOURS),
    )
    db.add(auth_session)
    db.add(
        LoginAttempt(
            email=email,
            client_ip=client_ip,
            succeeded=True,
            occurred_at=utc_now(),
        )
    )
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="auth.login",
            entity_type="user",
            entity_id=user.id,
            details={},
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=SESSION_HOURS * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=SESSION_HOURS * 60 * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path=CSRF_COOKIE_PATH,
    )
    return user


@router.get("/me", response_model=UserResponse)
def current_user(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/logout")
def logout(
    response: Response,
    request: Request,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE, "")
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(token))
    )
    if auth_session is not None:
        db.delete(auth_session)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="auth.logout",
            entity_type="user",
            entity_id=user.id,
            details={},
        )
    )
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE, path=CSRF_COOKIE_PATH)
    return {"status": "signed_out"}


@router.put("/password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a password you have not used before.",
        )
    user.password_hash = hash_password(payload.new_password)
    current_token = request.cookies.get(SESSION_COOKIE, "")
    current_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(current_token))
    )
    if current_session is not None:
        db.query(AuthSession).filter(
            AuthSession.user_id == user.id,
            AuthSession.id != current_session.id,
        ).delete(synchronize_session=False)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="auth.password_change",
            entity_type="user",
            entity_id=user.id,
            details={},
        )
    )
    db.commit()
    return {"status": "password_updated"}
