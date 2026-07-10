from sqlalchemy.orm import Session

from app.models import ChannelSource


def list_channels(db: Session) -> list[ChannelSource]:
    return db.query(ChannelSource).order_by(ChannelSource.id.asc()).all()


def get_active_channel_by_code(db: Session, code: str) -> ChannelSource | None:
    return db.query(ChannelSource).filter(ChannelSource.code == code, ChannelSource.is_active.is_(True)).first()


def get_channel_by_code(db: Session, code: str) -> ChannelSource | None:
    return db.query(ChannelSource).filter(ChannelSource.code == code).first()
