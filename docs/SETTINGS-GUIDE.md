# GivTCP Settings & Control Guide

This guide covers the settings you can change through GivTCP, from Home Assistant, over MQTT or over REST. For the full list of values GivTCP publishes, see [DATAPOINTS.md](DATAPOINTS.md).

## GivTCP Control (Inverters)
GivTCP provides a wide range of inverter control settings. When using HA an MQTT device is automatically created for each inverter:

<img src="images/settings-1.png" width="400"> <img src="images/settings-2.png" width="400">

| Control Function | Description | GivEnergy Cloud Equivalent |
| ------------- | ------------- | ------------- |
| Active Power Rate | Sets the maximum active power output as a percentage. 100% = inverter rating | Inverter Max Output Active Power Percent |
| Battery Calibration | Starts or stops a battery calibration. One of "Off", "Start" or "Charge Only". Progress is shown in Battery Calibration Status | — |
| Battery Charge Rate | Sets the battery charge power in Watts | Battery Charge Power |
| Battery Charge Rate AC | Sets the inverter AC charge power as a percentage. 100% = inverter rating | Inverter Charge Power Percentage |
| Battery Discharge Rate | Sets the battery discharge power in Watts | Battery Discharge Power |
| Battery Discharge Rate AC | Sets the inverter AC discharge power as a percentage. 100% = inverter rating | Inverter Discharge Power Percentage |
| Battery Pause Mode | Pauses the battery during the pause timeslot. One of "Disabled", "PauseCharge", "PauseDischarge" or "PauseBoth" | Pause Battery |
| Battery Pause Start/End Time Slot | Sets the time window in which Battery Pause Mode applies | — |
| Battery Power Cutoff | Sets the SOC, as a percentage, at which the battery stops discharging altogether | Battery Cutoff % Limit |
| Battery Power Reserve | Sets the minimum SOC the battery will discharge to in normal operation, as a percentage | Battery Reserve % Limit |
| Charge Start/End Time Slot (1-10) | Sets the start and end time of each charge slot. On HA 2026.5 or later, each slot also has a time picker entity (e.g. "Charge start slot 1") that does the same job | — |
| Charge Target SOC (1-10) | Sets the target SOC for each charge slot, as a percentage. Available on inverters that support a target per slot | AC Charge 1 Upper SOC % Limit |
| Discharge Start/End Time Slot (1-10) | Sets the start and end time of each discharge slot | — |
| Discharge Target SOC (1-10) | Sets the SOC to stop discharging at for each discharge slot, as a percentage. Minimum = Battery Power Reserve | AC Discharge 1 Lower SOC % Limit |
| Eco Mode | Turns Eco mode on or off | Enable Eco Mode |
| Enable Charge Schedule | Turns the charge schedule on or off. When off, the battery will not charge from the grid during the charge slots | — |
| Enable Charge Target | When on, charging stops at Target SOC. When off, the battery charges to 100% during charge slots | — |
| Enable Discharge | Allows or prevents the battery from discharging | — |
| Enable Discharge Schedule | Turns the discharge schedule on or off. When off, the battery ignores the discharge slots and discharges to meet demand | — |
| Force Charge | Charges the battery from the grid now for the chosen number of minutes. Shows "Normal" when idle and "Running" while active; choose "Cancel" to stop | — |
| Force Charge Num | Shows the minutes remaining in Force Charge. Setting a value starts Force Charge for that many minutes | — |
| Force Export | Discharges the battery at full power now for the chosen number of minutes. Shows "Normal" when idle and "Running" while active; choose "Cancel" to stop | — |
| Force Export Num | Shows the minutes remaining in Force Export. Setting a value starts Force Export for that many minutes | — |
| Mode | Sets the battery operation mode. One of "Eco", "Eco (Paused)", "Timed Demand" or "Timed Export" | — |
| Real Time Control | Turns on the inverter's Real Time Control setting. While on, writes to registers that are safe to change often are counted in Safe Write Count instead of Write Count | — |
| Reboot Addon | Restarts the GivTCP add-on | N/A |
| Reboot Invertor | Restarts the inverter | Restart Inverter |
| Sync Time | Sets the inverter's date and time to the current time | Set Date and Time |
| Target SOC | Sets the SOC to stop charging at during a charge slot, when Enable Charge Target is on | — |
| Temp Pause Charge | Pauses charging for the chosen number of minutes; choose "Cancel" to stop | — |
| Temp Pause Charge Num | Shows the minutes remaining in Temp Pause Charge. Setting a value starts a pause for that many minutes | — |
| Temp Pause Discharge | Pauses discharging for the chosen number of minutes; choose "Cancel" to stop | — |
| Temp Pause Discharge Num | Shows the minutes remaining in Temp Pause Discharge. Setting a value starts a pause for that many minutes | — |

Three-phase inverters also have:

| Control Function | Description |
| ------------- | ------------- |
| Force Charge Enable | Forces the battery to charge |
| Force Discharge Enable | Forces the battery to discharge |
| Force AC Charge Enable | Allows the battery to charge from AC |

An EMS has its own plant controls: Plant Control, EMS Charge/Discharge Target SOC (1-3), EMS Charge/Discharge Start/End Time Slots (1-3), Export Target SOC (1-3), Export Start/End Time Slots (1-3), Export Power Limit, Car Charge Mode and Car Charge Boost. See the EMS section of [DATAPOINTS.md](DATAPOINTS.md#ems).

## GivTCP Control (EVC)

When `EVC_ENABLE` is on, GivTCP creates a "GivEVC" device in HA with these controls:

| Control Function | Description |
| ------------- | ------------- |
| Plug and Go | When on, the vehicle starts charging as soon as it is plugged in. When off, charging starts from an RFID card or Charge Control |
| Charge Control | Starts or stops charging. One of "Start" or "Stop" |
| Charging Mode | One of "Grid", "Solar" or "Hybrid". Grid charges at Charge Limit regardless of the energy available. Solar charges only from excess solar (needs at least 1.4kW / 6A). Hybrid charges at 6A from the grid plus any excess solar on top |
| Charge Limit | Maximum charging current, 6-32A |
| Import Cap | Reduces charging current to keep grid import below this current. 0 = off |
| Max Session Energy | Stops the session after this much energy (kWh). 0 = off |

## GivTCP MQTT and REST Control
By enabling MQTT in the config, GivTCP will publish all inverter data directly to the nominated MQTT broker. Data is published to `GivEnergy/<serial_number>/` by default, or you can nominate a specific root topic by setting `MQTT_TOPIC` in the settings.

Control is also available using MQTT. By publishing to the same MQTT broker you can trigger the control functions below. The MQTT payload is the plain value, not JSON.

Root topic for control is:

`GivEnergy/control/<serial_number>/` - Default (note lower case "control")

`<MQTT_TOPIC>/control/<serial_number>/` - If `MQTT_TOPIC` is set

The same controls are available as REST calls. Send a `POST` with a JSON body to `http://<host>:8099/REST1/<function>` (use `REST2`, `REST3`… for other inverters), or directly to the inverter's REST port (6345 for the first inverter).

### Inverter

| Function | Description | REST URL | REST payload | MQTT Topic | MQTT Payload |
|---|---|---|---|---|---|
| enableChargeTarget | When enabled, charging from the grid stops when the battery reaches the charge target. When disabled, it charges to 100% during the charge slot | `/enableChargeTarget` | `{"state":"enable"}` | `enableChargeTarget` | `enable` / `disable` |
| enableChargeSchedule | Turns the charge schedule on or off. When off, the battery will not charge as per the schedule | `/enableChargeSchedule` | `{"state":"enable"}` | `enableChargeSchedule` | `enable` / `disable` |
| enableDischargeSchedule | Turns the discharge schedule on or off. When off, the battery ignores the discharge schedule and discharges to meet demand (similar to Eco mode) | `/enableDischargeSchedule` | `{"state":"enable"}` | `enableDischargeSchedule` | `enable` / `disable` |
| enableDischarge | Allows or prevents discharging, to pause discharging instantly | `/enableDischarge` | `{"state":"enable"}` | `enableDischarge` | `enable` / `disable` |
| setEcoMode | Turns Eco mode on or off | `/setEcoMode` | `{"state":"enable"}` | `setEcoMode` | `enable` / `disable` |
| setBatteryMode | Sets the battery operation mode: "Eco", "Eco (Paused)", "Timed Demand" or "Timed Export" | `/setBatteryMode` | `{"mode":"Eco"}` | `setBatteryMode` | `Eco` |
| setBatteryPauseMode | Sets the battery pause mode: "Disabled", "PauseCharge", "PauseDischarge" or "PauseBoth". Applies during the pause slot | `/setBatteryPauseMode` | `{"state":"PauseCharge"}` | `setBatteryPauseMode` | `PauseCharge` |
| setChargeRate | Sets the battery charge power in Watts | `/setChargeRate` | `{"chargeRate":"2500"}` | `setChargeRate` | `2500` |
| setDischargeRate | Sets the battery discharge power in Watts | `/setDischargeRate` | `{"dischargeRate":"2500"}` | `setDischargeRate` | `2500` |
| setChargeRateAC | Sets the AC charge power as a percentage of the inverter rating | `/setChargeRateAC` | `{"chargeRate":"75"}` | `setChargeRateAC` | `75` |
| setDischargeRateAC | Sets the AC discharge power as a percentage of the inverter rating | `/setDischargeRateAC` | `{"dischargeRate":"75"}` | `setDischargeRateAC` | `75` |
| setActivePowerRate | Sets the maximum inverter output as a percentage of its rating | — | — | `setActivePowerRate` | `100` |
| setChargeTarget | Sets the target charge SOC | `/setChargeTarget` | `{"chargeToPercent":"80"}` | `setChargeTarget` | `80` |
| setChargeTarget1-10 | Sets the target SOC for charge slot 1-10 | — | — | `setChargeTarget1` | `80` |
| setDischargeTarget | Sets the SOC to stop discharging at for a discharge slot | `/setDischargeTarget` | `{"dischargeToPercent":"20","slot":"1"}` | `setDischargeTarget1-10` | `20` |
| setBatteryReserve | Sets the minimum SOC the battery will discharge to | `/setBatteryReserve` | `{"reservePercent":"4"}` | `setBatteryReserve` | `4` |
| setBatteryCutoff | Sets the SOC at which the battery stops discharging altogether | `/setBatteryCutoff` | `{"dischargeToPercent":"4"}` | `setBatteryCutoff` | `4` |
| setChargeSlot1-3 | Sets the start and end time, and optionally the target SOC, of a charge slot. Times are hh:mm | `/setChargeSlot1` | `{"start":"01:00","finish":"04:00","chargeToPercent":"55"}` | — | — |
| setChargeSlot | As above, with the slot number in the payload | `/setChargeSlot` | `{"start":"01:00","finish":"04:00","slot":"4"}` | — | — |
| setChargeStart1-10 / setChargeEnd1-10 | Sets the start or end time of a charge slot | — | — | `setChargeStart1` | `01:00` |
| setDischargeSlot1-3 | Sets the start and end time, and optionally the target SOC, of a discharge slot. Times are hh:mm | `/setDischargeSlot1` | `{"start":"16:00","finish":"19:00","dischargeToPercent":"20"}` | — | — |
| setDischargeSlot | As above, with the slot number in the payload | `/setDischargeSlot` | `{"start":"16:00","finish":"19:00","slot":"4"}` | — | — |
| setDischargeStart1-10 / setDischargeEnd1-10 | Sets the start or end time of a discharge slot | — | — | `setDischargeStart1` | `16:00` |
| setPauseSlot | Sets the time window for Battery Pause Mode | `/setPauseSlot` | `{"start":"16:00","finish":"19:00"}` | `setPauseStart` / `setPauseEnd` | `16:00` |
| forceCharge | Charges the battery for the given number of minutes. Send "Cancel" or 0 to stop | `/forceCharge` | `{"duration":"30"}` | `forceCharge` | `30` |
| forceExport | Discharges the battery at maximum power for the given number of minutes. Send "Cancel" or 0 to stop | `/forceExport` | `{"duration":"30"}` | `forceExport` | `30` |
| tempPauseCharge | Pauses charging for the given number of minutes. Send "Cancel" or 0 to stop | `/tempPauseCharge` | `{"duration":"30"}` | `tempPauseCharge` | `30` |
| tempPauseDischarge | Pauses discharging for the given number of minutes. Send "Cancel" or 0 to stop | `/tempPauseDischarge` | `{"duration":"30"}` | `tempPauseDischarge` | `30` |
| setDateTime | Sets the inverter date and time | `/setDateTime` | `{"dateTime":"dd/mm/yyyy hh:mm:ss"}` | `setDateTime` | `dd/mm/yyyy hh:mm:ss` |
| syncDateTime | Sets the inverter date and time to the current time | `/syncDateTime` | `{}` | `syncDateTime` | (any value) |
| enableRTC | Turns the inverter's Real Time Control setting on or off | — | — | `enableRTC` | `enable` / `disable` |
| setBatteryCalibration | Starts or stops a battery calibration: "Off", "Start" or "Charge Only" | `/setBatteryCalibration` | `{"state":"Start"}` | `setBatteryCalibration` | `Start` |
| switchRate | Switches the tariff GivTCP uses for cost tracking between day and night | `/switchRate` | `{"rate":"day"}` | `switchRate` | `day` / `night` |
| rebootInverter | Restarts the inverter | `/reboot` | — | `rebootInverter` | (any value) |
| rebootAddon | Restarts GivTCP | `/restart` | — | `rebootAddon` | (any value) |

### Three-phase inverters

| Function | Description | REST URL | REST payload | MQTT Topic | MQTT Payload |
|---|---|---|---|---|---|
| setForceCharge | Forces the battery to charge | `/setForceCharge` | `{"state":"enable"}` | `setForceCharge` | `enable` / `disable` |
| setForceDischarge | Forces the battery to discharge | `/setForceDischarge` | `{"state":"enable"}` | `setForceDischarge` | `enable` / `disable` |
| setACCharge | Allows the battery to charge from AC | `/setACCharge` | `{"state":"enable"}` | `setACCharge` | `enable` / `disable` |

### EMS

| Function | Description | REST URL | REST payload | MQTT Topic | MQTT Payload |
|---|---|---|---|---|---|
| setEmsPlant | Lets the EMS control the plant | `/setEmsPlant` | `{"state":"enable"}` | `setEmsPlant` | `enable` / `disable` |
| setExportLimit | Sets the maximum plant export in Watts | `/setExportLimit` | `{"state":"3600"}` | `setExportLimit` | `3600` |
| setExportTarget | Sets the SOC to stop exporting at for an export slot | `/setExportTarget` | `{"exportToPercent":"20","slot":"1"}` | `setExportTarget1-3` | `20` |
| setExportSlot1-3 | Sets the start and end time of an export slot | `/setExportSlot1` | `{"start":"16:00","finish":"19:00"}` | `setExportStart1-3` / `setExportEnd1-3` | `16:00` |
| setEMSChargeTarget1-3 | Sets the target SOC for an EMS charge slot | — | — | `setEMSChargeTarget1` | `80` |
| setEMSChargeStart1-3 / setEMSChargeEnd1-3 | Sets the start or end time of an EMS charge slot | — | — | `setEMSChargeStart1` | `01:00` |
| setEMSDischargeStart1-3 / setEMSDischargeEnd1-3 | Sets the start or end time of an EMS discharge slot | — | — | `setEMSDischargeStart1` | `16:00` |
| setCarChargeBoost | Sets the EV charge boost power in Watts. Not yet supported: the givenergy-modbus library can't write this register, so the command returns an error | `/setCarChargeBoost` | `{"boost":"2500"}` | `setCarChargeBoost` | `2500` |

### EV Charger (EVC)

EVC control topics use the charger's serial number: `GivEnergy/control/<evc_serial_number>/`.

| Function | Description | REST URL | REST payload | MQTT Topic | MQTT Payload |
|---|---|---|---|---|---|
| Plug and Go | Starts charging as soon as a vehicle is plugged in | `/setChargeMode` | `"enable"` | `chargeMode` | `enable` / `disable` |
| Charge Control | Starts or stops charging | `/setChargeControl` | `{"mode":"Start"}` | `controlCharge` | `Start` / `Stop` |
| Charging Mode | Sets the charging mode: "Grid", "Solar" or "Hybrid" | `/setChargingMode` | `{"state":"Solar"}` | `setChargingMode` | `Solar` |
| Charge Limit | Sets the maximum charging current in Amps (6-32) | `/setCurrentLimit` | `{"current":"32"}` | `setCurrentLimit` | `32` |
| Import Cap | Sets the grid import limit in Amps. 0 = off | `/setImportCap` | `{"current":"60"}` | `setImportCap` | `60` |
| Max Session Energy | Sets the maximum energy per session in kWh. 0 = off | `/setMaxSessionEnergy` | `{"energy":"20"}` | `setMaxSessionEnergy` | `20` |
| System Time | Sets the charger's date and time | — | — | `setSystemTime` | `dd/mm/yyyy hh:mm:ss` |

### Reading data over REST

| REST URL | Method | Description |
|---|---|---|
| `/getCache` | GET | Latest data for the inverter as JSON, without publishing it anywhere |
| `/readData` | GET | Latest data, also published according to the output settings |
| `/runAll` | GET | Latest data from the cache |
| `/getEVCCache` | GET | Latest data from the EV charger |
| `/settings` | GET / POST | Read or save GivTCP's settings (used by the config page) |
