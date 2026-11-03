from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Permission, Role, User
from app.permission_catalog import OWNER_ONLY_PERMISSIONS
from app.security import hash_password


def test_owner_can_configure_limited_staff_permissions(client, db_session: Session):
    owner_role = db_session.scalar(select(Role).where(Role.name == "Owner"))
    staff_role = db_session.scalar(select(Role).where(Role.name == "Shop staff"))
    assert owner_role is not None and staff_role is not None
    db_session.add(
        User(
            email="owner@example.com",
            full_name="Owner",
            password_hash=hash_password("correct horse battery"),
            role=owner_role,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    csrf = client.cookies["mjd_csrf"]

    response = client.get("/api/v1/roles/staff/permissions")
    assert response.status_code == 200
    permission_ids = {permission["id"] for permission in response.json()["permissions"]}
    assert not permission_ids.intersection(OWNER_ONLY_PERMISSIONS)
    permission_ids.discard("inventory:read")
    permission_ids.add("expenses:create")
    updated = client.put(
        "/api/v1/roles/staff/permissions",
        headers={"X-CSRF-Token": csrf},
        json={"permission_ids": sorted(permission_ids)},
    )

    assert updated.status_code == 200
    grants = {item.id for item in staff_role.permissions}
    assert "inventory:read" not in grants
    assert "expenses:create" in grants
    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "role.permissions.update"))
    assert audit is not None


def test_owner_cannot_grant_owner_only_permissions_to_staff(client, db_session: Session):
    owner_role = db_session.scalar(select(Role).where(Role.name == "Owner"))
    assert owner_role is not None
    db_session.add(
        User(
            email="owner@example.com",
            full_name="Owner",
            password_hash=hash_password("correct horse battery"),
            role=owner_role,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    csrf = client.cookies["mjd_csrf"]
    sensitive_permission = db_session.scalar(
        select(Permission.id).where(Permission.id == "settings:manage")
    )
    assert sensitive_permission is not None

    response = client.put(
        "/api/v1/roles/staff/permissions",
        headers={"X-CSRF-Token": csrf},
        json={"permission_ids": ["settings:manage"]},
    )

    assert response.status_code == 422


def test_staff_cannot_view_or_change_role_permissions(client, db_session: Session):
    staff_role = db_session.scalar(select(Role).where(Role.name == "Shop staff"))
    assert staff_role is not None
    db_session.add(
        User(
            email="staff@example.com",
            full_name="Shop staff",
            password_hash=hash_password("correct horse battery"),
            role=staff_role,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "staff@example.com", "password": "correct horse battery"},
    )
    csrf = client.cookies["mjd_csrf"]

    read_response = client.get("/api/v1/roles/staff/permissions")
    update_response = client.put(
        "/api/v1/roles/staff/permissions",
        headers={"X-CSRF-Token": csrf},
        json={"permission_ids": ["sales:read"]},
    )

    assert read_response.status_code == 403
    assert update_response.status_code == 403
