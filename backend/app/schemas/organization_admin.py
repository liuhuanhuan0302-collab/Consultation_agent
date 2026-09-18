"""Organization diagnosis administrator read-only schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import UTCResponseModel


class OrganizationCompanySummary(UTCResponseModel):
    company_name: str
    submitted_count: int
    draft_count: int
    department_count: int
    latest_submitted_at: datetime | None


class OrganizationCompanyListResponse(BaseModel):
    items: list[OrganizationCompanySummary] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int


class OrganizationSubmissionAdminRead(UTCResponseModel):
    id: int
    company_name: str
    respondent_name: str
    department: str
    position: str
    status: str
    created_at: datetime
    submitted_at: datetime | None


class OrganizationCompanyDetailResponse(BaseModel):
    company_name: str
    submitted_count: int
    draft_count: int
    department_count: int
    latest_submitted_at: datetime | None
    departments: list[str] = Field(default_factory=list)
    items: list[OrganizationSubmissionAdminRead] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int


class OrganizationQuestionAnswerAdminRead(UTCResponseModel):
    code: str
    text: str
    max_score: int
    answer_value: int | None


class OrganizationQuestionModuleAdminRead(BaseModel):
    code: str
    name: str
    sort_order: int
    questions: list[OrganizationQuestionAnswerAdminRead] = Field(default_factory=list)


class OrganizationReportAdminRead(BaseModel):
    id: int
    version: int
    status: str
    report_format_version: int
    title: str
    source_enterprise_report_id: int | None = None
    model_name: str | None = None
    generation_error: str | None = None
    generation_started_at: datetime | None = None
    generation_completed_at: datetime | None = None
    created_at: datetime
    pdf_available: bool = False


class OrganizationReportGenerationResponse(BaseModel):
    report_id: int
    task_id: int
    version: int
    status: str
    message: str


class OrganizationSubmissionAdminDetail(OrganizationSubmissionAdminRead):
    analysis_status: str
    analysis_note: str | None = None
    reports: list[OrganizationReportAdminRead] = Field(default_factory=list)
    modules: list[OrganizationQuestionModuleAdminRead] = Field(default_factory=list)
