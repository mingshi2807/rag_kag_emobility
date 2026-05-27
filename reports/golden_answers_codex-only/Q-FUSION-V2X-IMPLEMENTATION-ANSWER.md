## Purpose

- Provide Codex-only implementation guidance for OCPP 2.1 Ed2 V2X energy services without using a DeepSeek generation request.
- Treat V2X as a fusion implementation topic: Section Q behavior defines energy-service intent, the Device Model exposes `V2XChargingCtrlr` capability and configuration, and JSON schema validation controls message payload correctness.
- Help a senior backend developer implement capability discovery, charging-needs processing, schedule/profile decisions, validation, persistence, and conformance tests.
- Keep the backend source-aware so every V2X decision can be traced to specification, Device Model, or schema evidence.

## Normative behavior

- V2X energy services must be handled as OCPP 2.1 Ed2 protocol behavior, not only as generic bidirectional charging business logic [Section Q V2X energy services](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf).
- The backend must read V2X capability from the Device Model before enabling V2X behavior. `V2XChargingCtrlr` and variables such as `SupportedEnergyTransferModes` define which energy transfer modes are available for a charging station [V2XChargingCtrlr / SupportedEnergyTransferModes](data/csv).
- V2X message handling must validate JSON schema payloads. Requests such as `NotifyEVChargingNeeds` carry charging-needs data, including V2X charging parameters, that must be schema-valid before backend logic accepts it [NotifyEVChargingNeeds.req.chargingNeeds.v2xChargingParameters](data/json).
- A CSMS should separate capability gating from session negotiation. Device Model support allows the backend to consider V2X, while each Request and Response still requires schema and state validation.
- Energy-service decisions must preserve evidence that explains why the backend selected, rejected, or constrained a V2X charging mode.

## Implementation guidance

- Start with a capability cache keyed by charging station identity and connector/EVSE scope where applicable. Populate it from `V2XChargingCtrlr` Device Model variables, especially `SupportedEnergyTransferModes`.
- Validate all V2X-related Request payloads against the JSON schema before updating session state. This includes nested V2X charging parameters, power limits, schedules, and enumerations.
- When handling `NotifyEVChargingNeeds`, normalize the requested energy transfer mode, requested power/energy values, and timing constraints into a backend session model.
- Compare EV charging needs with station capability. Reject or downgrade unsupported energy transfer modes rather than assuming all bidirectional modes are equivalent.
- Generate downstream charging or V2X control decisions only after schema validation, capability gating, and session-state checks have all passed.
- Persist the raw message ID, validation result, normalized V2X intent, Device Model snapshot, and citations to the retrieved spec/schema/Device Model evidence.
- Expose implementation errors with clear categories: schema invalid, unsupported Device Model capability, inconsistent session state, and accepted protocol Response with limited operational effect.

## Conformance-test focus

- Positive test: station exposes `V2XChargingCtrlr` with `SupportedEnergyTransferModes`, receives a valid `NotifyEVChargingNeeds` Request, and the backend persists a V2X-capable session decision.
- Negative schema test: invalid or missing V2X charging parameters must fail JSON schema validation before state changes.
- Negative capability test: a valid V2X Request that uses an unsupported energy transfer mode must be rejected or constrained according to capability evidence.
- State-machine test: V2X charging needs must not be accepted for a session or connector state where the backend has no active context.
- Persistence test: stored V2X decisions must include Device Model variables, schema validation output, and source citations.
- Regression test: run `rag eval-quality --topic V2X --mode fusion --top-k 12` plus `rag eval-answers --from-answers-dir` for the Codex-only answer directory.

## Evidence gaps

- This Codex-only benchmark validates answer structure and expected domain coverage, but it does not yet compare factual precision against a human expert rubric.
- Field-level V2X scoring should later check exact schema paths, enum names, required fields, and Response semantics.
- The current baseline proves V2X fusion coverage at a high level; enterprise readiness still requires CI enforcement and expert-approved expected-answer rubrics.
