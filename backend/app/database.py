"""Compatibility imports; new code should use :mod:`app.db`."""

from app.db import Base, SessionLocal, engine, ensure_schema_upgrades, get_db, init_db

__all__ = ["Base", "SessionLocal", "engine", "ensure_schema_upgrades", "get_db", "init_db"]
