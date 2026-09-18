"""Read-only queries for the organization diagnosis administrator view."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import case, distinct, func
from sqlalchemy.orm import Query, Session

from app.models import OrganizationAnswer, OrganizationReport, OrganizationSubmission, Question, QuestionModule


def _day_start(value: date) -> datetime:
    return datetime.combine(value, time.min)


def _day_after(value: date) -> datetime:
    return datetime.combine(value + timedelta(days=1), time.min)


def _apply_submission_filters(
    query: Query,
    *,
    company_name: str | None = None,
    department: str | None = None,
    respondent_name: str | None = None,
    status: str | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
) -> Query:
    if company_name:
        query = query.filter(OrganizationSubmission.company_name == company_name)
    if department:
        query = query.filter(OrganizationSubmission.department == department)
    if respondent_name:
        query = query.filter(OrganizationSubmission.respondent_name.like(f"%{respondent_name}%"))
    if status:
        query = query.filter(OrganizationSubmission.status == status)
    if submitted_from:
        query = query.filter(OrganizationSubmission.submitted_at >= _day_start(submitted_from))
    if submitted_to:
        query = query.filter(OrganizationSubmission.submitted_at < _day_after(submitted_to))
    return query


def _summary_columns():
    submitted = case((OrganizationSubmission.status == "submitted", 1), else_=0)
    drafts = case((OrganizationSubmission.status == "draft", 1), else_=0)
    latest_submitted = case(
        (OrganizationSubmission.status == "submitted", OrganizationSubmission.submitted_at),
        else_=None,
    )
    return (
        func.sum(submitted).label("submitted_count"),
        func.sum(drafts).label("draft_count"),
        func.count(distinct(OrganizationSubmission.department)).label("department_count"),
        func.max(latest_submitted).label("latest_submitted_at"),
    )


def _to_summary(row) -> dict:
    return {
        "company_name": row.company_name,
        "submitted_count": int(row.submitted_count or 0),
        "draft_count": int(row.draft_count or 0),
        "department_count": int(row.department_count or 0),
        "latest_submitted_at": row.latest_submitted_at,
    }


def list_company_summaries(
    db: Session,
    *,
    company_name: str | None = None,
    has_submitted: bool | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Find matching company groups, then aggregate each complete company group."""
    scope_query = db.query(OrganizationSubmission.company_name).filter(
        OrganizationSubmission.company_name.isnot(None)
    )
    if company_name:
        scope_query = scope_query.filter(OrganizationSubmission.company_name.like(f"%{company_name}%"))
    if has_submitted is True:
        scope_query = scope_query.filter(OrganizationSubmission.status == "submitted")
    elif has_submitted is False:
        submitted_companies = (
            db.query(OrganizationSubmission.company_name)
            .filter(OrganizationSubmission.status == "submitted")
            .distinct()
        )
        scope_query = scope_query.filter(~OrganizationSubmission.company_name.in_(submitted_companies))
    scope_query = _apply_submission_filters(
        scope_query,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
    )
    matched_companies = scope_query.distinct().subquery()
    total = int(db.query(func.count()).select_from(matched_companies).scalar() or 0)
    if total == 0:
        return [], 0

    summary_query = (
        db.query(OrganizationSubmission.company_name, *_summary_columns())
        .filter(OrganizationSubmission.company_name.in_(matched_companies.select()))
        .group_by(OrganizationSubmission.company_name)
        .order_by(func.max(OrganizationSubmission.created_at).desc(), OrganizationSubmission.company_name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [_to_summary(row) for row in summary_query.all()], total


def get_company_summary(db: Session, company_name: str) -> dict | None:
    row = (
        db.query(OrganizationSubmission.company_name, *_summary_columns())
        .filter(OrganizationSubmission.company_name == company_name)
        .group_by(OrganizationSubmission.company_name)
        .first()
    )
    return _to_summary(row) if row else None


def list_company_departments(db: Session, company_name: str) -> list[str]:
    rows = (
        db.query(OrganizationSubmission.department)
        .filter(
            OrganizationSubmission.company_name == company_name,
            OrganizationSubmission.department.isnot(None),
        )
        .distinct()
        .order_by(OrganizationSubmission.department.asc())
        .all()
    )
    return [row.department for row in rows if row.department]


def list_company_submissions(
    db: Session,
    *,
    company_name: str,
    department: str | None = None,
    respondent_name: str | None = None,
    status: str | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[OrganizationSubmission], int]:
    query = _apply_submission_filters(
        db.query(OrganizationSubmission),
        company_name=company_name,
        department=department,
        respondent_name=respondent_name,
        status=status,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
    )
    total = int(query.order_by(None).count())
    rows = (
        query.order_by(OrganizationSubmission.created_at.desc(), OrganizationSubmission.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def get_submission(db: Session, submission_id: int) -> OrganizationSubmission | None:
    return db.get(OrganizationSubmission, submission_id)


def list_active_questions_by_module(db: Session) -> list[tuple[QuestionModule, list[Question]]]:
    modules = (
        db.query(QuestionModule)
        .join(Question, Question.module_id == QuestionModule.id)
        .filter(QuestionModule.is_active.is_(True), Question.is_active.is_(True))
        .distinct()
        .order_by(QuestionModule.sort_order.asc(), QuestionModule.id.asc())
        .all()
    )
    if not modules:
        return []
    module_ids = [module.id for module in modules]
    questions = (
        db.query(Question)
        .filter(Question.module_id.in_(module_ids), Question.is_active.is_(True))
        .order_by(Question.module_id.asc(), Question.sort_order.asc(), Question.id.asc())
        .all()
    )
    by_module: dict[int, list[Question]] = {module.id: [] for module in modules}
    for question in questions:
        by_module.setdefault(question.module_id, []).append(question)
    return [(module, by_module.get(module.id, [])) for module in modules]


def list_answers_for_submission(db: Session, submission_id: int) -> dict[int, int]:
    rows = (
        db.query(OrganizationAnswer.question_id, OrganizationAnswer.answer_value)
        .filter(OrganizationAnswer.organization_submission_id == submission_id)
        .all()
    )
    return {question_id: answer_value for question_id, answer_value in rows}


def list_reports_for_submission(db: Session, submission_id: int) -> list[OrganizationReport]:
    return (
        db.query(OrganizationReport)
        .filter(OrganizationReport.organization_submission_id == submission_id)
        .order_by(OrganizationReport.version.desc(), OrganizationReport.id.desc())
        .all()
    )


def get_organization_report(db: Session, report_id: int) -> OrganizationReport | None:
    return db.get(OrganizationReport, report_id)


def list_submissions_for_export(
    db: Session,
    *,
    company_name: str | None = None,
    department: str | None = None,
    respondent_name: str | None = None,
    status: str | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
) -> list[OrganizationSubmission]:
    query = _apply_submission_filters(
        db.query(OrganizationSubmission),
        company_name=company_name,
        department=department,
        respondent_name=respondent_name,
        status=status,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
    )
    return query.order_by(OrganizationSubmission.created_at.asc(), OrganizationSubmission.id.asc()).all()


def list_answers_for_submissions(db: Session, submission_ids: list[int]) -> dict[int, dict[int, int]]:
    if not submission_ids:
        return {}
    rows = (
        db.query(
            OrganizationAnswer.organization_submission_id,
            OrganizationAnswer.question_id,
            OrganizationAnswer.answer_value,
        )
        .filter(OrganizationAnswer.organization_submission_id.in_(submission_ids))
        .all()
    )
    grouped: dict[int, dict[int, int]] = {}
    for submission_id, question_id, answer_value in rows:
        grouped.setdefault(submission_id, {})[question_id] = answer_value
    return grouped
