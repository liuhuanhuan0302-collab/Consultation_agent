"""Compatibility imports; new code should use :mod:`app.core.config`."""

from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
