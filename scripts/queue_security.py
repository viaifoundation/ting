"""Shared validation for the queue manager and worker."""
import os
import re
from urllib.parse import urlsplit


def require_secret():
    secret = os.environ.get("VPS_WEBHOOK_SECRET", "")
    if not re.fullmatch(r"[!-~]{32,256}", secret):
        raise ValueError("Set VPS_WEBHOOK_SECRET to a random secret of 32-256 printable ASCII characters without spaces")
    return secret


def validate_plan_id(plan_id):
    # A single filename component; also excludes SQL and CLI metacharacters.
    if not isinstance(plan_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", plan_id):
        raise ValueError("Invalid plan_id: use 1-128 ASCII letters, digits, underscores or hyphens")
    return plan_id


def validate_manager_url(url):
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("TING_MANAGER_URL must not contain credentials, query or fragment")
    if not parsed.hostname or parsed.path not in ("", "/"):
        raise ValueError("TING_MANAGER_URL must be an origin URL")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
    ):
        raise ValueError("TING_MANAGER_URL requires HTTPS except on loopback")
    return url.rstrip("/")
