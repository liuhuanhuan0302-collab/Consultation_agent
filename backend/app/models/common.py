"""Shared model defaults."""

from datetime import datetime
from uuid import uuid4

from app.utils.time_utils import utc_now


def now() -> datetime:
    return utc_now()


def token() -> str:
    return uuid4().hex
