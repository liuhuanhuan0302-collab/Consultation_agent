"""lead tracking statuses and export batches

Revision ID: 6f0a46f68473
Revises: 9c31a760
Create Date: 2026-08-23 03:47:36.040758
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f0a46f68473"
down_revision: Union[str, Sequence[str], None] = "9c31a760"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add three lead status dimensions and export batch history.

    Every row that exists when this migration runs is a pre-launch legacy
    customer: mark it 已经查看 + 已导出. The processing status is derived
    from each lead's latest submission / report / delivery job so the admin
    badges reflect the real pipeline state immediately after launch.
    """
    # ── company_leads 状态列 ────────────────────────────────────────────
    op.add_column(
        "company_leads",
        sa.Column("view_status", sa.String(length=20), nullable=False, server_default="unviewed"),
    )
    op.add_column("company_leads", sa.Column("first_viewed_at", sa.DateTime(), nullable=True))
    op.add_column("company_leads", sa.Column("first_viewed_by", sa.String(length=120), nullable=True))
    op.add_column(
        "company_leads",
        sa.Column("processing_status", sa.String(length=20), nullable=False, server_default="pending"),
    )
    op.add_column("company_leads", sa.Column("processing_note", sa.Text(), nullable=True))
    op.add_column(
        "company_leads",
        sa.Column("export_status", sa.String(length=20), nullable=False, server_default="unexported"),
    )
    op.add_column("company_leads", sa.Column("first_exported_at", sa.DateTime(), nullable=True))
    op.add_column("company_leads", sa.Column("last_exported_at", sa.DateTime(), nullable=True))
    op.create_index("ix_company_leads_view_status", "company_leads", ["view_status"], unique=False)
    op.create_index("ix_company_leads_processing_status", "company_leads", ["processing_status"], unique=False)
    op.create_index("ix_company_leads_export_status", "company_leads", ["export_status"], unique=False)

    # ── 导出批次与批次明细 ──────────────────────────────────────────────
    op.create_table(
        "export_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=True),
        sa.Column("rows_count", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.LargeBinary(length=16 * 1024 * 1024), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_export_batches_user_id"), "export_batches", ["user_id"], unique=False)
    op.create_table(
        "export_batch_leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["export_batches.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["company_leads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "lead_id", name="uq_export_batch_leads_batch_lead"),
    )
    op.create_index(op.f("ix_export_batch_leads_batch_id"), "export_batch_leads", ["batch_id"], unique=False)
    op.create_index(op.f("ix_export_batch_leads_lead_id"), "export_batch_leads", ["lead_id"], unique=False)

    # ── 存量数据：统一标记已经查看 + 已导出，处理状态按现状推导 ────────────
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE company_leads SET view_status = 'viewed', export_status = 'exported'"))

    rows = bind.execute(
        sa.text(
            "SELECT l.id,"
            "  (SELECT MAX(id) FROM diagnosis_submissions WHERE lead_id = l.id) AS submission_id"
            " FROM company_leads l"
        )
    ).fetchall()
    updates: list[tuple[str, str | None, int]] = []
    for lead_id, submission_id in rows:
        status, note = _derive_processing_status(bind, submission_id)
        updates.append((status, note, lead_id))
    for status, note, lead_id in updates:
        bind.execute(
            sa.text(
                "UPDATE company_leads SET processing_status = :status, processing_note = :note WHERE id = :lead_id"
            ),
            {"status": status, "note": note, "lead_id": lead_id},
        )


def _derive_processing_status(bind, submission_id) -> tuple[str, str | None]:
    """Derive a legacy lead's processing status from its latest pipeline state."""
    if not submission_id:
        return "pending", None
    report_row = bind.execute(
        sa.text(
            "SELECT id, status, research_status, generation_error FROM reports"
            " WHERE submission_id = :submission_id ORDER BY id DESC LIMIT 1"
        ),
        {"submission_id": submission_id},
    ).first()
    if not report_row:
        return "pending", None
    report_id, report_status, research_status, generation_error = report_row
    delivery_row = bind.execute(
        sa.text(
            "SELECT status, last_error FROM report_delivery_jobs"
            " WHERE report_id = :report_id ORDER BY id DESC LIMIT 1"
        ),
        {"report_id": report_id},
    ).first()
    delivery_status = delivery_row[0] if delivery_row else None
    delivery_error = delivery_row[1] if delivery_row else None

    if delivery_status == "sent":
        return "completed", None
    # 队列/流水线仍在推进（含失败后等待自动重试）→ 处理中；
    # 企业情报已终态失败且没有待处理投递任务时不算推进。
    in_flight = (
        delivery_status in ("queued", "processing")
        or research_status == "processing"
        or (report_status in ("pending", "generating") and research_status not in ("failed", "review"))
    )
    if in_flight:
        return "processing", None
    # 终态失败按根因从上游到下游：企业情报 → AI 报告 → 邮件/PDF
    if research_status in ("failed", "review"):
        return "manual_review", _shorten(_failure_note("企业情报检索失败", generation_error))
    if report_status == "failed":
        return "manual_review", _shorten(_failure_note("AI 报告生成失败", generation_error))
    if delivery_status == "failed":
        return "manual_review", _shorten(_failure_note("邮件/PDF 投递失败", delivery_error))
    if report_status in ("generated", "fallback") and delivery_status is None:
        return "manual_review", "报告已生成，未创建投递任务（可能缺少诊断邮箱）"
    return "pending", None


def _shorten(text: str, limit: int = 500) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


_KNOWN_FAILURE_PREFIXES = (
    "企业情报检索失败",
    "公司情报检索失败",
    "AI 报告生成失败",
    "邮件/PDF 投递失败",
    "邮件发送失败",
    "PDF 生成或校验失败",
)


def _failure_note(prefix: str, error: str | None) -> str:
    error = (error or "").strip()
    if not error:
        return f"{prefix}（未知原因）"
    # 上游模块写入的错误自带同类前缀（如「公司情报检索失败：」）时不再重复拼接。
    if error.startswith(_KNOWN_FAILURE_PREFIXES):
        return error
    return f"{prefix}：{error}"


def downgrade() -> None:
    """Drop the tables and columns created by this migration.

    The status columns only hold tracking bookkeeping and can be re-derived;
    export batch snapshots are recoverable by re-exporting leads.
    """
    op.drop_index(op.f("ix_export_batch_leads_lead_id"), table_name="export_batch_leads")
    op.drop_index(op.f("ix_export_batch_leads_batch_id"), table_name="export_batch_leads")
    op.drop_table("export_batch_leads")
    op.drop_index(op.f("ix_export_batches_user_id"), table_name="export_batches")
    op.drop_table("export_batches")

    op.drop_index("ix_company_leads_export_status", table_name="company_leads")
    op.drop_index("ix_company_leads_processing_status", table_name="company_leads")
    op.drop_index("ix_company_leads_view_status", table_name="company_leads")
    op.drop_column("company_leads", "last_exported_at")
    op.drop_column("company_leads", "first_exported_at")
    op.drop_column("company_leads", "export_status")
    op.drop_column("company_leads", "processing_note")
    op.drop_column("company_leads", "processing_status")
    op.drop_column("company_leads", "first_viewed_by")
    op.drop_column("company_leads", "first_viewed_at")
    op.drop_column("company_leads", "view_status")
