"""API 网关配置 — 单行数据库配置，后台页面可编辑，优先级高于 .env。

安全约定：
- 自定义接口地址必须通过 validate_gateway_url 校验（仅 HTTPS、公共主机、
  禁止内网/回环/保留地址与云元数据地址），且调用方不跟随重定向；
- API Key 一律用应用级密钥加密后入库（enc:v1: 前缀），读取失败视为未配置。
  密钥轮换：修改 .env 的 GATEWAY_ENCRYPTION_KEY 后，管理员在后台重新填写即可。
"""

import base64
import hashlib
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import GatewayApiConfig

DEFAULT_SEARCH_BASE_URLS = {
    "bocha": "https://api.bochaai.com/v1",
    "serpapi": "https://serpapi.com",
    "deepseek": "https://api.deepseek.com",
}

# DeepSeek 联网搜索默认模型（官方 Anthropic 协议接口 + 服务端 web_search 工具）。
DEFAULT_DEEPSEEK_SEARCH_MODEL = "deepseek-v4-flash"

# DeepSeek 官方 Anthropic 协议路径：联网搜索改用 /anthropic/v1/messages，
# 机器引用只从 web_search_tool_result 块读取（/responses 适配不返回可核验引用）。
DEEPSEEK_ANTHROPIC_MESSAGES_PATH = "/anthropic/v1/messages"

SUPPORTED_SEARCH_PROVIDERS = tuple(DEFAULT_SEARCH_BASE_URLS) + ("custom",)

# LLM 覆盖地址可信域名白名单：内置仅允许 DeepSeek 官方域名；
# 自定义 OpenAI 兼容服务需走 validate_gateway_url 且必须同时提供新 Key。
LLM_ALLOWED_HOSTS = {"api.deepseek.com"}

# 明确的元数据/本机主机名黑名单（域名解析校验之外的额外防线）。
BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal", "metadata"}

_ENCRYPTION_PREFIX = "enc:v1:"


def _is_public_ip(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def deepseek_anthropic_messages_url(base_url: str) -> str:
    """DeepSeek 服务商的 Anthropic 协议 Messages 接口地址。"""
    return f"{base_url.rstrip('/')}{DEEPSEEK_ANTHROPIC_MESSAGES_PATH}"


def validate_gateway_url(url: str) -> str:
    """校验网关地址：仅 HTTPS、公共主机、非内网/保留/元数据地址。返回规范化 URL。"""
    normalized = (url or "").strip()
    parsed = urlparse(normalized)
    if parsed.scheme != "https":
        raise ValueError("接口地址必须使用 https://")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("接口地址缺少主机名")
    if hostname.lower() in BLOCKED_HOSTNAMES or hostname.lower().endswith(".local"):
        raise ValueError("不允许使用该主机名")
    if parsed.port is not None and parsed.port != 443:
        raise ValueError("仅允许标准 443 端口")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_public_ip(str(literal)):
            raise ValueError("不允许指向内网或保留地址")
        return normalized

    try:
        resolved = {item[4][0] for item in socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)}
    except OSError as exc:
        raise ValueError("无法解析接口地址主机名") from exc
    if not resolved or any(not _is_public_ip(ip) for ip in resolved):
        raise ValueError("接口地址解析到内网或保留地址，已拒绝")
    return normalized


def validate_llm_base_url(url: str) -> str:
    """校验 LLM 覆盖地址：DeepSeek 官方域名直通，其余必须通过公网 HTTPS 校验。"""
    normalized = (url or "").strip()
    parsed = urlparse(normalized)
    hostname = (parsed.hostname or "").lower()
    if hostname in LLM_ALLOWED_HOSTS and parsed.scheme == "https" and parsed.port in (None, 443):
        return normalized
    return validate_gateway_url(normalized)


def _fernet() -> Fernet:
    settings = get_settings()
    raw = (settings.gateway_encryption_key or settings.secret_key).encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw).digest()))


def encrypt_secret(value: str) -> str:
    return f"{_ENCRYPTION_PREFIX}{_fernet().encrypt(value.encode()).decode()}"


def decrypt_secret(stored: str | None) -> str | None:
    """解密存储的密钥；历史明文兼容直读，解密失败（如密钥已轮换）返回 None。"""
    if not stored:
        return None
    if not stored.startswith(_ENCRYPTION_PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(_ENCRYPTION_PREFIX):].encode()).decode()
    except InvalidToken:
        return None


@dataclass(frozen=True)
class SearchGatewayConfig:
    provider: str
    api_key: str
    base_url: str
    timeout_seconds: int
    max_results: int
    model: str | None = None  # deepseek 服务商使用的检索模型


@dataclass(frozen=True)
class LlmGatewayOverride:
    api_key: str | None
    base_url: str | None
    model: str | None


def get_gateway_config(db: Session) -> GatewayApiConfig:
    """读取网关配置，不存在时创建默认行（id 固定为 1）。"""
    config = db.get(GatewayApiConfig, 1)
    if not config:
        config = GatewayApiConfig(id=1)
        db.add(config)
        db.flush()
    return config


def effective_search_config(db: Session) -> SearchGatewayConfig | None:
    """Return the required search config, sharing the DeepSeek env key when needed."""
    config = get_gateway_config(db)
    settings = get_settings()
    provider = (config.search_provider or "deepseek").strip() or "deepseek"
    api_key = decrypt_secret(config.search_api_key)
    custom_base = (config.search_base_url or "").strip()
    # 仅当未配置自定义接口地址时，才允许共享 .env 的 DeepSeek Key；
    # 防止把 .env Key 发往第三方地址（如网关 Key 因加密密钥轮换无法解密）。
    if provider == "deepseek" and not api_key and not custom_base:
        api_key = settings.deepseek_api_key
    if not api_key:
        return None
    base_url = custom_base or DEFAULT_SEARCH_BASE_URLS.get(provider, "")
    if not base_url:
        return None
    model = (config.search_model or "").strip() or None
    if provider == "deepseek" and not model:
        model = DEFAULT_DEEPSEEK_SEARCH_MODEL
    return SearchGatewayConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=max(3, config.search_timeout_seconds),
        max_results=max(1, config.search_max_results),
        model=model,
    )


def effective_llm_override(db: Session) -> LlmGatewayOverride:
    """LLM 覆盖配置：字段留空时回退到 .env 的 deepseek_* 设置。"""
    config = get_gateway_config(db)
    return LlmGatewayOverride(
        api_key=decrypt_secret(config.llm_api_key),
        base_url=(config.llm_base_url or "").strip() or None,
        model=(config.llm_model or "").strip() or None,
    )


def mask_key(value: str | None) -> str:
    """API key 掩码：保留首尾各 3 位，供后台页面展示。"""
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}***{value[-3:]}"


def config_has_undecryptable_key(config: GatewayApiConfig) -> bool:
    """检测是否存在已存储但无法解密的 key（加密密钥轮换后），提示管理员重新录入。"""
    for stored in (config.search_api_key, config.llm_api_key):
        if stored and stored.startswith(_ENCRYPTION_PREFIX) and decrypt_secret(stored) is None:
            return True
    return False


def migrate_gateway_secrets(db: Session) -> None:
    """启动迁移：把历史明文 key 用当前加密密钥加密后写回，并记录审计日志（不含密钥内容）。"""
    from app.utils.logging_utils import write_operation_log

    config = db.get(GatewayApiConfig, 1)
    if not config:
        return

    migrated_fields: list[str] = []
    for field in ("search_api_key", "llm_api_key"):
        value = getattr(config, field)
        if value and not value.startswith(_ENCRYPTION_PREFIX):
            setattr(config, field, encrypt_secret(value))
            migrated_fields.append(field)
    if not migrated_fields:
        return

    db.add(config)
    write_operation_log(
        db,
        None,
        "gateway_secrets_migrated",
        "gateway_api_config",
        "1",
        {"fields": migrated_fields},
    )
    db.commit()
