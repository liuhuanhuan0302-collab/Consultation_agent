"""线索管理 — 列表 / CSV 导出 / 详情 / 更正诊断邮箱 / Word 档案导出。"""

import csv
import json
from io import StringIO

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin._shared import escape_csv_cell
from app.database import get_db
from app.models import AiConversationMessage, CompanyLead, ExportLog, ReportDeliveryJob, User
from app.repositories.consult_repo import latest_submission_for_lead, list_leads
from app.repositories.qr_code_repo import get_channel_by_code
from app.schemas import LeadDiagnosticEmailUpdate, LeadResponse, MessageResponse
from app.service.lead_export_service import generate_lead_export_docx
from app.service.report_queue import enqueue_report_delivery, process_next_report_delivery
from app.utils.auth import LeadExporter, LeadViewer
from app.utils.logging_utils import write_operation_log

router = APIRouter()


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
        headers={"Content-Disposition": f'attachment; filename="lead-{lead.id}.docx"'},
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
