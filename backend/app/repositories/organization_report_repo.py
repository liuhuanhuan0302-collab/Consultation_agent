"""Persistence queries for independent organization reports and tasks."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, update
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CompanyLead,
    DiagnosisSubmission,
    OrganizationReport,
    OrganizationReportTask,
    OrganizationReportTaskStatus,
    OrganizationSubmission,
    OrganizationAnswer,
    Report,
)
from app.models.common import now
from app.models.report import ReportStatus
from app.models.organization import OrganizationSubmissionStatus


def list_enterprise_report_candidates(db: Session, company_name: str) -> list[Report]:
    """Return possible enterprise reports; the service validates evidence JSON."""

    report_time = func.coalesce(
        Report.generation_completed_at,
        Report.updated_at,
        Report.created_at,
    )
    return (
        db.query(Report)
        .join(DiagnosisSubmission, DiagnosisSubmission.id == Report.submission_id)
        .join(CompanyLead, CompanyLead.id == DiagnosisSubmission.lead_id)
        .filter(CompanyLead.company_name == company_name)
        .filter(Report.status.in_([ReportStatus.generated.value, ReportStatus.fallback.value]))
        .filter(Report.research_status == "generated")
        .filter(Report.company_research_json.isnot(None))
        .order_by(report_time.desc(), Report.id.desc())
        .all()
    )


def get_submission(db: Session, submission_id: int) -> OrganizationSubmission | None:
    return db.get(OrganizationSubmission, submission_id)


def get_submission_with_answers(db: Session, submission_id: int) -> OrganizationSubmission | None:
    return (
        db.query(OrganizationSubmission)
        .options(joinedload(OrganizationSubmission.answers))
        .filter(OrganizationSubmission.id == submission_id)
        .first()
    )


def get_answer_map(db: Session, submission_id: int) -> dict[int, int]:
    rows = (
        db.query(OrganizationAnswer.question_id, OrganizationAnswer.answer_value)
        .filter(OrganizationAnswer.organization_submission_id == submission_id)
        .all()
    )
    return {question_id: answer_value for question_id, answer_value in rows}


def has_submitted_same_department(db: Session, submission: OrganizationSubmission) -> bool:
    return (
        db.query(OrganizationSubmission.id)
        .filter(
            OrganizationSubmission.id != submission.id,
            OrganizationSubmission.company_name == submission.company_name,
            OrganizationSubmission.department == submission.department,
            OrganizationSubmission.status == OrganizationSubmissionStatus.submitted.value,
        )
        .first()
        is not None
    )


def next_report_version(db: Session, submission_id: int) -> int:
    current = (
        db.query(func.max(OrganizationReport.version))
        .filter(OrganizationReport.organization_submission_id == submission_id)
        .scalar()
    )
    return int(current or 0) + 1


def create_report_task(
    db: Session,
    *,
    submission: OrganizationSubmission,
    source_enterprise_report_id: int,
    task_kind: str,
) -> tuple[OrganizationReport, OrganizationReportTask]:
    version = next_report_version(db, submission.id)
    report = OrganizationReport(
        organization_submission_id=submission.id,
        version=version,
        status="pending",
        title=f"{submission.company_name} · {submission.department}组织诊断报告",
        source_enterprise_report_id=source_enterprise_report_id,
        created_at=now(),
        updated_at=now(),
    )
    db.add(report)
    db.flush()
    task = OrganizationReportTask(
        organization_submission_id=submission.id,
        organization_report_id=report.id,
        task_kind=task_kind,
        status=OrganizationReportTaskStatus.queued.value,
        attempts=0,
        max_attempts=1,
        run_after=now(),
        created_at=now(),
        updated_at=now(),
    )
    db.add(task)
    db.flush()
    return report, task


def list_reports_for_submission(db: Session, submission_id: int) -> list[OrganizationReport]:
    return (
        db.query(OrganizationReport)
        .filter(OrganizationReport.organization_submission_id == submission_id)
        .order_by(OrganizationReport.version.desc(), OrganizationReport.id.desc())
        .all()
    )


def get_report(db: Session, report_id: int) -> OrganizationReport | None:
    return db.get(OrganizationReport, report_id)


def get_report_with_submission(db: Session, report_id: int) -> OrganizationReport | None:
    return (
        db.query(OrganizationReport)
        .options(joinedload(OrganizationReport.submission))
        .filter(OrganizationReport.id == report_id)
        .first()
    )


def get_active_task_for_submission(db: Session, submission_id: int) -> OrganizationReportTask | None:
    return (
        db.query(OrganizationReportTask)
        .filter(
            OrganizationReportTask.organization_submission_id == submission_id,
            OrganizationReportTask.status.in_(
                [
                    OrganizationReportTaskStatus.queued.value,
                    OrganizationReportTaskStatus.processing.value,
                ]
            ),
        )
        .order_by(OrganizationReportTask.id.desc())
        .first()
    )


def claim_next_task(db: Session, at: datetime) -> tuple[int, str] | None:
    task = (
        db.query(OrganizationReportTask)
        .filter(
            OrganizationReportTask.status == OrganizationReportTaskStatus.queued.value,
            OrganizationReportTask.run_after <= at,
            OrganizationReportTask.attempts < OrganizationReportTask.max_attempts,
        )
        .order_by(OrganizationReportTask.run_after.asc(), OrganizationReportTask.id.asc())
        .with_for_update()
        .first()
    )
    if task is None:
        return None
    lock_token = uuid.uuid4().hex
    task.status = OrganizationReportTaskStatus.processing.value
    task.attempts += 1
    task.locked_at = at
    task.lock_token = lock_token
    task.started_at = at
    task.updated_at = at
    db.commit()
    return task.id, lock_token


def finish_task(
    db: Session,
    *,
    task_id: int,
    lock_token: str,
    status: str,
    error: str | None,
    completed_at: datetime,
) -> bool:
    result = db.execute(
        update(OrganizationReportTask)
        .where(
            OrganizationReportTask.id == task_id,
            OrganizationReportTask.status == OrganizationReportTaskStatus.processing.value,
            OrganizationReportTask.lock_token == lock_token,
        )
        .values(
            status=status,
            last_error=error,
            completed_at=completed_at,
            locked_at=None,
            lock_token=None,
            updated_at=completed_at,
        )
    )
    db.commit()
    return result.rowcount == 1
