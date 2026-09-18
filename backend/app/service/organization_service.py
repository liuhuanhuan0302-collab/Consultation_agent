"""Organization diagnosis workflows without enterprise report side effects."""

from collections.abc import Sequence
import logging

from sqlalchemy.orm import Session

from app.models.organization import OrganizationSubmission, OrganizationSubmissionStatus
from app.repositories import organization_repo
from app.models.common import now
from app.schemas.organization import OrganizationAnswerInput, OrganizationSubmissionCreate

logger = logging.getLogger(__name__)


class OrganizationServiceError(Exception):
    """Base class for errors that the organization endpoint maps to HTTP."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class OrganizationNotFoundError(OrganizationServiceError):
    pass


class OrganizationConflictError(OrganizationServiceError):
    pass


class OrganizationValidationError(OrganizationServiceError):
    pass


def suggest_company_names(db: Session, query: str, limit: int = 10) -> list[str]:
    term = query.strip()
    if len(term) < 2:
        return []
    return organization_repo.list_company_name_suggestions(db, term, limit=min(limit, 10))


def _required_text(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise OrganizationValidationError(f"{label}不能为空")
    return cleaned


def create_submission(db: Session, payload: OrganizationSubmissionCreate) -> OrganizationSubmission:
    submission = organization_repo.create_submission(
        db,
        company_name_input=_required_text(payload.company_name_input, "企业名称输入"),
        company_name=_required_text(payload.company_name, "企业名称"),
        respondent_name=_required_text(payload.respondent_name, "姓名"),
        department=_required_text(payload.department, "部门"),
        position=_required_text(payload.position, "职位"),
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(submission)
    return submission


def _get_submission_or_raise(
    db: Session,
    submission_id: int,
    access_token: str,
) -> OrganizationSubmission:
    submission = organization_repo.get_submission_for_update_by_access_token(
        db,
        submission_id,
        access_token,
    )
    if submission is None:
        raise OrganizationNotFoundError("组织答卷不存在或访问凭证无效")
    return submission


def _answer_pairs(answers: Sequence[OrganizationAnswerInput]) -> list[tuple[int, int]]:
    pairs = [(answer.question_id, answer.answer_value) for answer in answers]
    if len({question_id for question_id, _ in pairs}) != len(pairs):
        raise OrganizationValidationError("同一请求中不能重复提交同一道题")
    return pairs


def _validate_answer_ids(
    db: Session,
    pairs: list[tuple[int, int]],
    *,
    require_complete: bool,
) -> None:
    active_question_ids = organization_repo.get_active_question_ids(db)
    submitted_question_ids = {question_id for question_id, _ in pairs}
    invalid_question_ids = sorted(submitted_question_ids - active_question_ids)
    if invalid_question_ids:
        invalid = ", ".join(str(question_id) for question_id in invalid_question_ids)
        raise OrganizationValidationError(f"题目不存在或已停用：{invalid}")
    if require_complete:
        missing_question_ids = sorted(active_question_ids - submitted_question_ids)
        if missing_question_ids:
            missing = ", ".join(str(question_id) for question_id in missing_question_ids)
            raise OrganizationValidationError(f"缺少题目答案：{missing}")


def save_answers(
    db: Session,
    submission_id: int,
    access_token: str,
    answers: Sequence[OrganizationAnswerInput],
) -> None:
    submission = _get_submission_or_raise(db, submission_id, access_token)
    if submission.status == OrganizationSubmissionStatus.submitted.value:
        raise OrganizationConflictError("组织答卷已提交，不能继续修改")
    pairs = _answer_pairs(answers)
    _validate_answer_ids(db, pairs, require_complete=False)
    try:
        organization_repo.upsert_answers(db, submission.id, pairs)
        db.commit()
    except Exception:
        db.rollback()
        raise


def submit_answers(
    db: Session,
    submission_id: int,
    access_token: str,
    answers: Sequence[OrganizationAnswerInput] | None,
) -> OrganizationSubmission:
    submission = _get_submission_or_raise(db, submission_id, access_token)
    if submission.status == OrganizationSubmissionStatus.submitted.value:
        raise OrganizationConflictError("组织答卷已提交")
    if answers is None:
        stored_answers = organization_repo.list_answers(db, submission.id)
        pairs = [(answer.question_id, answer.answer_value) for answer in stored_answers]
    else:
        pairs = _answer_pairs(answers)
    _validate_answer_ids(db, pairs, require_complete=True)
    try:
        organization_repo.upsert_answers(db, submission.id, pairs)
        submission.status = OrganizationSubmissionStatus.submitted.value
        submission.submitted_at = now()
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(submission)
    # Analysis eligibility and queue creation happen after the answer commit.
    # The public submission response therefore never waits for AI/PDF work, and
    # any organization-report failure cannot roll back the user's raw answers.
    try:
        from app.service.organization_report_service import prepare_auto_analysis

        prepare_auto_analysis(db, submission.id)
    except Exception:  # noqa: BLE001
        logger.exception("组织答卷已保存，但自动分析入队失败：submission_id=%s", submission.id)
        db.rollback()
        failed_submission = organization_repo.get_submission(db, submission.id)
        if failed_submission is not None:
            failed_submission.analysis_status = "failed"
            failed_submission.analysis_note = "组织答卷已保存，但分析任务创建失败，请管理员手动重试。"
            db.commit()
    db.refresh(submission)
    return submission
