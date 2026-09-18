"""Persistence operations for singleton system settings."""

from sqlalchemy.orm import Session

from app.models.system_setting import ReportContactSetting, ReportQueueSetting


REPORT_CONTACT_SETTINGS_ID = 1
REPORT_QUEUE_SETTINGS_ID = 1


def get_report_contact_settings(db: Session) -> ReportContactSetting | None:
    return db.query(ReportContactSetting).filter(ReportContactSetting.id == REPORT_CONTACT_SETTINGS_ID).first()


def create_report_contact_settings(db: Session) -> ReportContactSetting:
    settings = ReportContactSetting(id=REPORT_CONTACT_SETTINGS_ID)
    db.add(settings)
    db.flush()
    return settings


def get_report_queue_settings(db: Session) -> ReportQueueSetting | None:
    return db.get(ReportQueueSetting, REPORT_QUEUE_SETTINGS_ID)


def lock_report_queue_settings(db: Session) -> ReportQueueSetting:
    """Lock the singleton row used to serialize queue mutations.

    Alembic always seeds this row. The creation fallback exists for isolated
    metadata-created test databases and local developer databases only.
    """

    settings = (
        db.query(ReportQueueSetting)
        .filter(ReportQueueSetting.id == REPORT_QUEUE_SETTINGS_ID)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if settings is None:
        settings = ReportQueueSetting(id=REPORT_QUEUE_SETTINGS_ID)
        db.add(settings)
        db.flush()
    return settings
