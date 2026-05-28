"""Private-knowledge redaction helpers for logs and diagnostics."""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any

_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_BASIC_RE = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9._~+/=-]+")
_DSN_RE = re.compile(r"(postgres(?:ql)?://[^:\s/@]+:)([^@\s]+)(@)")
_KEY_VALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)\b"
    r"(\s*[=:]\s*)"
    r"([^\s,;}\]]+)"
)
_JSON_FIELD_RE = re.compile(
    r'(?i)("(?:api[_-]?key|authorization|password|secret|token)"\s*:\s*)"([^"]*)"'
)

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
}

_REDACTION_ENABLED = True


def set_redaction_enabled(enabled: bool | str) -> None:
    """Set process-wide redaction behavior for logs and explicit redaction calls."""
    global _REDACTION_ENABLED
    _REDACTION_ENABLED = _coerce_bool(enabled)


def is_redaction_enabled() -> bool:
    """Return whether process-wide private-data redaction is active."""
    return _REDACTION_ENABLED


def redact_text(text: str, *, max_chars: int | None = 240) -> str:
    """Redact secrets and bound arbitrary text before it reaches logs.

    If ``max_chars`` is set and the sanitized string is longer, the content is
    replaced with a length and digest marker instead of a preview. This avoids
    leaking proprietary spec chunks, prompts, generated answers, or LLM payloads.
    """
    if not _REDACTION_ENABLED:
        return text

    sanitized = _BEARER_RE.sub("Bearer [REDACTED]", text)
    sanitized = _BASIC_RE.sub("Basic [REDACTED]", sanitized)
    sanitized = _DSN_RE.sub(r"\1[REDACTED]\3", sanitized)
    sanitized = _KEY_VALUE_RE.sub(r"\1\2[REDACTED]", sanitized)
    sanitized = _JSON_FIELD_RE.sub(r'\1"[REDACTED]"', sanitized)

    if max_chars is not None and len(sanitized) > max_chars:
        digest = hashlib.sha256(sanitized.encode("utf-8")).hexdigest()[:12]
        return f"[REDACTED_TEXT len={len(sanitized)} sha256={digest}]"
    return sanitized


def redact_value(value: Any, *, max_chars: int | None = 240) -> Any:
    """Redact secrets recursively in common logging values."""
    if not _REDACTION_ENABLED:
        return value

    if isinstance(value, BaseException):
        return redact_text(str(value), max_chars=max_chars)
    if isinstance(value, str):
        return redact_text(value, max_chars=max_chars)
    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower().replace("-", "_")
            if key_text in _SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_value(item, max_chars=max_chars)
        return redacted
    if isinstance(value, tuple):
        return tuple(redact_value(item, max_chars=max_chars) for item in value)
    if isinstance(value, list):
        return [redact_value(item, max_chars=max_chars) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return type(value)(redact_value(item, max_chars=max_chars) for item in value)
    return value


class RedactingFilter(logging.Filter):
    """Logging filter that redacts record templates and arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not _REDACTION_ENABLED:
            return True
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg, max_chars=None)
        if record.args:
            record.args = redact_value(record.args)
        return True


def configure_redacted_logging(
    level: int | str,
    *,
    format: str | None = None,
    enabled: bool | str = True,
) -> None:
    """Configure root logging with configurable private-data redaction."""
    set_redaction_enabled(enabled)
    kwargs: dict[str, Any] = {"level": level}
    if format is not None:
        kwargs["format"] = format
    logging.basicConfig(**kwargs)
    install_redacting_filter()


def install_redacting_filter() -> None:
    """Install a redacting filter on root handlers if not already present."""
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(flt, RedactingFilter) for flt in handler.filters):
            handler.addFilter(RedactingFilter())


def _coerce_bool(value: bool | str) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}
