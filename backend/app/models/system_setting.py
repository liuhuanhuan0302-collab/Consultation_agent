"""Administrator-managed singleton settings used by report generation."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.common import now


class ReportContactSetting(Base):
    """Global contact details snapshotted into newly generated reports."""

    __tablename__ = "report_contact_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    wechat: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    updated_by: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class ReportQueueSetting(Base):
    """Singleton database settings for the persistent report scheduler."""

    __tablename__ = "report_queue_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_report_queue_settings_singleton"),
        CheckConstraint("processing_concurrency >= 1", name="ck_report_queue_processing_positive"),
        CheckConstraint(
            "active_queue_capacity >= processing_concurrency",
            name="ck_report_queue_active_capacity",
        ),
        CheckConstraint("automatic_wait_capacity >= 0", name="ck_report_queue_automatic_capacity"),
        CheckConstraint("pdf_concurrency >= 1", name="ck_report_queue_pdf_positive"),
        CheckConstraint(
            "pdf_concurrency <= processing_concurrency",
            name="ck_report_queue_pdf_concurrency",
        ),
    )

    # This is a fixed singleton key, not a generated sequence.  Keeping it
    # non-auto-incrementing allows MySQL to enforce the id = 1 check.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    processing_concurrency: Mapped[int] = mapped_column(Integer, default=2)
    active_queue_capacity: Mapped[int] = mapped_column(Integer, default=50)
    automatic_wait_capacity: Mapped[int] = mapped_column(Integer, default=200)
    pdf_concurrency: Mapped[int] = mapped_column(Integer, default=1)
    processing_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    promotion_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
