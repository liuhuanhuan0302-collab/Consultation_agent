"""Organization diagnosis persistence models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.common import now, token


class OrganizationSubmissionStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"


class OrganizationSubmission(Base):
    """A standalone organization diagnosis response."""

    __tablename__ = "organization_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(String(64), default=token, unique=True, index=True)
    company_name_input: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str] = mapped_column(String(255), index=True)
    respondent_name: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(120), index=True)
    position: Mapped[str] = mapped_column(String(120))
    status: Mapped[OrganizationSubmissionStatus] = mapped_column(
        String(32),
        default=OrganizationSubmissionStatus.draft.value,
        server_default=OrganizationSubmissionStatus.draft.value,
        index=True,
    )
    analysis_status: Mapped[str] = mapped_column(
        String(32),
        default="not_eligible",
        server_default="not_eligible",
        index=True,
    )
    analysis_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)

    answers: Mapped[list["OrganizationAnswer"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["OrganizationReport"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
    )


class OrganizationAnswer(Base):
    """A raw answer belonging to an organization diagnosis response."""

    __tablename__ = "organization_answers"
    __table_args__ = (
        UniqueConstraint(
            "organization_submission_id",
            "question_id",
            name="uq_organization_submission_question",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_submission_id: Mapped[int] = mapped_column(
        ForeignKey("organization_submissions.id", ondelete="CASCADE"),
        index=True,
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    answer_value: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    submission: Mapped[OrganizationSubmission] = relationship(back_populates="answers")
