import pytest
from app.utils.time import utc_now, parse_iso_datetime, format_iso_datetime, get_user_timezone


def test_utc_now():
    now = utc_now()
    assert now.tzinfo is not None
    assert now.tzinfo.utcoffset(now).total_seconds() == 0


def test_parse_iso_datetime():
    dt = parse_iso_datetime("2026-08-08T10:30:00+00:00")
    assert dt.year == 2026
    assert dt.month == 8
    assert dt.day == 8
    assert dt.hour == 10
    assert dt.minute == 30
    assert dt.tzinfo is not None


def test_format_iso_datetime():
    from datetime import datetime, timezone
    dt = datetime(2026, 8, 8, 10, 30, tzinfo=timezone.utc)
    formatted = format_iso_datetime(dt)
    assert formatted == "2026-08-08T10:30:00+00:00"


def test_get_user_timezone_valid():
    tz = get_user_timezone("America/Los_Angeles")
    assert str(tz) == "America/Los_Angeles"


def test_get_user_timezone_invalid_fallback():
    tz = get_user_timezone("Invalid/Timezone")
    assert str(tz) == "UTC"