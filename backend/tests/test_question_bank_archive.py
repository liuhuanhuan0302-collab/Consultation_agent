from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin import archive_module, archive_question
from app.database import Base
from app.models import Question, QuestionModule, Role, User
from app.repositories.questionnaire_repo import active_modules_with_questions


def create_db() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine), engine


def create_admin(db: Session) -> User:
    user = User(email="admin@example.com", name="Admin", role=Role.admin.value, password_hash="hash")
    db.add(user)
    db.flush()
    return user


def test_archived_question_is_hidden_from_active_questionnaire():
    db, engine = create_db()
    user = create_admin(db)
    module = QuestionModule(code="M01", name="Module", max_score=4, sort_order=1)
    db.add(module)
    db.flush()
    question = Question(module_id=module.id, code="Q1", text="Question", sort_order=1)
    db.add(question)
    db.commit()

    archive_question(question.id, db=db, user=user)

    assert db.get(Question, question.id).is_active is False
    assert active_modules_with_questions(db)[0].questions == []
    db.close()
    engine.dispose()


def test_archived_module_is_hidden_from_active_questionnaire():
    db, engine = create_db()
    user = create_admin(db)
    module = QuestionModule(code="M01", name="Module", max_score=4, sort_order=1)
    db.add(module)
    db.flush()
    question = Question(module_id=module.id, code="Q1", text="Question", sort_order=1)
    db.add(question)
    db.commit()

    archive_module(module.id, db=db, user=user)

    assert db.get(QuestionModule, module.id).is_active is False
    assert db.get(Question, question.id).is_active is False
    assert active_modules_with_questions(db) == []
    db.close()
    engine.dispose()
