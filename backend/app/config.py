"""
应用配置 — Pydantic Settings 从 .env 文件加载。

所有配置项可通过环境变量或 .env 文件覆盖。
生产部署必须设置：SECRET_KEY、DATABASE_URL、DEEPSEEK_API_KEY、PUBLIC_WEB_BASE_URL
"""

from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置，自动从 .env 读取。"""

    # ── 基础 ──
    app_name: str = "Consultation Diagnosis Agent"
    environment: str = Field(default="development", description="运行环境：development / production")

    # ── 数据库 ──
    # 生产环境需改为 mysql+pymysql://user:pass@host:3306/db?charset=utf8mb4
    database_url: str = "sqlite:///./consultation_agent.db"
    db_pool_size: int = Field(default=10, description="数据库连接池常驻连接数")
    db_max_overflow: int = Field(default=20, description="数据库连接池额外临时连接数")
    db_pool_timeout: int = Field(default=30, description="获取数据库连接的超时时间（秒）")

    # ── 安全 ──
    secret_key: str = Field(
        default="",
        description="JWT 签名密钥，生产环境必须设置，缺失则启动报错"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=720, description="JWT 有效期（分钟），默认 12 小时")

    # ── AI 模型 ──
    deepseek_api_key: str | None = Field(default=None, description="DeepSeek API 密钥，可选，不填则报告不调用 AI")
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: int = Field(default=45, description="DeepSeek 请求超时秒数")
    report_generation_concurrency: int = Field(default=5, description="每个后端进程内允许同时生成报告的数量")

    # ── PDF ──
    pdf_browser_render: bool = Field(default=False, description="是否用浏览器渲染 PDF（暂未启用）")

    # ── 邮件 ──
    smtp_host: str | None = Field(default=None, description="SMTP 服务器地址，不配置则无法发送报告邮件")
    smtp_port: int = Field(default=465, description="SMTP 端口，SSL 通常为 465")
    smtp_username: str | None = Field(default=None, description="SMTP 登录账号")
    smtp_password: str | None = Field(default=None, description="SMTP 登录密码或授权码")
    smtp_from_email: str | None = Field(default=None, description="发件邮箱，不填则使用 SMTP 登录账号")
    smtp_from_name: str = Field(default="AI 原生转型诊断", description="发件人名称")

    # ── 前端 ──
    public_web_base_url: str = Field(default="http://localhost:5173", description="公开访问地址，用于生成二维码内容")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="允许跨域的前端地址，逗号分隔",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的 CORS 源字符串拆分为列表。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """单例模式获取配置实例（lru_cache 保证只初始化一次）。"""
    return Settings()
