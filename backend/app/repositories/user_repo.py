from sqlalchemy.orm import Session

from app.models import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_active_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email, User.is_active.is_(True)).first()


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id.asc()).all()
