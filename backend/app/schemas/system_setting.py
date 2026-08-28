"""Contracts for administrator-managed report contact settings."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import UTCResponseModel


class ReportContactSettingsUpdate(BaseModel):
    contact_name: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=64)
    wechat: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=254)


class ReportContactSettingsRead(UTCResponseModel):
    contact_name: str
    phone: str
    wechat: str
    email: str
    updated_by: str | None = None
    updated_at: datetime | None = None
