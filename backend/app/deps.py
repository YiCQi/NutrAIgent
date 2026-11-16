"""Shared FastAPI dependencies (kept separate so routers avoid importing app.main)."""
from . import db

_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = db.connect()
    return _conn


def get_provider_factory():
    """Overridable in tests."""
    from .ai import providers
    return providers.make_provider
