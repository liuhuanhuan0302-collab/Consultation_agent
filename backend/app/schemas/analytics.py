"""Administration dashboard analytics schemas."""

from pydantic import BaseModel, Field


class AnalyticsBucket(BaseModel):
    label: str
    count: int


class AnalyticsFunnelStep(BaseModel):
    label: str
    count: int
    rate: float


class AnalyticsSummary(BaseModel):
    visit_uv: int
    started_count: int
    info_completed_count: int
    questionnaire_completed_count: int
    report_generated_count: int
    report_claimed_count: int
    high_intent_leads: int
    lead_count: int
    questionnaire_completion_rate: float = 0
    funnel: list[AnalyticsFunnelStep] = Field(default_factory=list)
    hourly_questionnaire_counts: list[AnalyticsBucket] = Field(default_factory=list)
    lead_level_distribution: list[AnalyticsBucket] = Field(default_factory=list)
    industry_distribution: list[AnalyticsBucket] = Field(default_factory=list)
