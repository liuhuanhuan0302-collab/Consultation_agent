from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CompanyLead, DiagnosisSubmission, DimensionScore, QuestionAnswer, Report, ReportStatus, TrackingEvent


def get_lead_by_session(db: Session, session_token: str) -> CompanyLead | None:
    return db.query(CompanyLead).filter(CompanyLead.session_token == session_token).first()


def list_leads(
    db: Session,
    industry: str | None = None,
    lead_level: str | None = None,
    source_code: str | None = None,
    limit: int = 500,
) -> list[CompanyLead]:
    query = db.query(CompanyLead)
    if industry:
        query = query.filter(CompanyLead.industry == industry)
    if lead_level:
        query = query.filter(CompanyLead.lead_level == lead_level)
    if source_code:
        query = query.filter(CompanyLead.source_code == source_code)
    return query.order_by(CompanyLead.created_at.desc()).limit(limit).all()


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
        buckets[created_at.hour] += 1
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
