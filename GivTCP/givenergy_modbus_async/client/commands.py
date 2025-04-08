"""High-level methods for interacting with a remote system.

Note that these don't actually send requests to the inverter.
They simply prepare lists of requests that need to be sent using
the client.
"""

from datetime import datetime
from typing import Optional
from typing_extensions import deprecated  # type: ignore[attr-defined]

from ..model import TimeSlot
from ..model.register import BatteryPauseMode
from ..model.inverter import Inverter
from ..pdu import (
    ReadHoldingRegistersRequest,
    ReadInputRegistersRequest,
    ReadMeterProductRegistersRequest,
    TransparentRequest,
    WriteHoldingRegisterRequest,
)

# TODO: This list is deprecated. Use write_named_register() to find the
# register number from the master list in the inverter and perform
# validity checks.


class RegisterMap:
    """Mapping of holding register function to location."""

    ENABLE_CHARGE_TARGET = 20
    ECO_MODE = 27
    SOC_FORCE_ADJUST = 29
    CHARGE_SLOT_2_START = 31
    CHARGE_SLOT_2_END = 32
    SYSTEM_TIME_YEAR = 35
    SYSTEM_TIME_MONTH = 36
    SYSTEM_TIME_DAY = 37
    SYSTEM_TIME_HOUR = 38
    SYSTEM_TIME_MINUTE = 39
    SYSTEM_TIME_SECOND = 40
    DISCHARGE_SLOT_2_START = 44
    DISCHARGE_SLOT_2_END = 45
    ACTIVE_POWER_RATE = 50
    DISCHARGE_SLOT_1_START = 56
    DISCHARGE_SLOT_1_END = 57
    ENABLE_DISCHARGE = 59
    CHARGE_SLOT_1_START = 94
    CHARGE_SLOT_1_END = 95
    ENABLE_CHARGE = 96
    BATTERY_SOC_RESERVE = 110
    TPH_BATTERY_SOC_RESERVE = 1109
    BATTERY_CHARGE_LIMIT = 111
    BATTERY_DISCHARGE_LIMIT = 112
    BATTERY_DISCHARGE_MIN_POWER_RESERVE = 114
    TPH_BATTERY_DISCHARGE_MIN_POWER_RESERVE = 1078
    CHARGE_TARGET_SOC = 116
    TPH_CHARGE_TARGET_SOC = 1111
    REBOOT = 163
    ENABLE_RTC = 166
    CHARGE_TARGET_SOC_1 = 242
    CHARGE_SLOT_2_START = 243
    CHARGE_SLOT_2_END = 244
    CHARGE_TARGET_SOC_2 = 245
    CHARGE_SLOT_3_START = 246
    CHARGE_SLOT_3_END = 247
    CHARGE_TARGET_SOC_3 = 248
    CHARGE_SLOT_4_START = 249
    CHARGE_SLOT_4_END = 250
    CHARGE_TARGET_SOC_4 = 251
    CHARGE_SLOT_5_START = 252
    CHARGE_SLOT_5_END = 253
    CHARGE_TARGET_SOC_5 = 254
    CHARGE_SLOT_6_START = 255
    CHARGE_SLOT_6_END = 256
    CHARGE_TARGET_SOC_6 = 257
    CHARGE_SLOT_7_START = 258
    CHARGE_SLOT_7_END = 259
    CHARGE_TARGET_SOC_7 = 260
    CHARGE_SLOT_8_START = 261
    CHARGE_SLOT_8_END = 262
    CHARGE_TARGET_SOC_8 = 263
    CHARGE_SLOT_9_START = 264
    CHARGE_SLOT_9_END = 265
    CHARGE_TARGET_SOC_9 = 266
    CHARGE_SLOT_10_START = 267
    CHARGE_SLOT_10_END = 268
    CHARGE_TARGET_SOC_10 = 269
    DISCHARGE_TARGET_SOC_1 = 272
    DISCHARGE_TARGET_SOC_2 = 275
    DISCHARGE_SLOT_3_START = 276
    DISCHARGE_SLOT_3_END = 277
    DISCHARGE_TARGET_SOC_3 = 278
    DISCHARGE_SLOT_4_START = 279
    DISCHARGE_SLOT_4_END = 280
    DISCHARGE_TARGET_SOC_4 = 281
    DISCHARGE_SLOT_5_START = 282
    DISCHARGE_SLOT_5_END = 283
    DISCHARGE_TARGET_SOC_5 = 284
    DISCHARGE_SLOT_6_START = 285
    DISCHARGE_SLOT_6_END = 286
    DISCHARGE_TARGET_SOC_6 = 287
    DISCHARGE_SLOT_7_START = 288
    DISCHARGE_SLOT_7_END = 289
    DISCHARGE_TARGET_SOC_7 = 290
    DISCHARGE_SLOT_8_START = 291
    DISCHARGE_SLOT_8_END = 292
    DISCHARGE_TARGET_SOC_8 = 293
    DISCHARGE_SLOT_9_START = 294
    DISCHARGE_SLOT_9_END = 295
    DISCHARGE_TARGET_SOC_9 = 296
    DISCHARGE_SLOT_10_START = 297
    DISCHARGE_SLOT_10_END = 298
    DISCHARGE_TARGET_SOC_10 = 299
    BATTERY_CHARGE_LIMIT_AC = 313
    TPH_BATTERY_CHARGE_LIMIT_AC = 1110
    BATTERY_DISCHARGE_LIMIT_AC = 314
    TPH_BATTERY_DISCHARGE_LIMIT_AC = 1108
    BATTERY_PAUSE_MODE = 318
    BATTERY_PAUSE_SLOT_START = 319
    BATTERY_PAUSE_SLOT_END = 320
    TPH_CHARGE_SLOT_1_START = 1113
    TPH_CHARGE_SLOT_1_END = 1114
    TPH_CHARGE_TARGET_SOC_1 = 242
    TPH_CHARGE_SLOT_2_START = 1115
    TPH_CHARGE_SLOT_2_END = 1116
    TPH_CHARGE_TARGET_SOC_2 = 245
    TPH_CHARGE_SLOT_3_START = 246
    TPH_CHARGE_SLOT_3_END = 247
    TPH_CHARGE_TARGET_SOC_3 = 248
    TPH_CHARGE_SLOT_4_START = 249
    TPH_CHARGE_SLOT_4_END = 250
    TPH_CHARGE_TARGET_SOC_4 = 251
    TPH_CHARGE_SLOT_5_START = 252
    TPH_CHARGE_SLOT_5_END = 253
    TPH_CHARGE_TARGET_SOC_5 = 254
    TPH_CHARGE_SLOT_6_START = 255
    TPH_CHARGE_SLOT_6_END = 256
    TPH_CHARGE_TARGET_SOC_6 = 257
    TPH_CHARGE_SLOT_7_START = 258
    TPH_CHARGE_SLOT_7_END = 259
    TPH_CHARGE_TARGET_SOC_7 = 260
    TPH_CHARGE_SLOT_8_START = 261
    TPH_CHARGE_SLOT_8_END = 262
    TPH_CHARGE_TARGET_SOC_8 = 263
    TPH_CHARGE_SLOT_9_START = 264
    TPH_CHARGE_SLOT_9_END = 265
    TPH_CHARGE_TARGET_SOC_9 = 266
    TPH_CHARGE_SLOT_10_START = 267
    TPH_CHARGE_SLOT_10_END = 268
    TPH_CHARGE_TARGET_SOC_10 = 269
    TPH_DISCHARGE_SLOT_1_START = 1118
    TPH_DISCHARGE_SLOT_1_END = 1119
    TPH_DISCHARGE_TARGET_SOC_1 = 272
    TPH_DISCHARGE_SLOT_2_START = 1120
    TPH_DISCHARGE_SLOT_2_END = 1121
    TPH_DISCHARGE_TARGET_SOC_2 = 275
    TPH_DISCHARGE_SLOT_3_START = 276
    TPH_DISCHARGE_SLOT_3_END = 277
    TPH_DISCHARGE_TARGET_SOC_3 = 278
    TPH_DISCHARGE_SLOT_4_START = 279
    TPH_DISCHARGE_SLOT_4_END = 280
    TPH_DISCHARGE_TARGET_SOC_4 = 281
    TPH_DISCHARGE_SLOT_5_START = 282
    TPH_DISCHARGE_SLOT_5_END = 283
    TPH_DISCHARGE_TARGET_SOC_5 = 284
    TPH_DISCHARGE_SLOT_6_START = 285
    TPH_DISCHARGE_SLOT_6_END = 286
    TPH_DISCHARGE_TARGET_SOC_6 = 287
    TPH_DISCHARGE_SLOT_7_START = 288
    TPH_DISCHARGE_SLOT_7_END = 289
    TPH_DISCHARGE_TARGET_SOC_7 = 290
    TPH_DISCHARGE_SLOT_8_START = 291
    TPH_DISCHARGE_SLOT_8_END = 292
    TPH_DISCHARGE_TARGET_SOC_8 = 293
    TPH_DISCHARGE_SLOT_9_START = 294
    TPH_DISCHARGE_SLOT_9_END = 295
    TPH_DISCHARGE_TARGET_SOC_9 = 296
    TPH_DISCHARGE_SLOT_10_START = 297
    TPH_DISCHARGE_SLOT_10_END = 298
    TPH_DISCHARGE_TARGET_SOC_10 = 299
    # End of duplicates
    TPH_ENABLE_RTC = 166
    AC_CHARGE_ENABLE= 1112
    FORCE_DISCHARGE_ENABLE = 1122
    FORCE_CHARGE_ENABLE = 1123
    EMS_PLANT_ENABLE = 2040
    EMS_DISCHARGE_SLOT_1_START = 2044
    EMS_DISCHARGE_SLOT_1_END = 2045
    EMS_DISCHARGE_TARGET_SOC_1 = 2046
    EMS_DISCHARGE_SLOT_2_START = 2047
    EMS_DISCHARGE_SLOT_2_END = 2048
    EMS_DISCHARGE_TARGET_SOC_2 = 2049
    EMS_DISCHARGE_SLOT_3_START = 2050
    EMS_DISCHARGE_SLOT_3_END = 2051
    EMS_DISCHARGE_TARGET_SOC_3 = 2052
    EMS_CHARGE_SLOT_1_START = 2053
    EMS_CHARGE_SLOT_1_END = 2054
    EMS_CHARGE_TARGET_SOC_1 = 2055
    EMS_CHARGE_SLOT_2_START = 2056
    EMS_CHARGE_SLOT_2_END = 2057
    EMS_CHARGE_TARGET_SOC_2 = 2058
    EMS_CHARGE_SLOT_3_START = 2059
    EMS_CHARGE_SLOT_3_END = 2060
    EMS_CHARGE_TARGET_SOC_3 = 2061
    EXPORT_SLOT_1_START = 2062
    EXPORT_SLOT_1_END = 2063
    EXPORT_TARGET_SOC_1 = 2064
    EXPORT_SLOT_2_START = 2065
    EXPORT_SLOT_2_END = 2066
    EXPORT_TARGET_SOC_2 = 2067
    EXPORT_SLOT_3_START = 2068
    EXPORT_SLOT_3_END = 2069
    EXPORT_TARGET_SOC_3 = 2070
    EXPORT_POWER_LIMIT = 2071
    CAR_CHARGE_MODE = 2072
    CAR_CHARGE_BOOST = 2073


# Helper to look up an inverter holding register by name
# and prepare a write request. Value range checking gets
# done automatically.
def write_named_register(name: str, value: int) -> TransparentRequest:
    """Prepare a request to write to a register."""
    idx = Inverter.lookup_writable_register(name, value)
    return WriteHoldingRegisterRequest(idx, value)


def refresh_additional_holding_registers(
    base_register: int,
    slave_addr: int,
    reg_count: int = 60,
) -> list[TransparentRequest]:
    """Requests one specific set of holding registers.

    This is intended to be used in cases where registers may or may not be present,
    depending on device capabilities."""
    return [
        ReadHoldingRegistersRequest(
            base_register=base_register, register_count=reg_count, slave_address=slave_addr
        )
    ]

def refresh_meter_product_registers(
    base_register: int,
    slave_addr: int,
    reg_count: int = 60,
) -> list[TransparentRequest]:
    """Requests one specific set of meter registers.

    This is intended to be used in cases where registers may or may not be present,
    depending on device capabilities."""
    return [
        ReadMeterProductRegistersRequest(
            base_register=base_register, register_count=reg_count, slave_address=slave_addr
        )
    ]

def refresh_additional_input_registers(
    base_register: int,
    slave_addr: int,
) -> list[TransparentRequest]:
    """Requests one specific set of holding registers.

    This is intended to be used in cases where registers may or may not be present,
    depending on device capabilities."""
    
    return [
        ReadInputRegistersRequest(
            base_register=base_register, register_count=60, slave_address=slave_addr
        )
    ]


def refresh_plant_data(
    complete: bool,
    number_batteries: int = 0,
    bcu_list: list[tuple] = [],
    meter_list: list[int] = [],
    slave_addr: int = 0x31,
    isHV: bool = False,
    additional_holding_registers: Optional[list[int]] = None,
    additional_input_registers: Optional[list[int]] = None,
) -> list[TransparentRequest]:
    """Refresh plant data."""

    requests: list[TransparentRequest] = [
        ReadInputRegistersRequest(
            base_register=0, register_count=60, slave_address=slave_addr
        ),
        ReadInputRegistersRequest(
            base_register=180, register_count=60, slave_address=slave_addr
        ),
    ]
    #Always grab these regs for Inverter time
    requests.append(
        ReadHoldingRegistersRequest(
            base_register=0, register_count=60, slave_address=slave_addr
        )
    )

    for i in meter_list:
        requests.append(
            ReadInputRegistersRequest(
                base_register=60, register_count=60, slave_address=0x00 + i
            )
        )

    if additional_input_registers:
        for ir in additional_input_registers:
            requests.extend(refresh_additional_input_registers(ir, slave_addr))

    if complete:
        requests.append(
            ReadHoldingRegistersRequest(
                base_register=60, register_count=60, slave_address=slave_addr
            )
        )
        requests.append(
            ReadHoldingRegistersRequest(
                base_register=120, register_count=60, slave_address=slave_addr
            )
        )

        if additional_holding_registers:
            for hr in additional_holding_registers:
                if hr == 2040:      #For EMS there are only 36 regs in the 2040 block
                    requests.extend(refresh_additional_holding_registers(hr, slave_addr,36))
                else:
                    requests.extend(refresh_additional_holding_registers(hr, slave_addr))
                

    if isHV and not number_batteries==0:    #Get Battery data from AIO/HV systems
        # Get each BCU data
        for bcu in bcu_list:
        #for bcu_num in range (number_bcus):
            requests.append(
                ReadInputRegistersRequest(
                    base_register=60, register_count=60, slave_address=0x70 + bcu[0]
                )
            )
        # Get BMU inside each BCU
            for bmu_num in range(bcu[1]):
                requests.append(
                    ReadInputRegistersRequest(
                        base_register=(60+(120*bcu[0])), register_count=60, slave_address=0x50 + bmu_num
                    )
                )
    else:
        #LV Batteries
        for i in range(number_batteries):
            requests.append(
                ReadInputRegistersRequest(
                    base_register=60, register_count=60, slave_address=0x32 + i
                )
            )
    return requests


def disable_charge_target() -> list[TransparentRequest]:
    """Removes AC SOC limit and target 100% charging."""
    return [
        WriteHoldingRegisterRequest(RegisterMap.ENABLE_CHARGE_TARGET, False),
        WriteHoldingRegisterRequest(RegisterMap.CHARGE_TARGET_SOC, 100)
    ]

def enable_charge_target() -> list[TransparentRequest]:
    """Enables AC SOC limit."""
    return [
        WriteHoldingRegisterRequest(RegisterMap.ENABLE_CHARGE_TARGET, True),
    ]

def set_ems_plant(enable:bool) -> list[TransparentRequest]:
    """Enables AC SOC limit."""
    return [
        WriteHoldingRegisterRequest(RegisterMap.EMS_PLANT_ENABLE, enable),
    ]

def set_charge_target(target_soc: int, inv_type: str="") -> list[TransparentRequest]:
    """Sets inverter to stop charging when SOC reaches the desired level. Also referred to as "winter mode"."""
    if not 4 <= target_soc <= 100:
        raise ValueError(f"Charge Target SOC ({target_soc}) must be in [4-100]%")
    # Do we want to do this enable/disable charge etc... or just set the targets?
    ret = set_enable_charge(True)
    if target_soc == 100:
        ret.extend(disable_charge_target())
    else:
        ret.append(WriteHoldingRegisterRequest(RegisterMap.ENABLE_CHARGE_TARGET, True))
        ret.append(
            WriteHoldingRegisterRequest(RegisterMap.CHARGE_TARGET_SOC, target_soc)
        )
    return ret 



def set_export_soc_target(idx: int, target_soc: int) -> list[TransparentRequest]:
    """ Sets inverter SOC targets for any charge or discharge slot
    """
    if not 4 <= target_soc <= 100:
        raise ValueError(f" Target SOC ({target_soc}) must be in [4-100]%")
    reg = (getattr(RegisterMap, f'EXPORT_TARGET_SOC_{idx}'))
    return [WriteHoldingRegisterRequest(reg, target_soc)]

def set_soc_target(discharge: bool, idx: int, target_soc: int, inv_type: str) -> list[TransparentRequest]:
    """ Sets inverter SOC targets for any charge or discharge slot
    """
    if not 4 <= target_soc <= 100:
        raise ValueError(f" Target SOC ({target_soc}) must be in [4-100]%")
    reg = (getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}{"EMS_" if "ems" in inv_type else ""}{"DIS" if discharge else ""}CHARGE_TARGET_SOC_{idx}'))
    return [WriteHoldingRegisterRequest(reg, target_soc)]


def set_charge_target_only(target_soc: int, inv_type: str="") -> list[TransparentRequest]:
    """Sets inverter to stop charging when SOC reaches the desired level on AC Charge."""
    reg=getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}CHARGE_TARGET_SOC')
    target_soc = int(target_soc)
    if not 4 <= target_soc <= 100:
        raise ValueError(f"Specified SOC Limit ({target_soc}%) is not in [0-100]%")
    return [WriteHoldingRegisterRequest(reg, target_soc)]


def set_enable_rtc(enabled: bool, inv_type: str="") -> list[TransparentRequest]:
    """Enable the Real Time Control resgister to write to EEPROM."""
    reg=getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}ENABLE_RTC')
    return [WriteHoldingRegisterRequest(reg, enabled)]



def set_enable_charge(enabled: bool, inv_type: str="") -> list[TransparentRequest]:
    """Enable the battery to charge, depending on the mode and slots set."""
    if "3ph" in inv_type:
        reqs=[WriteHoldingRegisterRequest(RegisterMap.FORCE_CHARGE_ENABLE, enabled)]
        reqs.append(WriteHoldingRegisterRequest(RegisterMap.AC_CHARGE_ENABLE, enabled))
        return reqs
    else:
        return [WriteHoldingRegisterRequest(RegisterMap.ENABLE_CHARGE, enabled)]

def set_force_charge(enabled: bool) -> list[TransparentRequest]:
    """Enable the Three Phase battery to charge, depending on the mode and slots set."""
    return [WriteHoldingRegisterRequest(RegisterMap.FORCE_CHARGE_ENABLE, enabled)]

def set_force_discharge(enabled: bool) -> list[TransparentRequest]:
    """Enable the Three Phase battery to discharge, depending on the mode and slots set."""
    return [WriteHoldingRegisterRequest(RegisterMap.FORCE_DISCHARGE_ENABLE, enabled)]

def set_ac_charge(enabled: bool) -> list[TransparentRequest]:
    """Enable the Three Phase battery to charge, depending on the mode and slots set."""
    return [WriteHoldingRegisterRequest(RegisterMap.AC_CHARGE_ENABLE, enabled)]

def set_enable_discharge(enabled: bool, inv_type: str="") -> list[TransparentRequest]:
    """Enable the battery to discharge, depending on the mode and slots set."""
    if "3ph" in inv_type:
        return [WriteHoldingRegisterRequest(RegisterMap.FORCE_DISCHARGE_ENABLE, enabled)]
    else:
        return [WriteHoldingRegisterRequest(RegisterMap.ENABLE_DISCHARGE, enabled)]


def set_inverter_reboot() -> list[TransparentRequest]:
    """Restart the inverter."""
    return [WriteHoldingRegisterRequest(RegisterMap.REBOOT, 100)]

def set_active_power_rate(target: int) -> list[TransparentRequest]:
    """Set max inverter power rate"""
    return [WriteHoldingRegisterRequest(RegisterMap.ACTIVE_POWER_RATE, target)]

def set_calibrate_battery_soc(val: int) -> list[TransparentRequest]:
    """Set the inverter to recalibrate the battery state of charge estimation.
    0- Stop
    1- Start
    3- Charge only
    """
    if val in (0,1,3):
        return [
            WriteHoldingRegisterRequest(RegisterMap.SOC_FORCE_ADJUST, val),
        ]




@deprecated("use set_enable_charge(True) instead")
def enable_charge() -> list[TransparentRequest]:
    """Enable the battery to charge, depending on the mode and slots set."""
    return set_enable_charge(True)


@deprecated("use set_enable_charge(False) instead")
def disable_charge() -> list[TransparentRequest]:
    """Prevent the battery from charging at all."""
    return set_enable_charge(False)


@deprecated("use set_enable_discharge(True) instead")
def enable_discharge() -> list[TransparentRequest]:
    """Enable the battery to discharge, depending on the mode and slots set."""
    return set_enable_discharge(True)


@deprecated("use set_enable_discharge(False) instead")
def disable_discharge() -> list[TransparentRequest]:
    """Prevent the battery from discharging at all."""
    return set_enable_discharge(False)


def set_discharge_mode_max_power() -> list[TransparentRequest]:
    """Set the battery discharge mode to maximum power, exporting to the grid if it exceeds load demand."""
    return [WriteHoldingRegisterRequest(RegisterMap.ECO_MODE, 0)]


def set_discharge_mode_to_match_demand() -> list[TransparentRequest]:
    """Set the battery discharge mode to match demand, avoiding exporting power to the grid."""
    return [WriteHoldingRegisterRequest(RegisterMap.ECO_MODE, 1)]


@deprecated("Use set_battery_soc_reserve(val) instead")
def set_shallow_charge(val: int) -> list[TransparentRequest]:
    """Set the minimum level of charge to maintain."""
    return set_battery_soc_reserve(val)


def set_battery_soc_reserve(val: int, inv_type: str="") -> list[TransparentRequest]:
    """Set the minimum level of charge to maintain."""
    # TODO what are valid values? 4-100?
    reg=getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}BATTERY_SOC_RESERVE')
    val = int(val)
    if not 4 <= val <= 100:
        raise ValueError(f"Minimum SOC / shallow charge ({val}) must be in [4-100]%")
    return [WriteHoldingRegisterRequest(reg, val)]

def set_car_charge_boost(val: int) -> list[TransparentRequest]:
    """Set the minimum level of charge to maintain."""
    # TODO what are valid values? 4-100?
    val = int(val)
    if not 0 <= val <= 22000:
        raise ValueError(f"Charge Boost power ({val}) must be in [0-22kw]%")
    return [WriteHoldingRegisterRequest(RegisterMap.CAR_CHARGE_BOOST, val)]

def set_export_limit(val: int) -> list[TransparentRequest]:
    """Set the minimum level of charge to maintain."""
    # TODO what are valid values? 4-100?
    val = int(val)
    if not 0 <= val <= 65000:
        raise ValueError(f"Export Limit ({val}) must be in [0-65kw]%")
    return [WriteHoldingRegisterRequest(RegisterMap.EXPORT_POWER_LIMIT, val)]


def set_battery_charge_limit(val: int) -> list[TransparentRequest]:
    """Set the battery charge power limit as percentage. 50% (2.6 kW) is the maximum for most inverters."""
    val = int(val)
    if not 0 <= val <= 50:
        raise ValueError(f"Specified Charge Limit ({val}%) is not in [0-50]%")
    return [WriteHoldingRegisterRequest(RegisterMap.BATTERY_CHARGE_LIMIT, val)]


def set_battery_discharge_limit(val: int) -> list[TransparentRequest]:
    """Set the battery discharge power limit as percentage. 50% (2.6 kW) is the maximum for most inverters."""
    val = int(val)
    if not 0 <= val <= 50:
        raise ValueError(f"Specified Discharge Limit ({val}%) is not in [0-50]%")
    return [WriteHoldingRegisterRequest(RegisterMap.BATTERY_DISCHARGE_LIMIT, val)]

def set_battery_charge_limit_ac(val: int, inv_type: str="") -> list[TransparentRequest]:
    """Set the battery AC charge power limit as percentage."""
    reg=getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}BATTERY_CHARGE_LIMIT_AC')
    val = int(val)
    if not 1 <= val <= 100:
        raise ValueError(f"Specified Charge Limit ({val}%) is not in [1-99]%")
    
    return [WriteHoldingRegisterRequest(reg, val)]


def set_battery_discharge_limit_ac(val: int, inv_type: str="") -> list[TransparentRequest]:
    """Set the battery AC discharge power limit as percentage."""
    reg=getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}BATTERY_DISCHARGE_LIMIT_AC')
    val = int(val)
    if not 1 <= val <= 100:
        raise ValueError(f"Specified Discharge Limit ({val}%) is not in [1-99]%")
    return [WriteHoldingRegisterRequest(reg, val)]

def set_battery_power_reserve(val: int, inv_type: str="") -> list[TransparentRequest]:
    """Set the battery power reserve to maintain."""
    # TODO what are valid values?
    reg=getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}BATTERY_DISCHARGE_MIN_POWER_RESERVE')
    val = int(val)
    if not 4 <= val <= 100:
        raise ValueError(f"Battery power reserve ({val}) must be in [4-100]%")
    return [
        WriteHoldingRegisterRequest(reg, val)
    ]

def set_eco_mode(enabled: bool) -> list[TransparentRequest]:
    """enable eco mode."""
    if enabled:
        return [WriteHoldingRegisterRequest(RegisterMap.ECO_MODE, 1)]
    else:
        return [WriteHoldingRegisterRequest(RegisterMap.ECO_MODE, 0)]

def set_battery_pause_mode(val: BatteryPauseMode) -> list[TransparentRequest]:
    """Set the battery pause mode."""
    if not 0 <= val <= 3:
        raise ValueError(f"Battery pause mode ({val}) must be in [0-3]")
    return [WriteHoldingRegisterRequest(RegisterMap.BATTERY_PAUSE_MODE, val)]


def _set_charge_slot(
    discharge: bool, idx: int, slot: Optional[TimeSlot], inv_type: str
) -> list[TransparentRequest]:
    hr_start, hr_end = (
        getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}{"EMS_" if "ems"  in inv_type else ""}{"DIS" if discharge else ""}CHARGE_SLOT_{idx}_START'),
        getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}{"EMS_" if "ems"  in inv_type else ""}{"DIS" if discharge else ""}CHARGE_SLOT_{idx}_END'),
    )
    if slot:
        return [
            WriteHoldingRegisterRequest(hr_start, int(slot.start.strftime("%H%M"))),
            WriteHoldingRegisterRequest(hr_end, int(slot.end.strftime("%H%M"))),
        ]
    else:
        return [
            WriteHoldingRegisterRequest(hr_start, 0),
            WriteHoldingRegisterRequest(hr_end, 0),
        ]
        


def set_charge_slot_start(
    discharge: bool, idx: int, starttime: datetime, inv_type: str
) -> list[TransparentRequest]:
    hr_start = (
        getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}{"EMS_" if "ems"  in inv_type else ""}{"DIS" if discharge else ""}CHARGE_SLOT_{idx}_START')
    )
    return [WriteHoldingRegisterRequest(hr_start, int(starttime.strftime("%H%M")))]
    
def set_charge_slot_end(
    discharge: bool, idx: int, endtime: datetime, inv_type: str
) -> list[TransparentRequest]:
    hr_end = (
        getattr(RegisterMap, f'{"TPH_" if "3ph" in inv_type else ""}{"EMS_" if "ems"  in inv_type else ""}{"DIS" if discharge else ""}CHARGE_SLOT_{idx}_END')
    )
    return [WriteHoldingRegisterRequest(hr_end, int(endtime.strftime("%H%M")))]


def set_export_slot(
    idx: int, slot: Optional[TimeSlot]
) -> list[TransparentRequest]:
    hr_start, hr_end = (
        getattr(RegisterMap, f'EXPORT_SLOT_{idx}_START'),
        getattr(RegisterMap, f'EXPORT_SLOT_{idx}_END'),
    )
    if slot:
        return [
            WriteHoldingRegisterRequest(hr_start, int(slot.start.strftime("%H%M"))),
            WriteHoldingRegisterRequest(hr_end, int(slot.end.strftime("%H%M"))),
        ]
    else:
        return [
            WriteHoldingRegisterRequest(hr_start, 0),
            WriteHoldingRegisterRequest(hr_end, 0),
        ]

def set_export_slot_start(
    idx: int, starttime: datetime
) -> list[TransparentRequest]:
    hr_start = (
        getattr(RegisterMap, f'EXPORT_SLOT_{idx}_START')
    )
    return [WriteHoldingRegisterRequest(hr_start, int(starttime.strftime("%H%M")))]
    
def set_export_slot_end(
    idx: int, endtime: datetime
) -> list[TransparentRequest]:
    hr_end = (
        getattr(RegisterMap, f'EXPORT_SLOT_{idx}_END')
    )
    return [WriteHoldingRegisterRequest(hr_end, int(endtime.strftime("%H%M")))]

def set_pause_slot(
    slot: TimeSlot
) -> list[TransparentRequest]:
        return [
            WriteHoldingRegisterRequest(RegisterMap.BATTERY_PAUSE_SLOT_START, int(slot.start.strftime("%H%M"))),
            WriteHoldingRegisterRequest(RegisterMap.BATTERY_PAUSE_SLOT_END, int(slot.end.strftime("%H%M"))),
        ]


def set_pause_slot_end(
    endtime: datetime
) -> list[TransparentRequest]:
    return [WriteHoldingRegisterRequest(RegisterMap.BATTERY_PAUSE_SLOT_END, int(endtime.strftime("%H%M")))]

def set_pause_slot_start(
    starttime: datetime
) -> list[TransparentRequest]:
    return [WriteHoldingRegisterRequest(RegisterMap.BATTERY_PAUSE_SLOT_START, int(starttime.strftime("%H%M")))]

def set_charge_slot_1(timeslot: TimeSlot) -> list[TransparentRequest]:
    """Set first charge slot start & end times."""
    return _set_charge_slot(False, 1, timeslot)


def reset_charge_slot_1() -> list[TransparentRequest]:
    """Reset first charge slot to zero/disabled."""
    return _set_charge_slot(False, 1, None)


def set_charge_slot_2(timeslot: TimeSlot) -> list[TransparentRequest]:
    """Set second charge slot start & end times."""
    return _set_charge_slot(False, 2, timeslot)


def reset_charge_slot_2() -> list[TransparentRequest]:
    """Reset second charge slot to zero/disabled."""
    return _set_charge_slot(False, 2, None)


def set_discharge_slot_1(timeslot: TimeSlot) -> list[TransparentRequest]:
    """Set first discharge slot start & end times."""
    return _set_charge_slot(True, 1, timeslot)


def reset_discharge_slot_1() -> list[TransparentRequest]:
    """Reset first discharge slot to zero/disabled."""
    return _set_charge_slot(True, 1, None)


def set_discharge_slot_2(timeslot: TimeSlot) -> list[TransparentRequest]:
    """Set second discharge slot start & end times."""
    return _set_charge_slot(True, 2, timeslot)


def reset_discharge_slot_2() -> list[TransparentRequest]:
    """Reset second discharge slot to zero/disabled."""
    return _set_charge_slot(True, 2, None)


def set_system_date_time(dt: datetime) -> list[TransparentRequest]:
    """Set the date & time of the inverter."""
    return [
        WriteHoldingRegisterRequest(RegisterMap.SYSTEM_TIME_YEAR, dt.year - 2000),
        WriteHoldingRegisterRequest(RegisterMap.SYSTEM_TIME_MONTH, dt.month),
        WriteHoldingRegisterRequest(RegisterMap.SYSTEM_TIME_DAY, dt.day),
        WriteHoldingRegisterRequest(RegisterMap.SYSTEM_TIME_HOUR, dt.hour),
        WriteHoldingRegisterRequest(RegisterMap.SYSTEM_TIME_MINUTE, dt.minute),
        WriteHoldingRegisterRequest(RegisterMap.SYSTEM_TIME_SECOND, dt.second),
    ]


def set_mode_dynamic(paused: bool = False) -> list[TransparentRequest]:
    """Set system to Dynamic / Eco mode.

    This mode is designed to maximise use of solar generation. The battery will charge from excess solar
    generation to avoid exporting power, and discharge to meet load demand when solar power is insufficient to
    avoid importing power. This mode is useful if you want to maximise self-consumption of renewable generation
    and minimise the amount of energy drawn from the grid.
    """
    # r27=1 r110=4 r59=0
    reqs=set_discharge_mode_to_match_demand()
    reqs.extend(set_enable_discharge(False))
    if paused: 
        reqs.extend(set_battery_soc_reserve(100))       #Only change soc target is paused
    return reqs


def set_mode_storage(
#### Do we want a default discharge schedule here, or has it optional...
    #discharge_slot_1: TimeSlot = TimeSlot.from_repr(1600, 700),
    discharge_slot_1: Optional[TimeSlot] = None,
    discharge_slot_2: Optional[TimeSlot] = None,
    discharge_for_export: bool = False,
    inv_type: str = ""
) -> list[TransparentRequest]:
    """Set system to storage mode with specific discharge slots(s).

    This mode stores excess solar generation during the day and holds that energy ready for use later in the day.
    By default, the battery will start to discharge from 4pm-7am to cover energy demand during typical peak
    hours. This mode is particularly useful if you get charged more for your electricity at certain times to
    utilise the battery when it is most effective. If the second time slot isn't specified, it will be cleared.

    You can optionally also choose to export excess energy: instead of discharging to meet only your load demand,
    the battery will discharge at full power and any excess will be exported to the grid. This is useful if you
    have a variable export tariff (e.g. Agile export) and you want to target the peak times of day (e.g. 4pm-7pm)
    when it is most valuable to export energy.
    """
    if discharge_for_export:
        ret = set_discharge_mode_max_power()  # r27=0
    else:
        ret = set_discharge_mode_to_match_demand()  # r27=1
    #ret.extend(set_battery_soc_reserve(100))  # r110=100
    ret.extend(set_enable_discharge(True))  # r59=1
    #ret.extend(set_discharge_slot_1(discharge_slot_1))  # r56=1600, r57=700
    if discharge_slot_1:
        ret.extend(_set_charge_slot(True,1,discharge_slot_1,inv_type=inv_type))  # r56=1600, r57=700
    if discharge_slot_2:
        ret.extend(_set_charge_slot(True,2,discharge_slot_2,inv_type=inv_type))  # r56=1600, r57=700
    #else:
    #    ret.extend(reset_discharge_slot_2())
    return ret
