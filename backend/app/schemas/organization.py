"""Organization diagnosis request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.base import UTCResponseModel


class OrganizationSubmissionCreate(BaseModel):
    company_name_input: str = Field(min_length=1, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)
    respondent_name: str = Field(min_length=1, max_length=80)
    department: str = Field(min_length=1, max_length=120)
    position: str = Field(min_length=1, max_length=120)


class OrganizationAnswerInput(BaseModel):
    question_id: int = Field(gt=0)
    answer_value: int = Field(ge=0, le=4)


class OrganizationAnswerBatch(BaseModel):
    answers: list[OrganizationAnswerInput] = Field(default_factory=list)


class OrganizationSubmissionRead(UTCResponseModel):
    id: int
    company_name_input: str
    company_name: str
    respondent_name: str
    department: str
    position: str
    status: str
    created_at: datetime
    submitted_at: datetime | None


class OrganizationSubmissionCreated(BaseModel):
    id: int
    access_token: str
    status: str


class OrganizationCompanySuggestion(BaseModel):
    company_name: str


class OrganizationCompanySuggestionResponse(BaseModel):
    items: list[OrganizationCompanySuggestion] = Field(default_factory=list)


class OrganizationAnswerRead(UTCResponseModel):
    id: int
    organization_submission_id: int
    question_id: int
    answer_value: int
    created_at: datetime
    updated_at: datetime
