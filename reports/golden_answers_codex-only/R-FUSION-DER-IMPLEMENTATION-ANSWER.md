## Purpose

- Provide a Codex-assisted, MCP-evidence-grounded benchmark answer for OCPP 2.1 Ed2 DER control without calling DeepSeek or the OpenAI API from the repo CLI.
- Treat DER control as a fusion feature: Part 2 requirements define the protocol behavior, Device Model rows define advertised capability, and JSON schemas define the Request and Response validation boundary.
- Guide a CSMS backend that must discover DER capability, validate `SetDERControl` and `ReportDERControl` payloads, persist accepted control state, and expose conformance-test evidence.
- Keep the implementation bounded to retrieved MCP evidence; missing fields, enum values, or unsupported modes must be reported as evidence gaps instead of invented.

## Normative behavior

- A DC bidirectional Charging Station that supports DER control SHALL expose DC inverter DER capabilities in `DCDERCtrlr` variables for each EVSE [R01/R02 DER control requirements](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 564).
- When receiving `GetReportRequest` for `DCDERCtrlr`, a DC bidirectional Charging Station SHALL report mandatory `DCDERCtrlr` variables [R01.FR.02](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 564).
- DER controls received as `SetDERControlRequest` messages SHALL be stored persistently by the Charging Station [R01.FR.03](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 564).
- `DCDERCtrlr` is located at EVSE level and represents DC inverter nameplate information; key evidence includes `Enabled`, `ModesSupported`, and mandatory ratings such as `MaxW` [DCDERCtrlr / Enabled](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.xlsx) [DCDERCtrlr / ModesSupported](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.xlsx) [DCDERCtrlr / MaxW](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.xlsx).
- `ACDERCtrlr.ModesSupported` represents DER control functions the EVSE can emulate by controlling the EV inverter through ISO 15118-20 ChargeLoop messages [ACDERCtrlr / ModesSupported](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.xlsx).
- `SetDERControl.req` requires `isDefault`, `controlId`, and `controlType`; its payload may include control objects such as `curve`, `enterService`, `fixedPFAbsorb`, `fixedPFInject`, `fixedVar`, `freqDroop`, `gradient`, and `limitMaxDischarge` [SetDERControl.req](data/json/ocpp2.1Ed2/OCPP-2.1_part3_JSON_schemas/SetDERControlRequest.json).
- `ReportDERControl.req` requires `requestId` and reports DER control structures including `curve`, `enterService`, `fixedPFAbsorb`, `fixedPFInject`, `fixedVar`, `freqDroop`, `gradient`, and `limitMaxDischarge` [ReportDERControl.req](data/json/ocpp2.1Ed2/OCPP-2.1_part3_JSON_schemas/ReportDERControlRequest.json).
- `SetDERControl.conf` requires `status` and may include `statusInfo` and `supersededIds`, so backend state must be driven by a schema-valid Response rather than by send success alone [SetDERControl.conf](data/json/ocpp2.1Ed2/OCPP-2.1_part3_JSON_schemas/SetDERControlResponse.json).

## Implementation guidance

- Build a DER capability resolver before message dispatch. Read `DCDERCtrlr.Enabled`, `DCDERCtrlr.ModesSupported`, `DCDERCtrlr.MaxW`, and `ACDERCtrlr.ModesSupported` from Device Model reports and persist the EVSE-scoped capability snapshot with source metadata.
- Separate DC DER and AC DER behavior. DC DER uses station/EVSE inverter capability (`DCDERCtrlr`); AC DER may depend on ISO 15118-20 EV support and `ACDERCtrlr` modes.
- Validate `SetDERControl.req` against JSON schema before dispatch. Reject locally when `isDefault`, `controlId`, or `controlType` is missing, or when a nested required field such as `freqDroop.responseTime` is absent for a chosen control structure.
- On response, validate `SetDERControl.conf.status`, then persist accepted/rejected state, any `statusInfo`, and `supersededIds`. Do not mark a DER control active on transport acknowledgement alone.
- For reporting, validate `ReportDERControl.req.requestId` and map reported control structures back to the control ID and EVSE capability snapshot used by the CSMS.
- Store audit evidence for each control decision: retrieved spec section, Device Model component/variable rows, schema names, request/response validation result, and final protocol status.
- Keep Charging Station behavior distinct from CSMS behavior: the Charging Station reports capabilities and stores accepted control settings; the CSMS validates capability, selects control intent, sends the Request, and records evidence.

## Conformance-test focus

- Positive DC DER test: Device Model reports `DCDERCtrlr.Enabled`, `ModesSupported`, and mandatory nameplate variables; CSMS sends a schema-valid `SetDERControl.req`; Charging Station returns schema-valid `SetDERControl.conf.status`; backend persists the control.
- Positive AC DER test: `ACDERCtrlr.ModesSupported` exists and session evidence supports AC DER; backend validates the selected control path before dispatch.
- Negative schema test: omit `SetDERControl.req.controlType` or `isDefault`; backend must fail schema validation before sending.
- Negative nested schema test: provide `freqDroop` without required `responseTime`; backend must reject or report schema invalid.
- Negative capability test: no DER mode is advertised in `DCDERCtrlr.ModesSupported` or `ACDERCtrlr.ModesSupported`; backend must not send an unsupported `SetDERControl` Request.
- Reporting test: ingest `ReportDERControl.req` with a valid `requestId`, validate the control structures, and link the result to prior `SetDERControl` state.
- Persistence test: accepted DER controls remain represented after backend restart and are traceable to source evidence.

## Evidence gaps

- The MCP evidence confirms key requirements, Device Model variables, and schema fields, but this benchmark answer does not yet enumerate every `DERControlEnumType` value.
- Field-level conformance should later assert exact enum values, every nested DER control object, and all status values from `SetDERControl.conf`.
- This is a Codex-authored answer generated from MCP evidence and then scored offline; it is not an automated OpenAI API generation path.
