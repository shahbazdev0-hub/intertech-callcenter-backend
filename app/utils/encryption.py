"""
Encryption utility for storing sensitive integration credentials.
Uses Fernet symmetric encryption (AES-128-CBC + HMAC).
"""

import os
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")


def _get_fernet():
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY environment variable is not set")
    return Fernet(ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string, return base64-encoded ciphertext."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext, return plaintext string."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def mask_value(value: str, visible_chars: int = 4) -> str:
    """Mask a sensitive value, showing only last N characters."""
    if not value or len(value) <= visible_chars:
        return "****"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
