"""Final questionnaire submission workflow and transaction boundary."""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.questionnaire import SubmissionStatus
from app.repositories import submission_repo
from app.schemas.questionnaire import ScoreResponse
from app.service.diagnosis import (
    DiagnosisScoreValidationError,
    DiagnosisSubmissionNotFoundError,
    score_submission,
)
from app.service.lead_status import sync_lead_processing_status
from app.service.report_queue import enqueue_report_delivery
from app.utils.logging_utils import write_tracking_event
from app.utils.time_utils import utc_now


class SubmissionServiceError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class SubmissionNotFoundError(SubmissionServiceError):
    pass


class SubmissionConflictError(SubmissionServiceError):
    pass


class SubmissionValidationError(SubmissionServiceError):
    pass


class SubmissionQueueCapacityError(SubmissionServiceError):
    pass


@dataclass(frozen=True)
class SubmissionResult:
    score: ScoreResponse
    report: "ReportSnapshot"
    delivery_job_id: int | None


@dataclass(frozen=True)
class ReportSnapshot:
    id: int
    public_token: str
    status: str
    title: str
    html_content: str
    model_vendor: str
    model_name: str | None
    created_at: datetime


def is_mysql_deadlock(exc: OperationalError) -> bool:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    return bool(args and args[0] in {1205, 1213})


def validate_complete_answers(db: Session, answers: list, expected_question_ids: set[int] | None = None) -> None:
    expected_question_ids = expected_question_ids if expected_question_ids is not None else submission_repo.get_active_question_ids(db)
    submitted_question_ids = [answer.question_id for answer in answers]
    submitted_question_id_set = set(submitted_question_ids)
    if not expected_question_ids:
        raise SubmissionValidationError("当前题库暂无可提交题目，请联系管理员")
    if len(submitted_question_ids) != len(submitted_question_id_set):
        raise SubmissionValidationError("答案中存在重复题目，请刷新页面后重新提交")
    if submitted_question_id_set != expected_question_ids:
        if submitted_question_id_set - expected_question_ids:
            raise SubmissionValidationError("检测到题目已更新，页面数据已过期，请刷新页面后重新作答")
        raise SubmissionValidationError("当前页面题目尚未全部完成，请完成所有题目后再提交")


def save_submission_draft(db: Session, submission_id: int, session_token: str, answers: list) -> None:
    try:
        submission = submission_repo.get_submission_for_update(db, submission_id)
        if submission is None or submission.lead.session_token != session_token:
            raise SubmissionNotFoundError("Submission not found")
        if submission.status != SubmissionStatus.draft.value:
            raise SubmissionConflictError("该问卷已提交，请等待报告生成完成")
        submission_repo.upsert_answers(db, submission_id, answers)
        db.commit()
    except Exception:
        db.rollback()
        raise


async def submit_questionnaire(
    db: Session,
    submission_id: int,
    session_token: str,
    answers: list,
    *,
    user_agent: str | None,
    ip_address: str | None,
    max_pending_jobs: int,
    max_attempts: int = 3,
) -> SubmissionResult:
    """Persist, score and enqueue one submission in a retryable transaction."""
    for attempt in range(max_attempts):
        try:
            submission = submission_repo.get_submission_for_update(db, submission_id)
            if submission is None or submission.lead.session_token != session_token:
                raise SubmissionNotFoundError("Submission not found")
            if submission.status != SubmissionStatus.draft.value:
                raise SubmissionConflictError("该问卷已提交，请等待报告生成完成")
            active_question_ids = submission_repo.get_active_question_ids(db)
            validate_complete_answers(db, answers, active_question_ids)
            if submission_repo.count_pending_delivery_jobs(db) >= max_pending_jobs:
                raise SubmissionQueueCapacityError("当前报告生成任务较多，请稍后再试")

            # 题库改版后草稿可能残留已归档题目的旧答案；评分读取全部历史
            # 答案，残留行会导致 Unknown question id 失败且无法通过重答清除，
            # 因此提交事务中先按权威题集清理，再落当前答案。
            submission_repo.delete_answers_not_in(db, submission_id, active_question_ids)
            submission_repo.upsert_answers(db, submission_id, answers)
            submission.status = SubmissionStatus.submitted.value
            submission.submitted_at = utc_now()
            try:
                score = score_submission(db, submission_id)
            except DiagnosisSubmissionNotFoundError as exc:
                raise SubmissionNotFoundError(str(exc)) from exc
            except DiagnosisScoreValidationError as exc:
                raise SubmissionValidationError(str(exc)) from exc

            report = submission_repo.get_or_create_pending_report(
                db,
                submission,
                f"{submission.lead.company_name or '企业'} AI 原生转型诊断报告",
            )
            delivery_job = (
                enqueue_report_delivery(db, report, str(submission.lead.email))
                if submission.lead.email
                else None
            )
            # 提交即入队：线索进入处理中，直到报告/投递完成或终态失败。
            sync_lead_processing_status(db, submission.lead_id)
            write_tracking_event(
                db,
                "submit_questionnaire",
                session_token=submission.lead.session_token,
                lead_id=submission.lead_id,
                metadata={
                    "total_score": score.total_score,
                    "risk_level": score.risk_level,
                    "report_generated_inline": False,
                },
                user_agent=user_agent,
                ip_address=ip_address,
            )
            db.flush()
            report_snapshot = ReportSnapshot(
                id=report.id,
                public_token=report.public_token,
                status=getattr(report.status, "value", report.status),
                title=report.title,
                html_content=report.html_content,
                model_vendor=str(report.model_vendor),
                model_name=report.model_name,
                created_at=report.created_at,
            )
            delivery_job_id = delivery_job.id if delivery_job else None
            db.commit()
            return SubmissionResult(
                score=score,
                report=report_snapshot,
                delivery_job_id=delivery_job_id,
            )
        except OperationalError as exc:
            db.rollback()
            if not is_mysql_deadlock(exc) or attempt == max_attempts - 1:
                raise
            await asyncio.sleep(0.1 * (attempt + 1))
        except Exception:
            db.rollback()
            raise

    raise RuntimeError("submission retry loop exhausted")
