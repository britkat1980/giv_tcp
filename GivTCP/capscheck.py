"""Checks on detected capabilities before they're used or saved. Detect only finds the batteries that answer
while it runs, so one that times out then saves an inverter with fewer (or no) batteries, which are never
polled again"""
from givenergy_modbus.model.inverter import Model

# Models with built-in batteries, so detecting none means they didn't answer, not that there are none. The All in One
# has 4 packs; the All in One-HY 4, 8 or 12, on 1-3 BCUs
BUILT_IN_BATTERY_MODELS=(Model.ALL_IN_ONE, Model.ALL_IN_ONE_HYBRID)

def capsBatteryCount(caps):
    # v2's number_batteries only counts LV batteries; HV/three-phase/AIO batteries are modules
    return max(len(caps.lv_battery_addresses), sum(n for _,n in caps.bcu_stacks), len(caps.aio_battery_module_addresses), len(caps.hv_bmu_addresses))

def missingBatteries(caps):
    # True for a model that always has batteries but whose capabilities have none
    return getattr(caps,'device_type',None) in BUILT_IN_BATTERY_MODELS and capsBatteryCount(caps)==0

def batteryDevices(caps):
    # Each kind of battery device, counted separately, so one pack that didn't answer on a BCU that did is noticed
    return (len(caps.lv_battery_addresses), len(caps.bcu_stacks), sum(n for _,n in caps.bcu_stacks),
            len(caps.aio_battery_module_addresses), len(caps.hv_bmu_addresses))

def lostBatteries(new, saved):
    # True if a detect found fewer of any kind of battery device than the saved capabilities for the same model
    return (getattr(new,'device_type',None) is not None and getattr(saved,'device_type',None)==new.device_type
            and any(n<s for n,s in zip(batteryDevices(new), batteryDevices(saved))))
