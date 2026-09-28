# GivTCP Settings & Control Guide

## GivTCP Control (Inverters)
GivTCP provides a wide range of inverter control settings. When using HA an MQTT device is automatically created for each inverter:

<img src="docs/images/settings-1.png" width="400"> <img src="docs/images/settings-2.png" width="400">

| Control Function | Description | GivEnergy Cloud Equivalent |
| ------------- | ------------- | ------------- |
| Active Power Rate  | Sets the maximum active power output as a precentage. 100% = inverter rating | Inverter Max Output Active Power Percent |
| Battery Charge Rate | Sets the battery charge power in Watts | Battery Charge Power |
| Battery Charge Rate AC | Sets the inverter AC charge power as a percentage. 100% = inverter rating | Inverter Charge Power Precentage |
| Battery Discharge Rate | Sets the battery discharge power in Watts | Battery Discharge Power |
| Battery Discharge Rate AC | Sets the inverter AC dischrage power as a percentage. 100% = inverter rating | Inverter Discharge Power Precentage |
| Battery Pause Mode | Sets the battery operation mode. One of "Disabled","PauseCharge","PauseDischarge" or "PauseBoth" | Pause Battery |
| Battery Power Cutoff | ???? | Battery Cutoff % Limit |
| Battery Power Reserve | Sets the minimum battery discharge SOC as a precentage. 100% = battery capacity  | Battery Reserve % Limit |
| Charge Target SOC (1-10) | Sets the target SOC when charging as a percentage. 100% = battery capacity. There are 10 slots 1-10 | AC Charge 1 Upper SOC % Limit |
| Discharge Target (SOC 1-10) | Sets the target SOC when discharging as a percentage. Minimum = Battery Power Reserve. | AC Discharge 1 Lower SOC % Limit |
| Eco Mode | Sets Eco mode | Enable Eco mode |
| Enable Charge Schedule | Sets the Charging schedule state, if disabled the battery will not charge as per the schedule | xxx |
| Enable Discharge Schedule | Sets the Discharging schedule state, if disabled the battery will not discharge as per the schedule | xxx |
| Force Charge | Forces battery to charge for a given duration in Minutes. Select from "Normal" or an integer value | xxx |
| Force Charge Num | Displays the Minutes remaining in Force Charge | xxx |
| Force Export | Forces battery to discharge for a given duration in Minutes. Select from "Normal" or an integer value | xxx |
| Force Export Num | Displays the Minutes remaining in Force Discharge | xxx |
| Mode | Sets battery operation mode. Mode value must be one of Eco, Eco (Paused), Timed Demand or Timed Export | xxx |
| Reboot Addon | Reboots the GivTCP addon | N/A |
| Reboot Invertor | Reboots the Inverter | Restart Inverter |
| Sync Time | Synchronises inverter time to current time and date | Set Date and Time |
| Target SOC | Sets the target battery SOC when Force Charge or Discharging | xxx |
| Temp Pause Charge | Suspends charging for a for a given duration in Minutes. Command must be "Cancel" or an integer value | Pause Battery |
| Temp Pause Charge Num | Displays the Minutes remaining in Pause Charge | xxx |
| Temp Pause Discharge | Suspends discharging for a for a given duration in Minutes. Command must be "Cancel" or an integer value | Pause Battery |
| Temp Pause Discharge Num | Displays the Minutes remaining in Pause Discharge | xxx |

## GivTCP Control (EVC)

Coming soon

## GivTCP MQTT Control (Inverters)
By enabling MQTT in the config, GivTCP will publish directly to the nominated MQTT broker all inverter data. Data is published to "GivEnergy/<serial_number>/" by default or you can nominate a specific root topic by setting "MQTT_TOPIC" in the settings.

Control is also available using MQTT. By publishing data to the same MQTT broker as above you can trigger the control methods as per the above table.

Root topic for control is:

"GivEnergy/control/<serial_number>/" - Default (note lower case "control")

"<MQTT_TOPIC>/control/<serial_number>/" - If MQTT_TOPIC is set

| Function                | Description                                                                                                                                                                                               | REST URL                 | REST payload                                               | MQTT Topic              | MQTT Payload                                               |
|-------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------|------------------------------------------------------------|-------------------------|------------------------------------------------------------|
| enableChargeTarget      | Sets   inverter to follow setChargeTarget value when charging from grid (will stop   charging when battery SOC= ChargeTarget)                                                                             | /enableChargeTarget      | {"state","enable"}                                         | enableChargeTarget      | enable                                                     |
| disableChargeTarget     | Sets   inverter to ignore setChargeTarget value when charging from grid (will   continue to charge to 100% during ChargeSlot)                                                                             | /disableChargeTarget     | {"state","enable"}                                         | disableChargeTarget     | enable                                                     |
| enableChargeSchedule    | Sets   the Charging schedule state, if disabled the battery will not charge as per   the schedule                                                                                                         | /enableChargeSchedule    | {"state","enable"}                                         | enableChargeSchedule    | enable                                                     |
| enableDischargeSchedule | Sets   the Discharging schedule state, if disabled the battery will will ignore rhe   discharge schedule and discharge as per demand (similar to eco mode)                                                | /enableDischargeSchedule | {"state","enable"}                                         | enableDischargeSchedule | enable                                                     |
| enableDischarge         | Enable/Disables Discharging to instantly pause discharging,   use 'enable' or 'disable'                                                                                                                   | /enableDischarge         | {"state","enable"}                                         | enableDischarge         | enable                                                     |
| setChargeRate           | Sets the charge power as a percentage. 100% == 2.6kW                                                                                                                                                      | /setChargeRate           | {"chargeRate","100"}                                    | setChargeRate           | 100                                                        |
| setDischargeRate        | Sets the discharge power as a percentage. 100% == 2.6kW                                                                                                                                                   | /setDischargeRate        | {"dischargeRate","100"}                                       | setDischargeRate        | 100                                                        |
| setChargeTarget         | Sets   the Target charge SOC                                                                                                                                                                              | /setChargeTarget         | {"chargeToPercent":"50"}                                   | setChargeTarget         | 50                                                         |
| setBatteryReserve       | Sets   the Battery Reserve discharge cut-off limit                                                                                                                                                        | /setBatteryReserve       | {"reservePercent":"5"}                                 | setBatteryReserve       | 5                                                          |
| setChargeSlot1          | Sets   the time and target SOC of the first chargeslot. Times must be expressed in   hh:mm format. Enable flag show in the battery.api documentation is not needed   and chargeToPercent is optional       | /setChargeSlot1          | {"start":"01:00","finish":"04:00","chargeToPercent":"55"}    | setChargeSlot1          | {"start":"01:00","finish":"04:00","chargeToPercent":"55"}    |
| setDischargeSlot1       | Sets   the time and target SOC of the first dischargeslot. Times must be expressed   in hh:mm format. Enable flag show in the battery.api documentation is not   needed and dischargeToPercent is optional | /setDischargeSlot1       | {"start":"01:00","finish":"04:00","dischargeToPercent":"55"} | setDischargeSlot1       | {"start":"01:00","finish":"04:00","dischargeToPercent":"55"} |
| setDischargeSlot2       | Sets   the time and target SOC of the first dischargeslot. Times must be expressed   in hh:mm format. Enable flag show in the battery.api documentation is not   needed and dischargeToPercent is optional | /setDischargeSlot2       | {"start":"01:00","finish":"04:00","dischargeToPercent":"55"} | setDischargeSlot2       | {"start":"01:00","finish":"04:00","dischargeToPercent":"55"} |
| setBatteryMode          | Sets   battery operation mode. Mode value must be one of Eco, Timed Demand or Timed Export                                                                                                                                        | /setBatteryMode          | {"mode":"Eco"}                                               | setBatteryMode          | 1                                                          |
| setDateTime             | Sets   inverter time, format must be as define in payload                                                                                                                                                 | /setDateTime             | {"dateTime":"dd/mm/yyyy   hh:mm:ss"}                       | setDateTime             | "dd/mm/yyyy hh:mm:ss"                                      |
| setBatteryPauseMode          | Sets   battery operation mode. Mode value must be one of "Disabled","PauseCharge","PauseDischarge" or "PauseBoth"                                                                                                                                         | /setBatteryPauseMode          | {"state":"Disabled"}                                               | setBatteryPauseMode          | 1
| forceExport          | Forces battery to Export (discharge at Max power) for a given duration in Minutes. command must be "Cancel" or an integer value. Sending 0 will also call the cancel function                                                                                                                                         | /forceExport          | {"15"}                                               | forceExport          | 1
| forceCharge          | Forces battery to charge for a given duration in Minutes. Command must be "Cancel" or an integer value. Sending 0 will also call the cancel function                                                                                                                                         | /forceCharge          | {"15"}                                               | forceCharge          | 1
| tempPauseCharge          | Suspends charging for a for a given duration in Minutes. Command must be "Cancel" or an integer value. Sending 0 will also call the cancel function                                                                                                                                         | /tempPauseCharge          | {"15"}                                               | tempPauseCharge          | 1
| tempPauseDischarge          | Suspends discharging for a given duration in Minutes. command must be "Cancel" or an integer value. Sending 0 will also call the cancel function                                                                                                                                         | /tempPauseDischarge          | {"15"}                                               | tempPauseDischarge          | 1

