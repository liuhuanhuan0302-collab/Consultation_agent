"""Compatibility imports; new code should use :mod:`app.core.security`."""

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password

__all__ = ["create_access_token", "decode_access_token", "hash_password", "verify_password"]
