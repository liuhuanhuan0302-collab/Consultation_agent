"""后台用户管理 — 创建 / 列出后台账号。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.repositories.user_repo import get_user_by_email, list_users as list_user_accounts
from app.schemas import UserCreate, UserRead
from app.utils.auth import AdminOnly
from app.utils.logging_utils import write_operation_log
from app.utils.security import hash_password

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# 3.4 创建后台用户
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/users
# 功能：管理员创建新的后台用户
# 鉴权：admin 角色
# 请求：{ email*, name*, role*, password* }  password 最少 8 位
#       role: "admin" | "operator" | "sales" | "consultant"
# 返回：{ id, email, name, role, is_active, created_at }
# 错误：409 "Email already exists"
@router.post("/api/admin/users", response_model=UserRead)
def create_user(payload: UserCreate, db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> User:
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="Email already exists")
    created = User(email=payload.email, name=payload.name, role=payload.role.value, password_hash=hash_password(payload.password))
    db.add(created)
    write_operation_log(db, user, "create_user", "user", payload.email)
    db.commit()
    db.refresh(created)
    return created


# ══════════════════════════════════════════════════════════════════
# 3.4 列出后台用户
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/users
# 功能：管理员查看所有后台用户列表
# 鉴权：admin 角色
# 返回：UserRead[] 数组
@router.get("/api/admin/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> list[User]:
    return list_user_accounts(db)
