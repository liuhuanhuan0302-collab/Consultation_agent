"""Organization diagnosis persistence operations."""

from collections.abc import Iterable

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import CompanyLead, Question, QuestionModule
from app.models.common import now
from app.models.organization import OrganizationAnswer, OrganizationSubmission


def create_submission(
    db: Session,
    *,
    company_name_input: str,
    company_name: str,
    respondent_name: str,
    department: str,
    position: str,
) -> OrganizationSubmission:
    submission = OrganizationSubmission(
        company_name_input=company_name_input,
        company_name=company_name,
        respondent_name=respondent_name,
        department=department,
        position=position,
    )
    db.add(submission)
    db.flush()
    return submission


def get_submission(db: Session, submission_id: int) -> OrganizationSubmission | None:
    return db.get(OrganizationSubmission, submission_id)


def get_submission_for_update(db: Session, submission_id: int) -> OrganizationSubmission | None:
    return (
        db.query(OrganizationSubmission)
        .filter(OrganizationSubmission.id == submission_id)
        .with_for_update()
        .populate_existing()
        .first()
    )


def get_submission_for_update_by_access_token(
    db: Session,
    submission_id: int,
    access_token: str,
) -> OrganizationSubmission | None:
    return (
        db.query(OrganizationSubmission)
        .filter(
            OrganizationSubmission.id == submission_id,
            OrganizationSubmission.access_token == access_token,
        )
        .with_for_update()
        .populate_existing()
        .first()
    )


def list_company_name_suggestions(db: Session, query: str, limit: int = 10) -> list[str]:
    """Return distinct CompanyLead names for read-only organization autocomplete."""
    escaped_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    prefix_pattern = f"{escaped_query}%"
    contains_pattern = f"%{escaped_query}%"
    names: list[str] = []
    seen: set[str] = set()

    def append_rows(rows) -> None:
        for (name,) in rows:
            if name and name not in seen:
                seen.add(name)
                names.append(name)

    prefix_rows = (
        db.query(CompanyLead.company_name)
        .filter(CompanyLead.company_name.isnot(None))
        .filter(CompanyLead.company_name.like(prefix_pattern, escape="\\"))
        .order_by(CompanyLead.company_name.asc())
        .distinct()
        .limit(limit)
        .all()
    )
    append_rows(prefix_rows)
    if len(names) >= limit:
        return names[:limit]

    contains_rows = (
        db.query(CompanyLead.company_name)
        .filter(CompanyLead.company_name.isnot(None))
        .filter(CompanyLead.company_name.like(contains_pattern, escape="\\"))
        .order_by(CompanyLead.company_name.asc())
        .distinct()
        .limit(limit - len(names))
        .all()
    )
    append_rows(contains_rows)
    return names[:limit]


def get_active_question_ids(db: Session) -> set[int]:
    rows = (
        db.query(Question.id)
        .join(QuestionModule, Question.module_id == QuestionModule.id)
        .filter(Question.is_active.is_(True), QuestionModule.is_active.is_(True))
        .all()
    )
    return {row.id for row in rows}


def list_answers(db: Session, submission_id: int) -> list[OrganizationAnswer]:
    return (
        db.query(OrganizationAnswer)
        .filter(OrganizationAnswer.organization_submission_id == submission_id)
        .order_by(OrganizationAnswer.question_id.asc())
        .all()
    )


def upsert_answers(
    db: Session,
    submission_id: int,
    answers: Iterable[tuple[int, int]],
) -> None:
    """Insert or update raw answers without invoking any business workflow."""
    answer_values = list(dict(answers).items())
    question_ids = {question_id for question_id, _ in answer_values}
    if not question_ids:
        return

    timestamp = now()
    rows = [
        {
            "organization_submission_id": submission_id,
            "question_id": question_id,
            "answer_value": answer_value,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for question_id, answer_value in answer_values
    ]
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "sqlite":
        statement = sqlite_insert(OrganizationAnswer).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[
                OrganizationAnswer.organization_submission_id,
                OrganizationAnswer.question_id,
            ],
            set_={
                "answer_value": statement.excluded.answer_value,
                "updated_at": statement.excluded.updated_at,
            },
        )
        db.execute(statement)
    elif dialect_name == "mysql":
        statement = mysql_insert(OrganizationAnswer).values(rows)
        statement = statement.on_duplicate_key_update(
            answer_value=statement.inserted.answer_value,
            updated_at=statement.inserted.updated_at,
        )
        db.execute(statement)
    else:
        # SQLite and MySQL use atomic native upserts above. Keep a fallback
        # for other test dialects without adding a new runtime dependency.
        existing = (
            db.query(OrganizationAnswer)
            .filter(
                OrganizationAnswer.organization_submission_id == submission_id,
                OrganizationAnswer.question_id.in_(question_ids),
            )
            .all()
        )
        existing_by_question = {answer.question_id: answer for answer in existing}
        for question_id, answer_value in answer_values:
            stored = existing_by_question.get(question_id)
            if stored is None:
                db.add(
                    OrganizationAnswer(
                        organization_submission_id=submission_id,
                        question_id=question_id,
                        answer_value=answer_value,
                    )
                )
            else:
                stored.answer_value = answer_value
                stored.updated_at = timestamp
    db.flush()
