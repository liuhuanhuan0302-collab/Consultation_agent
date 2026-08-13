import re

from sqlalchemy.orm import Session, joinedload, with_loader_criteria

from app.models import Question, QuestionModule


def active_modules_with_questions(db: Session) -> list[QuestionModule]:
    return (
        db.query(QuestionModule)
        .options(
            joinedload(QuestionModule.questions),
            with_loader_criteria(Question, Question.is_active.is_(True), include_aliases=True),
        )
        .filter(QuestionModule.is_active.is_(True))
        .order_by(QuestionModule.sort_order.asc())
        .all()
    )


def get_module_by_code(db: Session, code: str) -> QuestionModule | None:
    return db.query(QuestionModule).filter(QuestionModule.code == code).first()


def get_question_by_module_and_code(db: Session, module_id: int, code: str) -> Question | None:
    return db.query(Question).filter(Question.module_id == module_id, Question.code == code).first()


def next_module_code(db: Session, base_code: str) -> str:
    """在全部模块（含已归档）中，按数字后缀递增出下一个可用的模块编码。"""
    match = re.match(r"^(.*?)(\d+)$", base_code)
    prefix, width = (match.group(1), len(match.group(2))) if match else (base_code, 2)
    numbers = []
    for (row_code,) in db.query(QuestionModule.code).all():
        code_match = re.match(rf"^{re.escape(prefix)}(\d+)$", row_code)
        if code_match:
            numbers.append(int(code_match.group(1)))
    return f"{prefix}{max(numbers, default=0) + 1:0{width}d}"


def next_question_code(db: Session, module_id: int, base_code: str) -> str:
    """在指定模块内（含已归档题目），按数字后缀递增出下一个可用的题目编码。"""
    match = re.match(r"^(.*?)(\d+)$", base_code)
    prefix, width = (match.group(1), len(match.group(2))) if match else (base_code, 2)
    numbers = []
    for (row_code,) in db.query(Question.code).filter(Question.module_id == module_id).all():
        code_match = re.match(rf"^{re.escape(prefix)}(\d+)$", row_code)
        if code_match:
            numbers.append(int(code_match.group(1)))
    return f"{prefix}{max(numbers, default=0) + 1:0{width}d}"


def list_all_modules_with_questions(db: Session) -> list[QuestionModule]:
    return (
        db.query(QuestionModule)
        .options(joinedload(QuestionModule.questions))
        .order_by(QuestionModule.sort_order.asc())
        .all()
    )
