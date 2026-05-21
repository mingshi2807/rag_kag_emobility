"""Text cleaner — normalize whitespace, strip artifacts, fix OCR, normalize OCPP terminology."""

from __future__ import annotations

import re
import unicodedata


class TextCleaner:
    """Normalize extracted document text for embedding and search.

    Operations in order:
        1. Unicode normalization (NFKC)
        2. Strip PDF headers/footers
        3. Fix common OCR artifacts
        4. Normalize OCPP terminology variants
        5. Collapse whitespace
        6. Trim empty lines

    Usage:
        cleaner = TextCleaner()
        clean_text = cleaner.clean(raw_text)
    """

    # Header/footer patterns
    HEADER_PATTERNS: list[re.Pattern[str]] = [
        re.compile(
            r"^OCPP\s+2\.\d\s*[-—–]\s*Part\s+\d+[:\s].*$",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^Open\s+Charge\s+Point\s+Protocol\s+2\.\d.*$",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(r"^Page\s+\d+\s*$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^[©\(C\)]\s*\d{4}.*$", re.MULTILINE),
        re.compile(r"^\d{4}-\d{2}-\d{2}\s*$", re.MULTILINE),
        re.compile(r"^https?://\S+\s*$", re.MULTILINE),
    ]

    # OCR fix pairs: (pattern, replacement)
    OCR_FIXES: list[tuple[str, str]] = [
        (r"\b(\w+)-\s*\n\s*(\w+)\b", r"\1\2"),
        (r"(?<=\d)l(?=\d)", "1"),
        (r"(?<=\d)O(?=\d)", "0"),
        ("\u201c", '"'), ("\u201d", '"'),
        ("\u2018", "'"), ("\u2019", "'"),
        ("\u2014", "—"), ("\u2013", "–"),
    ]

    # OCPP compound term normalization
    TERM_NORMALIZATIONS: list[tuple[str, str]] = [
        (r"Charge\s+Point", "ChargePoint"),
        (r"Smart\s+Charging", "SmartCharging"),
        (r"Charging\s+Station", "ChargingStation"),
        (r"Charging\s+Profile", "ChargingProfile"),
        (r"Charging\s+Schedule", "ChargingSchedule"),
        (r"Id\s+Token", "IdToken"),
        (r"Meter\s+Values", "MeterValues"),
        (r"Sampled\s+Value", "SampledValue"),
        (r"Boot\s+Notification", "BootNotification"),
        (r"Status\s+Notification", "StatusNotification"),
        (r"Firmware\s+Status\s+Notification", "FirmwareStatusNotification"),
        (r"Data\s+Transfer", "DataTransfer"),
        (r"Start\s+Transaction", "StartTransaction"),
        (r"Stop\s+Transaction", "StopTransaction"),
        (r"Get\s+Configuration", "GetConfiguration"),
        (r"Change\s+Configuration", "ChangeConfiguration"),
        (r"Clear\s+Cache", "ClearCache"),
        (r"Remote\s+Start\s+Transaction", "RemoteStartTransaction"),
        (r"Remote\s+Stop\s+Transaction", "RemoteStopTransaction"),
        (r"Reset\s+(?=Type)", "Reset"),
        (r"Trigger\s+Message", "TriggerMessage"),
        (r"Get\s+Diagnostics", "GetDiagnostics"),
        (r"Diagnostics\s+Status\s+Notification", "DiagnosticsStatusNotification"),
        (r"\bEVSE\b", "EVSE"),
        (r"\bCSMS\b", "CSMS"),
        (r"\bOCPP\b", "OCPP"),
        (r"\bISO\s*15118\b", "ISO15118"),
    ]

    def __init__(self, preserve_case: bool = True) -> None:
        self._preserve_case = preserve_case

    def clean(self, text: str) -> str:
        if not text:
            return ""

        # 1. Unicode normalization
        text = unicodedata.normalize("NFKC", text)

        # 2. Strip header/footer patterns
        for pattern in self.HEADER_PATTERNS:
            text = pattern.sub("", text)

        # 3. Fix OCR artifacts
        for pattern, replacement in self.OCR_FIXES:
            text = re.sub(pattern, replacement, text)

        # 4. Normalize OCPP terminology
        for pattern, replacement in self.TERM_NORMALIZATIONS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # 5. Collapse whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 6. Strip empty lines
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(line for line in lines if line)

        if not self._preserve_case:
            text = text.lower()

        return text.strip()

    def clean_page(self, text: str) -> str:
        return self.clean(text)
