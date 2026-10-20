"""MVP scheduling policy: one explicit IANA zone, independent of server locale.

Athlete-specific zones are a v0.2 follow-up. Inject an aware instant for boundary tests.
"""
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo
from app.core.config import get_settings


def scheduling_date(instant: datetime | None = None, *, timezone: str | None = None) -> date:
    instant = instant or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError('Scheduling requires a timezone-aware instant.')
    return instant.astimezone(ZoneInfo(timezone or get_settings().scheduling_timezone)).date()
