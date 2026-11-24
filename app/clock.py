"""Time helper. All times are naive local (venue) time, stored as 'YYYY-MM-DD HH:MM:SS'."""
import os
from datetime import datetime, timedelta, timezone

FMT = "%Y-%m-%d %H:%M:%S"
_override: datetime | None = None


def now() -> datetime:
    if _override is not None:
        return _override
    offset = int(os.getenv("TZ_OFFSET_MINUTES", "330"))
    return (datetime.now(timezone.utc) + timedelta(minutes=offset)).replace(tzinfo=None, microsecond=0)


def set_now(value: datetime | None) -> None:
    """Freeze the clock (used by tests); pass None to go back to real time."""
    global _override
    _override = value


def fmt(value: datetime) -> str:
    return value.strftime(FMT)


def parse(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    text = str(value).strip().replace("T", " ")
    for pattern in (FMT, "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise ValueError(f"Invalid date/time: {value!r}")
