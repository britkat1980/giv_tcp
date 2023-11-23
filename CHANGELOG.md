
# Change Log
All notable changes to this project will be documented in this file.
 
The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [2.4.2] - 2023-11-23
### Fixed
- PALM fix
- givenergy-modbus fix for time-based register errors

## [2.4.1] - 2023-11-05
### Fixed
- Fixed settigs error (LOAD_HIST_WEIGHT) for PALM

## [2.4.0] - 2023-11-04
### Fixed
- Enhanced Startup script with better uto discovery of Inverters and EVC
- PR #119 thanks to @gcoan
- Enable long term stats PR #103 thanks to @ajcollins

### Added
- GiVEVC: Ability to connect to GivEnergy EV Chargers. Monitoring and control (see Readme)
- GivTCP version published in MQTT
- GUI for configuration (not yet released)
- Nginx proxy to combine all web frontends via single port (8099)
  - REST can also be found at IPADDRESS:8099/REST1/ and REST2/ etc... for each inverter
  - Web dashboard can be accessed at IPADDRESS:8099/dashboard
- PALM 1.1.0 updated

## [2.3.3] - 2023-08-06
### Fixed
- Fixed PALM error
- Enabled long term stats for sensors. Thanks @ajcollins
- Changed default setting for "old firmware" to True. 


## [2.3.2] - 2023-07-31
### Fixed
- Fixed "SuperTimezone" error occuring on Docker installations
- Fixed PALM ge.batcap error
- Fix Chargeslot start register offset error


## [2.3.1] - 2023-07-30
### Fixed
- REST api fixed to correct (dis)charge timeslot error
- Corrected Config page to clarify the Inverter_AC_X setting applies to all inverters on "old" firmware

### Added
- Inverter frequency stats added
- PALM updated to v1.0.0, imporving Smart Target (Thanks @salewis38)


## [2.3] - 2023-07-29
### Breaking Change
- Inverter_Max_Rate now called Inverter_Max_Bat_Rate

### Fixed
- Upped maxBatPower to 8000 to account for AIO
- fix for Eco mode setting (when moving from Eco (Paused)) Thanks Ed-M72
- MQTT fix for retained topics (Thanks BrianUK6)
- Improved monitoring of failed write commands and associated logging
- soc_kWh state_class changed to 
- Inverter Scanning improved to determine inverter type pre-config (doesn't affect config yet...)
- Setting Charge Target to values below 4 or above 100 now force those max/min values
- Day/Night costs fixed
- Export rate now updates when ENV/Config is set
- 
### Added
- New Controls available for beta firmware:
  - Local Control Mode: Sets priority for Battery, Grid or Load
  - PV Input Mode: Sets MPPT tracking to 1x2 or Independent
  - Battery Pause Mode: Forces pause of Charge, Discharge or Both
  - Gen2 inverters now have access to 10 charge and discharge slots
- Inverter_Max_Inv_Rate added as new "Inverter Details" entity
- New ENV/Config item Inverter_AC_X - Only turn this on if you have an AC inverter on "old" firmware and you get errors on startup 
- MQTT changes to cope properly when run in docker (and not in Addon/HA)

## [2.2.4] - 2023-07-14
### Fixed
- Fixed Temp Pause Charge and Temp Pause Discharge selct controls, which weren't reverting
- Fixed Influxdb string error

## [2.2.3] - 2023-07-03
### Fixed
- Fixed Charge_time_remaining device_class error

## [2.2.2] - 2023-07-03
### Fixed
- Fixed charge target bug (Thanks S0ckhamster)

## [2.2.1] - 2023-06-29
### Fixed
- Invertor Mode calculation
- Fixed Inverer Time entity
### Added
- Work in progress compatability with the new GE AIO device (no battery data yet) - Beta testers needed
- New battery power mode switch (replicates the GE Portal "Eco" switch)


## [2.2.0] - 2023-06-28
### Fixed
- Type error in MQTT publishing handled gracefully
- Grid Current scaling factor corrected (x10)
### Added
- Updated SmartTarget to PALM 0.10.0 (Thanks Steve Lewis)
- Charge and Discharge time remaining entities (mins till full charge/discharge at current power rate) and absolute time to hit Target SOC/Battery Reserve
- Gen 3 invertors now recognised
- MQTT Auto recognition. If using the Mosquitto addon in HA it will now auto connect, removing need for MQTT configuration before running
- Refactored Write.py to always use the Redis Queue, to remove contention on modbus comms and create more reliable control signals
- Configurable retries on write commands to allow for installations with less reliable comms (Thanks @Ed-M72)
- Modified givenergy-modbus library to allow single timeslot control, to allow better integration with select controls in HA
- Individual timeslot start/end control, to remove race condition for setting start and end together
  
## [2.1.15] - 2023-06-08
### Fixed
- Fixed SmartTarget error for solcast calls with a single array

## [2.1.14] - 2023-06-05
### Fixed
- REST /getCache endpoint fixed (incorrect json format)
- Minor updates to README.md documentation
- Refactored Force Export to use queuing for more reliable revert
### Added
- Updated SmartTarget to PALM 0.8.5 (Thanks Stephen Lewis)

## [2.1.13] - 2023-05-13
### Fixed
- REST /getCache endpoint fixed (incorrect json format)
- Minor updates to README.md documentation
- Refactored Force Export to use queing for more reliable revert
### Added
- Updated SmartTarget to PALM 0.8.5 (Thanks Stephen Lewis)

## [2.1.13] - 2023-05-13
### Fixed
- Reverting entity naming to include serial number for compatability
### Added
- Reboot Invertor function

## [2.1.12] - 2023-05-13
### Fixed
- HA Invertor time device_class error removed
- Fixed Timed Export & Revert Export Settings (Thanks @Ed-M72)
- Timed Discharge and Force Export no longer set soc_reserve to 100 (which stopped discharge)

## [2.1.11] - 2023-05-07
### Fixed
- HA discovery message error fixed for string variables (Thanks @metalblue)
- Restructure config variables for ease of use (thanks @S0ckhamster)
- Improved handling of Timed Demand mode handing (Thanks @Ed-M72)

## [2.1.10] - 2023-04-30
### Fixed
- HADEVICEPREFIX config variables added for second and third invertors for HA Addon deployment

## [2.1.9] - 2023-04-30
### Fixed
- Updated max mppt pv voltage to match datasheet (550v)
- Remove Data Smoothing from SOC to prevent getting stuck on values below 4%
- Set Rate data points to GBP/kWh
- Dual site IDs now working for Solcast/PALM (Thanks to s0ckhamster)

### Added
- HA Device Prefix per Invertor (use the "_X" suffix )
- Retain Rate Data across reboots/updates (if data is from today)
- PALM settings now handled via ENV (Thanks to s0ckhamster)
- Entity Friendly names no longer use Serial Number

## [2.1.7] - 2023-03-10
### Fixed
- Updated max mppt pv voltage to match datasheet (550v)

## [2.1.3] - 2023-03-04
### Fixed
- modified givenergy-modbus library to calulate inverter type from registers, not from serial number
- Fixed day/Night rate stability in dynamic mode

## [2.1.3] - 2023-02-12
### Fixed
- Fixed error on garbage invertor output
- Fixed Force Charge/Export power rate setting from 100(%) to maxInvertorRate

### Added
- Per Invertor MQTT Topic now available
- Overlapping ForceCharge\Export now handled gracefully. You can extend a current Force action byt recalling it with a new duration and it will set a new Force end time

## [2.1.2] - 2023-02-09

### Added
- Charge and Discharge rates now use absolute power values (2600W) not percentage (100%) to align with Cloud portal and to give correct operation
- Prevented the REST readData call (pubFromPickle) from triggering another read 
 
### Fixed
- Worked on race conditions by using critical sections to replace file locks
- Fix select entities error when setting to a non-float value

### Added
- Changed logging levels so that Info now just shows which operations are called and everything else is Debug
- Force Charge, Force Export and Temp Pause controls now allow you to Cancel, reverting to preious settings immediately
- Updated Battery Reserve and Cut-off entities to correctly reflect invertor behaviour
- Updated Redis scheduling for control lockout
- Added "None" as a smoothing option
- Added invertor firmware to output
- Allow dynamic Day/Night energy slots as well as fixed time (Go vs Intelligent) New "select" entity created to allow external automations to change rate (DYNAMICTARIFF ENV can be set to true to ignore day/night ENV and change rates based on the value of the Select entity)
- Ability to accept dual array installations for Solcast Smart Target (new ENV) 


## [2.0.1] - 2022-09-18
 
Update to GivLUT to allow battery max power to go up to 4000w to account for Gen2 invertors

## [2.0.0rc2] - 2022-09-17
 
Major update including various stability fixes and new features
 
### Added
- Force Export boost function (and restore)
- Force Charge boost function (and restore)
- Temporary charge and discharge pause (and restore)
- Change timeslot start and end
- All new control functions are avalable via:
  - Select devices (Home assistant)
  - MQTT Topic
  - REST

- Smart target charge using Solcast forecast and load energy stats. Thanks to [Stephen Lewis](https://github.com/salewis38/palm)
  - Only avaiable in docker container or Home Assistant Addon

- User defined port for web dashboard. Thanks to [Dan Gallo](https://github.com/DanielGallo/GivEnergy-Smart-Home-Display/tree/givtcp)
  - Only avaiable in docker container or Home Assistant Addon

- Data smoothing across energy and battery data (not power)
- log to file by default
- Cache data stored in user defined folder. Useful to delete in the event of problems 

#### New ENV
- CACHELOCATION="/config/GivTCP" - if using Home assistant addon, make sure this starts with /config
- DATASMOOTHER="High" - High, medium or low. Level of aggression on smoothing large jumps in data
- SMARTTARGET=True - If True, then the three below ENV must be set. This will update your Target SOC 20mins before it is due to start charging
- GEAPI="" - API key from your GE account
- SOLCASTAPI="" - Solcast API key 
- SOLCASTSITEID="" - Solcast site ID
- DEBUG_FILE_LOCATION - has been removed

### Changed
- Re-structred the lookup tables into single class
- Data structure for all data points using new class type
- Logging to file now uses a rotating file handler and will keep 7 days of logs
- Underlying [givenergy-modbus](https://github.com/dewet22/givenergy-modbus) errors supressed in logging
- Mode control now automatically updates (dis)charge schedule as appropriate
### Fixed
- Obey Print Raw ENV
- Midnight data sticking for Energy Today stats
- many more...
