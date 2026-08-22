from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CompanyLead, DiagnosisSubmission, DimensionScore, QuestionAnswer, Report, ReportStatus, TrackingEvent
from app.utils.time_utils import CHINA_TIMEZONE, to_china_time


def get_lead_by_session(db: Session, session_token: str) -> CompanyLead | None:
    return db.query(CompanyLead).filter(CompanyLead.session_token == session_token).first()


def _day_range(created_from: date | None, created_to: date | None) -> tuple[datetime | None, datetime | None]:
    """把中国本地日期的起止转换为无时区 UTC 边界，与库内 UTC 存储对齐。

    前端日期筛选按展示的中国时间选择，而 created_at 以无时区 UTC 入库，
    直接用 UTC 日界会漏掉中国当日 0-8 点（UTC 前一天）的记录。
    """
    start = None
    end = None
    if created_from:
        start = (
            datetime.combine(created_from, time.min, tzinfo=CHINA_TIMEZONE)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
    if created_to:
        end = (
            datetime.combine(created_to, time.max, tzinfo=CHINA_TIMEZONE)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
    return start, end


def list_leads(
    db: Session,
    industry: str | None = None,
    lead_level: str | None = None,
    source_code: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    view_status: str | None = None,
    processing_status: str | None = None,
    export_status: str | None = None,
    sort: str = "newest",
    limit: int = 500,
) -> list[CompanyLead]:
    latest_completed_at = (
        select(func.max(DiagnosisSubmission.submitted_at))
        .where(DiagnosisSubmission.lead_id == CompanyLead.id)
        .correlate(CompanyLead)
        .scalar_subquery()
    )
    last_activity_at = func.coalesce(latest_completed_at, CompanyLead.updated_at)
    query = db.query(CompanyLead)
    if industry:
        query = query.filter(CompanyLead.industry == industry)
    if lead_level:
        query = query.filter(CompanyLead.lead_level == lead_level)
    if source_code:
        query = query.filter(CompanyLead.source_code == source_code)
    start, end = _day_range(created_from, created_to)
    if start:
        query = query.filter(CompanyLead.created_at >= start)
    if end:
        query = query.filter(CompanyLead.created_at <= end)
    if view_status:
        query = query.filter(CompanyLead.view_status == view_status)
    if processing_status:
        query = query.filter(CompanyLead.processing_status == processing_status)
    if export_status:
        query = query.filter(CompanyLead.export_status == export_status)
    ordering = last_activity_at.asc() if sort == "oldest" else last_activity_at.desc()
    rows = query.add_columns(last_activity_at.label("last_activity_at")).order_by(ordering).limit(limit).all()
    leads: list[CompanyLead] = []
    for lead, activity_at in rows:
        lead.last_activity_at = activity_at
        leads.append(lead)
    return leads


def latest_submission_for_lead(db: Session, lead_id: int) -> DiagnosisSubmission | None:
    return (
        db.query(DiagnosisSubmission)
        .filter(DiagnosisSubmission.lead_id == lead_id)
        .order_by(DiagnosisSubmission.id.desc())
        .first()
    )


def get_submission_by_id(db: Session, submission_id: int) -> DiagnosisSubmission | None:
    return db.query(DiagnosisSubmission).filter(DiagnosisSubmission.id == submission_id).first()


def get_report_by_public_token(db: Session, public_token: str) -> Report | None:
    return db.query(Report).filter(Report.public_token == public_token).first()


def get_report_by_id(db: Session, report_id: int) -> Report | None:
    return db.query(Report).filter(Report.id == report_id).first()


def get_event_counts_map(db: Session) -> dict[str, int]:
    rows = db.query(TrackingEvent.event_name, func.count(TrackingEvent.id)).group_by(TrackingEvent.event_name).all()
    return dict(rows)


def get_visit_uv(db: Session) -> int:
    return db.query(func.count(func.distinct(TrackingEvent.session_token))).filter(TrackingEvent.event_name == "enter_site").scalar() or 0


def get_report_generated_count(db: Session) -> int:
    return db.query(func.count(Report.id)).filter(Report.status.in_([ReportStatus.generated.value, ReportStatus.fallback.value])).scalar() or 0


def get_high_intent_lead_count(db: Session) -> int:
    return db.query(func.count(CompanyLead.id)).filter(CompanyLead.lead_level == "high").scalar() or 0


def get_total_lead_count(db: Session) -> int:
    return db.query(func.count(CompanyLead.id)).scalar() or 0


def get_lead_group_counts(db: Session, column) -> list[dict]:
    rows = (
        db.query(column, func.count(CompanyLead.id))
        .group_by(column)
        .order_by(func.count(CompanyLead.id).desc())
        .all()
    )
    return [{"label": label or "未填写", "count": count} for label, count in rows]


def get_questionnaire_hourly_counts(db: Session) -> list[dict]:
    events = (
        db.query(TrackingEvent.created_at)
        .filter(TrackingEvent.event_name == "submit_questionnaire")
        .all()
    )
    buckets = {hour: 0 for hour in range(24)}
    for (created_at,) in events:
        buckets[to_china_time(created_at).hour] += 1
    return [{"label": f"{hour:02d}:00", "count": buckets[hour]} for hour in range(24)]


def list_recent_events(db: Session, limit: int = 200) -> list[TrackingEvent]:
    return db.query(TrackingEvent).order_by(TrackingEvent.created_at.desc()).limit(limit).all()


def list_all_leads(db: Session) -> list[CompanyLead]:
    return db.query(CompanyLead).order_by(CompanyLead.created_at.desc()).all()


def get_existing_answers(db: Session, submission_id: int, question_ids: set[int]) -> dict[int, QuestionAnswer]:
    rows = (
        db.query(QuestionAnswer)
        .filter(QuestionAnswer.submission_id == submission_id, QuestionAnswer.question_id.in_(question_ids))
        .all()
    )
    return {row.question_id: row for row in rows}


def get_answer_map(db: Session, submission_id: int) -> dict[int, int]:
    rows = db.query(QuestionAnswer).filter(QuestionAnswer.submission_id == submission_id).all()
    return {row.question_id: row.score for row in rows}


def delete_dimension_scores(db: Session, submission_id: int) -> None:
    db.query(DimensionScore).filter(DimensionScore.submission_id == submission_id).delete()


def delete_lead_cascade(db: Session, lead: CompanyLead) -> None:
    """级联删除一条客户线索及其全部关联数据（答卷、报告、AI 消息、投递任务、埋点）。

    删除后该线索不再存在，前端会话可重新开始填写。
    """
    from app.models import (
        AiConversationMessage,
        QuestionAnswer,
        Recommendation,
        ReportDeliveryJob,
        TrackingEvent,
    )

    submission_ids = [row.id for row in db.query(DiagnosisSubmission.id).filter(DiagnosisSubmission.lead_id == lead.id).all()]
    report_ids = (
        [row.id for row in db.query(Report.id).filter(Report.submission_id.in_(submission_ids)).all()]
        if submission_ids
        else []
    )

    if report_ids:
        db.query(Recommendation).filter(Recommendation.report_id.in_(report_ids)).delete()
        db.query(AiConversationMessage).filter(AiConversationMessage.report_id.in_(report_ids)).delete()
        db.query(ReportDeliveryJob).filter(ReportDeliveryJob.report_id.in_(report_ids)).delete()
        db.query(Report).filter(Report.id.in_(report_ids)).delete()
    if submission_ids:
        db.query(AiConversationMessage).filter(AiConversationMessage.submission_id.in_(submission_ids)).delete()
        db.query(ReportDeliveryJob).filter(ReportDeliveryJob.submission_id.in_(submission_ids)).delete()
        db.query(QuestionAnswer).filter(QuestionAnswer.submission_id.in_(submission_ids)).delete()
        db.query(DimensionScore).filter(DimensionScore.submission_id.in_(submission_ids)).delete()
        db.query(DiagnosisSubmission).filter(DiagnosisSubmission.id.in_(submission_ids)).delete()

    db.query(AiConversationMessage).filter(AiConversationMessage.lead_id == lead.id).delete()
    db.query(ReportDeliveryJob).filter(ReportDeliveryJob.lead_id == lead.id).delete()
    db.query(TrackingEvent).filter(TrackingEvent.lead_id == lead.id).delete()
    # 删除线索时清掉批次明细；批次 CSV 快照保留，历史批次仍可重新下载。
    from app.models import ExportBatchLead

    db.query(ExportBatchLead).filter(ExportBatchLead.lead_id == lead.id).delete()
    db.delete(lead)
