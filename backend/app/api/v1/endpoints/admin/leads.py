"""线索管理 — 列表 / CSV 导出 / 详情 / 更正诊断邮箱 / Word 档案导出 / 手动企业情报检索。"""

import csv
import json
import logging
import re
from io import StringIO
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin._shared import escape_csv_cell
from app.database import SessionLocal, get_db
from app.models import AiConversationMessage, CompanyLead, ExportLog, Report, ReportDeliveryJob, User
from app.repositories.consult_repo import delete_lead_cascade, latest_submission_for_lead, list_leads
from app.repositories.qr_code_repo import get_channel_by_code
from app.schemas import LeadDiagnosticEmailUpdate, LeadResponse, MessageResponse
from app.service.api_gateway_service import effective_search_config
from app.service.company_research import research_company
from app.service.lead_export_service import generate_lead_export_docx
from app.service.report_queue import enqueue_report_delivery, process_next_report_delivery
from app.utils.auth import AdminOnly, LeadExporter, LeadViewer
from app.utils.logging_utils import write_operation_log

router = APIRouter()
logger = logging.getLogger(__name__)


async def run_company_research_task(report_id: int) -> None:
    """后台执行企业情报检索（联网搜索 + AI 提炼），失败仅记录日志不影响请求。"""
    db = SessionLocal()
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            return
        await research_company(db, report)
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("手动企业情报检索失败 report_id=%s", report_id)
        db.rollback()
    finally:
        db.close()


def lead_word_filename(company_name: str | None) -> str:
    """生成浏览器下载用的客户详情 Word 文件名。"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", (company_name or "").strip()).strip(". ")
    return f"{name or '客户'}客户详情.docx"


# ══════════════════════════════════════════════════════════════════
# 3.5 线索列表
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/leads
# 功能：查看所有客户线索，最多 500 条
#       支持按 行业 / 线索等级 / 来源渠道 筛选
# 鉴权：admin / operator / sales / consultant
# 查询参数（均可选）：
#       ?industry=制造业&lead_level=high&source_code=wechat_mp
# 返回：LeadResponse[] 数组（按创建时间倒序）
@router.get("/api/admin/leads", response_model=list[LeadResponse])
def admin_list_leads(
    industry: str | None = None,
    lead_level: str | None = None,
    source_code: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(LeadViewer),
) -> list[CompanyLead]:
    return list_leads(db, industry=industry, lead_level=lead_level, source_code=source_code)


# ══════════════════════════════════════════════════════════════════
# 3.6 导出线索 CSV
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/leads/export
# 功能：导出全部线索为 CSV 文件（最多 10 万条）
#       CSV 列：公司, 行业, 规模, 联系人, 职位, 手机, 微信, 来源, 线索等级, 创建时间
# 鉴权：admin / operator / sales
# 返回：CSV 文件下载（Content-Type: text/csv）
#       文件名：leads.csv
@router.get("/api/admin/leads/export")
def export_leads(db: Session = Depends(get_db), user: User = Depends(LeadExporter)) -> StreamingResponse:
    leads = list_leads(db, limit=100000)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["公司", "行业", "规模", "联系人", "职位", "手机", "邮箱", "微信", "来源", "线索等级", "诉求摘要", "创建时间"])
    for lead in leads:
        writer.writerow(
            [
                escape_csv_cell(lead.company_name),
                escape_csv_cell(lead.industry),
                escape_csv_cell(lead.company_size),
                escape_csv_cell(lead.contact_name),
                escape_csv_cell(lead.position),
                escape_csv_cell(lead.phone),
                escape_csv_cell(lead.email),
                escape_csv_cell(lead.wechat),
                escape_csv_cell(lead.source_code),
                escape_csv_cell(lead.lead_level),
                escape_csv_cell(lead.demand_summary),
                escape_csv_cell(lead.created_at.isoformat()),
            ]
        )
    db.add(ExportLog(user_id=user.id, export_type="leads", filters_json=None, rows_count=len(leads)))
    write_operation_log(db, user, "export_leads", "lead", "all", {"rows": len(leads)})
    db.commit()
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


# ══════════════════════════════════════════════════════════════════
# 3.6.1 更正诊断邮箱并重新发送报告
# ══════════════════════════════════════════════════════════════════
@router.put("/api/admin/leads/{lead_id}/diagnostic-email", response_model=MessageResponse)
async def update_lead_diagnostic_email(
    lead_id: int,
    payload: LeadDiagnosticEmailUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(LeadExporter),
) -> MessageResponse:
    lead = db.query(CompanyLead).filter(CompanyLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.email = str(payload.email).strip().lower()
    submission = latest_submission_for_lead(db, lead.id)
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
        background_tasks.add_task(process_next_report_delivery)
        return MessageResponse(message="诊断邮箱已更正，报告已重新加入发送队列")
    return MessageResponse(message="诊断邮箱已更正；该客户尚未生成报告")


# ══════════════════════════════════════════════════════════════════
# 3.6.2 导出单个客户 Word 档案
# ══════════════════════════════════════════════════════════════════
@router.get("/api/admin/leads/{lead_id}/export/word")
def export_lead_word(lead_id: int, db: Session = Depends(get_db), user: User = Depends(LeadExporter)) -> StreamingResponse:
    lead = db.query(CompanyLead).filter(CompanyLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    submission = latest_submission_for_lead(db, lead.id)
    report = submission.report if submission else None
    channel = get_channel_by_code(db, lead.source_code) if lead.source_code else None
    document = generate_lead_export_docx(lead, submission, report, source_name=channel.name if channel else None)
    db.add(ExportLog(user_id=user.id, export_type="lead_word", filters_json=json.dumps({"lead_id": lead.id}), rows_count=1))
    write_operation_log(db, user, "export_lead_word", "lead", str(lead.id))
    db.commit()
    return StreamingResponse(
        iter([document]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": (
                'attachment; filename="customer-detail.docx"; '
                f"filename*=UTF-8''{quote(lead_word_filename(lead.company_name))}"
            )
        },
    )


# ══════════════════════════════════════════════════════════════════
# 3.6.3 查看线索详情
# ══════════════════════════════════════════════════════════════════
@router.get("/api/admin/leads/{lead_id}")
def admin_get_lead_detail(lead_id: int, db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> dict:
    lead = db.query(CompanyLead).filter(CompanyLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    submission = latest_submission_for_lead(db, lead.id)
    report = submission.report if submission else None
    delivery = None
    if report:
        delivery = (
            db.query(ReportDeliveryJob)
            .filter(ReportDeliveryJob.report_id == report.id)
            .order_by(ReportDeliveryJob.created_at.desc())
            .first()
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

    advisor_messages = []
    if report:
        advisor_messages = (
            db.query(AiConversationMessage)
            .filter(AiConversationMessage.report_id == report.id)
            .order_by(AiConversationMessage.created_at.asc())
            .all()
        )

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
            "html_content": report.html_content,
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
        } if delivery else None,
    }


# ══════════════════════════════════════════════════════════════════
# 3.6.5 删除线索（级联清理）
# ══════════════════════════════════════════════════════════════════
# 方法：DELETE
# 路径：/api/admin/leads/{lead_id}
# 功能：删除一条客户线索及其全部关联数据（企业信息、答题、评分、报告、
#       AI 会话消息、报告投递任务、埋点事件）。删除后该客户可重新填写。
# 鉴权：仅 admin
@router.delete("/api/admin/leads/{lead_id}", response_model=MessageResponse)
def admin_delete_lead(lead_id: int, db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> MessageResponse:
    lead = db.query(CompanyLead).filter(CompanyLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    company_name = lead.company_name
    delete_lead_cascade(db, lead)
    write_operation_log(db, user, "delete_lead", "lead", str(lead_id), {"company_name": company_name})
    db.commit()
    return MessageResponse(message=f"已删除线索「{company_name or lead_id}」及其全部关联数据")


# ══════════════════════════════════════════════════════════════════
# 3.6.4 手动检索企业情报与 AI 分析
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/leads/{lead_id}/research
# 功能：企业情报未生成时，手动触发联网搜索 + AI 提炼（7 维情报与综合分析）
#       检索在后台任务中异步执行，接口立即返回；前端轮询线索详情刷新结果
# 鉴权：admin / operator / sales / consultant
# 返回：{ status: "started" | "already_generated", message }
@router.post("/api/admin/leads/{lead_id}/research")
def trigger_lead_research(
    lead_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(LeadViewer),
) -> dict:
    lead = db.query(CompanyLead).filter(CompanyLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    submission = latest_submission_for_lead(db, lead.id)
    report = submission.report if submission else None
    if not report:
        raise HTTPException(status_code=404, detail="该线索还没有诊断报告，暂无法检索企业信息")

    company_name = (lead.company_name or "").strip()
    if len(company_name) < 4:
        raise HTTPException(status_code=422, detail="公司名称过短（至少 4 个字），无法检索企业信息")

    if report.company_research_json:
        return {"status": "already_generated", "message": "企业情报已生成，无需重复检索"}

    if not effective_search_config(db):
        raise HTTPException(status_code=422, detail="联网搜索未启用，请先在「API 配置」页启用并保存搜索 Key")

    write_operation_log(db, user, "trigger_lead_research", "lead", str(lead.id))
    db.commit()
    background_tasks.add_task(run_company_research_task, report.id)
    return {"status": "started", "message": "已开始联网检索企业信息，完成后会自动刷新"}
