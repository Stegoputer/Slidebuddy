"""FastAPI dependencies — DB connection lifecycle and shared helpers."""

import sqlite3
from collections.abc import Generator

from fastapi import HTTPException

from slidebuddy.config.defaults import DB_PATH
from slidebuddy.db.migrations import get_connection


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a DB connection, close it after the request."""
    conn = get_connection(DB_PATH)
    try:
        yield conn
    finally:
        try:
            conn.rollback()  # Clean up any uncommitted transactions
        except Exception:
            pass
        conn.close()


def _llm_http_exception(exc: Exception, context: str = "LLM") -> HTTPException:
    """Map an LLM exception to an HTTPException with the correct status code."""
    if isinstance(exc, ValueError):
        return HTTPException(422, f"{context}: {exc}")
    err_str = str(exc).lower()
    if "timeout" in err_str or "deadline" in err_str:
        return HTTPException(504, f"{context}: Die KI-Anfrage hat zu lange gedauert. Bitte erneut versuchen.")
    if "auth" in err_str or "api_key" in err_str or "401" in err_str:
        return HTTPException(401, f"{context}: API-Schlüssel ungültig oder abgelaufen.")
    if "rate" in err_str or "429" in err_str:
        return HTTPException(429, f"{context}: Zu viele Anfragen. Bitte kurz warten.")
    if "credit" in err_str or "balance" in err_str or "billing" in err_str:
        return HTTPException(402, f"{context}: API-Guthaben aufgebraucht. Bitte Konto beim Anbieter aufladen.")
    return HTTPException(500, f"{context} fehlgeschlagen: {exc}")
