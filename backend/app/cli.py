import argparse
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    AuditLog,
    BusinessSettings,
    Permission,
    Role,
    User,
)
from app.permission_catalog import ALL_PERMISSIONS, STAFF_DEFAULT_PERMISSIONS
from app.security import hash_password


def ensure_foundation_records(db: Session) -> tuple[Role, Role]:
    permissions = {permission.id: permission for permission in db.scalars(select(Permission)).all()}
    for permission_id, description in ALL_PERMISSIONS.items():
        if permission_id not in permissions:
            permissions[permission_id] = Permission(id=permission_id, description=description)
            db.add(permissions[permission_id])

    owner = db.scalar(select(Role).where(Role.name == "Owner"))
    if owner is None:
        owner = Role(name="Owner", description="Business owner and administrator.")
        db.add(owner)
    staff = db.scalar(select(Role).where(Role.name == "Shop staff"))
    if staff is None:
        staff = Role(name="Shop staff", description="Limited day-to-day shop access.")
        db.add(staff)
    db.flush()
    owner.permissions = list(permissions.values())
    staff.permissions = [permissions[name] for name in STAFF_DEFAULT_PERMISSIONS]
    if db.get(BusinessSettings, 1) is None:
        db.add(BusinessSettings(id=1))
    return owner, staff


def create_admin(email: str, full_name: str, password: str) -> None:
    if not full_name.strip():
        raise ValueError("Owner name cannot be blank.")
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Password must contain between 12 and 128 characters.")
    normalized_email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    with SessionLocal() as db:
        owner, _ = ensure_foundation_records(db)
        existing_owner = db.scalar(select(User).where(User.role_id == owner.id))
        if existing_owner is not None:
            raise ValueError(
                "An owner account already exists; create additional users through the app."
            )
        if db.scalar(select(User).where(User.email == normalized_email)) is not None:
            raise ValueError("A user with that email address already exists.")
        user = User(
            email=normalized_email,
            full_name=full_name.strip(),
            password_hash=hash_password(password),
            role=owner,
        )
        db.add(user)
        db.flush()
        db.add(
            AuditLog(
                actor_user_id=user.id,
                action="user.bootstrap",
                entity_type="user",
                entity_id=user.id,
                details={"role": "Owner"},
            )
        )
        db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="MJD Square administrative commands.")
    commands = parser.add_subparsers(dest="command", required=True)
    create_owner = commands.add_parser("create-admin", help="Create the first owner account.")
    create_owner.add_argument("--email", required=True)
    create_owner.add_argument("--name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Owner password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    if len(password) < 12 or len(password) > 128:
        print("Password must contain between 12 and 128 characters.", file=sys.stderr)
        return 2
    try:
        create_admin(args.email, args.name, password)
    except (ValueError, ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Owner account created for {args.email.strip().lower()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
