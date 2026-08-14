"""Acquisition channel schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime


class ChannelUpsert(BaseModel):
    code: str
    name: str
    description: str | None = None
    is_active: bool = True
