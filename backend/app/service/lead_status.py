"""线索处理状态推导与同步。

处理状态是 company_leads 上的存储列，由本模块的 sync_lead_processing_status
在流水线各转换点统一维护（提交入队、队列领取、检索/报告/投递成功或终态失败、
手动检索、继续生成），保证徽标与流水线真实状态一致。
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import CompanyLead, ReportStatus
from app.models.report import CompanyResearchStatus, ReportDeliveryStatus
from app.repositories import lead_repo

logger = logging.getLogger(__name__)


def _shorten(text: str | None, limit: int = 500) -> str | None:
    if not text:
        return None
    text = text.strip()
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


# 上游模块写入错误时自带的前缀（company_research 写「公司情报检索失败：」，
# report_queue 写「邮件发送失败：」等）。错误已带同类前缀时不再重复拼接。
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
    if error.startswith(_KNOWN_FAILURE_PREFIXES):
        return _shorten(error)
    return _shorten(f"{prefix}：{error}")


def sync_lead_processing_status(db: Session, lead_id: int) -> None:
    """按最新答卷→报告→最新投递任务推导处理状态并写回线索。"""
    lead = db.query(CompanyLead).filter(CompanyLead.id == lead_id).first()
    if not lead:
        return
    submission = lead_repo.latest_submission_for_lead(db, lead.id)
    report = submission.report if submission else None
    delivery = lead_repo.latest_delivery_for_report(db, report.id) if report else None

    status, note = _derive(report, delivery)
    lead.processing_status = status
    lead.processing_note = note


def _derive(report, delivery) -> tuple[str, str | None]:
    if report is None and delivery is None:
        return "pending", None

    if delivery and delivery.status == ReportDeliveryStatus.sent.value:
        return "completed", None

    # 队列/流水线仍在推进（含失败后等待自动重试）时显示处理中，
    # 优先级高于历史失败状态：管理员手动修复启动后徽标立即回到处理中。
    # 企业情报已终态失败且没有待处理投递任务时不算推进（流水线停摆）。
    research_terminal = bool(
        report
        and report.research_status
        in (CompanyResearchStatus.failed.value, CompanyResearchStatus.review.value)
    )
    in_flight = (
        (delivery and delivery.status in (ReportDeliveryStatus.queued.value, ReportDeliveryStatus.processing.value))
        or (report and report.research_status == CompanyResearchStatus.processing.value)
        or (report and report.status in (ReportStatus.pending.value, ReportStatus.generating.value) and not research_terminal)
    )
    if in_flight:
        return "processing", None

    # 终态失败按根因从上游到下游排：企业情报 → AI 报告 → 邮件/PDF。
    if report and report.research_status in (
        CompanyResearchStatus.failed.value,
        CompanyResearchStatus.review.value,
    ):
        return "manual_review", _failure_note("企业情报检索失败", report.generation_error)

    if report and report.status == ReportStatus.failed.value:
        return "manual_review", _failure_note("AI 报告生成失败", report.generation_error)

    if delivery and delivery.status == ReportDeliveryStatus.failed.value:
        return "manual_review", _failure_note("邮件/PDF 投递失败", delivery.last_error)

    if report and report.status in (ReportStatus.generated.value, ReportStatus.fallback.value) and delivery is None:
        return "manual_review", "报告已生成，未创建投递任务（可能缺少诊断邮箱）"

    return "pending", None
