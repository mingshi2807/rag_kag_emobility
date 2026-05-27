## Purpose
- Define V2X energy services in OCPP 2.1 Ed2 for bidirectional power transfer, enabling EV‑to‑grid, local load‑balancing, and frequency support.
- Establish implementation boundaries for the CSMS: which messages, Device Model variables, and schedule fields must be processed to activate and control V2X sessions.
- Clarify required pre‑conditions (e.g., capability reporting via V2XChargingCtrlr) and normative constraints for each OperationMode.

## Normative behavior
- The Charging Station must report its V2X capabilities through the Device Model component **V2XChargingCtrlr**:  
  - **V2XChargingCtrlr.Enabled** – set by CSMS to activate/deactivate V2X (required when V2X is supported) [2.17.1](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 801).  
  - **V2XChargingCtrlr.SupportedEnergyTransferModes** – a MemberList of `EnergyTransferModeEnumType` values (required when V2X is supported) [2.17.2](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 801) / [Device Model](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.xlsx).  
  - **V2XChargingCtrlr.SupportedOperationModes** – list of supported `OperationModeEnumType` values that the CSMS may request in a ChargingSchedulePeriodType (required when V2X is supported) [2.17.3](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 802).
- A V2X session begins with the EV sending a `NotifyEVChargingNeedsRequest`. For bidirectional transfers the CSMS may receive the optional field **v2xChargingParameters.evMaxV2XEnergyRequest** (a negative number indicates the current SoC is above the V2X range), as per schema:  
  `NotifyEVChargingNeedsRequest.chargingNeeds.v2xChargingParameters.evMaxV2XEnergyRequest` [NotifyEVChargingNeeds.req.chargingNeeds.v2xChargingParameters.evMaxV2XEnergyRequest](data/json/ocpp2.1Ed2/OCPP-2.1_part3_JSON_schemas/NotifyEVChargingNeedsRequest.json).
- Depending on the chosen **OperationMode**, the ChargingSchedulePeriodType in `SetChargingProfileRequest` must satisfy strict rules:
  - **ChargingOnly** – field `dischargeLimit`, `setpoint`, `setpointReactive` (and their L2/L3 variants) SHALL NOT be present [Q02.FR.02](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 525).
  - **LocalFrequency** – SHALL NOT contain `limit`, `dischargeLimit`, `setpoint`, `setpointReactive`. Must include `v2xFreqWattCurve` (≥2 points) and `v2xBaseline`; optionally `v2xSignalWattCurve` for aFRR. ChargingRateUnit must be “W” [Q08.FR.01–Q08.FR.05](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, pages 541‑542).
  - **LocalLoadBalancing** – setpoint is calculated locally using configured `UpperThreshold`, `LowerThreshold`, and offsets. The station must be able to read an upstream meter (prerequisite) [Q09](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 544). The Device Model variables **V2XLocalLoadBalancing[UpperThreshold]**, **[LowerThreshold]**, **[UpperOffset]**, **[LowerOffset]** must be configured (required when this mode is supported) [2.17.6](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, pages 801‑802).
- For frequency support, the Charging Station must update the setpoint whenever the net frequency change exceeds **V2XChargingCtrlr.LocalFrequencyUpdateThreshold** (in mHz) [2.17.4](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 802) [Q08.FR.07](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 542).

## Implementation guidance
- **Device Model validation**: Before sending any V2X schedule, the CSMS must verify that the Charging Station reports a V2XChargingCtrlr component and that the desired OperationMode is present in **SupportedOperationModes**. Retrieve **SupportedEnergyTransferModes** to confirm whether the session’s requested transfer mode (e.g., DC_BPT, AC_BPT) is permissible.
- **Persist DER control settings**: When DER controls are configured via `SetDERControlRequest`, the Charging Station SHALL store them persistently (even after power‑cycle) [R01.FR.03](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 564). The CSMS must set `isDefault = true` and include the correct `controlType` and parameters (e.g., VoltWatt curve, `limitMaxDischargePct`) as described in [R01](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 561) and [R02](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 564).
- **Integration sequencing**:  
  1. CSMS receives `NotifyEVChargingNeedsRequest` with `requestedEnergyTransfer` possibly including bidirectional modes.  
  2. If V2X is not yet allowed, start with OperationMode **ChargingOnly** (by omitting `allowedEnergyTransfer` in `AuthorizeResponse` and sending a `SetChargingProfileRequest` with `operationMode = ChargingOnly`) [Q02](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 525).  
  3. Later, authorize V2X by sending `NotifyAllowedEnergyTransferRequest` with an updated list. This triggers a service re‑negotiation.  
  4. For a fully authorised V2X session, CSMS calculates a TxProfile and sends it via `SetChargingProfileRequest` with the appropriate `chargingProfileKind` (Dynamic recommended for central frequency control) and the correct OperationMode fields.
- **Error handling**:  
  - If a LocalFrequency schedule is missing `v2xFreqWattCurve` or `v2xBaseline`, or it has too few curve points, reply with `SetChargingProfileResponse(status = Rejected, statusInfo.reasonCode = "NoFreqWattCurve")` [Q08.FR.03](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 542).  
  - If forbidden fields (e.g., `limit`, `dischargeLimit`, `setpoint`) are present in LocalFrequency or ChargingOnly scenarios, reject with reason `"InvalidSchedule"` [Q08.FR.04](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 542).  
  - For aFRR, if an `AFRRSignalRequest` is received while no active period contains `v2xSignalWattCurve`, reject with reason `"NoSignalWattCurve"` [Q08.FR.11](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 544).
- **LocalLoadBalancing configuration**: Ensure that the four required Device Model variables (`UpperThreshold`, `LowerThreshold`, `UpperOffset`, `LowerOffset`) are written to the Charging Station before or along with the charging profile. The CSMS may read the grid meter values only indirectly through the station’s behaviour; no OCPP message conveys the raw meter reading.

## Conformance-test focus
- **Positive tests**:  
  - Send a `SetChargingProfileRequest` with a `LocalLoadBalancing` schedule; verify that the Charging Station adjusts its setpoint according to the threshold logic described in [Q09](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 544).  
  - Provide a `LocalFrequency` schedule with a valid `v2xFreqWattCurve` and `v2xBaseline`; observe that the setpoint is updated dynamically, and if `v2xSignalWattCurve` is present and an `AFRRSignalRequest` arrives, the delta is added.  
  - Start a session in `ChargingOnly` mode, later issue `NotifyAllowedEnergyTransferRequest` with `DC_BPT`; confirm that the CSMS can transition to a bidirectional schedule.
- **Negative tests**:  
  - Attempt to set `operationMode = LocalFrequency` without `v2xFreqWattCurve`; expect a `SetChargingProfileResponse` with `status = Rejected` and `reasonCode = "NoFreqWattCurve"`.  
  - Include `dischargeLimit` in a `ChargingOnly` schedule; the Charging Station must reject with `"InvalidSchedule"`.  
  - Send a `LocalLoadBalancing` schedule when the station does not support that mode (not listed in `SupportedOperationModes`); proper behaviour is to reject with an appropriate status (implied by device capability check).  
  - Validate the JSON schema for `NotifyEVChargingNeedsRequest`: omit the optional `evMaxV2XEnergyRequest` – must be accepted; provide a string instead of a number – must fail schema validation.

## Evidence gaps
- The retrieved context lacks the full JSON schema for `ChargingSchedulePeriodType` with the `operationMode` field and its enumerated values; only prose descriptions of allowed/disallowed fields per mode were provided.
- No explicit normative statement requiring the Charging Station to reject a profile when the required `LocalLoadBalancing` thresholds are missing; the text only states “when supporting V2X operationMode LocalLoadBalancing” these variables are required in the Device Model, leaving error handling up to implementation.
- The specification does not define a rejection reason for an unsupported OperationMode in `SetChargingProfileRequest`; testing this scenario may need to infer from common sense rather than a clear requirement.
