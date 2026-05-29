# OCPP Query Quality Evaluation: ocpp21-ed2-rqk-source-aware

- Cases: `12`
- Passed: `12/12`
- Score: `0.976`
- Fail-under: `0.800`
- Status: `PASS`

## Cases

### R-SPEC-DER-CONTROL - PASS

- Topic: `Section R DER control`
- Mode: `spec`
- Score: `0.933`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `0.333`
- Latency: `14367ms`
- Strategy: `{'vector': 7, 'keyword': 5}`
- Query: In OCPP 2.1 Ed2 Section R, what are the DER control objectives, requirements, and implementation responsibilities?
- Matched optional terms: `curve`

Evidence layer coverage:
- `spec` `spec_pdf` `R03 - Starting a V2X session with hybrid DER control in both EV and EVSE` `702aa98b-839d-53b0-a193-1609c5cb406f`

Top evidence:
- `spec` `spec_pdf` `R03 - Starting a V2X session with hybrid DER control in both EV and EVSE` `702aa98b-839d-53b0-a193-1609c5cb406f`
- `spec` `spec_pdf` `R05 - Charging station reporting a DER event` `14d279f3-7bf3-57df-8edb-2c1792577ef4`
- `spec` `spec_pdf` `R02 - Starting a V2X session with DER control in EV` `2d4d285c-2408-57f5-b21b-9c2a8e240375`
- `spec` `spec_pdf` `2.18. DER Control related` `b719b1bf-277d-5549-b455-818f73515901`
- `spec` `spec_pdf` `2.19. Battery Swapping related` `1889ca2d-c8fd-5373-a344-f183d35264d9`

### R-DM-DER-COMPONENTS - PASS

- Topic: `Section R DER control`
- Mode: `dm`
- Score: `0.933`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `0.333`
- Latency: `6324ms`
- Strategy: `{'vector': 7, 'keyword': 5}`
- Query: Which Device Model components and variables are relevant for OCPP 2.1 Ed2 DER control implementation?
- Matched optional terms: `required`

Evidence layer coverage:
- `device_model` `device_model_table` `SmartChargingCtrlr / SupportedAdditionalPurposes / no` `fb896b1e-48b3-5988-b965-7887dd1188b8`

Top evidence:
- `device_model` `device_model_table` `SmartChargingCtrlr / SupportedAdditionalPurposes / no` `fb896b1e-48b3-5988-b965-7887dd1188b8`
- `device_model` `device_model_table` `SmartChargingCtrlr / SupportedAdditionalPurposes` `849d1dc5-9392-5b1f-ba58-1cabfdc5b8f9`
- `device_model` `device_model_table` `DCDERCtrlr / Enabled / no` `022ab67c-d930-53a8-983c-816676b0019d`
- `device_model` `device_model_table` `DCDERCtrlr / ModesSupported` `6c5cca30-db74-5ad3-9060-2f84f4ed4062`
- `device_model` `device_model_table` `NetworkConfiguration / OcppVersion / yes` `f0b4bb42-04a9-55b1-98b4-3e354602ca91`

### R-SCHEMA-DER-MESSAGES - PASS

- Topic: `Section R DER control`
- Mode: `schema`
- Score: `1.000`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Latency: `11316ms`
- Strategy: `{'vector': 7, 'keyword': 5}`
- Query: Which OCPP 2.1 JSON schemas define DER control request and response payload constraints?
- Matched optional terms: `required, properties, enum`

Evidence layer coverage:
- `schema` `json_schema` `ReportDERControl.req` `691ce57a-b3a4-5594-92b0-15ca7faffd04`

Top evidence:
- `schema` `json_schema` `ReportDERControl.req` `691ce57a-b3a4-5594-92b0-15ca7faffd04`
- `schema` `json_schema` `SetNetworkProfile.req.connectionData.ocppVersion` `21422d9c-9c14-5514-9488-7cb943d13859`
- `schema` `json_schema` `DERChargingParametersType` `7ae12d68-6ab2-5e9f-bfdb-236b3ef394a9`
- `schema` `json_schema` `SetDERControl.req` `180331f3-1b62-51e5-ae91-59673b6ff03d`
- `schema` `json_schema` `NotifyDERStartStop.req.controlId` `f189cc57-15c1-50b7-ac2a-554d45ada8ad`

### R-FUSION-DER-IMPLEMENTATION - PASS

- Topic: `Section R DER control`
- Mode: `fusion`
- Score: `1.000`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Latency: `29373ms`
- Strategy: `{'vector': 5, 'keyword': 7}`
- Query: Build senior backend implementation guidance for OCPP 2.1 Ed2 DER control using Part 2 spec behavior, Device Model components and variables, and JSON schema validation.
- Matched optional terms: `Response, Variable, requirements, validation`

Evidence layer coverage:
- `spec` `spec_pdf` `2.18. DER Control related` `b719b1bf-277d-5549-b455-818f73515901`
- `schema` `json_schema` `ReportDERControl.req.tbc` `907e1c0c-ec7d-5605-9769-2dab64c0203c`
- `device_model` `device_model_table` `DCDERCtrlr / Enabled` `0b853dfe-3a91-5e4d-9d27-67aa28db6c87`

Top evidence:
- `spec` `spec_pdf` `2.18. DER Control related` `b719b1bf-277d-5549-b455-818f73515901`
- `spec` `spec_pdf` `2.15. ISO 15118 related` `38bd2b05-3eb6-53ea-96fe-7a8e1b99e832`
- `schema` `json_schema` `ReportDERControl.req.tbc` `907e1c0c-ec7d-5605-9769-2dab64c0203c`
- `spec` `spec_pdf` `Chapter 2. DER Control using OCPP and ISO 15118-20` `8e776275-8447-5707-abec-4851153b648d`
- `spec` `spec_pdf` `2.6. Local Authorization List Management related` `261d153a-e3d3-579e-8d05-75161a23e241`

### Q-SPEC-V2X-ENERGY - PASS

- Topic: `Section Q V2X energy services`
- Mode: `spec`
- Score: `1.000`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Latency: `14700ms`
- Strategy: `{'vector': 12}`
- Query: In OCPP 2.1 Ed2 Section Q, what V2X energy services behavior must a charging station backend implement?
- Matched optional terms: `bidirectional, EV, grid`

Evidence layer coverage:
- `spec` `spec_pdf` `Q03 - Central V2X control with charging schedule` `f8bc9158-0d33-5b39-8665-5d78d835fefe`

Top evidence:
- `spec` `spec_pdf` `Q03 - Central V2X control with charging schedule` `f8bc9158-0d33-5b39-8665-5d78d835fefe`
- `spec` `spec_pdf` `Q07 - Central V2X control for frequency support` `adb013e2-f02a-554f-a489-bc628d814c36`
- `spec` `spec_pdf` `Q05 - External V2X setpoint control with a charging profile from CSMS` `a97e6b3e-9c1c-524d-9be3-4396da773a4c`
- `spec` `spec_pdf` `Q01 - V2X Authorization` `a4ed9d09-3ad5-5911-9a4d-eb8e91d22524`
- `spec` `spec_pdf` `Chapter 3. Use Cases & Requirements` `98802d28-aa3d-598b-8dc4-a67b7f04238b`

### Q-DM-V2X-COMPONENTS - PASS

- Topic: `Section Q V2X energy services`
- Mode: `dm`
- Score: `0.933`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `0.333`
- Latency: `3679ms`
- Strategy: `{'vector': 11, 'keyword': 1}`
- Query: Which Device Model components and variables support V2X energy services in OCPP 2.1 Ed2?
- Matched optional terms: `required`

Evidence layer coverage:
- `device_model` `device_model_table` `V2XChargingCtrlr / SupportedEnergyTransferModes / yes` `481837d9-42c9-5bf1-ba6a-fc0ed4d62773`

Top evidence:
- `device_model` `device_model_table` `V2XChargingCtrlr / SupportedEnergyTransferModes / yes` `481837d9-42c9-5bf1-ba6a-fc0ed4d62773`
- `device_model` `device_model_table` `V2XChargingCtrlr / SupportedEnergyTransferModes` `9c10ac6d-8068-5304-9973-3e0aa30bc826`
- `device_model` `device_model_table` `V2XChargingCtrlr / TxUpdatedMeasurands / <OperationMode>` `991991b0-0c9e-5ebb-be68-86fef3772059`
- `device_model` `device_model_table` `V2XChargingCtrlr / SupportedOperationModes / yes` `82fa9621-a646-5d4d-a837-678ea58c456a`
- `device_model` `device_model_table` `ConnectedEV / ProtocolSupportedByEV / <Priority>` `d881d599-afb5-5c35-8b27-8bb803c5f4b2`

### Q-SCHEMA-V2X-PAYLOADS - PASS

- Topic: `Section Q V2X energy services`
- Mode: `schema`
- Score: `0.967`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `0.667`
- Latency: `6162ms`
- Strategy: `{'vector': 10, 'keyword': 2}`
- Query: Which OCPP 2.1 JSON schemas and payload fields are relevant to V2X energy services?
- Matched optional terms: `required, properties`

Evidence layer coverage:
- `schema` `json_schema` `V2XChargingParametersType` `321e023e-e46d-5b01-a0f1-231a16389b6e`

Top evidence:
- `schema` `json_schema` `V2XChargingParametersType` `321e023e-e46d-5b01-a0f1-231a16389b6e`
- `schema` `json_schema` `NotifyAllowedEnergyTransfer.req` `cfa21e11-2103-5c32-a8f6-48ae5d128077`
- `schema` `json_schema` `NotifyAllowedEnergyTransfer.conf` `79aa7468-9d3f-5579-ab30-cb42093c1b03`
- `schema` `json_schema` `V2XFreqWattPointType` `566c4c19-b4b8-5399-9251-70b9894f3bf6`
- `schema` `json_schema` `V2XFreqWattPointType` `f7bf6185-bd43-589e-8808-243a2753484f`

### Q-FUSION-V2X-IMPLEMENTATION - PASS

- Topic: `Section Q V2X energy services`
- Mode: `fusion`
- Score: `0.975`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `0.750`
- Latency: `29233ms`
- Strategy: `{'keyword': 8, 'vector': 4}`
- Query: Build implementation guidance for OCPP 2.1 Ed2 V2X energy services using spec rules, Device Model configuration, and JSON schemas.
- Matched optional terms: `services, Variable, Request`

Evidence layer coverage:
- `spec` `spec_pdf` `Q09 - Local V2X control for load balancing` `1c2f13fb-d32f-5aee-bcad-dca8bc7cd59c`
- `schema` `json_schema` `NotifyEVChargingNeeds.req.chargingNeeds.v2xChargingParameters.evMaxV2XEnergyRequest` `283cf5d1-5bc3-5abe-adff-fb0a24a73a1d`
- `device_model` `device_model_table` `V2XChargingCtrlr / SupportedEnergyTransferModes / yes` `481837d9-42c9-5bf1-ba6a-fc0ed4d62773`

Top evidence:
- `spec` `spec_pdf` `Q09 - Local V2X control for load balancing` `1c2f13fb-d32f-5aee-bcad-dca8bc7cd59c`
- `spec` `spec_pdf` `2.9. Reservation related` `499251d0-62cd-59ff-8f83-cc50e1c2edde`
- `spec` `spec_pdf` `Q08 - Local V2X control for frequency support` `d967b092-88b9-590e-b038-084c57a13a46`
- `spec` `spec_pdf` `R02 - Starting a V2X session with DER control in EV` `2d4d285c-2408-57f5-b21b-9c2a8e240375`
- `spec` `spec_pdf` `2.14. Charging Infrastructure related` `d772731c-958e-5d0c-bee4-cd0868c075b4`

### K-SPEC-SMART-CHARGING - PASS

- Topic: `Section K smart charging`
- Mode: `spec`
- Score: `1.000`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Latency: `14563ms`
- Strategy: `{'vector': 11, 'keyword': 1}`
- Query: In OCPP 2.1 Ed2 Section K, what are the smart charging purposes, profiles, limits, and implementation responsibilities?
- Matched optional terms: `ChargingProfile, schedule, transaction`

Evidence layer coverage:
- `spec` `spec_pdf` `K27 - Smart Charging with EMS and LocalGeneration` `6675c8fe-b0e4-5881-8db3-171acfa7c3eb`

Top evidence:
- `spec` `spec_pdf` `K27 - Smart Charging with EMS and LocalGeneration` `6675c8fe-b0e4-5881-8db3-171acfa7c3eb`
- `spec` `spec_pdf` `K23 - Smart Charging with EMS connected to Charging Stations` `d53eb2e1-f802-588f-96eb-206e03349c82`
- `spec` `spec_pdf` `K25 - Smart Charging with EMS acting as a Local Controller` `b23212c1-1875-5fff-a035-00f887a1d7c4`
- `spec` `spec_pdf` `Chapter 3. Charging profiles` `f2e7913e-b74e-5817-9c97-86f0299aeceb`
- `spec` `spec_pdf` `3.2. Charging profile purposes` `bf176edd-fd38-5720-b916-a3540b1d947c`

### K-DM-SMART-CHARGING-COMPONENTS - PASS

- Topic: `Section K smart charging`
- Mode: `dm`
- Score: `1.000`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Latency: `4794ms`
- Strategy: `{'vector': 6, 'keyword': 6}`
- Query: Which Device Model components and variables configure smart charging in OCPP 2.1 Ed2?
- Matched optional terms: `ChargingStation, EVSE, required`

Evidence layer coverage:
- `device_model` `device_model_table` `SmartChargingCtrlr / SupportedAdditionalPurposes / no` `fb896b1e-48b3-5988-b965-7887dd1188b8`

Top evidence:
- `device_model` `device_model_table` `SmartChargingCtrlr / SupportedAdditionalPurposes / no` `fb896b1e-48b3-5988-b965-7887dd1188b8`
- `device_model` `device_model_table` `SmartChargingCtrlr / SupportedAdditionalPurposes` `849d1dc5-9392-5b1f-ba58-1cabfdc5b8f9`
- `device_model` `device_model_table` `SmartChargingCtrlr / Available / no` `363b4063-b49a-5529-9f6a-8225ddd14e87`
- `device_model` `device_model_table` `SmartChargingCtrlr / ExternalControlSignalsEnabled / no` `bc71383d-d1a2-5a84-b320-04b71b451ac1`
- `device_model` `device_model_table` `SmartChargingCtrlr / LimitChangeSignificance / yes` `f6eb741e-652d-5d29-8d3f-2558aa34d59b`

### K-SCHEMA-SMART-CHARGING - PASS

- Topic: `Section K smart charging`
- Mode: `schema`
- Score: `1.000`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Latency: `4821ms`
- Strategy: `{'vector': 5, 'keyword': 7}`
- Query: Which JSON schemas define OCPP 2.1 smart charging messages such as SetChargingProfile and charging schedule payloads?
- Matched optional terms: `chargingSchedule, required, properties`

Evidence layer coverage:
- `schema` `json_schema` `SetChargingProfile.req` `8d107228-8ef0-5e07-8c31-37d7a2314a56`

Top evidence:
- `schema` `json_schema` `SetChargingProfile.req` `8d107228-8ef0-5e07-8c31-37d7a2314a56`
- `schema` `json_schema` `SetChargingProfile.conf` `6390bcca-58e9-5772-aa6d-949ea360e2ea`
- `schema` `json_schema` `SetChargingProfile.req.chargingProfile.chargingProfilePurpose` `ed86e40b-edb5-5a48-b405-3fb352df3ed1`
- `schema` `json_schema` `SetChargingProfile.req.chargingProfile.customData` `004e74f0-47e8-5262-a0b4-d0ca53cb508b`
- `schema` `json_schema` `SetChargingProfile.req.chargingProfile.chargingProfileKind` `8061415a-d0be-51b4-a8ad-de1d4e97208c`

### K-FUSION-SMART-CHARGING-IMPLEMENTATION - PASS

- Topic: `Section K smart charging`
- Mode: `fusion`
- Score: `0.975`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `0.750`
- Latency: `29371ms`
- Strategy: `{'vector': 5, 'keyword': 7}`
- Query: Build senior backend implementation guidance for OCPP 2.1 Ed2 smart charging using Section K spec behavior, Device Model variables, and JSON schema validation.
- Matched optional terms: `Variable, SetChargingProfile, limit`

Evidence layer coverage:
- `spec` `spec_pdf` `2.10. Smart Charging related` `e262bea2-c84b-52d0-a07b-1f6c4c91e5f8`
- `schema` `json_schema` `NotifyEVChargingSchedule.req.chargingSchedule.minChargingRate` `85119313-b24b-5718-be14-3e802647a1cb`
- `device_model` `device_model_table` `SmartChargingCtrlr / ACPhaseSwitchingSupported / no` `13b4c8ab-0ef3-5549-b348-152048681dba`

Top evidence:
- `spec` `spec_pdf` `2.10. Smart Charging related` `e262bea2-c84b-52d0-a07b-1f6c4c91e5f8`
- `schema` `json_schema` `NotifyEVChargingSchedule.req.chargingSchedule.minChargingRate` `85119313-b24b-5718-be14-3e802647a1cb`
- `spec` `spec_pdf` `K27 - Smart Charging with EMS and LocalGeneration` `6675c8fe-b0e4-5881-8db3-171acfa7c3eb`
- `spec` `spec_pdf` `2.12. Diagnostics related` `4e49c01c-eff5-5672-8530-155b8c8cdf0d`
- `device_model` `device_model_table` `SmartChargingCtrlr / ACPhaseSwitchingSupported / no` `13b4c8ab-0ef3-5549-b348-152048681dba`
