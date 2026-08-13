"""后台认证 — 登录 / 登出 / 当前用户 / 修改密码（HttpOnly Cookie 会话）。"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin._shared import limiter
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.repositories.user_repo import get_active_user_by_email
from app.schemas import LoginRequest, MessageResponse, PasswordChangeRequest, UserRead
from app.utils.auth import get_current_user
from app.utils.logging_utils import write_operation_log
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# 3.1 后台登录
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/auth/login
# 功能：后台用户登录，校验邮箱密码，写入 HttpOnly 会话 Cookie
#       密码使用 pbkdf2_sha256 哈希校验
# 限流：同一 IP 每分钟最多 5 次（防暴力破解）
# 鉴权：无
# 请求：{ email: string, password: string }
# 返回：{ message: "登录成功" }
# 错误：401 "账号或密码错误"
@router.post("/api/admin/auth/login", response_model=MessageResponse)
@limiter.limit("5/minute")
def admin_login(request: Request, payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> MessageResponse:
    user = get_active_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    settings = get_settings()
    token = create_access_token(str(user.id), {"role": user.role.value if hasattr(user.role, "value") else user.role})
    response.set_cookie(
        key=settings.admin_session_cookie_name,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.environment.lower() == "production",
        samesite="lax",
        path="/api/admin",
    )
    return MessageResponse(message="登录成功")


# ══════════════════════════════════════════════════════════════════
# 3.1 后台登出
# ══════════════════════════════════════════════════════════════════
@router.post("/api/admin/auth/logout", response_model=MessageResponse)
def admin_logout(response: Response) -> MessageResponse:
    response.delete_cookie(key=get_settings().admin_session_cookie_name, path="/api/admin", samesite="lax")
    return MessageResponse(message="已退出登录")


# ══════════════════════════════════════════════════════════════════
# 3.2 获取当前用户信息
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/me
# 功能：校验 token 有效性，返回当前登录用户信息
#       前端用来判断是否已登录、角色权限是什么
# 鉴权：Bearer Token（任意角色均可）
# 返回：{ id, email, name, role, is_active, created_at }
@router.get("/api/admin/me", response_model=UserRead)
def admin_me(user: User = Depends(get_current_user)) -> User:
    return user


# ══════════════════════════════════════════════════════════════════
# 3.3 修改当前登录用户密码
# ══════════════════════════════════════════════════════════════════
@router.post("/api/admin/auth/change-password", response_model=MessageResponse)
def change_current_password(
    payload: PasswordChangeRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
    user.password_hash = hash_password(payload.new_password)
    write_operation_log(db, user, "change_own_password", "user", str(user.id))
    db.commit()
    response.delete_cookie(key=get_settings().admin_session_cookie_name, path="/api/admin", samesite="lax")
    return MessageResponse(message="密码已更新，请重新登录")
