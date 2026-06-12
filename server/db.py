"""Backwards-compatible re-export.

The engine, session factory, `Base` and `TimestampMixin` now live in
`server.core.database`. This module re-exports them so existing imports
(`from server.db import Base, SessionLocal, engine, TimestampMixin`)
keep working without modification.
"""
from server.core.database import (  # noqa: F401
    Base,
    SessionLocal,
    TimestampMixin,
    engine,
)
