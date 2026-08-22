"""Application settings loaded from environment variables and ``.env``."""

from functools import lru_cache

from pydantic import Field, model_validator
from sqlalchemy.engine import make_url
from pydantic_settings import BaseSettings, SettingsConfigDict

# 环境取值白名单：未知值（如 prod）一律拒绝启动，防止绕过生产安全检查
VALID_ENVIRONMENTS = {"development", "staging", "production"}

# .env*.example 模板占位值：忘记替换时必须拒绝启动（fail-closed）
PLACEHOLDER_SECRET_PREFIXES = ("change-", "replace-")
PLACEHOLDER_PASSWORD_PREFIXES = ("change-", "replace-")
PLACEHOLDER_ADMIN_EMAIL_SUFFIX = "@your-company.com"


class Settings(BaseSettings):
    """Global application configuration."""

    app_name: str = "Consultation Diagnosis Agent"
    environment: str = Field(default="development", description="运行环境：development / production")
    database_url: str = "sqlite:///./consultation_agent.db"
    db_pool_size: int = Field(default=10, description="数据库连接池常驻连接数")
    db_max_overflow: int = Field(default=20, description="数据库连接池额外临时连接数")
    db_pool_timeout: int = Field(default=30, description="获取数据库连接的超时时间（秒）")

    secret_key: str = Field(default="", description="JWT 签名密钥，生产环境必须设置")
    gateway_encryption_key: str | None = Field(
        default=None,
        description="API 网关密钥的加密密钥；留空则从 SECRET_KEY 派生",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=720, description="JWT 有效期（分钟）")
    admin_session_cookie_name: str = Field(default="admin_session", description="后台 HttpOnly 会话 Cookie 名称")
    initial_admin_email: str | None = Field(default=None, description="首次初始化管理员邮箱")
    initial_admin_password: str | None = Field(
        default=None,
        min_length=12,
        description="首次初始化管理员密码",
    )

    deepseek_api_key: str | None = Field(default=None, description="DeepSeek API 密钥")
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: int = Field(default=45, description="DeepSeek 请求超时秒数")
    report_generation_concurrency: int = Field(default=5, description="每进程报告生成并发数")
    max_pending_report_jobs: int = Field(default=100, ge=1, description="报告任务队列上限")
    max_leads_per_email_per_hour: int = Field(default=3, ge=1, description="同邮箱每小时线索上限")

    pdf_browser_render: bool = Field(default=True, description="是否使用浏览器渲染 PDF")
    pdf_browser_executable: str | None = Field(default=None, description="Chrome/Edge/Chromium 路径")
    pdf_browser_no_sandbox: bool = Field(
        default=False,
        description="Chromium 加 --no-sandbox 启动；容器环境（cap_drop/no-new-privileges）必须开启",
    )

    smtp_host: str | None = Field(default=None, description="SMTP 服务器地址")
    smtp_port: int = Field(default=465, description="SMTP SSL 端口")
    smtp_username: str | None = Field(default=None, description="SMTP 登录账号")
    smtp_password: str | None = Field(default=None, description="SMTP 登录密码或授权码")
    smtp_from_email: str | None = Field(default=None, description="发件邮箱")
    smtp_from_name: str = Field(default="AI 原生转型诊断", description="发件人名称")
    smtp_recipient_allowlist: str = Field(
        default="",
        description="允许接收测试邮件的邮箱，逗号分隔；生产环境通常留空",
    )

    public_web_base_url: str = Field(default="http://localhost:5173", description="公开访问地址")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="允许跨域的前端地址，逗号分隔",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def smtp_recipient_allowlist_set(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.smtp_recipient_allowlist.split(",")
            if email.strip()
        }

    @model_validator(mode="after")
    def validate_environment_and_placeholders(self) -> "Settings":
        """环境名白名单校验 + 拒绝模板占位密钥（防止忘记替换导致 JWT 可伪造）。"""
        environment = self.environment.strip().lower()
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError(
                f"ENVIRONMENT 取值无效：{self.environment!r}，仅支持 development / staging / production"
            )
        self.environment = environment

        secret = self.secret_key.strip().lower()
        if secret and secret.startswith(PLACEHOLDER_SECRET_PREFIXES):
            raise ValueError(
                "SECRET_KEY 仍是模板占位值（change-*/replace-* 开头），请生成强随机密钥后替换"
            )

        password = (self.initial_admin_password or "").strip().lower()
        if password.startswith(PLACEHOLDER_PASSWORD_PREFIXES):
            raise ValueError(
                "INITIAL_ADMIN_PASSWORD 仍是模板占位值（change-*/replace-* 开头），请替换为一次性强密码"
            )

        email = (self.initial_admin_email or "").strip().lower()
        if email.endswith(PLACEHOLDER_ADMIN_EMAIL_SUFFIX):
            raise ValueError("INITIAL_ADMIN_EMAIL 仍是模板占位地址，请替换为真实管理员邮箱")
        return self

    @model_validator(mode="after")
    def prevent_staging_from_using_production_database(self) -> "Settings":
        if self.environment.lower() != "staging":
            return self

        database_name = make_url(self.database_url).database or ""
        if not database_name.lower().endswith(("_test", "_staging")):
            raise ValueError(
                "staging 环境只能连接名称以 _test 或 _staging 结尾的独立数据库"
            )
        if not self.smtp_recipient_allowlist_set:
            raise ValueError("staging 环境必须配置 SMTP_RECIPIENT_ALLOWLIST")
        return self

    @model_validator(mode="after")
    def reject_plaintext_http_in_production(self) -> "Settings":
        """生产环境强制 HTTPS：客户资料、报告 token 与登录 Cookie 不得明文传输。

        生产 Cookie 带 Secure 标记，纯 HTTP 下浏览器不会保存 Cookie，
        登录根本无法保持。http:// 配置一律拒绝启动（fail-closed）。
        """
        if self.environment.lower() != "production":
            return self
        if not self.public_web_base_url.startswith("https://"):
            raise ValueError(
                f"production 环境 PUBLIC_WEB_BASE_URL 必须为 https:// 地址，当前为 {self.public_web_base_url!r}"
            )
        plain_origins = [origin for origin in self.cors_origin_list if not origin.startswith("https://")]
        if plain_origins:
            raise ValueError(
                f"production 环境 CORS_ORIGINS 不得包含 http:// 地址：{', '.join(plain_origins)}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
