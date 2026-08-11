"""
认证 & 鉴权 — FastAPI 依赖注入。

认证链路：
  1. OAuth2PasswordBearer 从 Authorization: Bearer {token} 提取 JWT
  2. decode_access_token 解码校验
  3. 按 sub (user_id) 从 DB 查询用户
  4. 检查 is_active
  5. 角色鉴权：检查 user.role 是否在允许列表中
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import Role, User
from app.utils.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    从 JWT token 解析当前登录用户。
    token 无效 / 过期 / 用户不存在 / 已禁用 → 401。
    """
    settings = get_settings()
    token = credentials.credentials if credentials else request.cookies.get(settings.admin_session_cookie_name)
    payload = decode_access_token(token) if token else None
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    # 按 user_id 查找，同时校验 is_active
    user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    """
    角色鉴权工厂函数。
    用法: user: User = Depends(require_roles(Role.admin, Role.operator))
    用户角色不在允许列表中 → 403。
    """
    allowed = {role.value for role in roles}

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed and user.role.value not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency


# 预构建的角色守卫
AdminOnly = require_roles(Role.admin)
ContentManager = require_roles(Role.admin, Role.operator)
LeadViewer = require_roles(Role.admin, Role.operator, Role.sales, Role.consultant)
LeadExporter = require_roles(Role.admin, Role.operator, Role.sales)
ReportViewer = require_roles(Role.admin, Role.operator, Role.sales, Role.consultant)
