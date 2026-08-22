import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.seed as seed
from app.config import Settings
from app.database import Base
from app.models import User


def create_db() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine), engine


def test_production_seed_requires_explicit_initial_admin(monkeypatch):
    db, engine = create_db()
    monkeypatch.setattr(
        seed,
        "get_settings",
        lambda: Settings(
            environment="production",
            public_web_base_url="https://app.example.com",
            cors_origins="https://app.example.com",
        ),
    )

    with pytest.raises(RuntimeError, match="INITIAL_ADMIN_EMAIL"):
        seed.seed_initial_data(db)

    assert db.query(User).count() == 0
    db.close()
    engine.dispose()


def test_production_seed_uses_configured_initial_admin(monkeypatch):
    db, engine = create_db()
    monkeypatch.setattr(
        seed,
        "get_settings",
        lambda: Settings(
            environment="production",
            initial_admin_email="security@example.com",
            initial_admin_password="strong-one-time-password",
            public_web_base_url="https://app.example.com",
            cors_origins="https://app.example.com",
        ),
    )

    seed.seed_initial_data(db)

    admin = db.query(User).one()
    assert admin.email == "security@example.com"
    assert admin.password_hash != "strong-one-time-password"
    db.close()
    engine.dispose()


def test_staging_seed_uses_configured_initial_admin(monkeypatch):
    db, engine = create_db()
    monkeypatch.setattr(
        seed,
        "get_settings",
        lambda: Settings(
            environment="staging",
            database_url="mysql+pymysql://user:password@mysql/consultation_agent_test",
            smtp_recipient_allowlist="tester@example.com",
            initial_admin_email="staging-admin@example.com",
            initial_admin_password="strong-staging-password",
            _env_file=None,
        ),
    )

    seed.seed_initial_data(db)

    admin = db.query(User).one()
    assert admin.email == "staging-admin@example.com"
    assert admin.password_hash != "strong-staging-password"
    db.close()
    engine.dispose()
