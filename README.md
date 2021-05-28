# GivTCP
TCP Modbus connection to MQTT for Givenergy Battery/PV Invertors

This project allows connection to the GivEnergy invertors via TCP Modbus. Access is through the native Wifi/Ethernet dongle can be connected to through either the local LAN network or directly through the inbuilt SSID AP.

In essence the script connects to a Modbus TCP server which runs on the wifi dongle, so all you need is somewhere to run the script on the same network. You will need the following to make it work:
* MQTT server running on the network and know its IP address
* MQTT login credentials (optional)
* IP address of the invertor
* Serial Number of the wifi/gps dongle (not the invertor) - which can be found on the portal: https://www.givenergy.cloud/GivManage/setting/deviceMenu/inverterList
* Machine/Pi/VM running Python which has following modules installed:
  * crccheck
  * paho-mqtt

# Settings
A settings.py file is required in the root directory. Use the supplied settings_template.py and populate with the relevant detailes. Only InvertorIP, dataloggerSN and MQTT_Address are required. All other settings must be there but can be left blank if not needed.

# Usage
The scripts function through being called from the command line with appropriate parameters assigned. There are both Read and Write functions, providing data acquisiation and control.
Node-Red flows are available which can be used to call these scripts and provide control and data visualisation.
It is reccomended that the read.py script is called no more often than every 15s, if calling runAll.

# Read
To retrieve data and publish to the MQTT queue the read.py script is called with arguments as below:

`python3 read.py {{functionName}}`

Available read functions are:
| Function          | Payload       |  Description                      |
| ----------------- | ------------- |  -------------------------------- |
| getTimeslots      | None          | Gets all currently stored timeslots for Charge1, Discharge1 and Discharge2      |
| getCombinedStats  | None          | Gets power and Energy Stats (real-time, Today and Total)   |
| getModes          | None          | Gets the control state info including: Mode, Target Charge SOC, Battery Reserve, Charge and Discharge Schedule state (Paused/Active) and Battery Capacity    |
| runAll            | None          | Runs all of the above  |


# Control
Control is available through redefined functions which are called with arguments. The format of the function call matches the published GivEnegry cloud based battery.api. It requires a JSON pay load as per the below:

`python3 write.py {{functionName}} {{controlPayload}}`

An example payload can be found below and further details can be seen in the GivEnergy Docs to be found here: XXXXXXX

{
    "start": "0100",
    "finish": "0400",
    "chargeToPercent": "100"
}

Available control functions are:
| Function                | Payload       |  Description                      |
| ----------------------- | ------------- |  -------------------------------- |
| pauseChargeSchedule     | None          | Pauses the Charging schedule      |
| pauseDischargeSchedule  | None          | Pauses the Discharging schedule   |
| resumeChargeSchedule    | None          | Resumes the Charging schedule     |
| resumeDischargeSchedule | None          | Resumes the Discharging schedule  |
| setChargeTarget         | {"chargeToPercent":"50"}  | Sets the Target charge SOC |
| setBatteryReserve|{"dischargeToPercent":"5"}| Sets the Battery Reserve discharge cut-off limit|
| setChargeSlot1|{"start":"0100","finish":"0400","chargeToPercent":"55")| Sets the time and target SOC of the first chargeslot. Times must be expressed in hhmm format. Enable flag show in the battery.api documentation is not needed |
| setDischargeSlot1|{"start":"0100","finish":"0400","dischargeToPercent":"55")| Sets the time and target SOC of the first dischargeslot. Times must be expressed in hhmm format. Enable flag show in the battery.api documentation is not needed |
| setDischargeSlot2|{"start":"0100","finish":"0400","dischargeToPercent":"55")| Sets the time and target SOC of the first dischargeslot. Times must be expressed in hhmm format.  Enable flag show in the battery.api documentation is not needed |
|setBatteryMode|{"mode":"1"}| Sets battery operation mode. Mode value must be in the range 1-4|

The full call to set  Charge Timeslot 1 would then be:

`python3 write.py setChargeSlot1 '{"enable": true,"start": "0100","finish": "0400","chargeToPercent": "100"}'`

Not sure where to start? Check our [Quick Start Guide](/documentaion/tutorial.md)

[Some API Documentation](/documentaion/APIDocumentation.md)

[All the used registers are listed in here ](/documentaion/registersAndFunctions.xlsb.xlsx)
