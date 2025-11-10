"""
Helper classes for the Plant, Inverter and Battery.

Applications shouldn't need to worry about these.
"""

from dataclasses import dataclass
from datetime import datetime
from json import JSONEncoder, dumps
import logging
import math
from textwrap import dedent
from typing import Any, Callable, Optional, Union
from enum import IntEnum, StrEnum
from ..exceptions import (
    ConversionError,
)

from . import TimeSlot

_logger = logging.getLogger(__name__)

class Converter:
    """Type of data register represents. Encoding is always big-endian."""

    @staticmethod
    def nominal_frequency(option: int) -> Optional[int]:
        """Determine max inverter power from device_type_code."""
        frequency = [50,60]
        return frequency[option]
    
    @staticmethod
    def nominal_voltage(option: int) -> Optional[int]:
        """Determine max inverter power from device_type_code."""
        voltage = [230,208,240]
        return voltage[option]

    @staticmethod
    def uint16(val: int) -> int:
        """Simply return the raw unsigned 16-bit integer register value."""
        if val is not None:
            return int(val)

    @staticmethod
    def gateway_version(first: int,second: int,third: int,fourth: int,) -> Optional[str]:
        """Return Gateway software ID."""
        gwversion=bytearray.fromhex(hex(first)[2:]).decode()+bytearray.fromhex(hex(second)[2:]).decode()+str(third.to_bytes(2)[0])+str(third.to_bytes(2)[1])+str(fourth.to_bytes(2)[0])+str(fourth.to_bytes(2)[1])
        return gwversion

    @staticmethod
    def int16(val: int) -> int:
        """Interpret as a 16-bit integer register value."""
        if val is not None:
            if val & (1 << (16 - 1)):
                val -= 1 << 16
            return val

    @staticmethod
    def duint8(val: int, *idx: int) -> int:
        """Split one register into two unsigned 8-bit ints and return the specified index."""
        if val is not None:
            vals = (val >> 8), (val & 0xFF)
            return vals[idx[0]]

    @staticmethod
    def int32(high_val: int, low_val: int) -> int:
        """Combine two registers into an signed 32-bit int."""
        if high_val is not None and low_val is not None:
            val= (high_val << 16) + low_val
            if val & (1 << (16 - 1)):
                val -= 1 << 16
            return val
        
    def uint32(high_val: int, low_val: int) -> int:
        """Combine two registers into an unsigned 32-bit int."""
        if high_val is not None and low_val is not None:
            return (high_val << 16) + low_val

    @staticmethod
    def timeslot(start_time: int, end_time: int) -> TimeSlot:
        """Interpret register as a time slot."""
        if start_time is not None and end_time is not None:
            return TimeSlot.from_repr(start_time, end_time)

    @staticmethod
    def bool(val: int) -> bool:
        """Interpret register as a bool."""
        if val is not None:
            return bool(val)
        return None

    @staticmethod
    def bitfield(val: int, low: int, high: int) -> int:
        """Return int of binary string from range requested in input as binary string"""
        res=int(format(val,'016b')[low:high+1],2)
        return res

    @staticmethod
    def hexfield(val: int, idx: int, width: int=1) -> int:
        """Return int of hex string from range requested in input as binary string"""
        res=int(format(val,'04X')[idx:idx+width],16)
        return res

    @staticmethod
    def string(*vals: int) -> Optional[str]:
        """Represent one or more registers as a concatenated string."""
        if vals is not None and None not in vals:
            return (
                b"".join(v.to_bytes(2, byteorder="big") for v in vals)
                .decode(encoding="latin1")
                .replace("\x00", "")
                .upper()
            )
        return None

    @staticmethod
    def fstr(val, fmt) -> Optional[str]:
        """Render a value using a format string."""
        if val is not None:
            return f"{val:{fmt}}"
        return None

    @staticmethod
    def firmware_version(dsp_version: int, arm_version: int) -> Optional[str]:
        """Represent ARM & DSP firmware versions in the same format as the dashboard."""
        if dsp_version is not None and arm_version is not None:
            return f"D0.{dsp_version}-A0.{arm_version}"

    @staticmethod
    def battery_capacity(nom_cap: int, model: int) -> Optional[str]:
        """Represent BMU capacity in kWh from Ah."""
        model=f"{model:0{4}x}"
        if model[0] in ['8']:                       #AIO
            return round((nom_cap*317)/1000,2)
        elif model[0] in ['4','6']:                 #3PH
            return round((nom_cap*76.8)/1000,2)
        else:                                       #LV
            return round((nom_cap*51.2)/1000,2)
        
    @staticmethod
    def battery_capacity_hv(nom_cap: int) -> Optional[str]:
        """Represent BCU capacity in kWh from Ah."""
        return round((nom_cap*76.8)/1000,2)
    

    @staticmethod
    def inverter_max_power(device_type_code: str) -> Optional[int]:
        """Determine max inverter power from device_type_code."""
        dtc_to_power = {
            "2001": 5000,
            "2002": 4600,
            "2003": 3600,
            "2101": 5000,
            "2102": 4600,
            "2103": 3600,
            "2104": 6000,
            "2105": 7000,
            "2106": 8000,
            "2201": 5000,
            "2202": 4600,
            "2203": 3600,
            "2204": 6000,
            "2205": 7000,
            "2206": 8000,
            "2301": 5000,
            "2302": 4600,
            "2303": 3600,
            "2304": 6000,
            "3001": 3000,
            "3002": 3600,
            "4001": 6000,
            "4002": 8000,
            "4003": 10000,
            "4004": 11000,
            "7001": 12000,
            "8001": 6000,
            "8101": 6000,
            "8102": 8000,
            "8103": 10000,
            "8201": 6000,
            "8202": 8000,
            "8203": 10000,
            "8204": 12000,
            "8304": 6000,
        }
        return dtc_to_power.get(device_type_code)
    
    @staticmethod
    def inverter_max_power_new(moduleH: int) -> Optional[int]:
        return moduleH*100
    
    @staticmethod
    def threeph_inverter_max_power(inp: str) -> Optional[int]:
        """Determine max inverter power from device_type_code."""
        power = [
            1000,
            2000,
            3000,
            3600,
            4000,
            4600,
            5000,
            6000,
            7000,
            8000,
            10000,
            11000,
            15000,
            20000,
            30000,
            50000,
        ]
        return power[inp]
    
    @staticmethod
    def battery_fault_code(val: int) -> Optional[list]:
        """Collect Faults from error code."""
        errors = [
            "Meter Failure",
            "Voltage High",
            "Voltage Low",
            "Soft Start Fault",
            "Check Battery Connection",
            "BMS Comms failure",
            "Temperature Fault",
            "Charge/Discharge module temperature fault",
            "BMS Over Current",
            "BMS Short Current",
            "BMS Over Voltage",
            "BMS Under Voltage",
            "BMS Discharge over temperature",
            "BMS Charge over temperature",
            "BMS Discharge under temperature",
            "BMS Charge under temperature",
        ]
        out=[]
        if val is not None:
            inp= f"{val:016b}"
        for idx, bit in enumerate(inp): 
            if int(bit,2) == 1 and not errors[idx]==None:
                out.append(errors[idx])
        return out

    @staticmethod
    def inverter_fault_code2(val: int, word: int) -> Optional[list]:
        """Collect Faults from error code."""
        errors=[0,0,0,0,0,0,0,0,0]
        errors[0] = [
            "Battery Voltage High",
            None,
            "Bus 2 Voltage high ISR",
            "Bus Voltage high ISR",
            "Inverter OCP fault TZ",
            "Frequency unstable",
            "Buck Boost Fault ISR",
            "BDC OCP Fault",
            "Grid Zero cross loss",
            None,
            None,
            None,
            "Grid Phase 1 voltage fault",
            "Grid Phase 2 voltage fault",
            "Grid Phase 3 voltage fault",
            "Grid frequency out of range",
        ]
        errors[1] = [
            "Gateway Comm fault",
            "GFCI Damage",
            "Grid phase 1 voltage low",
            "Grid phase 1 voltage high",
            "Grid phase 2 voltage low",
            "Grid phase 2 voltage high",
            "Grid phase 3 voltage low",
            "Grid phase 3 voltage high",
            "Inverter OCP Fault ISR",
            None,
            None,
            None,
            "Inverter Phase 1 Current OCP (RMS)",
            "Inverter Phase 2 Current OCP (RMS)",
            "Inverter Phase 3 Current OCP (RMS)",
            "No Grid connection",
        ]
        errors[2] = [
            "Grid Frequency Low",
            "Grid frequency High",
            "Grid voltage imbalance",
            "AC PLL fault",
            "Overload fault",
            "Backflow timeout",
            None,
            "Grid connected v/f out of range",
            "EPS phase 1 voltage loss",
            "EPS phase 2 voltage loss",
            "EPS phase 3 voltage loss",
            "EPS bus voltage low",
            "EPS overload",
            "EPS voltage high",
            "DCV high",
            "Battery OCP",
        ]
        errors[3] = [
            "Battery reversed",
            "Battery open",
            "Battery voltage low",
            None,
            "Bus2 voltage abnormal",
            "Buck boost soft start fail",
            "Battery voltage high",
            None,
            "BMS Error",
            "BMS comm fault",
            None,
            None,
            None,
            "Battery sleep",
            "Lead acid NTC open",
            "BMS power forbid",
        ]
        errors[4] = [
            None,
            None,
            None,
            None,
            None,
            "PV1 voltage low",
            "PV2 voltage low",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]
        errors[5] = [
            "DCI high",
            "PV isolation low",
            "NTC open",
            "Bus voltage high",
            "PV voltage high",
            "Boost over temperature",
            "Buck Boost over temperature",
            "Inverter over temperature",
            "EPS output short circuit",
            "Auto test fault",
            "Init Model fault",
            "Relay fault",
            "Bus voltage unbalance",
            "DSP firmware unmatched",
            "PV1 short circuit",
            "PV2 short circuit",
        ]
        errors[6] = [
            "PV voltage high",
            "External ddevice faulty",
            "Acom fault",
            "Bcom fault",
            "Master force inverter fault",
            "Master force SP fault",
            "GFCI High",
            "Virtual Load over temp",
            "Internal com fault3",
            "Grid consistent",
            "EPS connected grid",
            "Internal over temperature",
            "Fan fault",
            "Hardware unmatch",
            None,
            None,
        ]
        errors[7] = [
            "CT clamp L/N reversed",
            "Pairing timeout",
            "Meter comms loss",
            None,
            None,
            None,
            "Battery over temperature",
            "Battery over load",
            "Battery full",
            "Battery needs Charge",
            "BMS Warning",
            "Battery weak",
            "Battery low power",
            "NTC open",
            "Fan warning",
            None,
        ]
        errors[8] = [
            "Parallel version different",
            "Parallel output voltage different",
            "Parallel battery voltage different",
            "Parallel grid voltage different",
            "Parallel grid frequency different",
            "Parallel output setting different",
            "Parallel parameter different",
            None,
            "Parallel host line loss",
            "Parallel comm loss",
            "Parallel low frequency sync line loss",
            "Parallel high frequency sync line loss",
            "Parallel fault",
            None,
            None,
            None,
        ]
        out=[]
        if val is not None:
            inp= f"{val:016b}"
        for idx, bit in enumerate(inp): 
            if int(bit,2) == 1 and not errors[word][idx]==None:
                out.append(errors[word][idx])
        return out

    @staticmethod
    def inverter_fault_code(val: int) -> Optional[list]:
        """Collect Faults from error code."""
        errors = [
            None,
            None,
            None,
            "Backup Overload Fault",
            None,
            None,
            "Grid Monitor Comm Fault",
            "ARM Comms Fault",
            "Consistent Fault",
            "EEPROM Fault",
            None,
            None,
            None,
            None,
            None,
            None,
            "Inverter Frequency Fault",
            "Relay Fault",
            "Inverter Voltage Fault",
            "GFCI Fault",
            "Hail Sensor Fault",
            "DSP Comms Fault",
            "Bus over voltage",
            "Inverter Current Fault",
            "No Utility",
            "PV Isolation Fault",
            "Current leak high",
            "DCI high",
            "PV Over voltage",
            "Grid voltage Fault",
            "Grid Frequency Fault",
            "Inverter NTC Fault",
            None,
        ]
        out=[]
        if val is not None:
            inp= f"{val:032b}"
        for idx, bit in enumerate(inp): 
            if int(bit,2) == 1 and not errors[idx]==None:
                out.append(errors[idx])
        return out
    
    @staticmethod
    def gateway_fault_code(val: int) -> Optional[list]:
        """Collect Faults from error code."""
        errors = [
            "Relay 1&2 bonding",
            "Relay 3&4 bonding",
            "Relay 1&2 disconnect",
            "Relay 3&4 disconnect",
            "AC over frequency 1",
            "AC under frequency 1",
            "AC over voltage 1",
            "AC under voltage 1",
            "AC over frequency 2",
            "AC under frequency 2",
            "AC over voltage 2",
            "AC under voltage 2",
            None,
            "No zero-point protection",
            "Over quarter AC voltage",
            "Under quarter AC voltage",
            "Over AC voltage long-time",
            "AC over frequency constant",
            "AC under frequency constant",
            "AC over voltage constant",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "Grid mode Off",
        ]
        out=[]
        if val is not None:
            inp= f"{val:032b}"
        for idx, bit in enumerate(inp): 
            if int(bit,2) == 1 and not errors[idx]==None:
                out.append(errors[idx])
        return out

    @staticmethod
    def get_model(dtc, fw) -> str:

        """Pick model from the arm_firmware_version."""
        arm_firmware_version_to_gen = {
            3: Model.HYBRID_GEN3,
            8: Model.HYBRID_GEN2,
            9: Model.HYBRID_GEN2
        }
        dtc=f"{dtc:0{4}x}"  # convert to hex  rep
        if str(dtc)[:2] == "20":       # These can only be determined by fw version
            if gen := arm_firmware_version_to_gen.get(math.floor(int(fw) / 100)):
                return gen
            else:
                return Model.HYBRID_GEN1
        return Model(dtc)



    @staticmethod
    def battery_max_power(dtc,fw) -> Optional[int]:
        """Determine max inverter power from device_type_code and fw version."""
        dtc=f"{dtc:0{4}x}"  # convert to hex rep

        dtc_to_batpower={
            "3001": 3000,
            "2201": 5400,
            "3002": 3000,
            "8001": 6000,
            "8102": 8000,
            "8103": 10000,
        }                   #Covers AC3, Gen4 and AIO
        arm_firmware_version_to_gen = [3,8,9]
        
        if str(dtc)[:2] == "20":       # These can only be determined by fw version
            if (math.floor(int(fw) / 100)) in arm_firmware_version_to_gen:  #Gen2&3
                return 3600
            else:
                return 2600
        elif dtc in dtc_to_batpower:
            return dtc_to_batpower[dtc]
        else:
            return 0
    

    @staticmethod
    def hex(val: int, width: int = 4) -> str:
        """Represent a register value as a 4-character hex string."""
        if val is not None:
            return f"{val:0{width}x}"

    @staticmethod
    def bits(val: int, width: int = 16) -> str:
        """Represent a register value as a 16-character bit string."""
        if val is not None:
            return f"{val:0{width}b}"

    @staticmethod
    def milli(val: int) -> float:
        """Represent a register value as a float in 1/1000 units."""
        if val is not None:
            return val / 1000

    @staticmethod
    def centi(val: int) -> float:
        """Represent a register value as a float in 1/100 units."""
        if val is not None:
            return val / 100

    @staticmethod
    def deci(val: int) -> float:
        """Represent a register value as a float in 1/10 units."""
        if val is not None:
            return val / 10

    @staticmethod
    def datetime(year, month, day, hour, min, sec): # -> Optional[datetime]:
        """Compose a datetime from 6 registers."""
        try:
            if None not in [year, month, day, hour, min, sec]:
                return datetime(year + 2000, month, day, hour, min, sec)
            return datetime(2000,1,1,0,0,0)
        except:
            _logger.error("Error processing datetime. Sending Zero Date")
            return datetime(2000,1,1,0,0,0)

class WorkMode(IntEnum):
    INITALISING = 0
    OFF_GRID = 1
    ON_GRID = 2
    FAULT = 3
    UPDATE = 4

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)
    
class State(IntEnum):
    STATIC = 0
    CHARGE = 1
    DISCHARGE = 2

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)
    
class Certification(IntEnum):
    UNKNOWN = 0
    G99 = 12
    G98 = 8
    G99_NI = 17
    G98_NI = 16


    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)
    
class BatteryPriority(IntEnum):
    LOAD = 0
    BATTERY = 1
    GRID = 2

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)

class Enable(IntEnum):
    DISABLE = 0
    ENABLE = 1
    UNKNOWN = 3

    @classmethod
    def _missing_(cls, value):
        """Default to Unknown"""
        return cls(3)

class MeterStatus(IntEnum):
    DISABLED = 0
    ONLINE = 1
    OFFLINE = 2

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)

class Model(StrEnum):
    """Known models of inverters."""
## Use the full mapping found in modbus docs and use first 2 chr of DTC code
    HYBRID_GEN1 = "20g1"
    HYBRID_GEN2 = "20g2"
    HYBRID_GEN3 = "20g3"
    POLAR = "21"
    HYBRID_GEN3_PLUS = "22"
    PV = "23"
    AC = "30"
    HYBRID_3PH = "40"
    AIO_COMMERCIAL = "41"
    AC_3PH = "60"
    EMS = "50"
    EMS_COMMERCIAL = "51"
    GATEWAY = "70"
    ALL_IN_ONE = "80"
    HYBRID_HV_GEN3 = "81"
    ALL_IN_ONE_HYBRID = "82"
    HYBRID_GEN4 = "83"

    @classmethod
    def _missing_(cls, value):
        """Just return Hybrid."""
        return cls(value[:2])
        
    @classmethod
    def core_regs(cls, value):
########## Currently unused  #############
        """Return core registers for each model to be pulled in a "partial" refresh. (IR,HR)"""

        '''
        HR 180-240 - Inverter Errors??
        HR 240-300 - 10 Timeslots
        HR 300-360 - 
        HR 480-540 - Gateway Controls
        HR 1000 - 1180 - Three Phase Control
        HR 2040 - EMS Controls
        
        IR 240-300 - 
        IR 2040 - EMS Data
        IR 1000 - 1420 - Three Phase Data
        IR 1600 - 1900 - Gateway Data
        '''
        regs={
            '2': ([0, 60, 120, 180],[0, 60, 120, 120]),    #Hybrid
            '3': ([0, 60, 120, 180],[0, 60, 120, 120]),    #AC
            '4': ([0, 60, 120, 180, 240,1000,1060,1120,1180,1240,1300,1360],[180,240,1000,1060,1120]),   #"Hybrid - 3ph"
            '5': ([2040],[2040]),   #EMS
            '6': ([0, 60, 120, 180, 240,1000,1060,1120,1180,1240,1300,1360],[180,240,1000,1060,1120]),   #AC - 3ph
            '7': ([0, 60, 120, 180,1600,1660,1720,1780,1840],[0, 60, 120, 120,180,240,300]),   #Gateway
            '8': ([0, 60, 120, 180, 240],[0, 60, 120, 120, 180, 240, 300]),   #All in One and Gen 4 and Hybrid HV
        }
        return regs.get(value[0])

    @classmethod
    def add_regs(cls, value):
############# THS NEEDS RESTRUCTURING TO ALLOW INDIVIDUAL "CORE" REGS TO BE GOT EVERYTIME (eg GATEWAY, EMS AND 3PH) #############
        """Return possible additional registers to be pulled in a "complete" refresh.(IR,HR)"""
        regs={
            '2': ([240],[180,240,300]),    #Hybrid
            '3': ([],[180,240,300]),    #AC
            '4': ([240,1000,1060,1120,1180,1240,1300,1360],[180,240,1000,1060,1120]),   #"Hybrid - 3ph"
            '5': ([2040],[2040]),   #EMS
            '6': ([1000,1060,1120,1180,1240,1300,1360],[180,240,1000,1060,1120]),   #AC - 3ph
            '7': ([1600,1660,1720,1780,1840],[180,240,300]),   #Gateway
            '8': ([240],[180,240,300]),   #All in One
        }
        return regs.get(value[0])


class Generation(StrEnum):
    """Known Generations"""
    GEN1 = "Gen 1"
    GEN2 = "Gen 2"
    GEN3 = "Gen 3"
    GEN3P = "Gen 3+"
    GEN4 = "Gen 4"
    AIO2 = "AIO 2"
    NA = "NoGen"

class UsbDevice(IntEnum):
    """USB devices that can be inserted into inverters."""

    NONE = 0
    WIFI = 1
    DISK = 8

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)


class BatteryPowerMode(IntEnum):
    """Battery discharge strategy."""

    EXPORT = 0
    SELF_CONSUMPTION = 1

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)

class BatteryCalibrationStage(IntEnum):
    """Battery calibration stages."""

    OFF = 0
    DISCHARGE = 1
    SET_LOWER_LIMIT = 2
    CHARGE = 3
    SET_UPPER_LIMIT = 4
    BALANCE = 5
    SET_FULL_CAPACITY = 6
    FINISH = 7

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)


class MeterType(IntEnum):
    """Installed meter type."""

    CT_OR_EM418 = 0
    EM115 = 1

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(1)


class BatteryType(IntEnum):
    """Installed battery type."""

    LEAD_ACID = 0
    LITHIUM = 1

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(1)


class BatteryPauseMode(IntEnum):
    """Battery pause mode."""

    DISABLED = 0
    PAUSE_CHARGE = 1
    PAUSE_DISCHARGE = 2
    PAUSE_BOTH = 3

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)

class SystemMode(IntEnum):
    OFFLINE = 0
    GRID_TIED = 1
    
    @classmethod
    def _missing_(cls, value: int):
        """Default to 0."""
        return cls(0)

class BatteryMaintenance(IntEnum):
    OFF = 0
    DISCHARGE = 1
    CHARGE = 2
    STANDBY=3
    
    @classmethod
    def _missing_(cls, value: int):
        """Default to 0."""
        return cls(0)

class PowerFactorFunctionModel(IntEnum):
    """Power Factor function model."""

    PF_1 = 0
    PF_BY_SET = 1
    DEFAULT_PF_LINE = 2
    USER_PF_LINE = 3
    UNDER_EXCITED_INDUCTIVE_REACTIVE_POWER = 4
    OVER_EXCITED_CAPACITIVE_REACTIVE_POWER = 5
    QV_MODEL = 6
    DEFAULT_PF_LINE2 = 7
    UNDER_EXCITED_QU_MODE = 8
    OVER_EXCITED_QU_MODE = 9

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)


class Status(IntEnum):
    """Inverter status."""

    WAITING = 0
    NORMAL = 1
    WARNING = 2
    FAULT = 3
    FLASHING_FIRMWARE_UPDATE = 4

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)
    
class InverterType(IntEnum):
    """Inverter status."""

    SINGLEPHASELV = 0
    SINGLEPHASEHV = 1
    THREEPHASELV = 2
    THREEPHASEHV = 3

    @classmethod
    def _missing_(cls, value):
        """Default to 0."""
        return cls(0)

class Phase(IntEnum):
    """Determine number of Phases."""

    OnePhase = 1
    ThreePhase = 3

    @classmethod
    def _missing_(cls, device_type_code: str):
        """Return the appropriate phase from a given dtc."""
        __dtc_to_phases_lut__ = {
        '2': cls.OnePhase,
        '3': cls.OnePhase,
        '4': cls.ThreePhase,
        '5': cls.OnePhase,
        '6': cls.ThreePhase,
        '7': cls.OnePhase,
        '8': cls.OnePhase,
    }
        prefix = device_type_code[0]
        if prefix in __dtc_to_phases_lut__:
            res= __dtc_to_phases_lut__[prefix]
            return res
        else:
            return 'Unknown'
        

@dataclass(init=False)
class RegisterDefinition:
    """Specifies how to convert raw register values into their actual representation."""

    pre_conv: Union[Callable, tuple, None]
    post_conv: Union[Callable, tuple[Callable, Any], None]
    registers: tuple["Register"]
    valid: Optional[tuple[int, int]]

    def __init__(self, *args, valid=None):
        self.pre_conv = args[0]
        self.post_conv = args[1]
        self.registers = args[2:]  # type: ignore[assignment]
        self.valid = valid
        # only single-register attributes are writable
        assert valid is None or len(self.registers) == 1

    def __hash__(self):
        return hash(self.registers)



# This is used as the metaclass for Inverter and Battery,
# in order to dynamically generate a docstring from the
# register definitions.

class DynamicDoc(type):
    """A metaclass for generating dynamic __doc__ string.

    A class using this metaclass must implement a class method
    _gendoc() which will be invoked by any access to cls.__doc__
    (typically documentation tools like pydoc).
    """

    @property
    def __doc__(self):
        """Invoke a helper to generate class docstring."""
        return self._gendoc()


class RegisterGetter:
    """
    Specifies how device attributes are derived from raw register values.
    
    This is the base class for Inverter and Battery, and provides the common
    code for constructing python attributes from the register definitions.
    """

    # defined by subclass
    REGISTER_LUT: dict[str, RegisterDefinition]
    _DOC: str

    # TODO: cache is actually a RegisterCache, but importing that gives a circular dependency
    def __init__(self, cache: Any):
        self.cache = cache  # RegisterCache

    # this implements the magic of providing attributes based
    # on the register lut
    def __getattr__(self, name: str):
        return self.get(name)

    
    # or you can just use inverter.get('name')
    def getall(self) -> Any:
        """Return a named register's value, after pre- and post-conversion."""
        inverter={}
        for key in self.REGISTER_LUT:
            inverter[key]=self.get(key)
        return inverter
    
    def getsn(self) -> Any:
        return self.cache['serial_number']

    # or you can just use inverter.get('name')
    def get(self, key: str) -> Any:
        """Return a named register's value, after pre- and post-conversion."""
        r = self.REGISTER_LUT[key]

        if isinstance(r,int):   #deal with the BCU number in HV battery data
            return r
        
        regs = [self.cache.get(r) for r in r.registers]

        if None in regs:
            return None

        try:
            if r.pre_conv:
                if isinstance(r.pre_conv, tuple):
                    args = regs + list(r.pre_conv[1:])
                    val = r.pre_conv[0](*args)
                else:
                    val = r.pre_conv(*regs)
            else:
                val = regs

            if r.post_conv:
                if isinstance(r.post_conv, tuple):
                    return r.post_conv[0](val, *r.post_conv[1:])
                else:
                    if not isinstance(r.post_conv, Callable):
                        pass
                    return r.post_conv(val)
            return val
        except ValueError as err:
            msg=key+": "+str(regs)+": "+str(err)
            raise ConversionError(key, regs, msg) from err

    # This gets invoked during pydoc or similar by a bit of python voodoo.
    # Inverter and Battery use util.DynamicDoc as a metaclass, and
    # that defines __doc__ as a property which ends up in here.
    @classmethod
    def _gendoc(cls):
        """"Construct a docstring from fixed prefix and register list."""

        doc = cls._DOC + dedent(
        """

        The following list of attributes was automatically generated from the
        register definition list. They are fabricated at runtime via ``__getattr__``.
        Note that the actual set of registers available depends on the inverter
        model - accessing a register that doesn't exist will return ``None``.

        Because these attributes are not listed in ``__dict__`` they may not be
        visible to all python tools.
        Some appear multiple times as aliases.\n\n"""
        )

        for reg in cls.REGISTER_LUT.keys():
            doc += '* ' + reg + "\n"
        return doc


class RegisterEncoder(JSONEncoder):
    """Custom JSONEncoder to work around Register behaviour.

    This is a workaround to force registers to render themselves as strings instead of
    relying on the internal identity by default.
    """

    def default(self, o: Any) -> str:
        """Custom JSON encoder to treat RegisterCaches specially."""
        if isinstance(o, Register):
            return f"{o._type}_{o._idx}"
        else:
            return super().default(o)


class Register:
    """Register base class."""

    TYPE_HOLDING = "HR"
    TYPE_INPUT = "IR"
    TYPE_METER = "MR"

    _type: str
    _idx: int

    def __init__(self, idx):
        self._idx = idx

    def __str__(self):
        return "%s_%d" % (self._type, int(self._idx))

    __repr__ = __str__

    def __eq__(self, other):
        return (
            isinstance(other, Register)
            and self._type == other._type
            and self._idx == other._idx
        )

    def __hash__(self):
        return hash((self._type, self._idx))


class HR(Register):
    """Holding Register."""

    _type = Register.TYPE_HOLDING


class IR(Register):
    """Input Register."""

    _type = Register.TYPE_INPUT

class MR(Register):
    """Meter Product Register."""

    _type = Register.TYPE_METER

"""
class InverterType_2:
    # Single Class to determine characteristics based on DTC
    def __init__(self,dT,imP, bmP, gN, pH, cR):
        self.invertermaxpower=imP,
        self.batterymaxpower=bmP,
        self.devicetype = dT
        self.phases = pH
        self.core_regs = cR
    
    def fw_to_batmax(fw): 
        if (math.floor(int(fw) / 100)) in [3,8,9]:
            return 3600
        else:
            return 2600

    # LUT is DeviceType, Phases, InverterMaxPower, BatteryMaxPower, Core Regs, Add Regs
    dtc_lut = {
    "2001": (Model.HYBRID,Phase.OnePhase,5000,fw_to_batmax("2001"),([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])), #special case for "20" inverters uses fw for batterymax
    "2002": (Model.HYBRID,Phase.OnePhase,4600,fw_to_batmax("2001"),([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])), #special case for "20" inverters uses fw for batterymax
    "2003": (Model.HYBRID,Phase.OnePhase,3600,fw_to_batmax("2001"),([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])), #special case for "20" inverters uses fw for batterymax
    "2101": (Model.HYBRID_POLAR,Phase.OnePhase,5000,2600,([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])), 
    "2102": (Model.HYBRID_POLAR,Phase.OnePhase,4600,2600,([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])), 
    "2103": (Model.HYBRID_POLAR,Phase.OnePhase,3600,2600,([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])), 
    "2104": (Model.HYBRID_POLAR,Phase.OnePhase,6000,2600,([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])), 
    "2105": (Model.HYBRID_POLAR,Phase.OnePhase,7000,2600,([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])), 
    "2106": (Model.HYBRID_POLAR,Phase.OnePhase,8000,2600,([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])), 
    "2201": (Model.HYBRID_GEN3_PLUS,Phase.OnePhase,5000,2600,([0, 60, 120, 180],[0, 60, 120, 120]),([240],[180,240,300])),
    "2202": 4600,
    "2203": 3600,
    "2204": 6000,
    "2205": 7000,
    "2206": 8000,
    "2301": 5000,
    "2302": 4600,
    "2303": 3600,
    "2304": 6000,
    "3001": 3000,
    "3002": 3600,
    "4001": 6000,
    "4002": 8000,
    "4003": 10000,
    "4004": 11000,
    "7001": 12000,
    "8001": 6000,
    "8101": 6000,
    "8102": 8000,
    "8103": 10000,
    "8201": 6000,
    "8202": 8000,
    "8203": 10000,
    "8204": 12000,
    "8304": 6000,
    }
"""