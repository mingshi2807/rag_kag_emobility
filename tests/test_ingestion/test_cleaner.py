"""Unit tests — TextCleaner."""

from rag_ocpp.ingestion.cleaner import TextCleaner


class TestTextCleaner:
    def test_strip_headers(self):
        cleaner = TextCleaner()
        result = cleaner.clean("OCPP 2.1 — Part 2: Core\n\nActual content here.")
        assert "Actual content here" in result
        assert "OCPP 2.1" not in result

    def test_collapse_whitespace(self):
        result = TextCleaner().clean("Hello    world\n\n\n\nfoo")
        assert "Hello world" in result

    def test_normalize_ocpp_terms(self):
        result = TextCleaner().clean("The Charge Point sends a Boot Notification with an Id Token.")
        assert "ChargePoint" in result
        assert "BootNotification" in result
        assert "IdToken" in result

    def test_preserve_case(self):
        result = TextCleaner(preserve_case=True).clean("Authorize.req uses IdToken")
        assert "Authorize" in result

    def test_empty_input(self):
        assert TextCleaner().clean("") == ""
        assert TextCleaner().clean("   \n\n  ") == ""

    def test_ocr_fixes(self):
        result = TextCleaner().clean("voltage: 4l0V")
        assert "410V" in result
