"""HTTP-independent admin lead workflows."""

import csv
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.export_batch import ExportBatch, ExportBatchLead
from app.models.lead import CompanyLead
from app.models.report import (
    CompanyResearchStatus,
    ReportDeliveryStatus,
    ReportFileStatus,
    ReportStatus,
)
from app.models.user import User
from app.repositories import lead_repo
from app.repositories.consult_repo import delete_lead_cascade, list_leads
from app.repositories.qr_code_repo import get_channel_by_code
from app.schemas.lead import ExportBatchResponse, LeadResponse
from app.service.api_gateway_service import effective_search_config
from app.service.company_research import research_company
from app.service.lead_export_service import generate_lead_export_docx
from app.service.lead_status import sync_lead_processing_status
from app.service.report_content import sanitize_report_content
from app.service.report_queue import enqueue_report_delivery
from app.utils.logging_utils import write_operation_log
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

# 三维状态的中文标签（CSV 导出与批次摘要使用）。
VIEW_STATUS_LABELS = {"unviewed": "尚未查看", "viewed": "已经查看"}
PROCESSING_STATUS_LABELS = {
    "pending": "待处理",
    "processing": "处理中",
    "manual_review": "待人工处理",
    "completed": "已完成",
}
EXPORT_STATUS_LABELS = {"unexported": "未导出", "exported": "已导出"}


class LeadServiceError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class LeadNotFoundError(LeadServiceError):
    pass


class LeadReportNotFoundError(LeadServiceError):
    pass


class LeadValidationError(LeadServiceError):
    pass


@dataclass(frozen=True)
class DiagnosticEmailResult:
    message: str
    should_process_queue: bool


@dataclass(frozen=True)
class LeadWordExport:
    document: bytes
    filename: str


@dataclass(frozen=True)
class ResearchTriggerResult:
    status: str
    message: str
    report_id: int | None = None
    force: bool = False


@dataclass(frozen=True)
class ResumeDeliveryResult:
    message: str
    should_process_queue: bool
    report_id: int | None = None


def elapsed_seconds(started_at: datetime | None, completed_at: datetime | None) -> int | None:
    if not started_at:
        return None
    end = completed_at or utc_now()
    return max(0, int((end - started_at).total_seconds()))


def lead_word_filename(company_name: str | None) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", (company_name or "").strip()).strip(". ")
    return f"{name or '客户'}客户详情.docx"


def _escape_csv_cell(value: object | None) -> object | None:
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


LEAD_CSV_HEADER = [
    "公司", "行业", "规模", "联系人", "职位", "手机", "邮箱", "微信", "来源", "线索等级", "诉求摘要", "创建时间",
    "查看状态", "处理状态", "处理备注", "导出状态", "首次查看时间", "首次导出时间", "最近导出时间",
]


def _csv_time(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def build_leads_csv_rows(leads: list[CompanyLead]) -> list[list[object]]:
    rows = [LEAD_CSV_HEADER]
    for lead in leads:
        rows.append(
            [
                _escape_csv_cell(lead.company_name),
                _escape_csv_cell(lead.industry),
                _escape_csv_cell(lead.company_size),
                _escape_csv_cell(lead.contact_name),
                _escape_csv_cell(lead.position),
                _escape_csv_cell(lead.phone),
                _escape_csv_cell(lead.email),
                _escape_csv_cell(lead.wechat),
                _escape_csv_cell(lead.source_code),
                _escape_csv_cell(lead.lead_level),
                _escape_csv_cell(lead.demand_summary),
                _escape_csv_cell(lead.created_at.isoformat()),
                VIEW_STATUS_LABELS.get(lead.view_status, lead.view_status),
                PROCESSING_STATUS_LABELS.get(lead.processing_status, lead.processing_status),
                _escape_csv_cell(lead.processing_note),
                EXPORT_STATUS_LABELS.get(lead.export_status, lead.export_status),
                _csv_time(lead.first_viewed_at),
                _csv_time(lead.first_exported_at),
                _csv_time(lead.last_exported_at),
            ]
        )
    return rows


def leads_csv(leads: list[CompanyLead]) -> str:
    buffer = StringIO()
    csv.writer(buffer).writerows(build_leads_csv_rows(leads))
    return buffer.getvalue()


def list_admin_leads(
    db: Session,
    *,
    industry: str | None = None,
    lead_level: str | None = None,
    source_code: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    view_status: str | None = None,
    processing_status: str | None = None,
    export_status: str | None = None,
    sort: str = "newest",
) -> list[CompanyLead]:
    return list_leads(
        db,
        industry=industry,
        lead_level=lead_level,
        source_code=source_code,
        created_from=created_from,
        created_to=created_to,
        view_status=view_status,
        processing_status=processing_status,
        export_status=export_status,
        sort=sort,
    )


def export_leads_csv(
    db: Session,
    user: User,
    *,
    industry: str | None = None,
    lead_level: str | None = None,
    source_code: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    view_status: str | None = None,
    processing_status: str | None = None,
    export_status: str | None = None,
    sort: str = "newest",
) -> str:
    """导出筛选结果：按当前筛选导出 CSV，不标记已导出、不建批次。"""
    leads = list_leads(
        db,
        industry=industry,
        lead_level=lead_level,
        source_code=source_code,
        created_from=created_from,
        created_to=created_to,
        view_status=view_status,
        processing_status=processing_status,
        export_status=export_status,
        sort=sort,
        limit=100000,
    )
    filters = {
        key: value
        for key, value in {
            "industry": industry,
            "lead_level": lead_level,
            "source_code": source_code,
            "created_from": created_from.isoformat() if created_from else None,
            "created_to": created_to.isoformat() if created_to else None,
            "view_status": view_status,
            "processing_status": processing_status,
            "export_status": export_status,
        }.items()
        if value is not None
    }
    lead_repo.add_export_log(db, user_id=user.id, export_type="leads", rows_count=len(leads), filters=filters)
    write_operation_log(db, user, "export_leads", "lead", "all", {"rows": len(leads), "filters": filters})
    db.commit()
    return leads_csv(leads)


@dataclass(frozen=True)
class ExportBatchResult:
    batch_id: int | None
    rows_count: int
    message: str


def export_unexported_leads(db: Session, user: User) -> ExportBatchResult:
    """一键导出未导出客户：标记已导出、保存批次快照与客户清单。

    同一事务内对未导出客户行加锁（MySQL FOR UPDATE），防止多人同时导出
    重复标记；CSV 快照独立保存，之后线索被删除也不影响历史批次重新下载。
    """
    leads = (
        db.query(CompanyLead)
        .filter(
            CompanyLead.export_status == "unexported",
            CompanyLead.company_name.is_not(None),
            CompanyLead.company_name != "",
        )
        .order_by(CompanyLead.created_at.asc())
        .with_for_update()
        .all()
    )
    if not leads:
        write_operation_log(db, user, "export_unexported_leads", "lead", "all", {"rows": 0})
        db.commit()
        return ExportBatchResult(None, 0, "没有未导出的客户，无需重复导出")

    exported_at = utc_now()
    for lead in leads:
        lead.export_status = "exported"
        lead.first_exported_at = lead.first_exported_at or exported_at
        lead.last_exported_at = exported_at
    db.flush()

    batch = ExportBatch(
        user_id=user.id,
        filters_json=json.dumps({"kind": "unexported_leads"}, ensure_ascii=False),
        rows_count=len(leads),
        file_name=f"leads-unexported-{exported_at.strftime('%Y%m%d-%H%M%S')}.csv",
        content=leads_csv(leads).encode("utf-8"),
    )
    db.add(batch)
    db.flush()
    for lead in leads:
        db.add(ExportBatchLead(batch_id=batch.id, lead_id=lead.id))
    lead_repo.add_export_log(
        db,
        user_id=user.id,
        export_type="leads_unexported_batch",
        rows_count=len(leads),
        filters={"kind": "unexported_leads"},
    )
    write_operation_log(
        db,
        user,
        "export_unexported_leads",
        "lead",
        "all",
        {"batch_id": batch.id, "rows": len(leads)},
    )
    db.commit()
    return ExportBatchResult(batch.id, len(leads), f"已导出 {len(leads)} 位未导出客户，本批已标记为已导出")


def list_export_batches(db: Session) -> list[ExportBatchResponse]:
    batches = lead_repo.list_export_batches(db)
    users = {batch.user_id: db.get(User, batch.user_id) for batch in batches}
    responses = []
    for batch in batches:
        operator = users.get(batch.user_id)
        filters = json.loads(batch.filters_json or "{}")
        responses.append(
            ExportBatchResponse(
                id=batch.id,
                created_at=batch.created_at,
                rows_count=batch.rows_count,
                file_name=batch.file_name,
                exported_by=(operator.name or operator.email) if operator else None,
                filters_summary="一键导出未导出客户" if filters.get("kind") == "unexported_leads" else None,
            )
        )
    return responses


@dataclass(frozen=True)
class BatchDownload:
    content: bytes
    filename: str


def download_export_batch(db: Session, batch_id: int) -> BatchDownload:
    batch = lead_repo.get_export_batch(db, batch_id)
    if not batch:
        raise LeadNotFoundError("Batch not found")
    return BatchDownload(content=batch.content, filename=batch.file_name)


def update_diagnostic_email(db: Session, user: User, lead_id: int, email: str) -> DiagnosticEmailResult:
    lead = lead_repo.get_lead_by_id(db, lead_id)
    if not lead:
        raise LeadNotFoundError("Lead not found")
    lead.email = email.strip().lower()
    submission = lead_repo.latest_submission_for_lead(db, lead.id)
    report = submission.report if submission else None
    if report:
        try:
            enqueue_report_delivery(db, report, lead.email)
        except ValueError:
            report = None
    write_operation_log(
        db,
        user,
        "update_lead_diagnostic_email",
        "lead",
        lead.id,
        {"report_resent": bool(report)},
    )
    db.commit()
    if report:
        return DiagnosticEmailResult("诊断邮箱已更正，报告已重新加入发送队列", True)
    return DiagnosticEmailResult("诊断邮箱已更正；该客户尚未生成报告", False)


def export_lead_word(db: Session, user: User, lead_id: int) -> LeadWordExport:
    lead = lead_repo.get_lead_by_id(db, lead_id)
    if not lead:
        raise LeadNotFoundError("Lead not found")
    submission = lead_repo.latest_submission_for_lead(db, lead.id)
    report = submission.report if submission else None
    channel = get_channel_by_code(db, lead.source_code) if lead.source_code else None
    sent_delivery = lead_repo.latest_sent_delivery_for_report(db, report.id) if report else None
    document = generate_lead_export_docx(
        lead,
        submission,
        report,
        source_name=channel.name if channel else None,
        final_report_sent=sent_delivery is not None,
    )
    lead_repo.add_export_log(
        db,
        user_id=user.id,
        export_type="lead_word",
        rows_count=1,
        filters={"lead_id": lead.id},
    )
    write_operation_log(db, user, "export_lead_word", "lead", str(lead.id))
    db.commit()
    return LeadWordExport(document=document, filename=lead_word_filename(lead.company_name))


def get_lead_detail(db: Session, lead_id: int, user: User | None = None) -> dict:
    lead = lead_repo.get_lead_by_id(db, lead_id)
    if not lead:
        raise LeadNotFoundError("Lead not found")
    if user is not None and lead.view_status != "viewed":
        # 首次打开详情：记录查看状态与首次查看人；之后重复打开不再更新。
        lead.view_status = "viewed"
        lead.first_viewed_at = utc_now()
        lead.first_viewed_by = user.name or user.email
        write_operation_log(db, user, "view_lead", "lead", str(lead.id))
        db.commit()
    submission = lead_repo.latest_submission_for_lead(db, lead.id)
    report = submission.report if submission else None
    delivery = lead_repo.latest_delivery_for_report(db, report.id) if report else None
    queue_position = (
        lead_repo.queued_delivery_position(db, delivery.id)
        if delivery and delivery.status == "queued"
        else None
    )
    dimensions = []
    if submission:
        dimensions = [
            {
                "module_code": item.module.code,
                "module_name": item.module.name,
                "raw_score": item.raw_score,
                "max_score": item.max_score,
                "score_rate": item.score_rate,
                "risk_level": item.risk_level,
            }
            for item in sorted(submission.dimension_scores, key=lambda score: score.module.sort_order)
        ]
    advisor_messages = lead_repo.advisor_messages_for_report(db, report.id) if report else []
    return {
        "lead": LeadResponse.model_validate(lead).model_dump(mode="json"),
        "submission": {
            "id": submission.id,
            "status": submission.status,
            "total_score": submission.total_score,
            "max_score": submission.max_score,
            "score_rate": submission.score_rate,
            "risk_level": submission.risk_level,
            "created_at": submission.created_at,
            "submitted_at": submission.submitted_at,
            "dimensions": dimensions,
        } if submission else None,
        "report": {
            "id": report.id,
            "public_token": report.public_token,
            "title": report.title,
            "status": report.status,
            "research_status": report.research_status,
            "research_started_at": report.research_started_at,
            "research_completed_at": report.research_completed_at,
            "research_elapsed_seconds": elapsed_seconds(report.research_started_at, report.research_completed_at),
            "generation_started_at": report.generation_started_at,
            "generation_completed_at": report.generation_completed_at,
            "generation_elapsed_seconds": elapsed_seconds(report.generation_started_at, report.generation_completed_at),
            "pdf_status": report.pdf_status,
            "pdf_started_at": report.pdf_started_at,
            "pdf_completed_at": report.pdf_completed_at,
            "pdf_elapsed_seconds": elapsed_seconds(report.pdf_started_at, report.pdf_completed_at),
            "html_content": sanitize_report_content(report.html_content),
            "summary": json.loads(report.summary_json or "{}"),
            "company_research": json.loads(report.company_research_json) if report.company_research_json else None,
            "generation_error": report.generation_error,
            "created_at": report.created_at,
            "advisor_messages": [
                {
                    "role": message.role,
                    "purpose": message.purpose,
                    "content": message.content,
                    "model_vendor": message.model_vendor,
                    "model_name": message.model_name,
                    "created_at": message.created_at,
                }
                for message in advisor_messages
            ],
        } if report else None,
        "delivery": {
            "status": delivery.status,
            "recipient_email": delivery.recipient_email,
            "last_error": delivery.last_error,
            "sent_at": delivery.sent_at,
            "started_at": delivery.locked_at,
            "updated_at": delivery.updated_at,
            "elapsed_seconds": elapsed_seconds(
                delivery.locked_at or delivery.created_at,
                delivery.sent_at or (delivery.updated_at if delivery.status == "failed" else None),
            ),
            "queue_position": queue_position,
        } if delivery else None,
    }


def delete_lead(db: Session, user: User, lead_id: int) -> str:
    lead = lead_repo.get_lead_by_id(db, lead_id)
    if not lead:
        raise LeadNotFoundError("Lead not found")
    company_name = lead.company_name
    delete_lead_cascade(db, lead)
    write_operation_log(db, user, "delete_lead", "lead", str(lead_id), {"company_name": company_name})
    db.commit()
    return f"已删除线索「{company_name or lead_id}」及其全部关联数据"


def trigger_research(db: Session, user: User, lead_id: int, force: bool) -> ResearchTriggerResult:
    lead = lead_repo.get_lead_by_id(db, lead_id)
    if not lead:
        raise LeadNotFoundError("Lead not found")
    submission = lead_repo.latest_submission_for_lead(db, lead.id)
    report = submission.report if submission else None
    if not report:
        raise LeadReportNotFoundError("该线索还没有诊断报告，暂无法检索企业信息")
    if not (lead.company_name or "").strip():
        raise LeadValidationError("公司名称为空，无法检索企业信息")
    if report.company_research_json and not force:
        return ResearchTriggerResult("already_generated", "企业情报已生成，无需重复检索")
    if not effective_search_config(db):
        raise LeadValidationError("联网搜索未启用，请先在「API 配置」页启用并保存搜索 Key")
    write_operation_log(db, user, "trigger_lead_research", "lead", str(lead.id))
    report.research_status = CompanyResearchStatus.processing.value
    report.research_started_at = utc_now()
    report.research_completed_at = None
    sync_lead_processing_status(db, lead.id)
    db.commit()
    message = "已开始重新检索企业信息，成功后会替换原结果" if force else "已开始联网检索企业信息，完成后会自动刷新"
    return ResearchTriggerResult("started", message, report.id, force)


async def run_company_research_task(report_id: int, force: bool = False) -> None:
    db = SessionLocal()
    try:
        report = lead_repo.get_report_by_id(db, report_id)
        if not report:
            return
        await research_company(db, report, force=force)
        # 手动检索结束后同步线索处理状态：检索失败→待人工处理（附原因）。
        if report.submission:
            sync_lead_processing_status(db, report.submission.lead_id)
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("手动企业情报检索失败 report_id=%s", report_id)
        db.rollback()
    finally:
        db.close()


def resume_report_delivery(db: Session, user: User, lead_id: int) -> ResumeDeliveryResult:
    """企业情报已生成、但报告/投递任务失败或耗尽重试时，重置状态重新入队。

    流程从已有企业情报继续：生成 AI 报告 → 生成 PDF → 发送邮件，
    不再重新搜索。投递任务不存在时按客户邮箱新建一条。
    """
    lead = lead_repo.get_lead_by_id(db, lead_id)
    if not lead:
        raise LeadNotFoundError("Lead not found")
    submission = lead_repo.latest_submission_for_lead(db, lead.id)
    report = submission.report if submission else None
    if not report:
        raise LeadReportNotFoundError("该线索还没有诊断报告，暂无法继续生成")
    if not report.company_research_json:
        raise LeadValidationError("企业情报尚未生成，请先手动搜索企业信息")
    delivery = lead_repo.latest_delivery_for_report(db, report.id)
    if delivery and delivery.status == ReportDeliveryStatus.sent.value:
        raise LeadValidationError("报告已成功发送给客户，无需继续生成")
    if delivery and delivery.status in (
        ReportDeliveryStatus.queued.value,
        ReportDeliveryStatus.processing.value,
    ):
        raise LeadValidationError("报告投递任务已在队列中，无需继续生成")

    report.status = ReportStatus.pending.value
    report.generation_error = None
    report.pdf_status = ReportFileStatus.pending.value
    if delivery:
        delivery.status = ReportDeliveryStatus.queued.value
        delivery.attempts = 0
        delivery.last_error = None
        delivery.run_after = utc_now()
        delivery.locked_at = None
    else:
        if not (lead.email or "").strip():
            raise LeadValidationError("客户邮箱为空，无法创建投递任务，请先更正诊断邮箱")
        delivery = enqueue_report_delivery(db, report, lead.email)
    write_operation_log(
        db,
        user,
        "resume_report_delivery",
        "lead",
        str(lead.id),
        {"report_id": report.id, "delivery_id": delivery.id},
    )
    sync_lead_processing_status(db, lead.id)
    db.commit()
    return ResumeDeliveryResult("已重新入队，将从已有企业情报继续生成 AI 报告并发送", True, report.id)
