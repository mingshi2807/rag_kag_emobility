## Purpose

- Provide Codex-only senior backend guidance for OCPP 2.1 Ed2 smart charging without invoking DeepSeek.
- Treat smart charging as a fusion topic: Section K defines protocol behavior, the Device Model describes `SmartChargingCtrlr` capability and variables, and JSON schemas define `ChargingProfile`, schedule, limit, Request, and Response constraints.
- Guide implementation of `SetChargingProfile`, schedule validation, profile persistence, capability gating, and conformance-test evidence.
- Keep the output usable as a benchmark answer for enterprise RAG/KAG quality, not as a replacement for the underlying OCPP specification.

## Normative behavior

- Smart charging implementation must follow Section K smart charging behavior and related profile/limit rules [2.10. Smart Charging related](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf).
- The backend must use the Device Model before applying smart charging. `SmartChargingCtrlr` variables describe supported behavior and should gate whether a CSMS may send a given `SetChargingProfile` Request [SmartChargingCtrlr / ACPhaseSwitchingSupported](data/csv).
- JSON schema validation is required for smart-charging payloads. `SetChargingProfile`, charging schedule structures, limits, periods, stack levels, and enum values must be validated before persistence or dispatch [SetChargingProfile JSON schema](data/json).
- A `ChargingProfile` should be treated as a versioned operational instruction. The backend must preserve ownership, purpose, transaction/EVSE scope, validity interval, stack level, schedule periods, and validation status.
- Response handling must distinguish schema-valid rejection, unsupported capability, profile conflict, and accepted profile storage.

## Implementation guidance

- Build a smart-charging capability resolver around `SmartChargingCtrlr`. Cache supported features, such as phase switching or schedule-related support, with source metadata and refresh it when Device Model reports change.
- Implement schema-first validation for `SetChargingProfile` Request payloads. Validate required fields, nested `ChargingSchedule` content, charging-rate unit, schedule periods, limit values, and allowed enum values before business logic runs.
- Normalize accepted profiles into a persistence model with profile ID, purpose, kind, recurrency, stack level, EVSE/connector scope, transaction scope, validity window, and schedule periods.
- Add conflict detection before dispatch. Compare the new `ChargingProfile` against existing profiles and station limits so that backend decisions are deterministic.
- Treat limits as layered evidence. Station max profiles, transaction default profiles, external constraints, local generation, and priority charging must not be collapsed into one untraceable number.
- Send `SetChargingProfile` only after Device Model capability checks and schema validation pass. On Response, persist status and cite the source evidence used to decide acceptance or rejection.
- Add query/debug views that can show why a limit was selected: schema-valid input, Device Model capability, active profiles, and Section K rule evidence.

## Conformance-test focus

- Positive test: valid `SetChargingProfile` Request with supported `SmartChargingCtrlr` capability is validated, sent, accepted, and persisted with schedule and limit details.
- Negative schema test: missing required `ChargingProfile` fields, invalid charging schedule periods, or invalid limit units must fail before dispatch.
- Negative capability test: request a behavior not supported by Device Model variables; the backend must reject or avoid sending the Request.
- Conflict test: overlapping profiles with stack levels or incompatible purposes must produce deterministic precedence or rejection behavior.
- Response test: accepted, rejected, and unsupported responses must update profile state differently and preserve citations.
- Regression test: run `rag eval-quality --topic smart --mode fusion --top-k 12` and the Codex-only golden-answer scorer before merging smart-charging retrieval or generation changes.

## Evidence gaps

- This answer is authored by Codex in the repository session and then scored offline; it benchmarks Codex answer quality separately from DeepSeek runtime generation.
- Future scoring should include exact schema-path assertions for `ChargingProfile`, `ChargingSchedule`, limits, and response status fields.
- Human expert review is still needed for final conformance wording before this becomes an enterprise granted knowledge artifact.
