"""统一时间语义：数据库使用无时区 UTC，展示和统计使用中国标准时间。"""

from datetime import datetime, timedelta, timezone


# 中国标准时间没有夏令时，固定偏移避免依赖操作系统时区数据库。
CHINA_TIMEZONE = timezone(timedelta(hours=8), name="CST")


def utc_now() -> datetime:
    """返回适合 MySQL DATETIME 保存的无时区 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(value: datetime) -> datetime:
    """将数据库中的无时区 UTC 时间转为带时区的 UTC 时间。"""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def serialize_utc_datetime(value: datetime) -> str:
    """API 时间统一输出 ISO 8601 UTC 格式，例如 2026-08-11T07:25:59Z。"""
    return as_utc(value).isoformat().replace("+00:00", "Z")


def to_china_time(value: datetime) -> datetime:
    return as_utc(value).astimezone(CHINA_TIMEZONE)
