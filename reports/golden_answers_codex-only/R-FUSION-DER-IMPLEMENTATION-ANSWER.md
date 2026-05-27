## Purpose

- Provide Codex-authored implementation guidance for OCPP 2.1 Ed2 Distributed Energy Resource (DER) control without calling DeepSeek generation.
- Treat DER control as a fusion feature: Part 2 behavior defines the protocol intent, the Device Model advertises capability and controllable variables, and JSON schema validation constrains each Request and Response payload.
- Guide a CSMS backend that must decide whether a charging station supports DER control, validate inbound and outbound message payloads, persist control state, and expose source-aware diagnostics.
- Keep the implementation bounded to evidence available in the OCPP 2.1 Ed2 corpus; unsupported control modes or missing schema fields must be rejected or reported rather than inferred.

## Normative behavior

- DER behavior belongs to the OCPP 2.1 Ed2 DER control functional area and must be implemented from the Section R / DER control evidence, not from generic smart-charging assumptions [2.18. DER Control related](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf).
- The backend must combine protocol behavior with Device Model evidence. DER capability is represented through DER-oriented components such as `DCDERCtrlr` and related variables; those variables are the source for deciding which controls are available before sending a control Request [DCDERCtrlr Device Model](data/csv).
- JSON schemas are mandatory validation boundaries. A `SetDERControl` or `ReportDERControl` implementation must validate the Request and Response shape before applying state transitions, storing evidence, or emitting conformance results [SetDERControl JSON schema](data/json).
- A CSMS should treat a Response as protocol evidence, not as proof that every downstream inverter action succeeded unless the retrieved specification and schema evidence explicitly provide that semantic.
- If a charging station does not advertise the required DER capability in the Device Model, the backend must avoid sending unsupported control commands and should produce a source-aware validation error.

## Implementation guidance

- Build a capability resolver that reads Device Model component/variable rows for DER support first. Normalize component names such as `DCDERCtrlr` and `ACDERCtrlr`, then persist the supported modes and mutable variables with source metadata.
- Add a schema-first message pipeline for DER messages. Validate each Request body, enum value, required property, nested object, and Response status before business logic observes the payload.
- Model DER control state separately from raw OCPP messages. Store the requested control target, the accepted or rejected Response, the evidence-layer references, and the station capability snapshot used at decision time.
- Sequence outbound control as: retrieve station capability, validate Device Model preconditions, build the `SetDERControl` Request, validate against JSON schema, send message, validate the Response, then persist state and audit evidence.
- Sequence inbound reporting as: receive `ReportDERControl` or related DER status evidence, validate schema, map reported values to the Device Model variable identity, store time-series/status data, and flag values outside advertised capability.
- Keep schema validation errors distinct from protocol rejection. A malformed JSON payload is an implementation validation failure; a well-formed but unsupported DER command is a protocol/capability rejection.
- Add source-aware logs that reference chunk IDs, section titles, schema names, and Device Model component names, but do not log full private source chunks or complete generated answers.

## Conformance-test focus

- Positive test: station advertises DER capability through Device Model variables, CSMS sends a valid `SetDERControl` Request, receives a valid Response, and persists the resulting DER state with citations.
- Negative schema test: omit a required schema field or use an invalid enum in the DER Request; the backend must reject before sending or applying the control.
- Negative capability test: no `DCDERCtrlr` or required variable exists; the backend must not send the control Request and must report a source-aware unsupported-capability result.
- Response handling test: validate accepted, rejected, and unknown status values against the schema and ensure only schema-valid responses affect state.
- Reporting test: ingest a `ReportDERControl` style payload, validate it, link the reported values back to Device Model variables, and preserve evidence references.
- Regression test: rerun `rag eval-quality --topic DER --mode fusion --top-k 12` and this golden-answer score to prove retrieval coverage and generated guidance quality remain aligned.

## Evidence gaps

- The current Codex-only benchmark is manually authored inside Codex and scored offline; it does not prove that an automated Codex model endpoint can generate the same answer through the application runtime.
- Detailed field-level DER rules should be expanded with exact schema paths and conformance assertions once the project adds finer-grained schema citation checks.
- No important high-level fusion gap was found for DER in the current R/Q/K baseline, but CI still needs to enforce both retrieval and answer gates.
