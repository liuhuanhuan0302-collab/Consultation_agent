"""
认证 & 鉴权 — FastAPI 依赖注入。

认证链路：
  1. OAuth2PasswordBearer 从 Authorization: Bearer {token} 提取 JWT
  2. decode_access_token 解码校验
  3. 按 sub (user_id) 从 DB 查询用户
  4. 检查 is_active
  5. 检查签发时间晚于 password_changed_at（修改密码后旧 JWT 立即失效）
  6. 角色鉴权：检查 user.role 是否在允许列表中
"""

from collections.abc import Callable
from datetime import timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import Role, User
from app.utils.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _token_revoked_by_password_change(user: User, payload: dict) -> bool:
    """JWT 签发时间早于最近一次修改密码时间即视为已撤销。"""
    issued_at = payload.get("iat")
    if not isinstance(issued_at, (int, float)):
        return False
    if not user.password_changed_at:
        return False
    changed_epoch = int(user.password_changed_at.replace(tzinfo=timezone.utc).timestamp())
    return int(issued_at) < changed_epoch


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    从 JWT token 解析当前登录用户。
    token 无效 / 过期 / 用户不存在 / 已禁用 / 密码已修改 → 401。
    """
    settings = get_settings()
    token = credentials.credentials if credentials else request.cookies.get(settings.admin_session_cookie_name)
    payload = decode_access_token(token) if token else None
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    # 按 user_id 查找，同时校验 is_active
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from None
    if not 1 <= user_id <= 2_147_483_647:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if _token_revoked_by_password_change(user, payload):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token issued before password change")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    """
    角色鉴权工厂函数。
    用法: user: User = Depends(require_roles(Role.admin, Role.operator))
    用户角色不在允许列表中 → 403。
    """
    allowed = {role.value for role in roles}

    def dependency(user: User = Depends(get_current_user)) -> User:
        role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_value not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency


# 预构建的角色守卫
AdminOnly = require_roles(Role.admin)
ContentManager = require_roles(Role.admin, Role.operator)
LeadViewer = require_roles(Role.admin, Role.operator, Role.sales, Role.consultant)
LeadExporter = require_roles(Role.admin, Role.operator, Role.sales)
ReportViewer = require_roles(Role.admin, Role.operator, Role.sales, Role.consultant)
