"""Persistence operations for singleton system settings."""

from sqlalchemy.orm import Session

from app.models.system_setting import ReportContactSetting


REPORT_CONTACT_SETTINGS_ID = 1


def get_report_contact_settings(db: Session) -> ReportContactSetting | None:
    return db.query(ReportContactSetting).filter(ReportContactSetting.id == REPORT_CONTACT_SETTINGS_ID).first()


def create_report_contact_settings(db: Session) -> ReportContactSetting:
    settings = ReportContactSetting(id=REPORT_CONTACT_SETTINGS_ID)
    db.add(settings)
    db.flush()
    return settings
