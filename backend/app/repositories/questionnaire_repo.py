from sqlalchemy.orm import Session, joinedload

from app.models import Question, QuestionModule


def active_modules_with_questions(db: Session) -> list[QuestionModule]:
    return (
        db.query(QuestionModule)
        .options(joinedload(QuestionModule.questions))
        .filter(QuestionModule.is_active.is_(True))
        .order_by(QuestionModule.sort_order.asc())
        .all()
    )


def get_module_by_code(db: Session, code: str) -> QuestionModule | None:
    return db.query(QuestionModule).filter(QuestionModule.code == code).first()


def get_question_by_module_and_code(db: Session, module_id: int, code: str) -> Question | None:
    return db.query(Question).filter(Question.module_id == module_id, Question.code == code).first()


def list_all_modules_with_questions(db: Session) -> list[QuestionModule]:
    return (
        db.query(QuestionModule)
        .options(joinedload(QuestionModule.questions))
        .order_by(QuestionModule.sort_order.asc())
        .all()
    )
