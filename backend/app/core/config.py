"""Application settings loaded from environment variables and ``.env``."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    pdf_browser_render: bool = Field(default=False, description="是否使用浏览器渲染 PDF")
    pdf_browser_executable: str | None = Field(default=None, description="Chrome/Edge/Chromium 路径")

    smtp_host: str | None = Field(default=None, description="SMTP 服务器地址")
    smtp_port: int = Field(default=465, description="SMTP SSL 端口")
    smtp_username: str | None = Field(default=None, description="SMTP 登录账号")
    smtp_password: str | None = Field(default=None, description="SMTP 登录密码或授权码")
    smtp_from_email: str | None = Field(default=None, description="发件邮箱")
    smtp_from_name: str = Field(default="AI 原生转型诊断", description="发件人名称")

    public_web_base_url: str = Field(default="http://localhost:5173", description="公开访问地址")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="允许跨域的前端地址，逗号分隔",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
