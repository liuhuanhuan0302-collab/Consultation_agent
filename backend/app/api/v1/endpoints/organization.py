"""Public organization diagnosis endpoints."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MessageResponse
from app.schemas.organization import (
    OrganizationAnswerBatch,
    OrganizationCompanySuggestion,
    OrganizationCompanySuggestionResponse,
    OrganizationSubmissionCreated,
    OrganizationSubmissionCreate,
    OrganizationSubmissionRead,
)
from app.service import organization_service
from app.utils.request import client_ip


router = APIRouter()
limiter = Limiter(key_func=client_ip)


def organization_rate_limit_key(request: Request) -> str:
    """Bind answer writes to both IP and the independent organization token."""
    return f"{client_ip(request)}:{request.headers.get('X-Organization-Access-Token', 'anonymous')}"


def _map_service_error(error: organization_service.OrganizationServiceError) -> HTTPException:
    if isinstance(error, organization_service.OrganizationNotFoundError):
        return HTTPException(status_code=404, detail=error.detail)
    if isinstance(error, organization_service.OrganizationConflictError):
        return HTTPException(status_code=409, detail=error.detail)
    return HTTPException(status_code=422, detail=error.detail)


@router.get(
    "/api/public/organization/company-suggestions",
    response_model=OrganizationCompanySuggestionResponse,
)
@limiter.limit("120/minute; 1000/hour")
def company_suggestions(
    request: Request,
    q: str = Query(default=""),
    db: Session = Depends(get_db),
) -> OrganizationCompanySuggestionResponse:
    del request
    names = organization_service.suggest_company_names(db, q)
    return OrganizationCompanySuggestionResponse(
        items=[OrganizationCompanySuggestion(company_name=name) for name in names]
    )


@router.post(
    "/api/public/organization/submissions",
    response_model=OrganizationSubmissionCreated,
)
@limiter.limit("10/hour")
def create_organization_submission(
    payload: OrganizationSubmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> OrganizationSubmissionCreated:
    del request
    try:
        submission = organization_service.create_submission(db, payload)
    except organization_service.OrganizationServiceError as error:
        raise _map_service_error(error) from error
    return OrganizationSubmissionCreated(
        id=submission.id,
        access_token=submission.access_token,
        status=str(submission.status),
    )


@router.put(
    "/api/public/organization/submissions/{submission_id}/answers",
    response_model=MessageResponse,
)
@limiter.limit("60/hour", key_func=organization_rate_limit_key)
def save_organization_answers(
    submission_id: int,
    payload: OrganizationAnswerBatch,
    request: Request,
    access_token: str = Header(
        alias="X-Organization-Access-Token",
        min_length=20,
        max_length=64,
    ),
    db: Session = Depends(get_db),
) -> MessageResponse:
    del request
    try:
        organization_service.save_answers(db, submission_id, access_token, payload.answers)
    except organization_service.OrganizationServiceError as error:
        raise _map_service_error(error) from error
    return MessageResponse(message="organization draft saved")


@router.post(
    "/api/public/organization/submissions/{submission_id}/submit",
    response_model=OrganizationSubmissionRead,
)
@limiter.limit("3/hour", key_func=organization_rate_limit_key)
def submit_organization_answers(
    submission_id: int,
    request: Request,
    payload: OrganizationAnswerBatch | None = None,
    access_token: str = Header(
        alias="X-Organization-Access-Token",
        min_length=20,
        max_length=64,
    ),
    db: Session = Depends(get_db),
) -> OrganizationSubmissionRead:
    del request
    try:
        submission = organization_service.submit_answers(
            db,
            submission_id,
            access_token,
            payload.answers if payload is not None else None,
        )
    except organization_service.OrganizationServiceError as error:
        raise _map_service_error(error) from error
    return OrganizationSubmissionRead.model_validate(submission)
