"""Generated report and delivery schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.questionnaire import ScoreResponse


class AiMessageRead(BaseModel):
    role: str
    purpose: str
    content: str
    model_vendor: str | None = None
    model_name: str | None = None
    created_at: datetime


class ReportRead(BaseModel):
    id: int
    public_token: str
    status: str
    title: str
    html_content: str
    model_vendor: str
    model_name: str | None
    created_at: datetime


class SubmitResponse(BaseModel):
    score: ScoreResponse
    report: ReportRead


class ReportEmailRequest(BaseModel):
    email: EmailStr = Field(description="接收报告的邮箱地址")
