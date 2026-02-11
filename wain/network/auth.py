"""
Wain API Authentication
=======================

Token-based authentication for server-worker communication.
The server generates a token on first run and stores it in a file.
Workers must provide this token in the Authorization header.
"""

import hashlib
import os
import secrets

from wain.config import AUTH_TOKEN_FILE


def generate_token() -> str:
    """Generate a cryptographically secure API token."""
    return secrets.token_urlsafe(32)


def load_or_create_token(token_path: str = AUTH_TOKEN_FILE) -> str:
    """Load existing token from disk, or generate and save a new one.

    Returns the token string.
    """
    if os.path.isfile(token_path):
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                return token
        except OSError:
            pass

    # Generate new token
    token = generate_token()
    try:
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(token)
        # Restrict file permissions on Unix-like systems
        try:
            os.chmod(token_path, 0o600)
        except (OSError, AttributeError):
            pass  # Windows doesn't support Unix permissions
        print(f"[Wain] Generated new API token → {token_path}")
    except OSError as e:
        print(f"[Wain] Warning: could not save token file: {e}")

    return token


def hash_token(token: str) -> str:
    """Create a SHA-256 hash of a token for safe comparison."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(provided: str, expected: str) -> bool:
    """Constant-time comparison of two tokens to prevent timing attacks."""
    return secrets.compare_digest(provided, expected)
