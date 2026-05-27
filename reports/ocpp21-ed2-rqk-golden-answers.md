# OCPP Golden Answer Evaluation: ocpp21-ed2-rqk-golden-answers

- Cases: `3`
- Passed: `3/3`
- Score: `1.000`
- Fail-under: `0.800`
- Status: `PASS`

## Cases

### R-FUSION-DER-IMPLEMENTATION-ANSWER - PASS

- Topic: `Section R DER control`
- Score: `1.000`
- Heading score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Markdown score: `1.000`
- Grounding score: `1.000`
- Answer chars: `7761`
- Query: Build senior backend implementation guidance for OCPP 2.1 Ed2 DER control using Part 2 spec behavior, Device Model components and variables, and JSON schema validation.
- Answer: `reports/golden_answers/R-FUSION-DER-IMPLEMENTATION-ANSWER.md`
- Matched optional terms: `DCDERCtrlr, SetDERControl, ReportDERControl, validation`

Answer excerpt:

## Purpose
- Enable OCPP 2.1 charging stations to execute Distributed Energy Resource (DER) control functions for bidirectional power transfer, aligning with grid code requirements.
- Define the protocol boundary where the CSMS acts as an aggregator between the utility (using IEC 61850, IEEE 2030.5, or other protocols) and the charging station, forwarding appropriate OCPP DER messages.
- Provide Device Model components (`DCDERCtrlr`, `ACDERCtrlr`) for capabilty advertisement and runtime variable reporting, and request messages (`SetDERControlRequest`, `ReportDERControlRequest`) for configuration and status.
- Support both DC (inverter in EVSE) and AC (inverter in EV or emulated by EVSE) scenarios, with hybrid control handled via `ACDERCtrlr.ModesSupported`.

## Normative behavior
- A DC bidirectional charging station **SHALL** expose the DER capabilities (“nameplate”) of its DC inverter
...

### Q-FUSION-V2X-IMPLEMENTATION-ANSWER - PASS

- Topic: `Section Q V2X energy services`
- Score: `1.000`
- Heading score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Markdown score: `1.000`
- Grounding score: `1.000`
- Answer chars: `8710`
- Query: Build implementation guidance for OCPP 2.1 Ed2 V2X energy services using spec rules, Device Model configuration, and JSON schemas.
- Answer: `reports/golden_answers/Q-FUSION-V2X-IMPLEMENTATION-ANSWER.md`
- Matched optional terms: `V2XChargingCtrlr, NotifyEVChargingNeeds, SupportedEnergyTransferModes, validation`

Answer excerpt:

## Purpose
- Define V2X energy services in OCPP 2.1 Ed2 for bidirectional power transfer, enabling EV‑to‑grid, local load‑balancing, and frequency support.
- Establish implementation boundaries for the CSMS: which messages, Device Model variables, and schedule fields must be processed to activate and control V2X sessions.
- Clarify required pre‑conditions (e.g., capability reporting via V2XChargingCtrlr) and normative constraints for each OperationMode.

## Normative behavior
- The Charging Station must report its V2X capabilities through the Device Model component **V2XChargingCtrlr**:  
  - **V2XChargingCtrlr.Enabled** – set by CSMS to activate/deactivate V2X (required when V2X is supported) [2.17.1](data/pdf/ocpp2.1Ed2/OCPP-2.1_edition2_part2_specification.pdf, page 801).  
  - **V2XChargingCtrlr.SupportedEnergyTransferModes** – a MemberList of `EnergyTransferModeEnumType` values (req
...

### K-FUSION-SMART-CHARGING-IMPLEMENTATION-ANSWER - PASS

- Topic: `Section K smart charging`
- Score: `1.000`
- Heading score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Markdown score: `1.000`
- Grounding score: `1.000`
- Answer chars: `11629`
- Query: Build senior backend implementation guidance for OCPP 2.1 Ed2 smart charging using Section K spec behavior, Device Model variables, and JSON schema validation.
- Answer: `reports/golden_answers/K-FUSION-SMART-CHARGING-IMPLEMENTATION-ANSWER.md`
- Matched optional terms: `SmartChargingCtrlr, charging schedule, limit, validation`

Answer excerpt:

## Purpose

- Define the contract for building an OCPP 2.1 Ed2 CSMS‑side smart‑charging backend that respects the Device Model, Section K rules, and JSON schema constraints.
- Focus on validating and orchestrating `ChargingProfile` creation, merging external limits and local generation, and correctly processing inbound limit notifications and composite schedule requests.
- Scope includes handling multiple‑actor limits (`ChargingStationMaxProfile`, `TxDefaultProfile`, `ChargingStationExternalConstraints`, `LocalGeneration`, `PriorityCharging`) as defined in Section K and SC rules.
- Excludes onboard EVSE‑internal load‑balancing decisions; backend only interprets reported capabilities and manages persistence/lifecycle of profiles it owns.

## Normative behavior

### Device Model capability gating
CSMS must read and honour the following `SmartChargingCtrlr` variables before sending any `Set
...
