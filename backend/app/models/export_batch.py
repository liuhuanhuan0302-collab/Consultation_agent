"""Export batch history models.

「一键导出未导出客户」每批保存 CSV 快照（content）与客户清单明细，
支持按历史批次重新下载；快照独立于线索数据，客户删除后批次仍可下载。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.common import now


class ExportBatch(Base):
    __tablename__ = "export_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    filters_json: Mapped[str | None] = mapped_column(Text)
    rows_count: Mapped[int] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String(255))
    content: Mapped[bytes] = mapped_column(LargeBinary(length=16 * 1024 * 1024))


class ExportBatchLead(Base):
    __tablename__ = "export_batch_leads"
    __table_args__ = (UniqueConstraint("batch_id", "lead_id", name="uq_export_batch_leads_batch_lead"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("export_batches.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("company_leads.id"), index=True)
