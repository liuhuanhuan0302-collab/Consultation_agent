import asyncio
import inspect
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    CompanyLead,
    DiagnosisSubmission,
    DimensionScore,
    Question,
    QuestionAnswer,
    QuestionModule,
    Report,
    ReportDeliveryJob,
    SubmissionStatus,
    TrackingEvent,
)
from app.schemas import AnswerInput, ScoreResponse, SubmitQuestionnaireRequest
from app.api.v1.endpoints import public
from app.utils.time_utils import utc_now
from app.service import diagnosis, submission_service


def create_submission(*, email: str | None = "customer@example.com") -> tuple[Session, object, DiagnosisSubmission, list[AnswerInput]]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    module = QuestionModule(code="M01", name="基础能力", max_score=8, sort_order=1)
    db.add(module)
    db.flush()
    questions = [
        Question(module_id=module.id, code="Q1", text="问题1", max_score=4, sort_order=1),
        Question(module_id=module.id, code="Q2", text="问题2", max_score=4, sort_order=2),
    ]
    db.add_all(questions)
    lead = CompanyLead(company_name="测试企业", email=email, phone="13800000000")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.commit()
    answers = [AnswerInput(question_id=questions[0].id, score=3), AnswerInput(question_id=questions[1].id, score=2)]
    return db, engine, submission, answers


def submit(db: Session, submission: DiagnosisSubmission, answers: list[AnswerInput]):
    return asyncio.run(
        submission_service.submit_questionnaire(
            db,
            submission.id,
            submission.lead.session_token,
            answers,
            user_agent="pytest",
            ip_address="127.0.0.1",
            max_pending_jobs=100,
        )
    )


def test_submission_service_commits_complete_workflow_once():
    db, engine, submission, answers = create_submission()
    result = submit(db, submission, answers)

    db.refresh(submission)
    assert submission.status == SubmissionStatus.scored.value
    assert result.report.id is not None
    assert result.delivery_job_id is not None
    assert db.query(QuestionAnswer).count() == 2
    assert db.query(DimensionScore).count() == 1
    assert db.query(Report).count() == 1
    assert db.query(ReportDeliveryJob).count() == 1
    assert db.query(TrackingEvent).filter(TrackingEvent.event_name == "submit_questionnaire").count() == 1

    with pytest.raises(submission_service.SubmissionConflictError):
        submit(db, submission, answers)
    assert db.query(Report).count() == 1
    assert db.query(ReportDeliveryJob).count() == 1
    assert db.query(TrackingEvent).filter(TrackingEvent.event_name == "submit_questionnaire").count() == 1
    db.close()
    engine.dispose()


def test_late_draft_cannot_overwrite_scored_answers():
    db, engine, submission, answers = create_submission()
    submit(db, submission, answers)
    original_score = db.query(QuestionAnswer).filter(QuestionAnswer.question_id == answers[0].question_id).one().score

    with pytest.raises(submission_service.SubmissionConflictError):
        submission_service.save_submission_draft(
            db,
            submission.id,
            submission.lead.session_token,
            [AnswerInput(question_id=answers[0].question_id, score=0)],
        )

    stored_score = db.query(QuestionAnswer).filter(QuestionAnswer.question_id == answers[0].question_id).one().score
    assert stored_score == original_score
    db.close()
    engine.dispose()


def test_submission_without_email_commits_without_delivery_job():
    db, engine, submission, answers = create_submission(email=None)
    result = submit(db, submission, answers)
    assert result.delivery_job_id is None
    assert db.query(ReportDeliveryJob).count() == 0
    db.close()
    engine.dispose()


def test_archived_question_answers_are_removed_on_final_submit():
    """题库改版：保存草稿后归档其中一道题，刷新后只提交活跃题目，
    提交必须成功且已归档题目的旧答案被清除，评分不再读到 Unknown question id。"""
    db, engine, submission, answers = create_submission()
    submission_service.save_submission_draft(
        db,
        submission.id,
        submission.lead.session_token,
        answers,
    )
    assert db.query(QuestionAnswer).count() == 2

    archived = db.query(Question).filter(Question.code == "Q2").one()
    archived.is_active = False
    db.commit()

    result = submit(db, submission, [answers[0]])
    assert result.report.id is not None

    remaining = {row.question_id for row in db.query(QuestionAnswer).all()}
    assert remaining == {answers[0].question_id}
    assert db.query(QuestionAnswer).filter(QuestionAnswer.question_id == archived.id).count() == 0
    db.close()
    engine.dispose()


def test_queue_capacity_failure_makes_no_writes():
    db, engine, submission, answers = create_submission()
    with pytest.raises(submission_service.SubmissionQueueCapacityError):
        asyncio.run(
            submission_service.submit_questionnaire(
                db,
                submission.id,
                submission.lead.session_token,
                answers,
                user_agent=None,
                ip_address=None,
                max_pending_jobs=0,
            )
        )
    db.refresh(submission)
    assert submission.status == SubmissionStatus.draft.value
    assert db.query(QuestionAnswer).count() == 0
    assert db.query(Report).count() == 0
    assert db.query(ReportDeliveryJob).count() == 0
    db.close()
    engine.dispose()


def test_validation_failure_rolls_back_service_transaction():
    db, engine, submission, answers = create_submission()
    with pytest.raises(submission_service.SubmissionValidationError):
        submit(db, submission, answers[:1])
    assert db.in_transaction() is False
    db.close()
    engine.dispose()


def test_workflow_exception_rolls_back_all_partial_writes(monkeypatch):
    db, engine, submission, answers = create_submission()
    monkeypatch.setattr(submission_service, "score_submission", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        submit(db, submission, answers)

    db.refresh(submission)
    assert submission.status == SubmissionStatus.draft.value
    assert db.query(QuestionAnswer).count() == 0
    assert db.query(DimensionScore).count() == 0
    assert db.query(Report).count() == 0
    assert db.query(ReportDeliveryJob).count() == 0
    assert db.query(TrackingEvent).count() == 0
    db.close()
    engine.dispose()


def test_deadlock_retry_rolls_back_then_creates_no_duplicates(monkeypatch):
    db, engine, submission, answers = create_submission()
    original_commit = db.commit
    commit_calls = 0

    class Deadlock:
        args = (1213, "deadlock")

    def flaky_commit():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 1:
            raise OperationalError("COMMIT", {}, Deadlock())
        original_commit()

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(db, "commit", flaky_commit)
    monkeypatch.setattr(submission_service.asyncio, "sleep", no_sleep)
    result = submit(db, submission, answers)

    assert commit_calls == 2
    assert result.report.id is not None
    assert db.query(Report).count() == 1
    assert db.query(ReportDeliveryJob).count() == 1
    assert db.query(TrackingEvent).filter(TrackingEvent.event_name == "submit_questionnaire").count() == 1
    db.close()
    engine.dispose()


def test_diagnosis_service_has_no_fastapi_dependency():
    assert "fastapi" not in inspect.getsource(diagnosis)


def request_with_session() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/public/submissions/7/submit",
            "headers": [(b"x-session-token", b"session-token"), (b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 12345),
        }
    )


def test_endpoint_schedules_worker_only_after_service_success(monkeypatch):
    score = ScoreResponse(
        submission_id=7,
        total_score=5,
        max_score=8,
        score_rate=0.625,
        risk_level="medium",
        low_dimensions=[],
        dimensions=[],
    )
    report = SimpleNamespace(
        id=9,
        public_token="public-token",
        status="pending",
        title="报告",
        html_content="<p>安全</p>",
        model_vendor="deepseek",
        model_name=None,
        created_at=utc_now(),
    )

    async def fake_submit(*_args, **_kwargs):
        return submission_service.SubmissionResult(score=score, report=report, delivery_job_id=11)

    monkeypatch.setattr(submission_service, "submit_questionnaire", fake_submit)
    background = BackgroundTasks()
    response = asyncio.run(
        public.submit_questionnaire(
            SubmitQuestionnaireRequest(answers=[]),
            request_with_session(),
            background,
            SimpleNamespace(id=7),
            object(),
        )
    )

    assert response.report.id == 9
    assert len(background.tasks) == 1
    assert background.tasks[0].args == (11,)


def test_endpoint_maps_domain_error_without_scheduling(monkeypatch):
    async def fake_submit(*_args, **_kwargs):
        raise submission_service.SubmissionConflictError("该问卷已提交，请等待报告生成完成")

    monkeypatch.setattr(submission_service, "submit_questionnaire", fake_submit)
    background = BackgroundTasks()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            public.submit_questionnaire(
                SubmitQuestionnaireRequest(answers=[]),
                request_with_session(),
                background,
                SimpleNamespace(id=7),
                object(),
            )
        )
    assert exc.value.status_code == 409
    assert background.tasks == []


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (submission_service.SubmissionNotFoundError("Submission not found"), 404),
        (submission_service.SubmissionValidationError("bad answers"), 422),
        (submission_service.SubmissionQueueCapacityError("queue full"), 503),
    ],
)
def test_endpoint_maps_remaining_domain_errors(monkeypatch, error, status_code):
    async def fake_submit(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(submission_service, "submit_questionnaire", fake_submit)
    background = BackgroundTasks()
    endpoint = getattr(public.submit_questionnaire, "__wrapped__", public.submit_questionnaire)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            endpoint(
                SubmitQuestionnaireRequest(answers=[]),
                request_with_session(),
                background,
                SimpleNamespace(id=7),
                object(),
            )
        )
    assert exc.value.status_code == status_code
    assert background.tasks == []
