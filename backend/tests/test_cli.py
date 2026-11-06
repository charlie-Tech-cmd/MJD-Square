import pytest
from sqlalchemy import select

from app import cli
from app.cli import ensure_foundation_records
from app.models import BusinessSettings, Permission, Role, User
from app.permission_catalog import STAFF_DEFAULT_PERMISSIONS
from app.security import hash_password


def test_foundation_seeding_preserves_custom_staff_permissions(db_session):
    staff = db_session.scalar(select(Role).where(Role.name == "Shop staff"))
    assert staff is not None

    custom_permission = db_session.get(Permission, "expenses:create")
    assert custom_permission is not None
    staff.permissions = [custom_permission]
    db_session.commit()

    ensure_foundation_records(db_session)
    db_session.commit()
    db_session.expire_all()

    staff = db_session.scalar(select(Role).where(Role.name == "Shop staff"))
    assert staff is not None
    assert {permission.id for permission in staff.permissions} == {
        "expenses:create"
    }


def test_new_staff_role_receives_default_permissions(db_session):
    staff = db_session.scalar(select(Role).where(Role.name == "Shop staff"))
    assert staff is not None
    db_session.delete(staff)
    db_session.commit()

    _, staff = ensure_foundation_records(db_session)
    db_session.commit()

    assert {permission.id for permission in staff.permissions} == (
        STAFF_DEFAULT_PERMISSIONS
    )


def test_create_admin_checks_existing_owner_before_seeding(
    db_session, monkeypatch
):
    owner_role = db_session.scalar(select(Role).where(Role.name == "Owner"))
    assert owner_role is not None

    db_session.add(
        User(
            email="existing-owner@example.com",
            full_name="Existing Owner",
            password_hash=hash_password("correct horse battery"),
            role=owner_role,
        )
    )
    settings = db_session.get(BusinessSettings, 1)
    assert settings is not None
    db_session.delete(settings)
    db_session.commit()

    class SessionContext:
        def __enter__(self):
            return db_session

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(cli, "SessionLocal", SessionContext)

    with pytest.raises(ValueError, match="owner account already exists"):
        cli.create_admin(
            "new-owner@example.com",
            "New Owner",
            "a sufficiently long password",
        )

    assert db_session.get(BusinessSettings, 1) is None
