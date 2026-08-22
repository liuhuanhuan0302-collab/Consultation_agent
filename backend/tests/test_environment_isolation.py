import pytest
from pydantic import ValidationError

from app.config import Settings
from app.service import email_service


def test_staging_requires_isolated_database_name():
    with pytest.raises(ValidationError, match="独立数据库"):
        Settings(
            environment="staging",
            database_url="mysql+pymysql://user:password@mysql/consultation_agent",
            smtp_recipient_allowlist="tester@example.com",
            _env_file=None,
        )


def test_settings_reject_unknown_environment():
    """环境名白名单：prod 这类拼写不能静默绕过生产安全检查，必须拒绝启动。"""
    for invalid in ("prod", "ProductionX", "test", "PROD"):
        with pytest.raises(ValidationError, match="ENVIRONMENT"):
            Settings(environment=invalid, _env_file=None)


def test_settings_normalize_environment_case():
    settings = Settings(
        environment="  Production ",
        public_web_base_url="https://app.example.com",
        cors_origins="https://app.example.com",
        _env_file=None,
    )
    assert settings.environment == "production"


def test_settings_reject_placeholder_secret_key():
    """模板占位 SECRET_KEY（change-*/replace-*）必须被拒绝，防止 JWT 可伪造。"""
    for placeholder in (
        "change-me-before-production",
        "change-this-secret-key",
        "replace-with-a-different-staging-secret",
    ):
        with pytest.raises(ValidationError, match="SECRET_KEY"):
            Settings(secret_key=placeholder, _env_file=None)


def test_settings_accept_real_secret_key():
    settings = Settings(secret_key="key-a", _env_file=None)
    assert settings.secret_key == "key-a"


def test_settings_reject_placeholder_admin_credentials():
    with pytest.raises(ValidationError, match="INITIAL_ADMIN_PASSWORD"):
        Settings(initial_admin_password="replace-with-a-strong-one-time-password", _env_file=None)
    with pytest.raises(ValidationError, match="INITIAL_ADMIN_EMAIL"):
        Settings(initial_admin_email="admin@your-company.com", _env_file=None)


def test_staging_accepts_test_database_and_email_allowlist():
    settings = Settings(
        environment="staging",
        database_url="mysql+pymysql://user:password@mysql/consultation_agent_test",
        smtp_recipient_allowlist="Tester@Example.com, second@example.com",
        _env_file=None,
    )

    assert settings.smtp_recipient_allowlist_set == {
        "tester@example.com",
        "second@example.com",
    }


def test_staging_requires_email_allowlist():
    with pytest.raises(ValidationError, match="SMTP_RECIPIENT_ALLOWLIST"):
        Settings(
            environment="staging",
            database_url="mysql+pymysql://user:password@mysql/consultation_agent_test",
            _env_file=None,
        )


def test_production_rejects_plaintext_http_endpoints():
    """生产环境拒绝 http:// 的 PUBLIC_WEB_BASE_URL 与 CORS_ORIGINS：
    客户资料与登录 Cookie 不得明文传输（Cookie 带 Secure 标记，HTTP 下
    浏览器根本不会保存，登录无法保持）。"""
    with pytest.raises(ValidationError, match="PUBLIC_WEB_BASE_URL"):
        Settings(
            environment="production",
            public_web_base_url="http://8.138.165.2/diagnosis",
            cors_origins="https://app.example.com",
            _env_file=None,
        )
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            environment="production",
            public_web_base_url="https://app.example.com/diagnosis",
            cors_origins="https://app.example.com,http://8.138.165.2",
            _env_file=None,
        )


def test_production_accepts_https_endpoints():
    settings = Settings(
        environment="production",
        public_web_base_url="https://app.example.com/diagnosis",
        cors_origins="https://app.example.com",
        _env_file=None,
    )
    assert settings.cors_origin_list == ["https://app.example.com"]


def test_email_allowlist_blocks_unapproved_recipient(monkeypatch):
    settings = Settings(
        smtp_host="smtp.example.com",
        smtp_username="sender@example.com",
        smtp_password="secret",
        smtp_recipient_allowlist="tester@example.com",
        _env_file=None,
    )
    monkeypatch.setattr(email_service, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="非测试邮箱"):
        email_service.send_report_pdf_email(
            "customer@example.com",
            "测试公司",
            b"pdf",
            "report.pdf",
        )
