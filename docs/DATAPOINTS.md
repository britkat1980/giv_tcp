# GivTCP Datapoints

This is a reference for every datapoint GivTCP publishes, grouped by where it appears in the output, with a short description of each.

The same data is available three ways:

| Where | How it looks |
|---|---|
| **MQTT** | One topic per value, following the nesting below: `GivEnergy/<serial>/Power/Power/SOC` (the root is `MQTT_TOPIC` if set) |
| **REST** | The whole tree as JSON from `GET /REST1/getCache` (`/REST2/`… for other inverters) |
| **Home Assistant** | One entity per value when `HA_AUTO_D` is on, e.g. `sensor.givtcp_<serial>_soc` |

Controllable datapoints also have a command topic, `GivEnergy/control/<serial>/<command>`. The **Command** column gives the `<command>` for each one. Home Assistant sets this up automatically.

## Conventions

- **Sign of power values:**
  - `Grid_Power`: positive = exporting, negative = importing.
  - `Battery_Power`: positive = discharging, negative = charging.
  - `Invertor_Power`: positive = inverter output, negative = AC charging the battery.
- **Units:** power in W, energy in kWh, voltage in V, current in A, temperature in °C, SOC in %, money in £ (per kWh for rates).
- **Spelling:** some names use the legacy spelling `Invertor`. This is intentional and kept for compatibility with existing automations.
- **Types:** Home Assistant entity types. `sensor` is read-only; `switch`, `select`, `number` and `button` can be changed from HA or over MQTT/REST.
- **Numbered families:** these are written once with `N`. For example, `Charge_Target_SOC_N` means `Charge_Target_SOC_1` to `Charge_Target_SOC_10`. How many slots appear depends on what the inverter supports.
- **Device support:** not every device publishes every value. The sections below say which devices each group applies to.

---

## Stats

`GivEnergy/<serial>/Stats/…`: the health of GivTCP itself. Published for all devices.

| Name | Type | Unit | Description |
|---|---|---|---|
| `status` | sensor | | `online` while GivTCP is reading the inverter |
| `Last_Updated_Time` | sensor | timestamp | When this set of data was published |
| `Time_Since_Last_Update` | sensor | s | Seconds since the last successful update |
| `Data_Age` | sensor | s | Age of the newest live register data from the inverter; `-1` if none has been read yet. A large value means values are being held from the last good read |
| `Write_Count` | sensor | | Number of register writes made to the inverter (excluding "safe" writes when Real Time Control is on) |
| `Safe_Write_Count` | sensor | | Number of writes to registers that are safe to write often (counted only when Real Time Control is on) |
| `GivTCP_Version` | sensor | | GivTCP version |

---

## Power

### Power/Power

`GivEnergy/<serial>/Power/Power/…`: live power, voltage and current. Hybrid, AC-coupled and All-in-One inverters.

| Name | Type | Unit | Description |
|---|---|---|---|
| `PV_Power` | sensor | W | Total solar generation |
| `PV_Power_String_1` / `_2` | sensor | W | Solar generation per PV string |
| `PV_Voltage_String_1` / `_2` | sensor | V | Voltage per PV string |
| `PV_Current_String_1` / `_2` | sensor | A | Current per PV string |
| `Grid_Power` | sensor | W | Grid power: positive = export, negative = import |
| `Import_Power` | sensor | W | Power being imported from the grid (always ≥ 0) |
| `Export_Power` | sensor | W | Power being exported to the grid (always ≥ 0) |
| `Grid_Voltage` | sensor | V | Grid voltage |
| `Grid_Current` | sensor | A | Grid current |
| `Grid_Frequency` | sensor | Hz | Grid frequency |
| `Inverter_Output_Frequency` | sensor | Hz | Inverter AC output frequency |
| `EPS_Power` | sensor | W | Power supplied to the EPS/backup output |
| `Invertor_Power` | sensor | W | Inverter AC power: positive = output, negative = charging the battery from AC |
| `AC_Charge_Power` | sensor | W | Power being drawn from AC to charge the battery |
| `Load_Power` | sensor | W | House load |
| `Self_Consumption_Power` | sensor | W | House load not covered by grid import |
| `Combined_Generation_Power` | sensor | W | Combined generation reported by the inverter |
| `Battery_Power` | sensor | W | Battery power: positive = discharging, negative = charging |
| `Charge_Power` | sensor | W | Battery charge power (always ≥ 0) |
| `Discharge_Power` | sensor | W | Battery discharge power (always ≥ 0) |
| `Battery_Voltage` | sensor | V | Battery voltage |
| `Battery_Current` | sensor | A | Battery current |
| `BMS_Voltage` | sensor | V | Battery voltage reported by the BMS |
| `SOC` | sensor | % | Battery state of charge |
| `SOC_kWh` | sensor | kWh | Energy stored in the battery (SOC × capacity) |
| `Charge_Time_Remaining` | sensor | min | Estimated minutes until the battery reaches `Target_SOC` at the current charge rate |
| `Discharge_Time_Remaining` | sensor | min | Estimated minutes until the battery reaches `Battery_Power_Reserve` at the current discharge rate |
| `Charge_Completion_Time` | sensor | timestamp | Estimated time charging will finish |
| `Discharge_Completion_Time` | sensor | timestamp | Estimated time discharging will reach reserve |

### Power/Flows

`GivEnergy/<serial>/Power/Flows/…`: where the power is going, derived from the values above. Single-phase inverters.

| Name | Type | Unit | Description |
|---|---|---|---|
| `Solar_to_House` | sensor | W | Solar power used by the house |
| `Solar_to_Battery` | sensor | W | Solar power charging the battery |
| `Solar_to_Grid` | sensor | W | Solar power exported |
| `Battery_to_House` | sensor | W | Battery power used by the house |
| `Battery_to_Grid` | sensor | W | Battery power exported |
| `Grid_to_House` | sensor | W | Grid power used by the house |
| `Grid_to_Battery` | sensor | W | Grid power charging the battery |

### Three-phase inverters

Three-phase inverters publish most of the values above in `Power/Power`, plus these:

| Name | Type | Unit | Description |
|---|---|---|---|
| `PV_Current` | sensor | A | Total PV current |
| `Battery_Charge_Power` / `Battery_Discharge_Power` | sensor | W | Battery charge / discharge power |
| `Grid_Apparent_Power` | sensor | W | Apparent power at the grid connection |
| `Inverter_Power_Out` | sensor | W | Inverter AC output power |
| `Meter_Import_Power` / `Meter_Export_Power` | sensor | W | Import / export measured by the grid meter |
| `Meter2_Power` | sensor | W | Power measured by a second meter |
| `Grid_PhaseN_Voltage` | sensor | V | Grid voltage per phase (N = 1–3) |
| `Grid_PhaseN_Current` | sensor | A | Grid current per phase |
| `Output_PhaseN_Voltage` | sensor | V | Inverter output voltage per phase |
| `Load_PhaseN_Power` | sensor | W | House load per phase |
| `Export_PhaseN_Power` | sensor | W | Export per phase |
| `EPS_PhaseN_Power` | sensor | W | EPS/backup output per phase |
| `PCS_Voltage` | sensor | V | Power conversion system (DC bus) voltage |
| `EPS_Nominal_Frequency` | sensor | Hz | Nominal EPS output frequency |

### Gateway

A Gateway also publishes these in `Power/Power`:

| Name | Type | Unit | Description |
|---|---|---|---|
| `Liberty_Power` | sensor | W | Power through the Gateway's Liberty connection (negative = export) |
| `Grid_Relay_Voltage` | sensor | V | Voltage on the grid side of the Gateway relay |
| `Inverter_Relay_Voltage` | sensor | V | Voltage on the inverter side of the Gateway relay |
| `Load_Voltage` | sensor | V | Voltage at the load output |
| `Load_Current` | sensor | A | Current at the load output |

For a Gateway, `Battery_Power` and `Invertor_Power` are derived from the combined output of the connected All-in-Ones.

### EMS

An EMS publishes plant-level values in `Power/Power`:

| Name | Type | Unit | Description |
|---|---|---|---|
| `Grid_Power` | sensor | W | Grid power measured by the EMS meter |
| `Battery_Power` | sensor | W | Combined battery power across all inverters |
| `Other_Battery_Power` | sensor | W | Battery power from inverters not managed by the EMS |
| `Calculated_Load_Power` | sensor | W | House load calculated from the other flows |
| `Measured_Load_Power` | sensor | W | House load measured by a load meter |
| `Generation_Load_Power` | sensor | W | Total generation |

It also publishes one entry per meter in `Power/Meters`:

| Name | Type | Unit | Description |
|---|---|---|---|
| `Meter_N_Power` | sensor | W | Power measured by meter N (N = 1–8) |
| `Meter_N_Status` | sensor | | Status of meter N |

---

## Energy

### Energy/Today and Energy/Total

`GivEnergy/<serial>/Energy/Today/…` and `…/Energy/Total/…`: `Today` values reset at midnight, and `Total` values are lifetime counters. Each name below exists as both `…_Today_kWh` and `…_Total_kWh`.

| Name | Type | Unit | Description |
|---|---|---|---|
| `PV_Energy_…` | sensor | kWh | Solar generation |
| `Import_Energy_…` | sensor | kWh | Energy imported from the grid |
| `Export_Energy_…` | sensor | kWh | Energy exported to the grid |
| `Load_Energy_…` | sensor | kWh | House consumption |
| `Self_Consumption_Energy_…` | sensor | kWh | Consumption not supplied by grid import |
| `Invertor_Energy_…` | sensor | kWh | Energy output by the inverter |
| `AC_Charge_Energy_…` | sensor | kWh | Energy used to charge the battery from AC |
| `Battery_Charge_Energy_…` | sensor | kWh | Energy into the battery |
| `Battery_Discharge_Energy_…` | sensor | kWh | Energy out of the battery |
| `Battery_Throughput_…` | sensor | kWh | Battery charge + discharge |

Three-phase inverters, EMS and Gateway also publish:

| Name | Type | Unit | Description |
|---|---|---|---|
| `PV1_Energy_Today_kWh`, `PV1_Energy_Total_kWh`, `PV2_Energy_Total_kWh` | sensor | kWh | Solar generation per PV input |
| `Export2_Energy_…` | sensor | kWh | Export measured by a second meter |
| `Generation_Energy_Total_kWh` | sensor | kWh | Lifetime generation |
| `Inverter_Out_Energy_…` | sensor | kWh | Energy output by the inverter |
| `Parallel_Total_Charge_Energy_…` | sensor | kWh | Battery charge across all parallel All-in-Ones (Gateway) |
| `Parallel_Total_Discharge_Energy_…` | sensor | kWh | Battery discharge across all parallel All-in-Ones (Gateway) |

### Energy/Rates

`GivEnergy/<serial>/Energy/Rates/…`: import cost tracking using the Day/Night tariff set in the config page.

| Name | Type | Command | Unit | Description |
|---|---|---|---|---|
| `Current_Rate_Type` | select | `switchRate` | | Which tariff is active: `Day` or `Night`. Can be switched manually, e.g. by an external tariff automation |
| `Current_Rate` | sensor | | £/kWh | Import price now in effect |
| `Day_Rate` / `Night_Rate` | sensor | | £/kWh | Configured day / night import price |
| `Export_Rate` | sensor | | £/kWh | Configured export price |
| `Day_Energy_kWh` / `Night_Energy_kWh` | sensor | | kWh | Import during the current day / night period |
| `Day_Energy_Total_kWh` / `Night_Energy_Total_kWh` | sensor | | kWh | Import carried forward from earlier day / night slots today |
| `Day_Start_Energy_kWh` / `Night_Start_Energy_kWh` | sensor | | kWh | Import meter reading when the day / night period started |
| `Day_Cost` / `Night_Cost` | sensor | | £ | Cost of day / night import today |
| `Import_ppkwh_Today` | sensor | | £/kWh | Average import price paid today |
| `Battery_Value` | sensor | | £ | Estimated value of the energy currently stored in the battery, based on what it cost to charge |
| `Battery_ppkwh` | sensor | | £/kWh | Average cost per kWh of the energy in the battery |

---

## Inverter details

`GivEnergy/<serial>/<serial>/…`: information about the inverter itself. In Home Assistant these are attributes of the inverter device.

| Name | Type | Unit | Description |
|---|---|---|---|
| `Invertor_Serial_Number` | sensor | | Inverter serial number |
| `Invertor_Type` | sensor | | Model (Hybrid, AC, AIO, three-phase, EMS, Gateway, …) |
| `Invertor_Firmware` | sensor | | Firmware version |
| `Invertor_Software` | sensor | | Software version (three-phase) |
| `Modbus_Version` | sensor | | Modbus protocol version |
| `Invertor_Time` | sensor | timestamp | Inverter clock (see `Sync_Time`) |
| `Invertor_Max_Inv_Rate` | sensor | W | Maximum inverter AC output |
| `Invertor_Max_Bat_Rate` | sensor | W | Maximum battery charge / discharge rate |
| `Export_Limit` | sensor | W | Export limit configured on the inverter |
| `Meter_Type` | sensor | | Type of grid meter the inverter is using |
| `Battery_Type` | sensor | | Battery type reported by the inverter |
| `Battery_Capacity_kWh` | sensor | kWh | Battery capacity |
| `Battery_Capacity_kWh_calc` | sensor | kWh | Battery capacity calculated by GivTCP from the battery modules |
| `Battery_Calibration_Status` | sensor | | Stage of any running battery calibration |
| `Invertor_Temperature` | sensor | °C | Inverter heatsink temperature |
| `status` | sensor | | Inverter status |

Three-phase inverters add:

| Name | Type | Unit | Description |
|---|---|---|---|
| `System_Mode` | sensor | | Inverter operating mode |
| `Power_Factor` | sensor | | Output power factor |
| `Start_Delay_Time` | sensor | s | Delay before the inverter reconnects to the grid |
| `Battery_Priority` | sensor | | Whether the battery or load has priority |
| `Inverter_Temperature` / `Boost_Temperature` / `Buck_Boost_Temperature` | sensor | °C | Internal temperatures |
| `DC_Status` | sensor | | DC side status |

---

## Control

`GivEnergy/<serial>/Control/…`: current settings, which can also be changed. Hybrid, AC-coupled, All-in-One and three-phase inverters.

| Name | Type | Command | Unit | Description |
|---|---|---|---|---|
| `Mode` | select | `setBatteryMode` | | Battery mode: `Eco`, `Eco (Paused)`, `Timed Demand`, `Timed Export` |
| `Eco_Mode` | switch | `setEcoMode` | | Eco mode on/off |
| `Battery_pause_mode` | select | `setBatteryPauseMode` | | Pause battery `Disabled`, `PauseCharge`, `PauseDischarge` or `PauseBoth` (applies during the pause timeslot) |
| `Battery_Power_Reserve` | number | `setBatteryReserve` | % | SOC the battery will not discharge below |
| `Battery_Power_Cutoff` | number | `setBatteryCutoff` | % | SOC at which the battery stops discharging altogether |
| `Target_SOC` | number | `setChargeTarget` | % | SOC to stop charging at during a charge slot |
| `Charge_Target_SOC_N` | number | `setChargeTargetN` | % | Target SOC for charge slot N (1–10, on inverters with per-slot targets) |
| `Discharge_Target_SOC_N` | number | `setDischargeTargetN` | % | SOC to stop discharging at for discharge slot N (1–10) |
| `Enable_Charge_Schedule` | switch | `enableChargeSchedule` | | Use the charge timeslots |
| `Enable_Charge_Target` | switch | `enableChargeTarget` | | Stop charging at `Target_SOC` (otherwise charge to 100%) |
| `Enable_Discharge_Schedule` | switch | `enableDischargeSchedule` | | Use the discharge timeslots |
| `Enable_Discharge` | switch | `enableDischarge` | | Allow the battery to discharge |
| `Battery_Charge_Rate` | number | `setChargeRate` | W | Maximum battery charge power |
| `Battery_Discharge_Rate` | number | `setDischargeRate` | W | Maximum battery discharge power |
| `Battery_Charge_Rate_AC` | number | `setChargeRateAC` | % | AC charge rate as a percentage of maximum |
| `Battery_Discharge_Rate_AC` | number | `setDischargeRateAC` | % | AC discharge rate as a percentage of maximum |
| `Active_Power_Rate` | number | `setActivePowerRate` | % | Limit inverter output as a percentage of maximum |
| `Force_Charge` | select | `forceCharge` | min | Charge from the grid now for the chosen number of minutes. Shows `Normal` or `Running`; `Cancel` stops it |
| `Force_Export` | select | `forceExport` | min | Export at full power now for the chosen number of minutes |
| `Temp_Pause_Charge` | select | `tempPauseCharge` | min | Pause charging for the chosen number of minutes |
| `Temp_Pause_Discharge` | select | `tempPauseDischarge` | min | Pause discharging for the chosen number of minutes |
| `Force_Charge_Num`, `Force_Export_Num`, `Temp_Pause_Charge_Num`, `Temp_Pause_Discharge_Num` | number | as above | min | Minutes remaining on the matching timer (0 when not running). Setting a value starts the timer for that many minutes (up to 250) |
| `Real_Time_Control` | switch | `enableRTC` | | Turns on the inverter's Real Time Control setting. While it is on, writes to registers that are safe to change often are counted in `Safe_Write_Count` rather than `Write_Count` |
| `Battery_Calibration` | select | `setBatteryCalibration` | | Start a battery calibration: `Off`, `Start`, `Charge Only` |
| `Sync_Time` | button | `syncDateTime` | | Set the inverter clock to the current time |
| `Reboot_Invertor` | button | `rebootInverter` | | Restart the inverter |
| `Reboot_Addon` | button | `rebootAddon` | | Restart GivTCP |

Three-phase inverters add:

| Name | Type | Command | Description |
|---|---|---|---|
| `Force_Charge_Enable` | switch | `setForceCharge` | Force battery charging |
| `Force_Discharge_Enable` | switch | `setForceDischarge` | Force battery discharging |
| `Force_AC_Charge_Enable` | switch | `setACCharge` | Allow charging the battery from AC |

---

## Timeslots

`GivEnergy/<serial>/Timeslots/…`: charge, discharge and pause schedules. Times are `HH:MM:SS`, in one-minute steps.

| Name | Type | Command | Description |
|---|---|---|---|
| `Charge_start_time_slot_N` / `Charge_end_time_slot_N` | select | `setChargeStartN` / `setChargeEndN` | Start / end of charge slot N (1–10) |
| `Discharge_start_time_slot_N` / `Discharge_end_time_slot_N` | select | `setDischargeStartN` / `setDischargeEndN` | Start / end of discharge slot N (1–10) |
| `Battery_pause_start_time_slot` / `Battery_pause_end_time_slot` | select | `setPauseStart` / `setPauseEnd` | Window in which `Battery_pause_mode` applies |

---

## Battery details

`GivEnergy/<serial>/Battery_Details/Battery_Stack_N/<battery serial>/…`: one entry per battery module. In Home Assistant, each battery module appears as its own device.

| Name | Type | Unit | Description |
|---|---|---|---|
| `Battery_Serial_Number` | sensor | | Module serial number |
| `Battery_SOC` | sensor | % | Module state of charge |
| `Battery_Capacity` | sensor | Ah | Current full capacity |
| `Battery_Design_Capacity` | sensor | Ah | Capacity when new |
| `Battery_Remaining_Capacity` | sensor | Ah | Charge currently stored |
| `Battery_Voltage` | sensor | V | Module voltage |
| `Battery_Cells` | sensor | | Number of cells |
| `Battery_Cycles` | sensor | | Charge cycles |
| `Battery_Firmware_Version` | sensor | | BMS firmware |
| `Battery_Temperature` | sensor | °C | Module temperature |
| `BMS_Temperature` | sensor | °C | BMS board temperature |
| `BMS_Voltage` | sensor | V | Voltage measured by the BMS |
| `Battery_USB_present` | binary_sensor | | USB stick inserted in the module |
| `Battery_Cell_N_Voltage` | sensor | V | Voltage of cell N |
| `Battery_Cell_N_Temperature` | sensor | °C | Temperature of cell (group) N |

High-voltage battery stacks (three-phase and All-in-One) also report stack-level values from the battery control unit (BCU), under `Battery_Stack_N`:

| Name | Type | Unit | Description |
|---|---|---|---|
| `Stack_Power` / `Stack_Voltage` / `Stack_Current` | sensor | W / V / A | Stack power, voltage and current |
| `Stack_Load_Voltage` | sensor | V | Voltage on the load side of the stack |
| `Stack_SOC_kWh` | sensor | kWh | Energy stored in the stack |
| `Stack_SOC_High` / `Stack_SOC_Low` | sensor | % | Highest / lowest module SOC in the stack |
| `Stack_SOC_Difference` | sensor | % | Spread between highest and lowest module SOC |
| `Stack_SOH` | sensor | % | Stack state of health |
| `Stack_Cycles` | sensor | | Stack charge cycles |
| `Stack_Design_Capacity` | sensor | Ah | Stack capacity when new |
| `Stack_Charge_Energy_…` / `Stack_Discharge_Energy_…` | sensor | kWh | Stack charge / discharge energy (`Today_kWh` and `Total_kWh`) |
| `Stack_Firmware` | sensor | | BCU firmware |
| `BMS_Temperature` | sensor | °C | BCU temperature |

---

## Meter details

`GivEnergy/<serial>/Meter_Details/Meter_ID<N>/…`: one entry per external energy meter (EM115/EM418), where fitted.

| Name | Type | Unit | Description |
|---|---|---|---|
| `Import_Energy_kWh` / `Export_Energy_kWh` | sensor | kWh | Lifetime import / export measured by the meter |
| `Phase_N_Voltage` | sensor | V | Voltage on phase N (1–3) |
| `Phase_N_Current` | sensor | A | Current on phase N |
| `Phase_N_Power` | sensor | W | Power on phase N |
| `Phase_N_Power_Factor` | sensor | | Power factor on phase N |
| `Frequency` | sensor | Hz | Grid frequency |

---

## EMS

An EMS manages several inverters as one plant. On top of the EMS power values above, it publishes the following.

**Device info** (`GivEnergy/<serial>/<serial>/…`):

| Name | Type | Unit | Description |
|---|---|---|---|
| `Plant_Status` | sensor | | Plant operating status |
| `Inverter_Count` | sensor | | Number of inverters in the plant |
| `Meter_Count` | sensor | | Number of meters connected |
| `Remaining_Battery_Wh` | sensor | Wh | Energy left across all batteries |
| `Car_Charge_Count` | sensor | | Number of EV chargers linked to the plant |

**Per inverter** (`Inverters/<inverter serial>/…`): `Serial_Number`, `status`, `SOC` (%), `Power` (W) and `Temperature` (°C) for each inverter in the plant.

**Controls:**

| Name | Type | Command | Unit | Description |
|---|---|---|---|---|
| `Plant_Control` | switch | `setEmsPlant` | | Let the EMS control the plant |
| `EMS_Charge_Target_SOC_N` | number | `setEMSChargeTargetN` | % | Target SOC for EMS charge slot N (1–3) |
| `EMS_Discharge_Target_SOC_N` | number | `setEMSDischargeTargetN` | % | Target SOC for EMS discharge slot N (1–3) |
| `Export_Target_SOC_N` | number | `setExportTargetN` | % | SOC to stop exporting at for export slot N (1–3) |
| `Export_Power_Limit` | number | `setExportLimit` | W | Maximum plant export |
| `Plant_Charge_Compensation` / `Plant_Discharge_Compensation` | number | | | Charge / discharge compensation adjustment |
| `Car_Charge_Mode` | select | | | EV charging mode: `Stop`, `Eco`, `Eco+`, `Fast` |
| `Car_Charge_Boost` | number | `setCarChargeBoost` | W | EV charge boost power. Read-only for now: the givenergy-modbus library can't write it yet |

**Timeslots** (N = 1–3):

| Name | Type | Command | Description |
|---|---|---|---|
| `EMS_Charge_start_time_slot_N` / `EMS_Charge_end_time_slot_N` | select | `setEMSChargeStartN` / `setEMSChargeEndN` | EMS charge slot N |
| `EMS_Discharge_start_time_slot_N` / `EMS_Discharge_end_time_slot_N` | select | `setEMSDischargeStartN` / `setEMSDischargeEndN` | EMS discharge slot N |
| `Export_start_time_slot_N` / `Export_end_time_slot_N` | select | `setExportStartN` / `setExportEndN` | EMS export slot N |

---

## Gateway

A Gateway connects up to three All-in-Ones in parallel. On top of the Gateway power values above, it publishes the following.

**Device info** (`GivEnergy/<serial>/<serial>/…`):

| Name | Type | Description |
|---|---|---|
| `Gateway_Software_Version` | sensor | Gateway software version |
| `Gateway_State` | sensor | Gateway operating state |
| `Gateway_Mode` | sensor | Gateway mode |
| `Parallel_Total_AIO_Number` | sensor | Number of All-in-Ones configured |
| `Parallel_Total_AIO_Online_Number` | sensor | Number of All-in-Ones online |
| `DI_State` / `DO_State` | sensor | Digital input / output state |

**Per All-in-One** (`Inverters/AIO_N/…`, N = 1–3):

| Name | Type | Unit | Description |
|---|---|---|---|
| `AIO_N_Serial_Number` | sensor | | All-in-One serial number |
| `SOC` | sensor | % | All-in-One battery state of charge |
| `Invertor_Power` | sensor | W | All-in-One inverter power (negative = export) |
| `AC_Charge_Energy_Today_kWh` / `_Total_kWh` | sensor | kWh | All-in-One AC charge energy |
| `AC_Discharge_Energy_Today_kWh` / `_Total_kWh` | sensor | kWh | All-in-One AC discharge energy |

---

## EV Charger (GivEVC)

`GivEnergy/<charger serial>/Charger/…`: published when `EVC_ENABLE` is on. In Home Assistant these appear on a device named "GivEVC".

| Name | Type | Command | Unit | Description |
|---|---|---|---|---|
| `Serial_Number` | sensor | | | Charger serial number |
| `Charging_State` | sensor | | | Charger state, e.g. `Connected`, `Charging` |
| `Connection_Status` | sensor | | | Whether a vehicle is plugged in |
| `Error_Code` | sensor | | | Charger error, if any |
| `Active_Power` | sensor | | W | Total charging power |
| `Active_Power_L1` / `_L2` / `_L3` | sensor | | W | Charging power per phase |
| `Current_L1` / `_L2` / `_L3` | sensor | | A | Charging current per phase |
| `Voltage_L1` / `_L2` / `_L3` | sensor | | V | Supply voltage per phase |
| `Evse_Min_Current` / `Evse_Max_Current` | sensor | | A | Charger current limits |
| `Meter_Energy` | sensor | | kWh | Lifetime energy delivered |
| `Charge_Session_Energy` | sensor | | kWh | Energy delivered this session (held after the session ends) |
| `Charge_Session_Duration` | sensor | | | Length of the current / last session |
| `Charge_Start_Time` / `Charge_End_Time` | sensor | | timestamp | Start / end of the current or last session |
| `System_Time` | sensor | | timestamp | Charger clock |
| `Plug_and_Go` | switch | `chargeMode` | | Start charging as soon as a vehicle is plugged in |
| `Charge_Control` | select | `controlCharge` | | `Start` / `Stop` charging |
| `Charging_Mode` | select | `setChargingMode` | | `Grid`, `Solar` or `Hybrid` (see the readme page for details) |
| `Charge_Limit` | number | `setCurrentLimit` | A | Charging current limit (6–32 A) |
| `Import_Cap` | number | `setImportCap` | A | Reduce charging to keep grid import under this current; 0 = off |
| `Max_Session_Energy` | number | `setMaxSessionEnergy` | kWh | Stop the session after this much energy; 0 = off |
