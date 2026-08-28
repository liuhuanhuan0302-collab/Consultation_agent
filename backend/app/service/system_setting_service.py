"""Business rules for report contact settings and immutable report snapshots."""

from sqlalchemy.orm import Session

from app.models.system_setting import ReportContactSetting
from app.repositories.system_setting_repo import create_report_contact_settings, get_report_contact_settings
from app.schemas.system_setting import ReportContactSettingsUpdate


REPORT_CONTACT_FIELDS = ("contact_name", "phone", "wechat", "email")


def load_report_contact_settings(db: Session) -> ReportContactSetting:
    settings = get_report_contact_settings(db)
    # Reads must not create database state. The singleton is persisted only when
    # an administrator saves it; until then callers receive empty defaults.
    return settings if settings is not None else ReportContactSetting(
        id=1,
        contact_name="",
        phone="",
        wechat="",
        email="",
    )


def update_report_contact_settings(
    db: Session,
    payload: ReportContactSettingsUpdate,
    *,
    updated_by: str,
) -> ReportContactSetting:
    settings = get_report_contact_settings(db)
    if settings is None:
        settings = create_report_contact_settings(db)
    for field in REPORT_CONTACT_FIELDS:
        setattr(settings, field, str(getattr(payload, field) or "").strip())
    settings.updated_by = updated_by
    db.commit()
    db.refresh(settings)
    return settings


def report_contact_snapshot(db: Session) -> dict[str, str]:
    """Return only populated values for persistence inside one report summary."""

    settings = load_report_contact_settings(db)
    return {
        field: value
        for field in REPORT_CONTACT_FIELDS
        if (value := str(getattr(settings, field, "") or "").strip())
    }
