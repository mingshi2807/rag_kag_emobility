"""OCPP entity type definitions and regex extraction patterns (Pass 1 — fast, free)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


# ── Entity type enum ─────────────────────────────────────

class OCPPEntityType(Enum):
    """OCPP 2.1 entity types — corresponds to entity_types table rows."""
    COMMAND          = (1,  "command")
    DATATYPE         = (2,  "datatype")
    COMPONENT        = (3,  "component")
    VARIABLE         = (4,  "variable")
    ENUM             = (5,  "enum")
    MESSAGE_FLOW     = (6,  "message_flow")
    FUNCTIONAL_BLOCK = (7,  "functional_block")
    ERROR_CODE       = (8,  "error_code")
    TEST_CASE        = (9,  "test_case")

    @property
    def type_id(self) -> int:
        return self.value[0]

    @property
    def label(self) -> str:
        return self.value[1]

    @classmethod
    def from_type_id(cls, type_id: int) -> OCPPEntityType | None:
        for member in cls:
            if member.type_id == type_id:
                return member
        return None


# ── Known OCPP terms per entity type ─────────────────────

_COMMANDS = [
    "Authorize", "BootNotification", "Heartbeat", "MeterValues",
    "StatusNotification", "StartTransaction", "StopTransaction",
    "DataTransfer", "DiagnosticsStatusNotification",
    "FirmwareStatusNotification", "GetConfiguration",
    "ChangeConfiguration", "ClearCache", "RemoteStartTransaction",
    "RemoteStopTransaction", "Reset", "TriggerMessage",
    "GetDiagnostics", "UnlockConnector", "ChangeAvailability",
    "ClearChargingProfile", "GetCompositeSchedule",
    "SetChargingProfile", "GetLocalListVersion", "SendLocalList",
    "ReserveNow", "CancelReservation", "UpdateFirmware",
    "GetLog", "SignedUpdateFirmware", "InstallCertificate",
    "GetInstalledCertificateIds", "DeleteCertificate",
    "NotifyEvent", "ReportChargingProfiles", "NotifyMonitoringReport",
    "SetMonitoringBase", "GetMonitoringReport",
    "SetMonitoringLevel", "ClearMonitoringResult",
    "SetNetworkProfile", "SetVariableMonitoring",
    "ClearVariableMonitoring", "GetVariables", "SetVariables",
    "GetBaseReport", "GetReport", "CustomerInformation",
    "NotifyCustomerInformation", "PublishFirmware",
    "PublishFirmwareStatusNotification", "GetTransactionStatus",
    "RequestStartTransaction", "RequestStopTransaction",
    "GetDisplayMessages", "SetDisplayMessage", "ClearDisplayMessage",
    "CostUpdated", "NotifyChargingLimit",
    "NotifyEVChargingNeeds", "NotifyEVChargingSchedule",
    "NotifyPriorityCharging", "NotifySettlement",
    "PullDynamicScheduleUpdate",
]

_DATATYPES = [
    "IdToken", "IdTokenInfo", "ChargingProfile", "ChargingSchedule",
    "ChargingSchedulePeriod", "TransactionData", "MeterValue",
    "SampledValue", "Component", "Variable", "EVSE",
    "NetworkConnectionProfile",
    "FirmwareInfo", "LogParameters", "CertificateHashData",
    "AuthorizationData", "MessageInfo", "OCSPRequestData",
    "StatusInfo", "SetVariableData", "GetVariableData",
    "VariableMonitoring", "EventData", "ReportData",
    "ChargingLimit", "ChargingNeeds", "ACChargingParameters",
    "DCChargingParameters", "V2GChargingParameters",
    "Cost", "ConsumptionCost", "RelativePrice",
    "SalesTariff", "SalesTariffEntry", "CompositeSchedule",
    "ChargingProfileCriterion", "ClearChargingProfileInfo",
    "CertificateSignedData", "CertificateChainData",
    "GetVariableResult", "SetVariableResult",
]

_COMPONENTS = [
    "ChargePoint", "ChargingStation", "Connector", "EVSE",
    "EV", "CSMS", "ChargingStationOperator", "EVDriver",
]

_VARIABLES = [
    "HeartbeatInterval", "ConnectionTimeout",
    "TransactionMessageRetryInterval",
    "AuthorizationCacheEnabled", "LocalAuthListEnabled",
    "StopTransactionOnEVSideDisconnect", "StopTransactionOnInvalidId",
    "MaxEnergyOnInvalidId", "AllowOfflineTxForUnknownId",
    "CpoName", "ChargePointSerialNumber",
]

_ENUMS = [
    "ChargingState", "ConnectorStatus", "Reason",
    "ReadingContext", "ValueFormat", "Measurand", "Phase",
    "Location", "UnitOfMeasure", "AuthorizationStatus",
    "MessageTrigger", "ResetType", "FirmwareStatus",
    "DiagnosticsStatus", "UpdateStatus", "ChargingProfilePurposeType",
    "ChargingProfileKindType", "RecurrencyKindType",
    "ChargingRateUnitType", "CostKindType",
    "HashAlgorithmEnumType", "CertificateStatus",
    "CertificateUse",
    "LogStatus", "UploadLogStatus", "MonitoringCriterion",
    "EventTrigger", "EventNotification", "ReportBase",
]

_FUNCTIONAL_BLOCKS = [
    "Core", "Security", "SmartCharging", "LocalController",
    "ISO15118", "DisplayAndMessaging", "FirmwareManagement",
    "Provisioning", "RemoteTrigger", "Reservation",
    "Authorization", "LocalAuthListManagement",
    "Diagnostics", "Monitoring", "Customer",
    "TariffAndCost", "Transaction",
]

_ERROR_CODES = [
    "NotSupported", "InternalError", "ProtocolError",
    "SecurityError", "FormationViolation", "PropertyConstraintViolation",
    "OccurrenceConstraintViolation", "TypeConstraintViolation",
    "GenericError", "SecurityViolation", "MessageSyntaxError",
    "FormatViolation", "RpcFrameworkError",
]

_TEST_CASE_PATTERN = r"\bTC_[A-Z]{2}_\d{2,3}\b"


# ── Compiled patterns ────────────────────────────────────

class OCPPPatterns:
    """Compiled regex patterns for Pass 1 entity extraction."""

    PROTOCOL_ID: ClassVar[int] = 1
    _patterns: ClassVar[list[tuple[OCPPEntityType, re.Pattern[str]]]] = []

    @classmethod
    def get_patterns(cls) -> list[tuple[OCPPEntityType, re.Pattern[str]]]:
        if not cls._patterns:
            cls._patterns = cls._build()
        return cls._patterns

    @classmethod
    def _build(cls) -> list[tuple[OCPPEntityType, re.Pattern[str]]]:
        patterns: list[tuple[OCPPEntityType, re.Pattern[str]]] = []
        sl = lambda items: sorted(items, key=len, reverse=True)

        patterns.append(
            (OCPPEntityType.COMMAND,
             re.compile(r"\b(?P<name>" + "|".join(sl(_COMMANDS)) + r")(?:\.(?:req|conf))?\b"))
        )
        patterns.append(
            (OCPPEntityType.DATATYPE,
             re.compile(r"\b(?P<name>" + "|".join(sl(_DATATYPES)) + r")\b"))
        )
        patterns.append(
            (OCPPEntityType.COMPONENT,
             re.compile(r"\b(?P<name>" + "|".join(sl(_COMPONENTS)) + r")\b"))
        )
        patterns.append(
            (OCPPEntityType.VARIABLE,
             re.compile(r"\b(?P<name>" + "|".join(sl(_VARIABLES)) + r")\b"))
        )
        patterns.append(
            (OCPPEntityType.VARIABLE,
             re.compile(r"\b(?P<name>[a-z]+(?:[A-Z][a-z0-9]*){1,4})\b"))
        )
        patterns.append(
            (OCPPEntityType.ENUM,
             re.compile(r"\b(?P<name>" + "|".join(sl(_ENUMS)) + r")\b"))
        )
        patterns.append(
            (OCPPEntityType.FUNCTIONAL_BLOCK,
             re.compile(r"\b(?P<name>" + "|".join(sl(_FUNCTIONAL_BLOCKS)) + r")\b"))
        )
        patterns.append(
            (OCPPEntityType.ERROR_CODE,
             re.compile(r"\b(?P<name>" + "|".join(sl(_ERROR_CODES)) + r")\b"))
        )
        patterns.append(
            (OCPPEntityType.TEST_CASE,
             re.compile(_TEST_CASE_PATTERN))
        )
        return patterns


# ── Data types ────────────────────────────────────────────

@dataclass
class PatternMatch:
    """A single regex match with entity type and span."""
    entity_type: OCPPEntityType
    name: str
    span_start: int
    span_end: int


def extract_pattern_matches(text: str) -> list[PatternMatch]:
    """Extract all OCPP entity mentions from text via regex.

    Deduplicated by overlapping spans (longest match wins).
    """
    matches: list[PatternMatch] = []
    seen_spans: set[tuple[int, int]] = set()

    for entity_type, pattern in OCPPPatterns.get_patterns():
        for m in pattern.finditer(text):
            name = m.group("name")
            span = (m.start(), m.end())

            if any(span[0] >= s[0] and span[1] <= s[1] for s in seen_spans):
                continue

            if entity_type == OCPPEntityType.VARIABLE:
                if any(
                    ms.entity_type in (OCPPEntityType.COMMAND, OCPPEntityType.DATATYPE)
                    and ms.span_start <= span[0] and ms.span_end >= span[1]
                    for ms in matches
                ):
                    continue

            seen_spans.add(span)
            matches.append(PatternMatch(
                entity_type=entity_type,
                name=name,
                span_start=m.start(),
                span_end=m.end(),
            ))

    return matches


def extract_entity_names(
    text: str, entity_type: OCPPEntityType | None = None
) -> list[str]:
    """Extract unique entity names from text, optionally filtered by type."""
    matches = extract_pattern_matches(text)
    if entity_type is not None:
        matches = [m for m in matches if m.entity_type == entity_type]
    return sorted(set(m.name for m in matches))
