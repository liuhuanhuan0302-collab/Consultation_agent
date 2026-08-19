"""Authentication and back-office user schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import Role
from app.schemas.base import UTCResponseModel


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="登录邮箱")
    password: str = Field(description="登录密码")


class UserRead(UTCResponseModel):
    id: int
    email: EmailStr
    name: str
    role: Role
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr = Field(description="登录邮箱")
    name: str = Field(description="姓名")
    role: Role = Field(description="角色：admin/operator/sales/consultant")
    password: str = Field(min_length=8, description="初始密码，不少于 8 位")


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, description="当前密码")
    new_password: str = Field(min_length=12, description="新密码，不少于 12 位")
