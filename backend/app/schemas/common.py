"""Cross-domain request and response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str


class TrackEventRequest(BaseModel):
    session_token: str | None = None
    lead_id: int | None = None
    event_name: str
    metadata: dict[str, Any] | None = None
