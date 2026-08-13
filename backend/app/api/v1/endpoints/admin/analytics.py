"""统计看板与埋点事件。"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CompanyLead, User
from app.repositories.consult_repo import (
    get_event_counts_map,
    get_high_intent_lead_count,
    get_lead_group_counts,
    get_questionnaire_hourly_counts,
    get_report_generated_count,
    get_total_lead_count,
    get_visit_uv,
    list_recent_events,
)
from app.schemas import AnalyticsSummary
from app.utils.auth import LeadViewer

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# 3.15 统计分析看板
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/analytics/summary
# 功能：后台首页统计看板，展示转化漏斗
# 鉴权：admin / operator / sales / consultant
# 返回：{
#         visit_uv         → 独立访客数（进入页面）
#         started_count    → 点击"开始自测"人数
#         info_completed_count    → 完成企业信息填写
#         questionnaire_completed_count → 完成全部 68 题
#         report_generated_count     → 成功生成报告
#         report_claimed_count       → 下载 PDF 数
#         high_intent_leads → 高意向线索（有联系方式+至少 2 个低分维度）
#         lead_count        → 线索总数
#       }
@router.get("/api/admin/analytics/summary", response_model=AnalyticsSummary)
def analytics_summary(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> AnalyticsSummary:
    event_counts = get_event_counts_map(db)
    visit_uv = get_visit_uv(db)
    started_count = event_counts.get("click_start", 0)
    info_completed_count = event_counts.get("submit_customer_info", 0)
    questionnaire_completed_count = event_counts.get("submit_questionnaire", 0)
    report_generated_count = get_report_generated_count(db)
    report_claimed_count = event_counts.get("claim_full_report", 0)
    lead_count = get_total_lead_count(db)

    def rate(count: int, base: int) -> float:
        return round(count / base, 4) if base else 0

    return AnalyticsSummary(
        visit_uv=visit_uv,
        started_count=started_count,
        info_completed_count=info_completed_count,
        questionnaire_completed_count=questionnaire_completed_count,
        report_generated_count=report_generated_count,
        report_claimed_count=report_claimed_count,
        high_intent_leads=get_high_intent_lead_count(db),
        lead_count=lead_count,
        questionnaire_completion_rate=rate(questionnaire_completed_count, info_completed_count),
        funnel=[
            {"label": "访问 UV", "count": visit_uv, "rate": 1 if visit_uv else 0},
            {"label": "开始自测", "count": started_count, "rate": rate(started_count, visit_uv)},
            {"label": "信息完成", "count": info_completed_count, "rate": rate(info_completed_count, started_count)},
            {"label": "问卷完成", "count": questionnaire_completed_count, "rate": rate(questionnaire_completed_count, info_completed_count)},
            {"label": "报告生成", "count": report_generated_count, "rate": rate(report_generated_count, questionnaire_completed_count)},
            {"label": "报告领取", "count": report_claimed_count, "rate": rate(report_claimed_count, report_generated_count)},
        ],
        hourly_questionnaire_counts=get_questionnaire_hourly_counts(db),
        lead_level_distribution=get_lead_group_counts(db, CompanyLead.lead_level),
        industry_distribution=get_lead_group_counts(db, CompanyLead.industry)[:8],
    )


# ══════════════════════════════════════════════════════════════════
# 3.16 埋点事件列表
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/events
# 功能：查看最近 200 条用户行为埋点事件
# 鉴权：admin / operator / sales / consultant
# 返回：[{ id, session_token, lead_id, event_name, metadata, created_at }]
@router.get("/api/admin/events")
def list_events(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> list[dict]:
    events = list_recent_events(db)
    return [
        {
            "id": event.id,
            "session_token": event.session_token,
            "lead_id": event.lead_id,
            "event_name": event.event_name,
            "metadata": json.loads(event.metadata_json or "{}"),
            "created_at": event.created_at,
        }
        for event in events
    ]
