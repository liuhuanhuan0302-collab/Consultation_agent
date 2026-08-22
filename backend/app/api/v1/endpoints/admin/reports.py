"""报告详情 — 后台查看诊断报告完整内容。"""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AiConversationMessage, User
from app.repositories.consult_repo import get_report_by_id
from app.service.report_content import sanitize_report_content
from app.utils.auth import ReportViewer

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# 3.7 查看报告详情
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/reports/{report_id}
# 功能：后台查看某份诊断报告的完整内容（HTML + 结构化摘要 JSON）
#       注意：report_id 是数字 ID，不是 public_token
# 鉴权：admin / operator / sales / consultant
# 请求：路径参数 report_id (int)
# 返回：{ id, public_token, title, status, html_content, summary, created_at }
@router.get("/api/admin/reports/{report_id}")
def admin_get_report(report_id: int, db: Session = Depends(get_db), user: User = Depends(ReportViewer)) -> dict:
    report = get_report_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    advisor_messages = (
        db.query(AiConversationMessage)
        .filter(AiConversationMessage.report_id == report.id)
        .order_by(AiConversationMessage.created_at.asc())
        .all()
    )
    return {
        "id": report.id,
        "public_token": report.public_token,
        "title": report.title,
        "status": report.status,
        "html_content": sanitize_report_content(report.html_content),
        "summary": json.loads(report.summary_json or "{}"),
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
        "created_at": report.created_at,
    }
