"""Questionnaire submission persistence operations."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.questionnaire import DiagnosisSubmission, Question, QuestionAnswer, QuestionModule
from app.models.report import Report, ReportDeliveryJob, ReportDeliveryStatus, ReportStatus


def get_submission_for_update(db: Session, submission_id: int) -> DiagnosisSubmission | None:
    """Reload and lock a submission so concurrent final submissions serialize."""
    return (
        db.query(DiagnosisSubmission)
        .filter(DiagnosisSubmission.id == submission_id)
        .with_for_update()
        .populate_existing()
        .first()
    )


def get_active_question_ids(db: Session) -> set[int]:
    rows = (
        db.query(Question.id)
        .join(QuestionModule, Question.module_id == QuestionModule.id)
        .filter(Question.is_active.is_(True), QuestionModule.is_active.is_(True))
        .all()
    )
    return {row.id for row in rows}


def count_pending_delivery_jobs(db: Session) -> int:
    return (
        db.query(func.count(ReportDeliveryJob.id))
        .filter(
            ReportDeliveryJob.status.in_(
                [ReportDeliveryStatus.queued.value, ReportDeliveryStatus.processing.value]
            )
        )
        .scalar()
        or 0
    )


def upsert_answers(db: Session, submission_id: int, answers: list) -> None:
    question_ids = {answer.question_id for answer in answers}
    existing = (
        db.query(QuestionAnswer)
        .filter(
            QuestionAnswer.submission_id == submission_id,
            QuestionAnswer.question_id.in_(question_ids),
        )
        .all()
    )
    existing_by_question = {answer.question_id: answer for answer in existing}
    for answer in answers:
        stored = existing_by_question.get(answer.question_id)
        if stored:
            stored.score = answer.score
        else:
            db.add(
                QuestionAnswer(
                    submission_id=submission_id,
                    question_id=answer.question_id,
                    score=answer.score,
                )
            )
    db.flush()


def delete_answers_not_in(db: Session, submission_id: int, question_ids: set[int]) -> None:
    """删除草稿中不属于当前题库的旧答案。

    题库改版（题目归档/停用）后，草稿仍可能残留旧题目的答案行；评分读取
    全部历史答案，遇到已归档题目会以 Unknown question id 失败，且用户刷新
    重答也无法清除。最终提交时调用，保证评分只看到权威题集内的答案。
    """
    query = db.query(QuestionAnswer).filter(QuestionAnswer.submission_id == submission_id)
    if question_ids:
        query = query.filter(QuestionAnswer.question_id.notin_(question_ids))
    query.delete(synchronize_session=False)
    db.flush()


def get_or_create_pending_report(db: Session, submission: DiagnosisSubmission, title: str) -> Report:
    report = submission.report
    if report is None:
        report = Report(
            submission_id=submission.id,
            title=title,
            html_content="",
            status=ReportStatus.pending.value,
        )
        db.add(report)
        db.flush()
    else:
        report.status = ReportStatus.pending.value
    return report
