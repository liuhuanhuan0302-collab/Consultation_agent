"""
安全工具 — 密码哈希 + JWT 令牌签发与校验。

密码方案：pbkdf2_sha256（passlib），单向不可逆。
JWT 方案：HS256 签名（python-jose），默认 720 分钟过期。
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """对明文密码做 pbkdf2_sha256 哈希。"""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码是否与哈希匹配。"""
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    """
    创建 JWT access token。
    subject — 用户标识（user_id 字符串）
    extra   — 可选额外 claims，如 {"role": "admin"}
    过期时间从 config.ACCESS_TOKEN_EXPIRE_MINUTES 读取。
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    解码并校验 JWT token。
    成功返回 payload dict，失败（过期/签名错误）返回 None，不抛异常。
    """
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
