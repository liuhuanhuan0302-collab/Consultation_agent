from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.api.v1.endpoints.public as public
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

        with pytest.raises(HTTPException) as exc:
            public.validate_complete_answers(db, [AnswerInput(question_id=1, score=4)])
        assert exc.value.status_code == 422

        public.validate_complete_answers(
            db,
            [AnswerInput(question_id=1, score=4), AnswerInput(question_id=2, score=4)],
        )
    engine.dispose()
