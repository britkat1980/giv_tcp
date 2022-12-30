# GivTCP
## TCP Modbus connection to MQTT/JSON for Givenergy Battery/PV Invertors

This project allows connection to the GivEnergy invertors via TCP Modbus. Access is through the native Wifi/Ethernet dongle and can be connected to through either the local LAN network or directly through the inbuilt SSID AP.

In basis of this project is a connection to a Modbus TCP server which runs on the wifi dongle, so all you need is somewhere to run the script on the same network. You will need the following to make it work:
* GivEnergy Invertor properly commissioned and working
* IP address of the invertor


## Docker
Reccomended usage is through the Docker container found here: https://hub.docker.com/repository/docker/britkat/giv_tcp-ma
This will set up a self-running service which will publish data as required and provide a REST interface for control. An internal MQTT broker can be activiated to make data avalable on the network.
  
* Docker image is multi-architecture so docker should grab the correct version for your system (tested on x86 and rpi3)
* Create a container with the relevant ENV variables below (mimicing the settings.py file)
* Set the container to auto-restart to ensure reliability
* Out of the box the default setup enables local MQTT broker and REST service (see below for details)
* For Invertor autodiscovery to function your container must run on the "Host" network within docker (not Bridge). If it fails then you will need to manually add in INVERTOR_IP to the env variables

## Home Assistant Add-on
This container can also be used as an add-on in Home Assistant.
The add-on requires an existing MQTT broker such as Mosquitto, also available to install from the Add-on store.
To install GivTCP as an add-on, add this repository (https://github.com/britkat1980/giv_tcp) to the Add-on Store repository list.
The following configuration items are mandatory before the add-on can be started:
* Inverter IP address
* MQTT username (can also be a Home Assistant user - used to authenticate againt your MQTT broker)
* MQTT password
All other configuration items can be left as-is unless you need to change them.

### Installation
The simplist installation method for GivTCP is to use the built-in self-run option which will automatically connect to your invertor and grab the data.

1. Install docker on a suitable machine which is "always on" in your network.
2. Open up your docker interface (I prefer portainer https://www.portainer.io/)
3. Navigate to "Stacks" and click "Add Stack"
4. Copy the contents of the docker-compose.yml file in this repo into the web editor pane
5. Scoll down to the "Advanced container settings" and select the Env tab
6. Edit any settings you wish. Specifically the INVERTOR_IP
   1. See the below table for other optional variables which you can also use.
7. Deploy the container

Alternatively you can run the container from the command line by downloading the docker-compose.yml file, modifying it and then run the following commmand in the same file location: "docker-compose up".

Once this has been done the container should start-up and begin publishing data to its internal MQTT broker. You can test this by using an MQTT client, such as MQTT Explorer(http://mqtt-explorer.com/) and connect using the IP address of the machine you are running docker on.

From here your invertor data is available through either MQTT or REST as described below. 

### Docker Environment Variables

| ENV Name                | Example       |  Description                      |
| ----------------------- | ------------- |  -------------------------------- |
| NUMINVERTORS | 1 | Number of invertors on the network. Currently reserved for future development. Leave it at 1 |
| INVERTOR_IP_1 |192.168.10.1 | Docker container can auto detect Invertors if running on your host network. If this fails then add the IP manually to this ENV |
| NUMBATTERIES_1 | 1 | Number of battery units connected to the invertor |
| MQTT_OUTPUT | True | Optional if set to True then MQTT_ADDRESS is required |
| MQTT_ADDRESS | 127.0.0.1 | Optional (but required if OUTPUT is set to MQTT) |
| MQTT_USERNAME | bob | Optional |
| MQTT_PASSWORD | cat | Optional |
| MQTT_TOPIC | GivEnergy/Data | Optional - default is Givenergy.<serial number>|
| LOG_LEVEL | Error | Optional - you can choose Error, Info or Debug. Output will be sent to the debug file location if specified, otherwise it is sent to stdout|
| DEBUG_FILE_LOCATION | /usr/pi/data | Optional  |
| PRINT_RAW | False | Optional - If set to True the raw register values will be returned alongside the normal data |
| SELF_RUN | True | Optional - If set to True the system will loop round connecting to invertor and publishing its data |
| SELF_RUN_LOOP_TIMER | 5 | Optional - The wait time bewtween invertor calls when using SELF_RUN |
| INFLUX_OUTPUT | False | Optional - Used to enable publishing of energy and power data to influx |
| INFLUX_TOKEN |abcdefg123456789| Optional - If using influx this is the token generated from within influxdb itself |
| INFLUX_BUCKET |giv_bucket| Optional - If using influx this is data bucket to use|
| INFLUX_ORG |giv_tcp| Optional - If using influx this is the org that the token is assigned to | 
| HA_AUTO_D | True | Optional - If set to true and MQTT is enabled, it will publish Home Assistant Auto Discovery messages, which will allow Home Assistant to automagically create all entitites and devices to allow read and control of your Invertor |
| HADEVICEPREFIX | GivTCP | Optional - Prefix to be placed in front of every Home Assistent entity created by the above |
| DAYRATE | 0.155 | Optional - Cost of your daytime energy if using Economy 7 or Octopus Go |
| NIGHTRATE | 0.155 | Optional - Cost of your night time energy if using Economy 7 or Octopus Go |
| DAYRATESTART | 04:30 | Optional - Start time of your daytime energy if using Economy 7 or Octopus Go |
| NIGHTRATESTART | 00:00 | Optional - Start time of your night time energy if using Economy 7 or Octopus Go |
| HOSTIP | 192.168.1.20 | Optional - The host IP address of your container. Required to access the web dashboard from any browser |




## GivTCP Read data

GivTCP collects all invertor and battery data through the "runAll" function. It creates a nested data structure with all data available in a structured format.
Data Elements are:
* Energy - Today and all-time Total
    * Today
    * Total
* Power - Real-time stats and power flow data
    * Power stats (eg. Import)
    * Power Flow (eg. Grid to House)
* Invertor Details - Status details such as Serial Number
* Timeslots - Charge and Discharge
* Control - Charge/Discharge rates, Battery SOC
* Battery Details - Status and real-time cell voltages
    * Battery 1
    * Battery 2
    * ...

| Function      | Description                                                                        | REST URL  |
|---------------|------------------------------------------------------------------------------------|-----------|
| getData       | This connects to the invertor, collects all data and stores a cache for publishing | /getData  |
| pubFromPickle | Retrieves data from the local cache and publishes data according to the settings   | /readData |
| RunAll        | Runs both getData and pubFromPickle to refresh data and then publish               | /runAll   |

## GivTCP Control
| Function                | Description                                                                                                                                                                                               | REST URL                 | REST payload                                               | MQTT Topic              | MQTT Payload                                               |
|-------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------|------------------------------------------------------------|-------------------------|------------------------------------------------------------|
| enableChargeTarget      | Sets   invertor to follow setChargeTarget value when charging from grid (will stop   charging when battery SOC= ChargeTarget)                                                                             | /enableChargeTarget      | {"state","enable"}                                         | enableChargeTarget      | enable                                                     |
| disableChargeTarget     | Sets   invertor to ignore setChargeTarget value when charging from grid (will   continue to charge to 100% during ChargeSlot)                                                                             | /disableChargeTarget     | {"state","enable"}                                         | disableChargeTarget     | enable                                                     |
| enableChargeSchedule    | Sets   the Charging schedule state, if disabled the battery will not charge as per   the schedule                                                                                                         | /enableChargeSchedule    | {"state","enable"}                                         | enableChargeSchedule    | enable                                                     |
| enableDischargeSchedule | Sets   the Discharging schedule state, if disabled the battery will will ignore rhe   discharge schedule and discharge as per demand (similar to eco mode)                                                | /enableDischargeSchedule | {"state","enable"}                                         | enableDischargeSchedule | enable                                                     |
| enableDischarge         | Enable/Disables Discharging to instantly pause discharging,   use 'enable' or 'disable'                                                                                                                   | /enableDischarge         | {"state","enable"}                                         | enableDischarge         | enable                                                     |
| setChargeRate           | Sets the charge power as a percentage. 100% == 2.6kW                                                                                                                                                      | /setChargeRate           | {"dischargeRate","100"}                                    | setChargeRate           | 100                                                        |
| setDischargeRate        | Sets the discharge power as a percentage. 100% == 2.6kW                                                                                                                                                   | /setDischargeRate        | {"chargeRate","100"}                                       | setDischargeRate        | 100                                                        |
| setChargeTarget         | Sets   the Target charge SOC                                                                                                                                                                              | /setChargeTarget         | {"chargeToPercent":"50"}                                   | setChargeTarget         | 50                                                         |
| setBatteryReserve       | Sets   the Battery Reserve discharge cut-off limit                                                                                                                                                        | /setBatteryReserve       | {"dischargeToPercent":"5"}                                 | setBatteryReserve       | 5                                                          |
| setChargeSlot1          | Sets   the time and target SOC of the first chargeslot. Times must be expressed in   hhmm format. Enable flag show in the battery.api documentation is not needed   and chargeToPercent is optional       | /setChargeSlot1          | {"start":"0100","finish":"0400","chargeToPercent":"55")    | setChargeSlot1          | {"start":"0100","finish":"0400","chargeToPercent":"55")    |
| setDischargeSlot1       | Sets   the time and target SOC of the first dischargeslot. Times must be expressed   in hhmm format. Enable flag show in the battery.api documentation is not   needed and dischargeToPercent is optional | /setDischargeSlot1       | {"start":"0100","finish":"0400","dischargeToPercent":"55") | setDischargeSlot1       | {"start":"0100","finish":"0400","dischargeToPercent":"55") |
| setDischargeSlot2       | Sets   the time and target SOC of the first dischargeslot. Times must be expressed   in hhmm format. Enable flag show in the battery.api documentation is not   needed and dischargeToPercent is optional | /setDischargeSlot2       | {"start":"0100","finish":"0400","dischargeToPercent":"55") | setDischargeSlot2       | {"start":"0100","finish":"0400","dischargeToPercent":"55") |
| setBatteryMode          | Sets   battery operation mode. Mode value must be in the range 1-4                                                                                                                                        | /setBatteryMode          | {"mode":"1"}                                               | setBatteryMode          | 1                                                          |
| setDateTime             | Sets   invertor time, format must be as define in payload                                                                                                                                                 | /setDateTime             | {"dateTime":"dd/mm/yyyy   hh:mm:ss"}                       | setDateTime             | "dd/mm/yyyy hh:mm:ss"                                      |

## Usage methods:
### MQTT
By setting MQTT_OUTPUT = True The script will publish directly to the nominated MQTT broker (MQTT_ADDRESS) all the requested read data.

Data is published to "GivEnergy/<serial_number>/" by default or you can nominate a specific root topic by setting "MQTT_TOPIC" in the settings.

<img width="245" alt="image" src="https://user-images.githubusercontent.com/69121158/149670766-0d9a6c92-8ee2-44d6-9045-2d21b6db7ebf.png">

Control is available using MQTT. By publishing data to the smae MQTT broker as above you can trigger the control methods as per the above table.
Root topic for control is:
"GivEnergy/<serial_number>/control/"    - Default
"<MQTT_TOPIC>/<serial_number>/control/" - If MQTT_TOPIC is set


### RESTful Service
GivTCP provides a wrapper function REST.py which uses Flask to expose the read and control functions as RESTful http calls. To utilise this service you will need to either use a WSGI serivce such as gunicorn or use the pre-built Docker container.

If Docker is running in Host mode then the REST service is available on port 6345

This can be used within a Node-Red flow to integrate into your automation or using Home Assistany REST sensors unsing the Home Assistant yaml package provided.
NB.This does require the Docker container running on your network.
