"""Administrator-managed singleton settings used by report generation."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
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
