## Purpose
- Enable OCPP 2.1 charging stations to execute Distributed Energy Resource (DER) control functions for bidirectional power transfer, aligning with grid code requirements.
- Define the protocol boundary where the CSMS acts as an aggregator between the utility (using IEC 61850, IEEE 2030.5, or other protocols) and the charging station, forwarding appropriate OCPP DER messages.
- Provide Device Model components (`DCDERCtrlr`, `ACDERCtrlr`) for capabilty advertisement and runtime variable reporting, and request messages (`SetDERControlRequest`, `ReportDERControlRequest`) for configuration and status.
- Support both DC (inverter in EVSE) and AC (inverter in EV or emulated by EVSE) scenarios, with hybrid control handled via `ACDERCtrlr.ModesSupported`.

## Normative behavior
- A DC bidirectional charging station **SHALL** expose the DER capabilities (“nameplate”) of its DC inverter through all mandatory variables of the `DCDERCtrlr` component, one such component per EVSE.  
  [R01.FR.01 / DCDERCtrlr table](OCPP-2.1_edition2_part2_specification.pdf, pages 809‑810, 561)
- When a `GetReportRequest` targets `DCDERCtrlr`, the charging station **SHALL** report every mandatory variable (`MaxW`, `OverExcitedW`, …, `ReactiveSusceptance`) as defined in the component table.  
  [R01.FR.02](OCPP-2.1_edition2_part2_specification.pdf, page 561)
- All DER control settings received via `SetDERControlRequest` **SHALL** be stored persistently (surviving power-cycles) by the charging station.  
  [R01.FR.03](OCPP-2.1_edition2_part2_specification.pdf, page 561)
- `DCDERCtrlr.ModesSupported` is a mandatory `MemberList` of `DERControlEnumType` that advertises the control modes the EVSE’s inverter can execute.  
  [2.18.1 DCDERCtrlr](OCPP-2.1_edition2_part2_specification.pdf, page 809)
- `ACDERCtrlr.ModesSupported` (a member list of the same enum) advertises which DER control modes the EVSE can emulate via ISO 15118‑20 ChargeLoop; an empty list means all control must be provided by the EV.  
  [2.18.2 ACDERCtrlr](OCPP-2.1_edition2_part2_specification.pdf, page 810)
- The optional `DCDERCtrlr.Enabled` boolean indicates whether DC DER control is enabled and that the corresponding capabilities are reported.  
  [DCDERCtrlr / Enabled](Appendices_CSV_v2.1/dm_components_vars.csv)
- The `ReportDERControlRequest` includes an optional boolean `tbc` (To Be Continued, default `false`) for pagination of a multi-part report; `false` signals the last message.  
  [ReportDERControl.req.tbc](OCPP-2.1_part3_JSON_schemas/ReportDERControlRequest.json)

## Implementation guidance
- **Capability discovery and reporting**  
  Implement a `GetReportRequest` handler for `component: DCDERCtrlr` (and optionally `ACDERCtrlr`). Return all mandatory variables exactly as defined, e.g., `MaxW`, `OverExcitedW`, `ModesSupported`, etc. Ensure `ModesSupported` lists only the `DERControlEnumType` values truly supported by the inverter or emulation logic.  
  [2.18.1, R01.FR.02](OCPP-2.1_edition2_part2_specification.pdf, pages 809, 561)

- **Processing SetDERControlRequest**  
  Validate incoming requests against the supported modes: reject any `controlType` not present in `DCDERCtrlr.ModesSupported` or `ACDERCtrlr.ModesSupported` (depending on the targeted charger). If accepted, apply the settings (curves, limits, etc.) to the power electronics and **persist** them in non‑volatile storage immediately.  
  [R01.FR.03](OCPP-2.1_edition2_part2_specification.pdf, page 561)

- **State transitions and alarm reporting**  
  When a DER control function (e.g., high‑frequency trip) modifies the charging/discharging process, inform the CSMS via `NotifyDERAlarmRequest`, supplying the affected `controlType` and relevant `gridEventFault` (e.g., `OverFrequency`, `LimitMaxDischarge`).  
  [R01 & R02 scenarios](OCPP-2.1_edition2_part2_specification.pdf, pages 549‑553)

- **Integration sequencing**  
  - At boot, the station should report its DER capabilities via BootNotification or a separate `NotifyReportRequest` containing `DCDERCtrlr`/`ACDERCtrlr` variables.  
  - The CSMS typically sends `SetDERControlRequest` with `isDefault = true` to install base grid‑code settings before any V2X session starts.  
  - During an active session, dynamic control may augment these defaults; the station must blend the DER limits with the active `ChargingProfile`.  
  - Use `ReportDERControlRequest` (to CSMS) to provide status of currently active DER controls; respect the `tbc` pagination flag.

- **Schema validation**  
  Validate every `SetDERControlRequest` against the OCPP JSON schema (ensure required fields present, correct types). For `ReportDERControlRequest`, enforce that `tbc` is boolean and default `false`; reject messages that fail schema checks. (Full schema for `SetDERControlRequest` is not in scope of the provided evidence, but the same principle applies.)

- **Error handling**  
  - Unsupported `controlType`: return `Rejected` with an appropriate reason code.  
  - Missing mandatory curve data or invalid limit values: reject with `FormationViolation` or `PropertyConstraintViolation`.  
  - If `DCDERCtrlr` is not available (e.g., DC DER not enabled), respond to a `GetReportRequest` with `NotSupported` or omit the component, consistent with the `Enabled` variable.  
  - When a DER alarm occurs but cannot be reported (offline), queue the `NotifyDERAlarmRequest` for later delivery.

## Conformance-test focus
- **Positive tests**  
  - Send `GetReportRequest` for `component: DCDERCtrlr` on a DC V2X‑capable station; verify all mandatory variables are returned with valid values per the definition (e.g., `MaxW`, `ModesSupported` containing `HFMustTrip`).  
  - Issue `SetDERControlRequest` with `controlType = VoltWatt` and a valid curve when `VoltWatt` is present in `ModesSupported`; check that `SetDERControlResponse` status is `Accepted` and the curve is applied.  
  - Power‑cycle the station and confirm the previously sent DER settings are still active (e.g., via a `GetDERControlRequest` or a custom report).  
  - Send a `ReportDERControlRequest` with `tbc = true` followed by another with `tbc = false`; the CSMS must correctly reassemble the paginated report.

- **Negative tests**  
  - Send `SetDERControlRequest` with a `controlType` not listed in `DCDERCtrlr.ModesSupported`; expect a `Rejected` response.  
  - Submit a `GetReportRequest` for `component: DCDERCtrlr` on a station where `DCDERCtrlr.Enabled` is `false`; the response must indicate the component is unavailable or report only the `Enabled = false` variable.  
  - Provide a `ReportDERControlRequest` with `tbc` set to a string; the station must reject the message with a schema validation error.  
  - Send a `SetDERControlRequest` that omits a required field (e.g., curve points for a trip curve); validate that the station rejects it with a `FormationViolation`.

## Evidence gaps
- The exact JSON schema for `SetDERControlRequest` is not provided; validation rules, field requirements, and type definitions cannot be fully detailed.  
- The complete structure and semantics of `ReportDERControlRequest` beyond the `tbc` field are absent; the purpose (e.g., reporting applied values, capabilities, or alarms) remains unclear.  
- No detailed description of `ACDERCtrlr` variables beyond `ModesSupported` is present; implementations relying on AC‑side DER emulation need additional variable definitions.  
- The use case “R04 – Configure DER control settings at Charging Station” is referenced but not included; normative configuration steps and timing are missing.  
- The evidence does not clarify how `isDefault` in `SetDERControlRequest` is handled by the station (e.g., effect on ongoing sessions, priority relative to session‑specific settings).
