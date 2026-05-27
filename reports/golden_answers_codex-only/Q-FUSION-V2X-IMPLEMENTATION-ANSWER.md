## Purpose

- Provide a Codex-assisted, MCP-evidence-grounded benchmark answer for OCPP 2.1 Ed2 V2X energy services without a DeepSeek or OpenAI API generation call from the repo CLI.
- Treat V2X as a fusion implementation area: Section Q defines authorization and energy-transfer behavior, the Device Model exposes V2X capability, and JSON schemas constrain the Request payloads.
- Guide a backend that must handle V2X authorization, `NotifyEVChargingNeeds` validation, Device Model capability checks, charging profile decisions, persistence, and conformance tests.
- Preserve traceability from every implementation decision back to specification, Device Model, or schema evidence.

## Normative behavior

- Q01 V2X Authorization describes authorization of an EV by the CSMS to start a V2X power transfer loop; the CSMS returns allowed energy transfers and the EV selects the desired transfer [Q01 - V2X Authorization](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 521).
- The V2X flow includes `AuthorizeRequest`, `TransactionEventRequest`, `NotifyEVChargingNeedsRequest`, and then a CSMS `SetChargingProfileRequest` with a charging schedule containing a V2X operation mode other than `ChargingOnly` [Q01 - V2X Authorization](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 521).
- Q01 prerequisites include `ISO15118Ctrlr.Enabled = true` and `V2XChargingCtrlr.Enabled = true` [Q01 - V2X Authorization](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 521).
- `V2XChargingCtrlr.Enabled` is the Device Model variable used by the CSMS to activate or deactivate V2X functionality [V2XChargingCtrlr / Enabled](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.xlsx).
- `V2XChargingCtrlr.SupportedEnergyTransferModes` lists energy transfer services supported by the Charging Station [V2XChargingCtrlr / SupportedEnergyTransferModes](data/csv/ocpp2.1Ed2/Appendices_CSV_v2.1/dm_components_vars.xlsx).
- Q01 requirements include that the Charging Station SHALL report supported energy transfer modes in `V2XChargingCtrlr.SupportedEnergyTransferModes` [Q02 / Q01.FR.32 evidence](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 525).
- `NotifyEVChargingNeeds.req.chargingNeeds.requestedEnergyTransfer` is required and has enum values including `AC_BPT`, `AC_BPT_DER`, `AC_DER`, `DC_BPT`, `DC_ACDP`, `DC_ACDP_BPT`, and `WPT` [NotifyEVChargingNeeds.req.chargingNeeds.requestedEnergyTransfer](data/json/ocpp2.1Ed2/OCPP-2.1_part3_JSON_schemas/NotifyEVChargingNeedsRequest.json).
- `NotifyEVChargingNeeds.req.chargingNeeds.v2xChargingParameters` is optional and carries ISO 15118-20 V2X charging/discharging parameters; fields such as `evMinV2XEnergyRequest` and `evMaxV2XEnergyRequest` may be negative or positive according to the schema descriptions [NotifyEVChargingNeeds.req.chargingNeeds.v2xChargingParameters](data/json/ocpp2.1Ed2/OCPP-2.1_part3_JSON_schemas/NotifyEVChargingNeedsRequest.json).

## Implementation guidance

- Start with capability preflight. Cache `ISO15118Ctrlr.Enabled`, `V2XChargingCtrlr.Enabled`, and `V2XChargingCtrlr.SupportedEnergyTransferModes` before accepting V2X session decisions.
- Validate `NotifyEVChargingNeeds.req` before updating session state. Enforce required `chargingNeeds.requestedEnergyTransfer` and enum membership, then validate optional `v2xChargingParameters` fields.
- Normalize charging-needs input into a session model containing requested energy transfer, V2X energy bounds, target energy request, departure time when present, and selected control mode.
- Compare requested V2X transfer against `SupportedEnergyTransferModes`. A schema-valid Request can still be rejected if the station does not advertise the mode.
- For authorization flows, distinguish the CSMS decision to allow V2X from the Charging Station and EV negotiation. The backend should store the allowed-energy-transfer result and the later selected transfer reported by `NotifyEVChargingNeeds`.
- If CSMS will send a profile, generate or select a `SetChargingProfileRequest` only after authorization, schema validation, and Device Model capability checks have passed.
- Persist the validation result, normalized V2X intent, Device Model snapshot, profile decision, and evidence references.
- Use explicit failure categories: schema invalid, unsupported energy transfer mode, V2X disabled, ISO 15118 disabled, missing session context, or profile generation failure.

## Conformance-test focus

- Positive authorization test: `ISO15118Ctrlr.Enabled` and `V2XChargingCtrlr.Enabled` are true, allowed energy transfer is returned, `NotifyEVChargingNeeds.req` is schema-valid, and backend prepares a V2X-capable profile.
- Positive Device Model test: `SupportedEnergyTransferModes` contains the requested transfer, and backend accepts the V2X path.
- Negative schema test: omit `chargingNeeds.requestedEnergyTransfer` or use a value outside the schema enum; backend rejects before state update.
- Negative capability test: request `AC_BPT_DER` while `SupportedEnergyTransferModes` does not advertise it; backend rejects or constrains the decision.
- ChargingOnly transition test: when V2X is not yet allowed, backend supports the `ChargingOnly` start path and later V2X enabling flow from Section Q.
- Persistence test: audit records include authorization outcome, requested energy transfer, V2X parameters, Device Model capability snapshot, and citation metadata.

## Evidence gaps

- MCP evidence confirms the key Q01 flow, Device Model variables, and `NotifyEVChargingNeeds` schema fields, but this answer does not enumerate every V2X operation-mode rule.
- Future expert scoring should require exact requirement IDs for all LocalFrequency, LocalLoadBalancing, and CentralSetpoint constraints.
- This benchmark validates Codex-assisted answer quality from MCP evidence; it does not represent an automated OpenAI API provider inside `rag eval-answers`.
