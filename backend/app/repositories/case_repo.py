from sqlalchemy.orm import Session

from app.models import CaseStudy


def list_case_studies(db: Session) -> list[CaseStudy]:
    return db.query(CaseStudy).order_by(CaseStudy.id.desc()).all()


def get_active_cases_by_modules(db: Session, module_codes: list[str]) -> list[CaseStudy]:
    return (
        db.query(CaseStudy)
        .filter(CaseStudy.is_active.is_(True), CaseStudy.module_code.in_(module_codes))
        .order_by(CaseStudy.roi_level.desc(), CaseStudy.id.asc())
        .all()
    )


def get_active_generic_cases(db: Session, limit: int = 5) -> list[CaseStudy]:
    return (
        db.query(CaseStudy)
        .filter(CaseStudy.is_active.is_(True), CaseStudy.industry == "通用")
        .limit(limit)
        .all()
    )
