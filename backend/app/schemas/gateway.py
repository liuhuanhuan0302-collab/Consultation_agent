"""Runtime search and LLM gateway configuration schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import UTCResponseModel


class GatewayConfigRead(UTCResponseModel):
    search_enabled: bool
    search_provider: str
    search_api_key: str
    search_base_url: str | None = None
    search_timeout_seconds: int
    search_max_results: int
    search_model: str | None = None
    llm_api_key: str
    llm_base_url: str | None = None
    llm_model: str | None = None
    key_reentry_required: bool = False
    updated_by: str | None = None
    updated_at: datetime | None = None


class SearchConfigUpdate(BaseModel):
    search_enabled: bool = True
    search_provider: str = "bocha"
    search_api_key: str = ""
    search_base_url: str | None = None
    search_timeout_seconds: int = Field(default=15, ge=3, le=120)
    search_max_results: int = Field(default=20, ge=1, le=50)
    search_model: str | None = None


class LlmConfigUpdate(BaseModel):
    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_model: str | None = None


class SearchTestRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    search_provider: str = "bocha"
    search_api_key: str = ""
    search_base_url: str | None = None
    search_timeout_seconds: int = Field(default=15, ge=3, le=120)
    search_max_results: int = Field(default=20, ge=1, le=50)
    search_model: str | None = None


class LlmTestRequest(BaseModel):
    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_model: str | None = None
