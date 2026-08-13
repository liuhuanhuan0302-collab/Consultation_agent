from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin import upsert_module, upsert_question
from app.database import Base
from app.models import Question, QuestionModule, Role, User
from app.schemas import ModuleUpsert, QuestionUpsert


def create_db() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine), engine


def create_admin(db: Session) -> User:
    user = User(email="admin@example.com", name="Admin", role=Role.admin.value, password_hash="hash")
    db.add(user)
    db.flush()
    return user


def test_upsert_archived_module_uses_new_code():
    db, engine = create_db()
    user = create_admin(db)
    archived = QuestionModule(code="M99", name="已下线题库", max_score=4, sort_order=99, is_active=False)
    db.add(archived)
    db.commit()

    created = upsert_module(ModuleUpsert(code="M99", name="新题库", max_score=4, sort_order=1, is_active=True), db=db, user=user)

    assert created.id != archived.id
    assert created.code == "M100"
    assert created.is_active is True
    assert archived.is_active is False  # 历史题库未被激活
    assert db.get(QuestionModule, archived.id).is_active is False
    db.close()
    engine.dispose()


def test_upsert_archived_question_uses_new_code():
    db, engine = create_db()
    user = create_admin(db)
    module = QuestionModule(code="M01", name="Module", max_score=4, sort_order=1)
    db.add(module)
    db.flush()
    archived = Question(module_id=module.id, code="Q5", text="已下线题目", sort_order=9, is_active=False)
    db.add(archived)
    db.commit()

    created = upsert_question(
        QuestionUpsert(module_code="M01", code="Q5", text="新题目", sort_order=1, max_score=4, is_active=True),
        db=db,
        user=user,
    )

    assert created.id != archived.id
    assert created.code == "Q6"
    assert created.is_active is True
    assert db.get(Question, archived.id).is_active is False
    db.close()
    engine.dispose()
