"""Checks on the endpoint a credential is about to be sent to."""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlsplit

logger = logging.getLogger("chameleon_llm")

# Base URLs already reported in this process (one WARNING per distinct URL).
_WARNED_CLEARTEXT: set[str] = set()


def _reset_cleartext_warnings() -> None:
    """Forget which base URLs were reported (for tests)."""
    _WARNED_CLEARTEXT.clear()


def _split(base_url: str):
    try:
        parts = urlsplit(base_url.strip())
        return parts, parts.hostname  # .hostname raises on a malformed IPv6 host
    except ValueError:
        return None, None


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    host = host.lower().rstrip(".")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback  # 127.0.0.0/8, ::1
    except ValueError:
        return False


def is_cleartext_remote(base_url: str) -> bool:
    """True unless ``base_url`` is https or names a loopback host."""
    parts, host = _split(base_url)
    if parts is None:
        return True
    return parts.scheme.lower() != "https" and not _is_loopback(host)


def _display(base_url: str) -> str:
    """The URL without user info, query or fragment (they can hold secrets)."""
    parts, host = _split(base_url)
    if parts is None or not host:
        return "<unparseable base URL>"
    if ":" in host:
        host = f"[{host}]"
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = f"{host}:{port}" if port else host
    return f"{parts.scheme}://{netloc}{parts.path}"


def warn_if_cleartext_key(api_key: str | None, base_url: str | None,
                          provider: str) -> None:
    """Log one WARNING per base URL when a real API key is about to be sent
    to an endpoint that is neither https nor loopback. The request is still
    sent: the endpoint is operator-configured and may be deliberate. The key
    itself is never logged."""
    if not api_key or not base_url or not is_cleartext_remote(base_url):
        return
    if base_url in _WARNED_CLEARTEXT:
        return
    _WARNED_CLEARTEXT.add(base_url)
    logger.warning(
        "chameleon_llm: the %s API key is being sent unencrypted to %s: the "
        "base URL is not https and its host is not loopback. Use an https "
        "endpoint unless this network path is trusted", provider,
        _display(base_url))
