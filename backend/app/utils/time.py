"""Timezone utilities."""

from datetime import datetime, timezone
import zoneinfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_iso_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def get_user_timezone(tz_name: str) -> zoneinfo.ZoneInfo:
    try:
        return zoneinfo.ZoneInfo(tz_name)
    except zoneinfo.ZoneInfoNotFoundError:
        return zoneinfo.ZoneInfo("UTC")


def convert_to_user_tz(dt: datetime, user_tz: str) -> datetime:
    user_zone = get_user_timezone(user_tz)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(user_zone)


def convert_to_utc(dt: datetime, user_tz: str) -> datetime:
    user_zone = get_user_timezone(user_tz)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=user_zone)
    return dt.astimezone(timezone.utc)