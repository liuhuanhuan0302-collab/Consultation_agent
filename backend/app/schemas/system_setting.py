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


class ReportQueueSettingsUpdate(BaseModel):
    processing_concurrency: int = Field(ge=1, le=64)
    active_queue_capacity: int = Field(ge=1, le=10000)
    automatic_wait_capacity: int = Field(ge=0, le=100000)
    pdf_concurrency: int = Field(ge=1, le=64)
    processing_paused: bool
    promotion_paused: bool
    confirm_processing_increase: bool = False


class ReportQueueSettingsRead(UTCResponseModel):
    processing_concurrency: int
    active_queue_capacity: int
    automatic_wait_capacity: int
    pdf_concurrency: int
    processing_paused: bool
    promotion_paused: bool
    updated_by: str | None = None
    updated_at: datetime | None = None


class ReportQueueManualJobRead(UTCResponseModel):
    id: int
    lead_id: int
    company_name: str
    report_id: int
    report_title: str
    task_kind: str
    status: str
    queue_state: str
    attempts: int
    max_attempts: int
    last_error: str | None = None
    approved_at: datetime | None = None
    approved_by: str | None = None
    created_at: datetime


class ReportQueueOverviewRead(BaseModel):
    settings: ReportQueueSettingsRead
    queue_state_counts: dict[str, int]
    lifecycle_counts: dict[str, int]
    processing_stage_counts: dict[str, int]
    approximate_drain_minutes: float | None = None
    eta_basis_completed_jobs: int = 0
    manual_review_jobs: list[ReportQueueManualJobRead]


class ReportQueueActionRequest(BaseModel):
    job_ids: list[int] = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=500)


class ReportQueueActionResponse(BaseModel):
    affected_job_ids: list[int]
    message: str
