"""Question bank, answer and scoring persistence models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.common import now


class SubmissionStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    scored = "scored"


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

    lead: Mapped["CompanyLead"] = relationship(back_populates="submissions")
    answers: Mapped[list["QuestionAnswer"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    dimension_scores: Mapped[list["DimensionScore"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
    )
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
