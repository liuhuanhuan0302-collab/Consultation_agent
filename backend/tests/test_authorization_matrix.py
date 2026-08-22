from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import admin
from app.config import get_settings
from app.database import Base, get_db
from app.models import CompanyLead, DiagnosisSubmission, Report, Role, User
from app.utils.auth import AdminOnly, get_current_user
from app.utils.security import create_access_token
from app.utils.time_utils import utc_now


@pytest.fixture()
def authorization_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with Session(engine) as db:
        users = {}
        for role in Role:
            user = User(
                email=f"{role.value}@example.com",
                name=role.value,
                role=role.value,
                password_hash="hash",
            )
            db.add(user)
            db.flush()
            users[role.value] = user.id
        disabled = User(
            email="disabled@example.com",
            name="disabled",
            role=Role.admin.value,
            password_hash="hash",
            is_active=False,
        )
        unknown_role = User(
            email="auditor@example.com",
            name="auditor",
            role="auditor",
            password_hash="hash",
        )
        db.add_all([disabled, unknown_role])
        lead = CompanyLead(company_name="Authorization Test")
        db.add(lead)
        db.flush()
        submission = DiagnosisSubmission(lead_id=lead.id)
        db.add(submission)
        db.flush()
        report = Report(submission_id=submission.id, title="Report", html_content="<p>ok</p>")
        db.add(report)
        db.commit()
        disabled_id = disabled.id
        unknown_role_id = unknown_role.id
        report_id = report.id

    test_app = FastAPI()
    test_app.include_router(admin.router)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_db
    with TestClient(test_app) as client:
        yield client, users, disabled_id, unknown_role_id, report_id
    engine.dispose()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def token_for(user_id: int) -> str:
    return create_access_token(str(user_id))


def test_missing_invalid_expired_disabled_and_malformed_credentials_return_401(authorization_app):
    client, users, disabled_id, _unknown_role_id, _report_id = authorization_app
    assert client.get("/api/admin/me").status_code == 401
    assert client.get("/api/admin/me", headers=bearer("not-a-jwt")).status_code == 401

    settings = get_settings()
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {"sub": str(users[Role.admin.value]), "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    malformed_subject = jwt.encode(
        {"sub": "not-an-integer", "iat": now, "exp": now + timedelta(minutes=5)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    oversized_subject = jwt.encode(
        {"sub": "9" * 1000, "iat": now, "exp": now + timedelta(minutes=5)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    assert client.get("/api/admin/me", headers=bearer(expired)).status_code == 401
    assert client.get("/api/admin/me", headers=bearer(token_for(disabled_id))).status_code == 401
    assert client.get("/api/admin/me", headers=bearer(malformed_subject)).status_code == 401
    assert client.get("/api/admin/me", headers=bearer(oversized_subject)).status_code == 401


def test_bearer_and_cookie_authentication_paths(authorization_app):
    client, users, _disabled_id, _unknown_role_id, _report_id = authorization_app
    token = token_for(users[Role.sales.value])
    bearer_response = client.get("/api/admin/me", headers=bearer(token))
    assert bearer_response.status_code == 200
    assert bearer_response.json()["role"] == Role.sales.value

    settings = get_settings()
    client.cookies.set(settings.admin_session_cookie_name, token)
    cookie_response = client.get("/api/admin/me")
    assert cookie_response.status_code == 200
    assert cookie_response.json()["role"] == Role.sales.value
    client.cookies.clear()


def test_admin_only_real_route_matrix(authorization_app):
    client, users, _disabled_id, _unknown_role_id, _report_id = authorization_app
    for role in Role:
        response = client.get("/api/admin/api-gateway", headers=bearer(token_for(users[role.value])))
        assert response.status_code == (200 if role == Role.admin else 403)


def test_content_manager_real_route_matrix(authorization_app):
    client, users, _disabled_id, _unknown_role_id, _report_id = authorization_app
    payload = {
        "title": "Auth Case",
        "industry": "制造业",
        "function_area": "运营",
        "module_code": "M01",
        "description": "权限测试",
        "expected_benefit": "验证权限",
    }
    for role in Role:
        response = client.post("/api/admin/cases", headers=bearer(token_for(users[role.value])), json=payload)
        expected = 200 if role in {Role.admin, Role.operator} else 403
        assert response.status_code == expected


def test_lead_viewer_real_route_matrix(authorization_app):
    client, users, _disabled_id, unknown_role_id, _report_id = authorization_app
    for role in Role:
        response = client.get("/api/admin/cases", headers=bearer(token_for(users[role.value])))
        assert response.status_code == 200
    assert client.get("/api/admin/cases").status_code == 401
    assert client.get("/api/admin/cases", headers=bearer(token_for(unknown_role_id))).status_code == 403


def test_lead_exporter_real_route_matrix(authorization_app):
    client, users, _disabled_id, _unknown_role_id, _report_id = authorization_app
    for role in Role:
        response = client.get("/api/admin/leads/export", headers=bearer(token_for(users[role.value])))
        expected = 200 if role in {Role.admin, Role.operator, Role.sales} else 403
        assert response.status_code == expected


def test_report_viewer_real_route_matrix(authorization_app):
    client, users, _disabled_id, unknown_role_id, report_id = authorization_app
    for role in Role:
        response = client.get(f"/api/admin/reports/{report_id}", headers=bearer(token_for(users[role.value])))
        assert response.status_code == 200
    assert client.get(f"/api/admin/reports/{report_id}").status_code == 401
    assert client.get(f"/api/admin/reports/{report_id}", headers=bearer(token_for(unknown_role_id))).status_code == 403


def test_guard_rejects_enum_role_with_403():
    user = type("UserStub", (), {"role": Role.sales})()
    with pytest.raises(HTTPException) as exc:
        AdminOnly(user)
    assert exc.value.status_code == 403


def test_token_issued_before_password_change_is_rejected():
    """修改密码后，此前签发的 JWT（Bearer 或 Cookie）立即失效，
    即使仍在 720 分钟有效期内。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="u@example.com", name="u", role=Role.admin.value, password_hash="h")
        db.add(user)
        db.commit()
        token = create_access_token(str(user.id))
        # 模拟 token 签发 5 秒后用户修改了密码
        user.password_changed_at = utc_now() + timedelta(seconds=5)
        db.commit()

        request = Request(
            {"type": "http", "method": "GET", "path": "/api/admin/me", "headers": [], "client": ("127.0.0.1", 1)}
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc:
            get_current_user(request, credentials, db)
        assert exc.value.status_code == 401
    engine.dispose()


def test_token_issued_after_password_change_is_accepted():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="u2@example.com", name="u2", role=Role.admin.value, password_hash="h")
        db.add(user)
        db.commit()
        user.password_changed_at = utc_now() - timedelta(seconds=5)
        db.commit()
        token = create_access_token(str(user.id))  # 修改密码后重新登录签发的 token

        request = Request(
            {"type": "http", "method": "GET", "path": "/api/admin/me", "headers": [], "client": ("127.0.0.1", 1)}
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        assert get_current_user(request, credentials, db) is user
    engine.dispose()
