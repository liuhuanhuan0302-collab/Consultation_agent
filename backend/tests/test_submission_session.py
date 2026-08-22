from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.api.v1.endpoints.public as public
from app.service import submission_service
from app.database import Base
from app.models import Question, QuestionModule
from app.schemas import AnswerInput


def test_submission_write_requires_owning_session_token(monkeypatch):
    submission = SimpleNamespace(lead=SimpleNamespace(session_token="correct-session-token-123456"))
    monkeypatch.setattr(public, "get_submission_by_id", lambda _db, _submission_id: submission)

    assert public.get_submission_for_session(1, "correct-session-token-123456", object()) is submission

    with pytest.raises(HTTPException) as exc:
        public.get_submission_for_session(1, "another-session-token-123456", object())

    assert exc.value.status_code == 404


def test_submission_write_hides_missing_submission(monkeypatch):
    monkeypatch.setattr(public, "get_submission_by_id", lambda _db, _submission_id: None)

    with pytest.raises(HTTPException) as exc:
        public.get_submission_for_session(9999, "correct-session-token-123456", object())

    assert exc.value.status_code == 404


def test_local_report_regeneration_is_development_only(monkeypatch):
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    monkeypatch.setattr(public, "settings", SimpleNamespace(environment="development"))
    assert public.is_local_development_request(request) is True

    monkeypatch.setattr(public, "settings", SimpleNamespace(environment="production"))
    assert public.is_local_development_request(request) is False


def test_submit_requires_every_active_question():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        module = QuestionModule(code="M01", name="Module", max_score=8, sort_order=1)
        db.add(module)
        db.flush()
        db.add_all([
            Question(module_id=module.id, code="Q1", text="Question 1", sort_order=1),
            Question(module_id=module.id, code="Q2", text="Question 2", sort_order=2),
        ])
        db.commit()

        with pytest.raises(submission_service.SubmissionValidationError):
            submission_service.validate_complete_answers(db, [AnswerInput(question_id=1, score=4)])

        submission_service.validate_complete_answers(
            db,
            [AnswerInput(question_id=1, score=4), AnswerInput(question_id=2, score=4)],
        )
    engine.dispose()


def test_submit_rejects_extra_stale_questions():
    """提交包含当前题库之外（已停用/归档）的题目时，应提示题目已更新而非笼统的未完成。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        module = QuestionModule(code="M01", name="Module", max_score=8, sort_order=1)
        db.add(module)
        db.flush()
        db.add_all([
            Question(module_id=module.id, code="Q1", text="Question 1", sort_order=1),
            Question(module_id=module.id, code="Q2", text="Question 2", sort_order=2),
        ])
        db.commit()

        # 提交了完整题目 + 一个不存在的旧题目（模拟题库变更后的残留答案）
        with pytest.raises(submission_service.SubmissionValidationError) as exc:
            submission_service.validate_complete_answers(
                db,
                [
                    AnswerInput(question_id=1, score=4),
                    AnswerInput(question_id=2, score=4),
                    AnswerInput(question_id=99, score=4),
                ],
            )
        assert "题目已更新" in exc.value.detail

        # 重复题目同样 422
        with pytest.raises(submission_service.SubmissionValidationError):
            submission_service.validate_complete_answers(
                db,
                [
                    AnswerInput(question_id=1, score=4),
                    AnswerInput(question_id=1, score=4),
                    AnswerInput(question_id=2, score=4),
                ],
            )
    engine.dispose()


def test_report_status_endpoint_never_leaks_internal_errors():
    """公开状态接口必须把内部异常原文替换为通用提示，不得泄露 SMTP/API/路径细节。

    凭证通过 X-Session-Token 请求头传入（依赖 get_submission_for_session），
    不进入 URL 查询参数，避免写入浏览器历史与 Nginx/应用访问日志。
    """
    from app.models import (
        CompanyLead,
        DiagnosisSubmission,
        Report,
        ReportDeliveryJob,
        ReportDeliveryStatus,
        ReportStatus,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        lead = CompanyLead(company_name="测试公司")
        db.add(lead)
        db.flush()
        submission = DiagnosisSubmission(lead_id=lead.id)
        db.add(submission)
        db.flush()
        report = Report(
            submission_id=submission.id,
            title="T",
            html_content="<p>x</p>",
            status=ReportStatus.failed.value,
            generation_error="第 3 次调用失败：ConnectTimeout(host='api.deepseek.com', path='/v1/chat/completions')",
        )
        db.add(report)
        db.flush()
        job = ReportDeliveryJob(
            lead_id=lead.id,
            submission_id=submission.id,
            report_id=report.id,
            recipient_email="a@example.com",
            status=ReportDeliveryStatus.failed.value,
            last_error="SMTPAuthenticationError(535) at C:\\Users\\x\\email_service.py:42",
        )
        db.add(job)
        db.commit()

        data = public.submission_report_status(submission, db)

        assert data["delivery_status"] == "failed"
        assert data["delivery_error"] == public.PUBLIC_REPORT_FAILURE_HINT
        assert data["generation_error"] == public.PUBLIC_REPORT_FAILURE_HINT
        # 内部细节不得出现在任何公开字段中
        serialized = str(data)
        assert "api.deepseek.com" not in serialized
        assert "SMTP" not in serialized
        assert "email_service.py" not in serialized
    engine.dispose()
