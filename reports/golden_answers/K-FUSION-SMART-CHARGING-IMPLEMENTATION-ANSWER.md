## Purpose

- Define the contract for building an OCPP 2.1 Ed2 CSMS‑side smart‑charging backend that respects the Device Model, Section K rules, and JSON schema constraints.
- Focus on validating and orchestrating `ChargingProfile` creation, merging external limits and local generation, and correctly processing inbound limit notifications and composite schedule requests.
- Scope includes handling multiple‑actor limits (`ChargingStationMaxProfile`, `TxDefaultProfile`, `ChargingStationExternalConstraints`, `LocalGeneration`, `PriorityCharging`) as defined in Section K and SC rules.
- Excludes onboard EVSE‑internal load‑balancing decisions; backend only interprets reported capabilities and manages persistence/lifecycle of profiles it owns.

## Normative behavior

### Device Model capability gating
CSMS must read and honour the following `SmartChargingCtrlr` variables before sending any `SetChargingProfileRequest`:

- [SmartChargingEnabled](OCPP-2.1_edition2_part2_specification.pdf, page 769) – if `false`, smart charging is disabled; no charging profiles should be set.
- [ChargingProfileMaxStackLevel](OCPP-2.1_edition2_part2_specification.pdf, page 757) – the maximum acceptable `stackLevel`. The number of usable stack levels per purpose per EVSE = `ProfileStackLevel + 1` (since lowest is 0).
- [ChargingScheduleChargingRateUnit](OCPP-2.1_edition2_part2_specification.pdf, page 757) – the supported rate units (A, W). Any `chargingRateUnit` in a schedule must be a member of this list.
- [PeriodsPerSchedule](OCPP-2.1_edition2_part2_specification.pdf, page 757) – maximum number of periods in a single schedule.
- [SupportedAdditionalPurposes](SmartChargingCtrlr / SupportedAdditionalPurposes, CSV) – if absent or empty, purposes `PriorityCharging` and `LocalGeneration` are not supported.
- [ExternalConstraintsProfileDisallowed](OCPP-2.1_edition2_part2_specification.pdf, page 758) – when `true`, the CSMS must not create `ChargingStationExternalConstraints` profiles.
- [MaxExternalConstraintsId](OCPP-2.1_edition2_part2_specification.pdf, page 760) – the highest profile id the station itself may use for external constraints; CSMS‑created constraints must use higher ids.
- Feature‑support variables with instance‑based `SupportsFeature`:
  - `DynamicProfiles` – if absent or `false`, profiles of kind `Dynamic` are not allowed ([2.10.18](OCPP-2.1_edition2_part2_specification.pdf, page 761)).
  - `MaxOfflineDuration` – controls support for `maxOfflineDuration` / `invalidAfterOfflineDuration` fields ([2.10.19](OCPP-2.1_edition2_part2_specification.pdf, page 761)).
  - `UseLocalTime` – if absent or `false`, `useLocalTime` in schedules is unsupported ([2.10.20](OCPP-2.1_edition2_part2_specification.pdf, page 762)).
  - `RandomizedDelay` – similarly for `randomizedDelay` ([2.10.21](OCPP-2.1_edition2_part2_specification.pdf, page 762)).
- [ChargingProfilePersistence](OCPP-2.1_edition2_part2_specification.pdf, page 759) – determines if `TxProfile`, `LocalGeneration`, and `ChargingStationExternalConstraints` profiles survive reboots. `ChargingStationMaxProfile`, `TxDefaultProfile` and `PriorityCharging` are always persistent.

### Limit merging and external signals (Section K)
- The Charging Station internally enforces **SC.01** [(Smart Charging Signals, page 339)](OCPP-2.1_edition2_part2_specification.pdf, page 339): at every point, the charging limit (and setpoint) is the **minimum** of the highest‑stack profiles from `ChargingStationMaxProfile`, `ChargingStationExternalConstraints`, and `TxDefaultProfile` (or `TxProfile`/`PriorityCharging`). If a `LocalGeneration` profile is active, its limit is **added** on top of that minimum.
- When an external limit/schedule representing local generation arrives, the station treats it as a `LocalGeneration` charging profile ([K27.FR.01](OCPP-2.1_edition2_part2_specification.pdf, page 386)).
- The station SHALL report a changed charging limit to the CSMS whenever the change exceeds `LimitChangeSignificance` % (SC.03, same page). For external control signals, this report is a `NotifyChargingLimitRequest`; for local load balancing, a `TransactionEventRequest` (SC.02). For EV‑initiated limits (ISO 15118), a `NotifyEVChargingScheduleRequest` is used.
- [NotifyChargingLimitWithSchedules](OCPP-2.1_edition2_part2_specification.pdf, page 758) – when `true`, the `NotifyChargingLimitRequest` must include the full schedule(s) responsible for the limit change.
- If both external constraints with `ExternalSetpoint` and a TX profile with a setpoint are active, the station uses the priority defined by [SetpointPriority](OCPP-2.1_edition2_part2_specification.pdf, page 760); default precedence is external constraints.
- [K27.FR.03](OCPP-2.1_edition2_part2_specification.pdf, page 386) – for limits caused by `LocalGeneration`, `NotifyChargingLimitRequest` must carry `chargingLimitSource = EMS` (or `Other`) and `isLocalGeneration = true`. If the station also owns `ChargingStationExternalConstraints` profiles, those must be sent in a separate `NotifyChargingLimitRequest` with `isLocalGeneration = false` (K27.FR.05).

### `GetCompositeSchedule` semantics
- [SC.04](OCPP-2.1_edition2_part2_specification.pdf, page 339) – the response must report the expected charging schedule: the **lowest** limit and setpoint (when not discharging) after considering all merged sources, and if the EV has indicated a lower consumption via `NotifyEVChargingScheduleRequest`, that lower limit must be reflected.

## Implementation guidance

### Profiling validation checklist
1. **StackLevel** ≤ `SmartChargingCtrlr.ProfileStackLevel`.
2. **chargingRateUnit** ∈ `RateUnit` list.
3. **chargingSchedulePeriod** count ≤ `PeriodsPerSchedule`.
4. For purpose `PriorityCharging` or `LocalGeneration`: verify `SupportedAdditionalPurposes` includes the purpose.
5. For `chargingProfileKind = Dynamic`: `SupportsFeature.DynamicProfiles` must be `true`.
6. For `useLocalTime = true`: `SupportsFeature.UseLocalTime` must be `true`.
7. For any `randomizedDelay`: `SupportsFeature.RandomizedDelay` must be `true`.
8. For `maxOfflineDuration` / `invalidAfterOfflineDuration`: `SupportsFeature.MaxOfflineDuration` must be `true`.
9. `ChargingStationExternalConstraints` profiles: if `ExternalConstraintsProfileDisallowed = true`, reject; if `MaxExternalConstraintsId` is present, ensure `chargingProfileId` > that value.
10. If `ACPhaseSwitchingSupported` is required for schedules that select phases (e.g., `PhaseToUse`), check that it is `true` [(device model CSV)](SmartChargingCtrlr / ACPhaseSwitchingSupported / no).
11. Similarly, when the station supports switching from 3 to 1 phases during transaction, `Phases3to1` must be respected.
12. `operationMode` must be valid for the given `chargingProfilePurpose` – see [Table 95](OCPP-2.1_edition2_part2_specification.pdf, page 333).

### Handling limit notifications
- On receiving a `NotifyChargingLimitRequest`, store the reported limit/schedule. If `NotifyChargingLimitWithSchedules` is `false`, only the aggregated limit will be present; do not expect schedules.
- When processing a `NotifyEVChargingScheduleRequest`, note that the EV’s `minChargingRate` (optional, per [schema](NotifyEVChargingScheduleRequest.json)) may constrain the allowed minimum charging rate. This must be considered when later computing composite schedules.
- Because SC.03 allows the station to skip reports for changes below `LimitChangeSignificance`, the CSMS must tolerate missing updates for small fluctuations.

### Persistence and reboot
- Profiles with purpose `TxDefaultProfile`, `ChargingStationMaxProfile`, and `PriorityCharging` survive reboots unconditionally.
- For `TxProfile`, `LocalGeneration`, `ChargingStationExternalConstraints`, check the corresponding instance of `ChargingProfilePersistence`. If `false`, the CSMS must re‑send those profiles after a station reboot or when informed of their loss.
- After a reboot, the station will report its current `ChargingProfileEntries`. Cross‑check and reconcile state.

### Integration sequencing
1. CSMS retrieves all `SmartChargingCtrlr` variables and confirms `Enabled` is `true`.
2. Read capability variables (`SupportedAdditionalPurposes`, `SupportsDynamicProfiles`, etc.).
3. If needed, set `ExternalConstraintsProfileDisallowed` according to site policy.
4. Send initial `TxDefaultProfile` and optionally `ChargingStationMaxProfile`.
5. On receiving external limits (e.g., from an EMS), push corresponding `ChargingStationExternalConstraints` or `LocalGeneration` profiles, respecting the id range if `MaxExternalConstraintsId` is defined.
6. Monitor `NotifyChargingLimitRequest` and update internal state for reconciliation.

### Error handling
- If `SetChargingProfileResponse` indicates rejection (e.g., `Rejected`, `NotSupported`), log the reason and avoid retrying with incompatible parameters.
- When the station reports `NotifyChargingLimitRequest` with `isLocalGeneration = true`, ensure that the next `GetCompositeSchedule` includes the additive capacity.
- If a profile is sent with an unsupported operation mode, the station will reject; the backend must map correctly using valid combinations from Table 95.

## Conformance-test focus

### Positive tests
- Send a `SetChargingProfileRequest` with `TxDefaultProfile`, `stackLevel` ≤ `ProfileStackLevel`, `chargingRateUnit` = `W` (when supported), periods ≤ max, and observe acceptance.
- Provide a `ChargingStationExternalConstraints` profile when `ExternalConstraintsProfileDisallowed = false` and id > `MaxExternalConstraintsId`, then verify the station reports the new limit in `NotifyChargingLimitRequest`.
- Set `NotifyChargingLimitWithSchedules = true` and confirm that subsequent `NotifyChargingLimitRequest` messages carry the full schedule.
- Trigger a limit change larger than `LimitChangeSignificance` and ensure the station sends a notification; then make a change less than the threshold and expect no notification.
- After restart, verify that profiles marked as persistent survive and non‑persistent are removed.

### Negative tests
- Send a profile with `stackLevel > ProfileStackLevel` → expect rejection.
- Send a profile with `chargingProfileKind = Dynamic` when `SupportsDynamicProfiles = false` → rejection.
- Send a `PriorityCharging` profile when `SupportedAdditionalPurposes` does not contain `PriorityCharging` → rejection.
- Attempt to create an `ExternalConstraints` profile when `ExternalConstraintsProfileDisallowed = true` → rejection.
- Send a schedule with a rate unit not in `RateUnit` (`A` when only `W` supported) → rejection.
- Provide `useLocalTime = true` when `SupportsFeature.UseLocalTime` is `false` → rejection.
- Attempt to include `maxOfflineDuration` when `SupportsFeature.MaxOfflineDuration` is absent/false → rejection.

## Evidence gaps

- The full schema for `SetChargingProfileRequest` is not supplied in the retrieved evidence; only the `NotifyEVChargingScheduleRequest` schema appears. Validation rules for profile fields are therefore inferred from the specification text.
- The Device Model variable `SupportsLimitAtSoC` (2.10.22) is only mentioned by name and not described in the provided context; its exact behaviour and constraints could not be verified.
- Details about the `NotifyChargingLimitRequest` message structure (e.g., presence of `chargingSchedule` field) are not in the evidence beyond the use‑case description.
- The complete CSV for all `SmartChargingCtrlr` variables was not included; some optional variables like `ChargingProfileUpdateRateLimit` (deprecated) are noted but cannot be cross‑referenced against a full Device Model table.
