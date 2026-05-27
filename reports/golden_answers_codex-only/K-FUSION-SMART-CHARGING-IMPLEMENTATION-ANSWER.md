## Purpose

- Provide a Codex-assisted, MCP-evidence-grounded benchmark answer for OCPP 2.1 Ed2 smart charging without invoking DeepSeek or OpenAI API generation from the repo CLI.
- Treat smart charging as a fusion topic: Section K behavior defines profile/limit semantics, `SmartChargingCtrlr` Device Model variables define supported capability, and JSON schemas define message payload constraints.
- Guide backend implementation for `SetChargingProfile`, `ChargingProfile`, schedule/limit validation, Device Model gating, persistence, and conformance testing.
- Keep implementation advice source-aware and suitable for later expert review.

## Normative behavior

- `SmartChargingCtrlr.Enabled` controls whether smart charging is enabled, and `SmartChargingCtrlr.Available` reports whether smart charging is supported [2.10. Smart Charging related](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 769).
- `SmartChargingCtrlr.ACPhaseSwitchingSupported` indicates whether an EVSE supports in-transaction phase selection for one-phase AC charging [2.10. Smart Charging related](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 769).
- `SmartChargingCtrlr.ProfileStackLevel` is required and defines the maximum acceptable `stackLevel`; because the lowest stack level is 0, value 1 means at most two valid profiles per charging-profile purpose per EVSE [SmartChargingCtrlr / ProfileStackLevel](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.csv).
- `SmartChargingCtrlr.RateUnit` is required and lists supported charging schedule quantities, such as `A` and `W` [2.10. Smart Charging related](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 769).
- `SmartChargingCtrlr.PeriodsPerSchedule` is required and defines the maximum number of periods per charging schedule [2.10. Smart Charging related](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 769).
- `SmartChargingCtrlr.SupportedAdditionalPurposes` lists additional OCPP 2.1 charging-profile purposes supported by the Charging Station [SmartChargingCtrlr / SupportedAdditionalPurposes](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.csv).
- `SmartChargingCtrlr.ChargingProfilePersistence` instances for purposes such as `TxProfile`, `LocalGeneration`, and `ChargingStationExternalConstraints` indicate whether those profiles persist after reboot [SmartChargingCtrlr / ChargingProfilePersistence / TxProfile](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.xlsx) [SmartChargingCtrlr / ChargingProfilePersistence / LocalGeneration](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.xlsx).
- `SetChargingProfile.req` requires top-level `evseId` and `chargingProfile`; backend schema validation must enforce those fields before dispatch [SetChargingProfile.req](data/json/ocpp2.1Ed2/OCPP-2.1_part3_JSON_schemas/SetChargingProfileRequest.json).
- Dynamic schedule update structures may contain `limit`, `dischargeLimit`, `setpoint`, and reactive setpoint fields; smart-charging storage should preserve these separately instead of flattening them into one limit [ChargingScheduleUpdateType](data/json/ocpp2.1Ed2/OCPP-2.1_part3_JSON_schemas/UpdateDynamicScheduleRequest.json).

## Implementation guidance

- Build a `SmartChargingCtrlr` capability snapshot before accepting or sending a smart-charging Request. Include `Enabled`, `Available`, `ProfileStackLevel`, `RateUnit`, `PeriodsPerSchedule`, `SupportedAdditionalPurposes`, and persistence variables.
- Validate `SetChargingProfile.req` against JSON schema before business logic. Reject locally when `evseId` or `chargingProfile` is missing or malformed.
- Validate profile semantics after schema validation: stack level must not exceed `ProfileStackLevel`, schedule period count must not exceed `PeriodsPerSchedule`, and charging-rate units must be present in `RateUnit`.
- Normalize accepted `ChargingProfile` objects into a persistence model with profile ID, purpose, kind, stack level, EVSE scope, schedule periods, limits, discharge limits, setpoints, validity windows, and persistence behavior.
- Keep limit-like fields distinct. `limit`, `dischargeLimit`, `setpoint`, and reactive setpoints have different operational meanings and must be traceable independently.
- Apply Device Model gating before dispatching `SetChargingProfile`. For example, do not rely on phase-switching behavior unless `ACPhaseSwitchingSupported` indicates support.
- Preserve provenance in storage: schema version/file, Device Model variables used for gating, active profile set at decision time, and Section K evidence.
- On response, persist accepted/rejected status separately from the original Request and expose the reason to conformance tests.

## Conformance-test focus

- Positive test: `SmartChargingCtrlr.Enabled` is true, required Device Model limits are present, `SetChargingProfile.req` has `evseId` and `chargingProfile`, and backend stores a valid profile.
- Negative schema test: omit `chargingProfile` or `evseId`; backend rejects before sending.
- Negative stack-level test: profile stack level exceeds `SmartChargingCtrlr.ProfileStackLevel`; backend rejects or maps to protocol rejection.
- Negative schedule test: schedule period count exceeds `PeriodsPerSchedule` or rate unit is not in `RateUnit`; backend rejects deterministically.
- Persistence test: profiles with `ChargingProfilePersistence` support survive restart according to the relevant purpose; non-persistent profiles do not.
- Dynamic schedule test: update payloads preserve `limit`, `dischargeLimit`, and setpoint fields independently.
- Regression test: rerun fusion retrieval quality and offline golden-answer scoring before merging smart-charging retrieval or generation changes.

## Evidence gaps

- MCP evidence confirms key SmartChargingCtrlr variables and top-level `SetChargingProfile.req` fields, but this answer does not enumerate every nested `ChargingProfile` schema property.
- Future expert-grade scoring should require exact schema paths for profile purpose, kind, schedule period fields, operation mode, and response statuses.
- This benchmark is Codex-authored from MCP evidence and scored offline; it is provider-neutral but not a fully automated OpenAI API generation path.
