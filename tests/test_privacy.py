"""Private-data redaction tests."""

from __future__ import annotations

import logging

from rag_ocpp.config import load_config
from rag_ocpp.privacy import (
    RedactingFilter,
    configure_redacted_logging,
    is_redaction_enabled,
    redact_text,
    redact_value,
    set_redaction_enabled,
)


def test_redact_text_masks_common_secret_shapes():
    text = (
        "Authorization=Bearer sk-test "
        "password=supersecret "
        '"api_key": "abc123" '
        "postgresql://rag:dbpass@localhost:5432/rag"
    )

    redacted = redact_text(text, max_chars=None)

    assert "sk-test" not in redacted
    assert "supersecret" not in redacted
    assert "abc123" not in redacted
    assert "dbpass" not in redacted
    assert "Authorization=[REDACTED]" in redacted
    assert "password=[REDACTED]" in redacted
    assert '"api_key": "[REDACTED]"' in redacted
    assert "postgresql://rag:[REDACTED]@localhost:5432/rag" in redacted


def test_redact_text_replaces_long_private_payload_with_digest():
    payload = "OCPP private specification paragraph " * 30

    redacted = redact_text(payload, max_chars=80)

    assert redacted.startswith("[REDACTED_TEXT len=")
    assert "sha256=" in redacted
    assert "OCPP private specification" not in redacted


def test_redact_value_recurses_and_masks_sensitive_mapping_keys():
    value = {
        "query": "What is BootNotification?",
        "api_key": "secret-key",
        "nested": {"Authorization": "Bearer sk-nested"},
    }

    redacted = redact_value(value)

    assert redacted["query"] == "What is BootNotification?"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["Authorization"] == "[REDACTED]"


def test_redacting_filter_sanitizes_log_record_arguments():
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="failed payload: %s",
        args=("Bearer sk-secret " + ("private answer " * 40),),
        exc_info=None,
    )

    assert RedactingFilter().filter(record)
    rendered = record.getMessage()

    assert "sk-secret" not in rendered
    assert "private answer" not in rendered
    assert "[REDACTED_TEXT" in rendered


def test_redaction_can_be_disabled_for_local_debug():
    set_redaction_enabled(False)
    try:
        raw = "Authorization=Bearer sk-debug " + ("private prompt " * 20)

        assert redact_text(raw, max_chars=20) == raw
        assert redact_value({"api_key": "sk-debug"}) == {"api_key": "sk-debug"}
    finally:
        set_redaction_enabled(True)


def test_configure_redacted_logging_accepts_env_style_strings():
    configure_redacted_logging(logging.INFO, enabled="false")
    try:
        assert is_redaction_enabled() is False
        assert redact_text("password=dev-secret") == "password=dev-secret"
    finally:
        configure_redacted_logging(logging.INFO, enabled="true")

    assert is_redaction_enabled() is True
    assert redact_text("password=prod-secret") == "password=[REDACTED]"


def test_logging_redaction_config_env_flag_is_boolean(monkeypatch):
    monkeypatch.setenv("LOG_REDACTION_ENABLED", "false")

    cfg = load_config()

    assert cfg.logging.redaction_enabled is False
    monkeypatch.setenv("LOG_REDACTION_ENABLED", "true")
    load_config()
