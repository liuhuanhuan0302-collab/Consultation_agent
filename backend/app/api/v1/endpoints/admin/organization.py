"""Organization diagnosis administrator read-only endpoints."""

from datetime import date
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OrganizationSubmissionStatus, User
from app.schemas.organization_admin import (
    OrganizationCompanyDetailResponse,
    OrganizationCompanyListResponse,
    OrganizationReportGenerationResponse,
    OrganizationSubmissionAdminDetail,
)
from app.service import organization_admin_service, organization_report_service
from app.utils.auth import AdminOnly

router = APIRouter()


def _validate_date_range(submitted_from: date | None, submitted_to: date | None) -> None:
    if submitted_from and submitted_to and submitted_from > submitted_to:
        raise HTTPException(status_code=422, detail="submitted_from must not be after submitted_to")


@router.get(
    "/api/admin/organization/companies",
    response_model=OrganizationCompanyListResponse,
)
def admin_list_organization_companies(
    company_name: str | None = None,
    has_submitted: bool | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> OrganizationCompanyListResponse:
    del user
    _validate_date_range(submitted_from, submitted_to)
    return organization_admin_service.list_companies(
        db,
        company_name=company_name,
        has_submitted=has_submitted,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/api/admin/organization/companies/{company_name}/submissions",
    response_model=OrganizationCompanyDetailResponse,
)
def admin_list_organization_submissions(
    company_name: str,
    department: str | None = None,
    respondent_name: str | None = None,
    status: OrganizationSubmissionStatus | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> OrganizationCompanyDetailResponse:
    del user
    _validate_date_range(submitted_from, submitted_to)
    try:
        return organization_admin_service.list_company_submissions(
            db,
            company_name=company_name,
            department=department,
            respondent_name=respondent_name,
            status=status.value if status else None,
            submitted_from=submitted_from,
            submitted_to=submitted_to,
            page=page,
            page_size=page_size,
        )
    except organization_admin_service.OrganizationAdminNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/api/admin/organization/submissions/{submission_id}",
    response_model=OrganizationSubmissionAdminDetail,
)
def admin_get_organization_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> OrganizationSubmissionAdminDetail:
    del user
    try:
        return organization_admin_service.get_submission_detail(db, submission_id)
    except organization_admin_service.OrganizationAdminNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/api/admin/organization/submissions/{submission_id}/reports",
    response_model=OrganizationReportGenerationResponse,
)
def admin_queue_organization_report(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> OrganizationReportGenerationResponse:
    del user
    try:
        return organization_admin_service.queue_report_generation(db, submission_id)
    except organization_admin_service.OrganizationAdminNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except organization_report_service.OrganizationReportNotEligibleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except organization_report_service.OrganizationReportConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/admin/organization/reports/{report_id}/pdf")
def admin_download_organization_report_pdf(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> Response:
    del user
    try:
        _title, content = organization_admin_service.get_report_pdf(db, report_id)
    except organization_admin_service.OrganizationAdminNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="organization-report-{report_id}.pdf"'},
    )


@router.get("/api/admin/organization/export")
def admin_export_organization(
    company_name: str | None = None,
    department: str | None = None,
    respondent_name: str | None = None,
    status: Literal["draft", "submitted", "all"] = Query(default="submitted"),
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> StreamingResponse:
    del user
    _validate_date_range(submitted_from, submitted_to)
    content = organization_admin_service.export_csv(
        db,
        company_name=company_name,
        department=department,
        respondent_name=respondent_name,
        status=None if status == "all" else status,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
    )
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="organization-diagnosis.csv"; '
                f"filename*=UTF-8''{quote('organization-diagnosis.csv')}"
            )
        },
    )
