"""Question bank, answers and score response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    dimension: str | None
    text: str
    option_text: str | None
    sort_order: int
    max_score: int


class ModuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    max_score: int
    sort_order: int
    questions: list[QuestionRead] = Field(default_factory=list)


class QuestionUpsert(BaseModel):
    module_code: str
    code: str
    dimension: str | None = None
    text: str
    option_text: str | None = None
    sort_order: int
    max_score: int = Field(default=4, ge=1, le=4)
    is_active: bool = True


class ModuleUpsert(BaseModel):
    code: str
    name: str
    description: str | None = None
    max_score: int = Field(ge=1)
    sort_order: int = 0
    is_active: bool = True


class AnswerInput(BaseModel):
    question_id: int
    score: int = Field(ge=0, le=4)


class DraftSaveRequest(BaseModel):
    answers: list[AnswerInput]


class SubmitQuestionnaireRequest(BaseModel):
    answers: list[AnswerInput]


class DimensionScoreRead(BaseModel):
    module_code: str
    module_name: str
    raw_score: int
    max_score: int
    score_rate: float
    risk_level: str


class ScoreResponse(BaseModel):
    submission_id: int
    total_score: int
    max_score: int
    score_rate: float
    risk_level: str
    low_dimensions: list[DimensionScoreRead]
    dimensions: list[DimensionScoreRead]
