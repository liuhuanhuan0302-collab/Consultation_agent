"""Anonymous session and customer lead schemas."""

from datetime import datetime
import re
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.base import UTCResponseModel


class SessionCreate(BaseModel):
    source_code: str | None = Field(default=None, description="来源渠道编码")
    metadata: dict[str, Any] | None = Field(default=None, description="额外页面元数据")


class SessionResponse(BaseModel):
    session_token: str = Field(description="匿名会话令牌")


class LeadCreate(BaseModel):
    session_token: str | None = Field(default=None, description="匿名会话令牌")
    company_name: str = Field(min_length=1, max_length=255, description="企业全称")
    industry: str = Field(min_length=1, max_length=120, description="所属行业")
    company_size: str = Field(min_length=1, max_length=80, description="企业规模")
    annual_revenue: str | None = Field(default=None, description="年营收区间")
    contact_name: str = Field(min_length=1, max_length=80, description="联系人姓名")
    position: str = Field(min_length=1, max_length=120, description="联系人职位")
    phone: str | None = Field(default=None, description="手机号")
    email: EmailStr = Field(description="接收诊断报告的邮箱")
    wechat: str | None = Field(default=None, description="微信号")
    ai_focus: str | None = Field(default=None, description="当前关注的 AI 转型方向")
    privacy_accepted: bool = Field(description="是否同意隐私政策")
    contact_authorized: bool = Field(description="是否授权后续联系")
    source_code: str | None = Field(default=None, description="来源渠道编码")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        phone = value.strip()
        if not re.fullmatch(r"1[3-9]\d{9}", phone):
            raise ValueError("请输入正确的 11 位手机号")
        return phone


class LeadResponse(UTCResponseModel):
    id: int
    session_token: str
    company_name: str | None
    industry: str | None
    company_size: str | None
    annual_revenue: str | None
    contact_name: str | None
    position: str | None
    phone: str | None
    email: EmailStr | None
    wechat: str | None
    ai_focus: str | None
    source_code: str | None
    lead_level: str = Field(description="线索等级")
    priority_strategy: str | None = Field(default=None, description="建议打法")
    demand_summary: str | None = Field(default=None, description="客户诉求摘要")
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime | None = Field(default=None, description="最近处理时间")


class LeadCreatedResponse(BaseModel):
    lead: LeadResponse
    submission_id: int


class LeadDiagnosticEmailUpdate(BaseModel):
    email: EmailStr = Field(description="更正后的诊断报告接收邮箱")
