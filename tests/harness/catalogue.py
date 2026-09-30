"""Every control GivTCP offers, with sample payloads, for each entry point.

Each case is a list of steps run in order from the same starting state (most cases have one step; the Cancel
cases start the thing they cancel first). test_catalogue_coverage.py fails if GivTCP gains a write function,
REST route or MQTT topic that isn't listed here, so new controls get tested on every device model.
"""

def _id(name, value):
    return "%s(%s)" % (name, value)

# --- write.py functions, called as the read loop calls them: func(device, payload, readloop=True) -----------

DIRECT = {}

def _direct(command, *payloads):
    for payload in payloads:
        DIRECT[_id(command, payload)] = [(command, payload)]

for _command in ("enableChargeTarget", "enableChargeSchedule", "enableDischargeSchedule", "enableRTC", "setEcoMode",
                 "setForceCharge", "setForceDischarge", "setACCharge", "setEmsPlant"):
    _direct(_command, {"state": "enable"}, {"state": "disable"})
_direct("setChargeTarget", {"chargeToPercent": "85"})
_direct("setChargeTarget2", {"chargeToPercent": "85", "slot": 1}, {"chargeToPercent": "85", "slot": 2},
        {"chargeToPercent": "85", "slot": 10}, {"chargeToPercent": "85", "slot": 1, "EMS": True})
_direct("setExportTarget", {"exportToPercent": "30", "slot": "1"})
_direct("setDischargeTarget", {"dischargeToPercent": "30", "slot": "1"}, {"dischargeToPercent": "30", "slot": "10"})
_direct("setExportLimit", {"state": "3600"})
_direct("setCarChargeBoost", {"boost": "2500"})
_direct("setBatteryReserve", {"reservePercent": "20"}, {"reservePercent": "2"})
_direct("setBatteryCutoff", {"dischargeToPercent": "10"})
_direct("setActivePowerRate", {"activePowerRate": "80"})
_direct("setChargeRate", {"chargeRate": "2500"}, {"chargeRate": "99999"})
_direct("setDischargeRate", {"dischargeRate": "2500"})
_direct("setChargeRateAC", {"chargeRate": "75"})
_direct("setDischargeRateAC", {"dischargeRate": "75"})
_direct("setChargeSlot", {"start": "01:30", "finish": "04:30", "slot": "1", "chargeToPercent": "90"},
        {"start": "01:30", "finish": "04:30", "slot": "2"})
_direct("setDischargeSlot", {"start": "16:00", "finish": "19:00", "slot": "1", "dischargeToPercent": "20"},
        {"start": "16:00", "finish": "19:00", "slot": "2"})
_direct("setExportSlot", {"start": "16:00", "finish": "19:00", "slot": "1"})
_direct("setPauseSlot", {"start": "16:00", "finish": "19:00"})
for _kind in ("Charge", "Discharge", "Export"):
    _direct("set%sSlotStart" % _kind, {"start": "02:00", "slot": 1}, {"start": "02:00", "slot": 2})
    _direct("set%sSlotEnd" % _kind, {"finish": "05:00", "slot": 1}, {"finish": "05:00", "slot": 2})
_direct("setChargeSlotStart", {"start": "02:00", "slot": 1, "EMS": True})
_direct("setDischargeSlotStart", {"start": "16:00", "slot": 1, "EMS": True})
_direct("setPauseStart", {"start": "16:00"})
_direct("setPauseEnd", {"finish": "19:00"})
_direct("setBatteryMode", *({"mode": m} for m in ("Eco", "Eco (Paused)", "Timed Demand", "Timed Export")))
_direct("setBatteryPauseMode", *({"state": s} for s in ("Disabled", "PauseCharge", "PauseDischarge", "PauseBoth")))
_direct("setLocalControlMode", *({"state": s} for s in ("Load", "Battery", "Grid")))
_direct("setBatteryCalibration", *({"state": s} for s in ("Off", "Start", "Charge Only")))
_direct("setDateTime", {"dateTime": "01/01/2026 12:00:00"})
_direct("syncDateTime", {"state": "enable"})
_direct("forceCharge", 30)
_direct("forceExport", 30)
_direct("tempPauseCharge", 30)
_direct("tempPauseDischarge", 30)
_direct("rebootinverter", {})
_direct("enableDischarge", {"state": "enable"}, {"state": "disable"})
_direct("setPVInputMode", {"state": "1x2"})
_direct("switchRate", "day")
# The revert jobs these queue are run later by the RQ worker via queueWrite: run them with what was queued
DIRECT["forceCharge(30) then FCResume"] = [("forceCharge", 30), ("FCResume", "@job")]
DIRECT["forceExport(30) then FEResume"] = [("forceExport", 30), ("FEResume", "@job")]
DIRECT["tempPauseCharge(30) then tmpPCResume"] = [("tempPauseCharge", 30), ("tmpPCResume", "@job")]
DIRECT["tempPauseDischarge(30) then tmpPDResume"] = [("tempPauseDischarge", 30), ("tmpPDResume", "@job")]

# write.py functions that aren't controls, or aren't safe to run here
DIRECT_SKIP = {
    "rebootAddon": "restarts the add-on through the Supervisor",
    "sbcla": "helper for the rate commands", "sbdla": "helper for the rate commands",
    "cancelJob": "takes a job id, covered by the Cancel cases via REST and MQTT",
}

# --- REST: POST route -> JSON payload ---------------------------------------------------------------------

REST = {}

def _rest(route, *payloads):
    for payload in payloads:
        REST[_id(route, payload)] = [(route, payload)]

for _route in ("/enableChargeTarget", "/enableChargeSchedule", "/enableDischargeSchedule", "/enableDischarge",
               "/setEcoMode", "/setForceCharge", "/setForceDischarge", "/setACCharge", "/setEmsPlant"):
    _rest(_route, {"state": "enable"}, {"state": "disable"})
_rest("/setChargeTarget", {"chargeToPercent": "85"})
_rest("/setExportTarget", {"exportToPercent": "30", "slot": "1"})
_rest("/setDischargeTarget", {"dischargeToPercent": "30", "slot": "1"})
_rest("/setBatteryReserve", {"reservePercent": "20"})
_rest("/setBatteryCutoff", {"dischargeToPercent": "10"})
_rest("/setChargeRateAC", {"chargeRate": "75"})
_rest("/setChargeRate", {"chargeRate": "2500"})
_rest("/setCarChargeBoost", {"boost": "2500"})
_rest("/setExportLimit", {"state": "3600"})
_rest("/setDischargeRateAC", {"dischargeRate": "75"})
_rest("/setDischargeRate", {"dischargeRate": "2500"})
_rest("/setPauseSlot", {"start": "16:00", "finish": "19:00"})
_rest("/setChargeSlot", {"start": "01:30", "finish": "04:30", "slot": "1", "chargeToPercent": "90"})
for _n in (1, 2, 3):
    _rest("/setChargeSlot%d" % _n, {"start": "01:30", "finish": "04:30", "chargeToPercent": "90"})
    _rest("/setDischargeSlot%d" % _n, {"start": "16:00", "finish": "19:00", "dischargeToPercent": "20"})
    _rest("/setExportSlot%d" % _n, {"start": "16:00", "finish": "19:00"})
_rest("/setDischargeSlot", {"start": "16:00", "finish": "19:00", "slot": "1", "dischargeToPercent": "20"})
for _route in ("/forceCharge", "/forceExport", "/tempPauseCharge", "/tempPauseDischarge"):
    _rest(_route, {"duration": "30"})
    REST[_id(_route, "Cancel")] = [(_route, {"duration": "30"}), (_route, {"duration": "Cancel"})]
_rest("/setBatteryMode", *({"mode": m} for m in ("Eco", "Eco (Paused)", "Timed Demand", "Timed Export")))
_rest("/setBatteryPauseMode", *({"state": s} for s in ("Disabled", "PauseCharge", "PauseDischarge", "PauseBoth")))
_rest("/setDateTime", {"dateTime": "01/01/2026 12:00:00"})
_rest("/syncDateTime", {"state": "enable"})
_rest("/switchRate", {"rate": "day"})
_rest("/setBatteryCalibration", *({"state": s} for s in ("Off", "Start", "Charge Only")))
_rest("/reboot", {})

# POST routes that aren't inverter controls
REST_SKIP = {
    "/settings": "saves GivTCP's settings",
    "/restart": "restarts the add-on through the Supervisor",
    "/setImportCap": "EVC", "/setCurrentLimit": "EVC", "/setChargeControl": "EVC", "/setChargeMode": "EVC",
    "/setChargingMode": "EVC", "/setMaxSessionEnergy": "EVC",
}

# --- MQTT: control topic (the last part of <MQTT_Topic>/control/<serial>/<topic>) -> message payload -------

MQTT = {}

def _mqtt(topic, *payloads):
    for payload in payloads:
        MQTT[_id(topic, payload)] = [(topic, payload)]

for _topic in ("enableChargeTarget", "enableChargeSchedule", "enableDischargeSchedule", "enableDischarge", "enableRTC",
               "setEcoMode", "setForceCharge", "setForceDischarge", "setACCharge", "setEmsPlant"):
    _mqtt(_topic, "enable", "disable")
_mqtt("setChargeRate", "2500")
_mqtt("setDischargeRate", "2500")
_mqtt("setChargeRateAC", "75")
_mqtt("setDischargeRateAC", "75")
_mqtt("setActivePowerRate", "80")
_mqtt("setChargeTarget", "85")
for _n in range(1, 11):
    _mqtt("setChargeTarget%d" % _n, "85")
    _mqtt("setDischargeTarget%d" % _n, "30")
    _mqtt("setChargeStart%d" % _n, "02:00:00")
    _mqtt("setChargeEnd%d" % _n, "05:00:00")
    _mqtt("setDischargeStart%d" % _n, "16:00:00")
    _mqtt("setDischargeEnd%d" % _n, "19:00:00")
for _n in (1, 2, 3):
    _mqtt("setEMSChargeTarget%d" % _n, "85")
    _mqtt("setEMSChargeStart%d" % _n, "02:00:00")
    _mqtt("setEMSChargeEnd%d" % _n, "05:00:00")
    _mqtt("setEMSDischargeStart%d" % _n, "16:00:00")
    _mqtt("setEMSDischargeEnd%d" % _n, "19:00:00")
    _mqtt("setExportStart%d" % _n, "16:00:00")
    _mqtt("setExportEnd%d" % _n, "19:00:00")
    _mqtt("setExportTarget%d" % _n, "30")
_mqtt("setBatteryReserve", "20")
_mqtt("setBatteryCutoff", "10")
_mqtt("setBatteryMode", "Eco", "Eco (Paused)", "Timed Demand", "Timed Export")
_mqtt("setBatteryPauseMode", "Disabled", "PauseCharge", "PauseDischarge", "PauseBoth")
_mqtt("setLocalControlMode", "Load", "Battery", "Grid")
_mqtt("setPVInputMode", "Independent", "1x2")
_mqtt("setBatteryCalibration", "Off", "Start", "Charge Only")
_mqtt("setCarChargeBoost", "2500")
_mqtt("setExportLimit", "3600")
_mqtt("setDateTime", "01/01/2026 12:00:00")
_mqtt("syncDateTime", "enable")
_mqtt("setPauseStart", "16:00:00")
_mqtt("setPauseEnd", "19:00:00")
_mqtt("switchRate", "day")
_mqtt("rebootInverter", "")
for _topic in ("forceCharge", "forceExport", "tempPauseCharge", "tempPauseDischarge"):
    _mqtt(_topic, "30")
    MQTT[_id(_topic, "Cancel")] = [(_topic, "30"), (_topic, "Cancel")]

MQTT_SKIP = {
    "testCommand": "development only",
    "rebootAddon": "restarts the add-on through the Supervisor",
    "chargeMode": "EVC", "controlCharge": "EVC",
}
