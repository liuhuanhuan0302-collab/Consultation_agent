from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now() -> datetime:
    return datetime.utcnow()


def token() -> str:
    return uuid4().hex


class Role(str, Enum):
    admin = "admin"
    operator = "operator"
    sales = "sales"
    consultant = "consultant"


class SubmissionStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    scored = "scored"


class ReportStatus(str, Enum):
    pending = "pending"
    generating = "generating"
    generated = "generated"
    fallback = "fallback"
    failed = "failed"


class ReportDeliveryStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    sent = "sent"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[Role] = mapped_column(String(32), default=Role.sales.value)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ChannelSource(Base):
    __tablename__ = "channel_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class CompanyLead(Base):
    __tablename__ = "company_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(64), default=token, unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), index=True)
    industry: Mapped[str | None] = mapped_column(String(120), index=True)
    company_size: Mapped[str | None] = mapped_column(String(80))
    annual_revenue: Mapped[str | None] = mapped_column(String(80))
    contact_name: Mapped[str | None] = mapped_column(String(80))
    position: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    wechat: Mapped[str | None] = mapped_column(String(80))
    ai_focus: Mapped[str | None] = mapped_column(Text)
    privacy_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    source_code: Mapped[str | None] = mapped_column(String(80), index=True)
    lead_level: Mapped[str] = mapped_column(String(40), default="low", index=True)
    priority_strategy: Mapped[str | None] = mapped_column(String(40), index=True)
    demand_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    submissions: Mapped[list["DiagnosisSubmission"]] = relationship(back_populates="lead")


class QuestionModule(Base):
    __tablename__ = "question_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    max_score: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    questions: Mapped[list["Question"]] = relationship(back_populates="module", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("module_id", "code", name="uq_question_module_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("question_modules.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    dimension: Mapped[str | None] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text)
    option_text: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    max_score: Mapped[int] = mapped_column(Integer, default=4)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    module: Mapped[QuestionModule] = relationship(back_populates="questions")


class DiagnosisSubmission(Base):
    __tablename__ = "diagnosis_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("company_leads.id"), index=True)
    status: Mapped[SubmissionStatus] = mapped_column(String(32), default=SubmissionStatus.draft.value)
    total_score: Mapped[int | None] = mapped_column(Integer)
    max_score: Mapped[int] = mapped_column(Integer, default=260)
    score_rate: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str | None] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)

    lead: Mapped[CompanyLead] = relationship(back_populates="submissions")
    answers: Mapped[list["QuestionAnswer"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    dimension_scores: Mapped[list["DimensionScore"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    report: Mapped["Report | None"] = relationship(back_populates="submission", cascade="all, delete-orphan")


class QuestionAnswer(Base):
    __tablename__ = "question_answers"
    __table_args__ = (UniqueConstraint("submission_id", "question_id", name="uq_submission_question"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("diagnosis_submissions.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    submission: Mapped[DiagnosisSubmission] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()


class DimensionScore(Base):
    __tablename__ = "dimension_scores"
    __table_args__ = (UniqueConstraint("submission_id", "module_id", name="uq_submission_module_score"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("diagnosis_submissions.id"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("question_modules.id"), index=True)
    raw_score: Mapped[int] = mapped_column(Integer)
    max_score: Mapped[int] = mapped_column(Integer)
    score_rate: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(40))

    submission: Mapped[DiagnosisSubmission] = relationship(back_populates="dimension_scores")
    module: Mapped[QuestionModule] = relationship()


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("diagnosis_submissions.id"), unique=True, index=True)
    public_token: Mapped[str] = mapped_column(String(64), default=token, unique=True, index=True)
    status: Mapped[ReportStatus] = mapped_column(String(32), default=ReportStatus.pending.value)
    title: Mapped[str] = mapped_column(String(255))
    html_content: Mapped[str] = mapped_column(Text)
    summary_json: Mapped[str | None] = mapped_column(Text)
    model_vendor: Mapped[str] = mapped_column(String(80), default="deepseek")
    model_name: Mapped[str | None] = mapped_column(String(120))
    generation_error: Mapped[str | None] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    submission: Mapped[DiagnosisSubmission] = relationship(back_populates="report")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class AiConversationMessage(Base):
    __tablename__ = "ai_conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("company_leads.id"), index=True)
    submission_id: Mapped[int | None] = mapped_column(ForeignKey("diagnosis_submissions.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(80), default="report_advisor", index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    content: Mapped[str] = mapped_column(Text)
    model_vendor: Mapped[str | None] = mapped_column(String(80))
    model_name: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class ReportDeliveryJob(Base):
    __tablename__ = "report_delivery_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("company_leads.id"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("diagnosis_submissions.id"), index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[ReportDeliveryStatus] = mapped_column(String(32), default=ReportDeliveryStatus.queued.value, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    run_after: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    lead: Mapped[CompanyLead] = relationship()
    submission: Mapped[DiagnosisSubmission] = relationship()
    report: Mapped[Report] = relationship()


class CaseStudy(Base):
    __tablename__ = "case_studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str] = mapped_column(String(120), index=True)
    function_area: Mapped[str] = mapped_column(String(120), index=True)
    module_code: Mapped[str] = mapped_column(String(40), index=True)
    maturity: Mapped[str] = mapped_column(String(80), default="MVP")
    roi_level: Mapped[str] = mapped_column(String(40), default="medium")
    difficulty: Mapped[str] = mapped_column(String(40), default="medium")
    description: Mapped[str] = mapped_column(Text)
    expected_benefit: Mapped[str] = mapped_column(Text)
    priority_tag: Mapped[str] = mapped_column(String(40), default="攻坚战")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("case_studies.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    priority_score: Mapped[int] = mapped_column(Integer, default=50)

    report: Mapped[Report] = relationship(back_populates="recommendations")
    case: Mapped[CaseStudy | None] = relationship()


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    content: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str | None] = mapped_column(String(64), index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("company_leads.id"), index=True)
    event_name: Mapped[str] = mapped_column(String(120), index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class ExportLog(Base):
    __tablename__ = "export_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    export_type: Mapped[str] = mapped_column(String(80))
    filters_json: Mapped[str | None] = mapped_column(Text)
    rows_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str | None] = mapped_column(String(120))
    target_id: Mapped[str | None] = mapped_column(String(120))
    detail_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
