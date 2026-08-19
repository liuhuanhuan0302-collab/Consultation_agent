"""Shared Pydantic response behavior."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.utils.time_utils import serialize_utc_datetime


class UTCResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: serialize_utc_datetime})
