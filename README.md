# GivTCP
## TCP Modbus connection to MQTT/JSON for GivEnergy Battery/PV Invertors

This project opens a connection to the GivEnergy invertors via TCP Modbus. Access is given through the native Wifi/Ethernet dongle and can be connected via either LAN or directly through the inbuilt SSID AP.

Typically run through the Home Assistant Addon, it is also possible to run as a standalone docker container. 

## Home Assistant Add-on
This container can also be used as an add-on in Home Assistant.
The add-on requires an existing MQTT broker such as Mosquito, also available to install from the Add-on store.
To install GivTCP as an add-on, add this repository (https://github.com/britkat1980/giv_tcp) to the Add-on Store repository list.

### Home Assistant Usage
GivTCP will automatically create Home Assistant devices if "HA_AUTO_D" setting is True. This does require MQTT_OUTPUT to also be true and for GivTCP to publish its data to the same MQTT broker as HA is listening to.
This will populate HA with all devices and entities for control and monitoring. The key entities and their usage are outlined below:

The Home Assistant Addon config page outlines the configuration environmental variables for set-up of GivTCP

If you have enabled the "SELF_RUN" setting (recommended) then the container/add-on will automatically call "RunALL" every "SELF_LOOPTIMER" seconds and you will not need to use the REST commands here. If you wish to take data from GivTCP and push to another system, then you should call "getCache" which will return the json data without pushing to MQTT or other defined publish settings.

## GivTCP Control
| Function                | Description                                                                                                                                                                                               | REST URL                 | REST payload                                               | MQTT Topic              | MQTT Payload                                               |
|-------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------|------------------------------------------------------------|-------------------------|------------------------------------------------------------|
| enableChargeTarget      | Sets   inverter to follow setChargeTarget value when charging from grid (will stop   charging when battery SOC= ChargeTarget)                                                                             | /enableChargeTarget      | {"state","enable"}                                         | enableChargeTarget      | enable                                                     |
| disableChargeTarget     | Sets   inverter to ignore setChargeTarget value when charging from grid (will   continue to charge to 100% during ChargeSlot)                                                                             | /disableChargeTarget     | {"state","enable"}                                         | disableChargeTarget     | enable                                                     |
| enableChargeSchedule    | Sets   the Charging schedule state, if disabled the battery will not charge as per   the schedule                                                                                                         | /enableChargeSchedule    | {"state","enable"}                                         | enableChargeSchedule    | enable                                                     |
| enableDischargeSchedule | Sets   the Discharging schedule state, if disabled the battery will ignore the    discharge schedule and discharge as per demand (similar to eco mode)                                                | /enableDischargeSchedule | {"state","enable"}                                         | enableDischargeSchedule | enable                                                     |
| enableDischarge         | Enable/Disables Discharging to instantly pause discharging,   use 'enable' or 'disable'                                                                                                                   | /enableDischarge         | {"state","enable"}                                         | enableDischarge         | enable                                                     |
| setChargeRate           | Sets the charge power as a percentage. 100% == 2.6kW                                                                                                                                                      | /setChargeRate           | {"chargeRate","100"}                                    | setChargeRate           | 100                                                        |
| setDischargeRate        | Sets the discharge power as a percentage. 100% == 2.6kW                                                                                                                                                   | /setDischargeRate        | {"dischargeRate","100"}                                       | setDischargeRate        | 100                                                        |
| setChargeTarget         | Sets   the Target charge SOC                                                                                                                                                                              | /setChargeTarget         | {"chargeToPercent":"50"}                                   | setChargeTarget         | 50                                                         |
| setBatteryReserve       | Sets   the Battery Reserve discharge cut-off limit                                                                                                                                                        | /setBatteryReserve       | {"reservePercent":"5"}                                 | setBatteryReserve       | 5                                                          |
| setChargeSlot1          | Sets   the time and target SOC of the first chargeslot. Times must be expressed in   hhmm format. Enable flag show in the battery.api documentation is not needed   and chargeToPercent is optional       | /setChargeSlot1          | {"start":"0100","finish":"0400","chargeToPercent":"55"}    | setChargeSlot1          | {"start":"0100","finish":"0400","chargeToPercent":"55"}    |
| setDischargeSlot1       | Sets   the time and target SOC of the first dischargeslot. Times must be expressed   in hhmm format. Enable flag show in the battery.api documentation is not   needed and dischargeToPercent is optional | /setDischargeSlot1       | {"start":"0100","finish":"0400","dischargeToPercent":"55"} | setDischargeSlot1       | {"start":"0100","finish":"0400","dischargeToPercent":"55"} |
| setDischargeSlot2       | Sets   the time and target SOC of the first dischargeslot. Times must be expressed   in hhmm format. Enable flag show in the battery.api documentation is not   needed and dischargeToPercent is optional | /setDischargeSlot2       | {"start":"0100","finish":"0400","dischargeToPercent":"55"} | setDischargeSlot2       | {"start":"0100","finish":"0400","dischargeToPercent":"55"} |
| setBatteryMode          | Sets   battery operation mode. Mode value must be one of Eco, Timed Demand or Timed Export                                                                                                                                        | /setBatteryMode          | {"mode":"Eco"}                                               | setBatteryMode          | 1                                                          |
| setDateTime             | Sets   inverter time, format must be as define in payload                                                                                                                                                 | /setDateTime             | {"dateTime":"dd/mm/yyyy   hh:mm:ss"}                       | setDateTime             | "dd/mm/yyyy hh:mm:ss"                                      |

## Usage methods:
GivTCP data and control is generally available through two core methods. If you are using the Home Assistant Add-On then these are generally transparent to the user, but are working and available in the background.

### MQTT
By setting MQTT_OUTPUT = True, the script will publish directly to the nominated MQTT broker (MQTT_ADDRESS) all the requested read data.

Data is published to "GivEnergy/<serial_number>/" by default or you can nominate a specific root topic by setting "MQTT_TOPIC" in the settings.

<img width="245" alt="image" src="https://user-images.githubusercontent.com/69121158/149670766-0d9a6c92-8ee2-44d6-9045-2d21b6db7ebf.png">

Control is available using MQTT. By publishing data to the same MQTT broker as above you can trigger the control methods as per the above table.
Root topic for control is:
"GivEnergy/control/<serial_number>/"    - Default
"<MQTT_TOPIC>/control/<serial_number>/" - If MQTT_TOPIC is set

### RESTful Service
GivTCP provides a wrapper function REST.py which uses Flask to expose the read and control functions as RESTful http calls. To utilise this service you will need to either use a WSGI service such as gunicorn or use the pre-built Docker container.

If Docker is running in Host mode then the REST service is available on port 6345

#### GivTCP Read data

GivTCP collects all inverter and battery data and creates a nested data structure with all data available in a structured format.

| Function      | Description                                                                        | REST URL  |
|---------------|------------------------------------------------------------------------------------|-----------|
| getData       | This connects to the inverter, collects all data and stores a cache for publishing | /getData  |
| readData      | Retrieves data from the local cache and publishes data according to the settings   | /readData |
| getCache      | Retrieves data from the local cache returns it without publishing to MQTT etc...   | /getCache |
| RunAll        | Runs both getData and pubFromPickle to refresh data and then publish               | /runAll   |

## Web Dashboard

You can enable the built-in web dashboard if you'd like a way to visualise data for your inverter(s). For more details
please see the [ReadMe file in the separate repository](https://github.com/DanielGallo/GivEnergy-Smart-Home-Display/).

![Dashboard-Example-Landscape.png](graphics/Dashboard-Example-Landscape.png)

The web dashboard is able to summarise data for a single inverter, or multiple inverters in either a single-phase 
or three-phase environment.

If you have any issues or feedback regarding the web dashboard, please post a question or issue [here](https://github.com/DanielGallo/GivEnergy-Smart-Home-Display/issues).

# GivEVC

## GivEnergy Electric Vehicle Charger

From version 2.4 onwards GivTCP incorporates control and monitoring of the GE charger. Connecting via local modbus it can monitor real-time stats and provide simple control features. With the EVC cloud conrol does not use the modbus protocol, so there is minimal opportunity for changes to reflect in the official app/cloud portal. Particularly the Charging modes, which are merely mimiced in GivEVC

## Configuration

All that is required for config are the IP address and the self run timer. Setting EVC_ENABLE to True will turn on the function.

## Control

Most controls are self explanatory but some require clarification on their function:

### Plug and Go: 
When turned on the vehicle will start to charge as soon as it is plugged in. When off charging will commence when triggered by RFID card or "Charge Control"

### Charge Control:
This starts and stops vehicle charging, when "Plug and Go" is on.

### Charging Mode:
Mimcs the cloud based "modes" of charging.

#### Grid
Charges at current set by "Charge Limit", regardless of what energy is available (typically will pull from Grid)

#### Solar
Modulates the Charge Limit based on the amount of "excess solar" available after serving the current house Load. This requires minimum of 1.4kW (6A) excess as required by the EVSE spec.

#### Hybrid
This will modulate Charge Limit to top up a base 6A grid charge with any excess solar energy. Similar to Solar but uses a constant 6A from Grid plus additional solar energy on top.

### Max Session Energy
This will cap the maximum energy delivered to the vehicle in a single charge session. Setting this to 0kWh disables this setting.

### Import Cap
This will monitor the Grid current from the first GivTCP inverter and if it is within 5% of the Import Cap setting it will reduce EVC Charge current to stay 10% under the import Cap. Setting this to 0A disables this setting.
