"""Organization diagnosis administrator read-only orchestration."""

from __future__ import annotations

import csv
from datetime import date
from io import StringIO

from app.repositories import organization_admin_repo
from app.schemas.organization_admin import (
    OrganizationCompanyDetailResponse,
    OrganizationCompanyListResponse,
    OrganizationCompanySummary,
    OrganizationQuestionAnswerAdminRead,
    OrganizationQuestionModuleAdminRead,
    OrganizationReportAdminRead,
    OrganizationReportGenerationResponse,
    OrganizationSubmissionAdminDetail,
    OrganizationSubmissionAdminRead,
)


class OrganizationAdminNotFoundError(Exception):
    """Raised when an administrator requests an unknown organization record."""


def _escape_csv_cell(value: object | None) -> object | None:
    """Keep administrator exports from being interpreted as spreadsheet formulas."""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _pages(total: int, page_size: int) -> int:
    return (total + page_size - 1) // page_size if total else 0


def _submission_read(submission) -> OrganizationSubmissionAdminRead:
    return OrganizationSubmissionAdminRead.model_validate(submission)


def list_companies(
    db,
    *,
    company_name: str | None,
    has_submitted: bool | None,
    submitted_from: date | None,
    submitted_to: date | None,
    page: int,
    page_size: int,
) -> OrganizationCompanyListResponse:
    rows, total = organization_admin_repo.list_company_summaries(
        db,
        company_name=company_name.strip() or None if company_name else None,
        has_submitted=has_submitted,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        page=page,
        page_size=page_size,
    )
    return OrganizationCompanyListResponse(
        items=[OrganizationCompanySummary.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


def list_company_submissions(
    db,
    *,
    company_name: str,
    department: str | None,
    respondent_name: str | None,
    status: str | None,
    submitted_from: date | None,
    submitted_to: date | None,
    page: int,
    page_size: int,
) -> OrganizationCompanyDetailResponse:
    company_name = company_name.strip()
    summary = organization_admin_repo.get_company_summary(db, company_name)
    if not summary:
        raise OrganizationAdminNotFoundError("Organization company not found")
    rows, total = organization_admin_repo.list_company_submissions(
        db,
        company_name=company_name,
        department=department.strip() or None if department else None,
        respondent_name=respondent_name.strip() or None if respondent_name else None,
        status=status,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        page=page,
        page_size=page_size,
    )
    return OrganizationCompanyDetailResponse(
        **summary,
        departments=organization_admin_repo.list_company_departments(db, company_name),
        items=[_submission_read(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


def get_submission_detail(db, submission_id: int) -> OrganizationSubmissionAdminDetail:
    submission = organization_admin_repo.get_submission(db, submission_id)
    if not submission:
        raise OrganizationAdminNotFoundError("Organization submission not found")
    answer_values = organization_admin_repo.list_answers_for_submission(db, submission_id)
    reports = [
        OrganizationReportAdminRead(
            id=report.id,
            version=report.version,
            status=report.status,
            report_format_version=report.report_format_version,
            title=report.title,
            source_enterprise_report_id=report.source_enterprise_report_id,
            model_name=report.model_name,
            generation_error=report.generation_error,
            generation_started_at=report.generation_started_at,
            generation_completed_at=report.generation_completed_at,
            created_at=report.created_at,
            pdf_available=bool(report.pdf_content),
        )
        for report in organization_admin_repo.list_reports_for_submission(db, submission_id)
    ]
    modules = []
    for module, questions in organization_admin_repo.list_active_questions_by_module(db):
        modules.append(
            OrganizationQuestionModuleAdminRead(
                code=module.code,
                name=module.name,
                sort_order=module.sort_order,
                questions=[
                    OrganizationQuestionAnswerAdminRead(
                        code=question.code,
                        text=question.text,
                        max_score=question.max_score,
                        answer_value=answer_values.get(question.id),
                    )
                    for question in questions
                ],
            )
        )
    return OrganizationSubmissionAdminDetail(
        **_submission_read(submission).model_dump(),
        analysis_status=submission.analysis_status,
        analysis_note=submission.analysis_note,
        reports=reports,
        modules=modules,
    )


def queue_report_generation(db, submission_id: int) -> OrganizationReportGenerationResponse:
    from app.service.organization_report_service import queue_manual_analysis

    report, task = queue_manual_analysis(db, submission_id)
    return OrganizationReportGenerationResponse(
        report_id=report.id,
        task_id=task.id,
        version=report.version,
        status=report.status,
        message="已进入组织报告生成队列。",
    )


def get_report_pdf(db, report_id: int) -> tuple[str, bytes]:
    report = organization_admin_repo.get_organization_report(db, report_id)
    if report is None or report.status != "generated" or not report.pdf_content:
        raise OrganizationAdminNotFoundError("组织报告PDF尚未生成")
    return report.title, report.pdf_content


def _csv_datetime(value) -> str:
    return value.isoformat() if value else ""


def export_csv(
    db,
    *,
    company_name: str | None,
    department: str | None,
    respondent_name: str | None,
    status: str | None,
    submitted_from: date | None,
    submitted_to: date | None,
) -> str:
    question_groups = organization_admin_repo.list_active_questions_by_module(db)
    questions = [question for _module, module_questions in question_groups for question in module_questions]
    submissions = organization_admin_repo.list_submissions_for_export(
        db,
        company_name=company_name.strip() or None if company_name else None,
        department=department.strip() or None if department else None,
        respondent_name=respondent_name.strip() or None if respondent_name else None,
        status=status,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
    )
    answers = organization_admin_repo.list_answers_for_submissions(db, [row.id for row in submissions])
    header = [
        "企业名称",
        "姓名",
        "部门",
        "职位",
        "状态",
        "创建时间",
        "提交时间",
        *[f"Q{index:02d}" for index, _question in enumerate(questions, start=1)],
    ]
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    for submission in submissions:
        row_answers = answers.get(submission.id, {})
        writer.writerow(
            [
                _escape_csv_cell(submission.company_name),
                _escape_csv_cell(submission.respondent_name),
                _escape_csv_cell(submission.department),
                _escape_csv_cell(submission.position),
                submission.status,
                _csv_datetime(submission.created_at),
                _csv_datetime(submission.submitted_at),
                *[row_answers.get(question.id, "") for question in questions],
            ]
        )
    return "\ufeff" + buffer.getvalue()
