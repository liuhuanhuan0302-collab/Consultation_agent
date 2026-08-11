from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.api.v1.endpoints.public as public


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
