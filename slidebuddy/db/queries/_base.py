import sqlite3
from datetime import datetime


def _parse_datetime(value: str | datetime | None) -> datetime:
    """Parse a datetime string from SQLite into a datetime object."""
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.utcnow()
