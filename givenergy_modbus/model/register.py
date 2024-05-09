# type: ignore  # shut up mypy, this whole file is just a minefield
import logging
from datetime import time
from enum import Enum, auto, unique
from typing import Any

_logger = logging.getLogger(__package__)


class Type(Enum):
    """Type of data register represents. Encoding is always big-endian."""

    BOOL = auto()
    BITFIELD = auto()
    HEX = auto()
    UINT8 = auto()
    DUINT8 = auto()  # double-uint8
    UINT16 = auto()
    INT16 = auto()
    UINT32_HIGH = auto()  # higher (MSB) address half
    UINT32_LOW = auto()  # lower (LSB) address half
    ASCII = auto()  # 2 ASCII characters
    TIME = auto()  # BCD-encoded time. 430 = 04:30
    PERCENT = auto()  # same as UINT16, but might be useful for rendering
    POWER_FACTOR = auto()  # zero point at 10^4, scale factor 10^4

    def convert(self, value: int, scaling: int) -> Any:
        """Convert `val` to its true value as determined by the type and scaling definitions."""
        if self == self.UINT32_HIGH:
            # shift MSB half of the 32-bit int left
            if scaling != 1:
                return (value << 16) / scaling
            return value << 16

        if self == self.INT16:
            # Subtract 2^n if bit n-1 is set:
            if value & (1 << (16 - 1)):
                value -= 1 << 16
            if scaling != 1:
                return value / scaling
            return value

        if self == self.BOOL:  # TODO is this the correct assumption?
            return bool(value)

        if self == self.TIME:
            # Convert a BCD-encoded int into datetime.time."""
            hour = int(f'{value:04}'[:2])
            minute = int(f'{value:04}'[2:])
            if hour == 24:
                hour = 0
            if minute == 60:
                minute = 0
            return time(hour, minute)

        if self == self.ASCII:
            return value.to_bytes(2, byteorder='big').decode(encoding='ascii')

        if self == self.UINT8:
            return value & 0xFF

        if self == self.DUINT8:
            return (value >> 8), (value & 0xFF)

        if self == self.POWER_FACTOR:
            return (value - 10_000) / 10_000

        if self == self.BITFIELD:
            return value  # scaling makes no sense

        if self == self.HEX:
            return f'{value:04x}'  # scaling makes no sense

        if scaling != 1:
            return value / scaling
        return value

    def repr(self, value: Any, scaling: float, unit: str = '') -> str:
        """Return user-friendly representation of scaled `val` as appropriate for the data type."""
        v = self.convert(value, scaling)

        if unit:
            unit = f' {unit}'

        if self == self.TIME:
            # Convert a BCD-encoded int into datetime.time."""
            return v.strftime('%H:%M')

        if self == self.DUINT8:
            return f'{v[0]}, {v[1]}'

        if self == self.BITFIELD:
            return ' '.join([f'{int(n, 16):04b}' for n in list(f'{v:04x}')])

        if self == self.HEX:
            return f'0x{v}'

        if isinstance(v, float):
            return f'{v:0.2f}{unit}'

        return f'{v}{unit}'


class Scaling(Enum):
    """What scaling factor needs to be applied to a register's value.

    Specified as a divisor instead, because python deals with rounding precision better that way.
    """

    UNIT = 1
    DECI = 10
    CENTI = 100
    MILLI = 1000


class Unit(Enum):
    """Measurement unit for the register value."""

    NONE = ''
    ENERGY_KWH = 'kWh'
    POWER_W = 'W'
    POWER_KW = 'kW'
    POWER_VA = 'VA'
    FREQUENCY_HZ = 'Hz'
    VOLTAGE_V = 'V'
    CURRENT_A = 'A'
    CURRENT_MA = 'mA'
    TEMPERATURE_C = '°C'
    CHARGE_AH = 'Ah'
    TIME_MS = 'ms'
    TIME_S = 'sec'
    TIME_M = 'min'


@unique
class Register(str, Enum):
    """Mixin to help easier access to register bank structures."""

    def __new__(cls, value: int, data=None):
        """Allows indexing by register index."""
        if data is None:
            data = {}
        obj = str.__new__(cls, f'{cls.__name__[0]}R:{int(value)}')
        obj._value_ = value
        obj.type = data.get('type', Type.UINT16)
        obj.scaling = data.get('scaling', Scaling.UNIT)
        obj.unit = data.get('unit', Unit.NONE)
        obj.description = data.get('description', None)
        obj.write_safe = data.get('write_safe', False)
        return obj

    def __str__(self) -> str:
        return f'{self.__class__.__name__[0]}R:{self.value:03}'

    def __repr__(self) -> str:
        return self.__str__()

    def convert(self, val):
        """Convert val to its true representation as determined by the register type."""
        return self.type.convert(val, self.scaling.value)

    def repr(self, val):
        """Convert val to its true representation as determined by the register type."""
        return self.type.repr(val, self.scaling.value, self.unit.value)


class HoldingRegister(Register):
    """Holding Register definitions."""

    DEVICE_TYPE_CODE = (0, {'type': Type.HEX})  # 0x[01235]xxx where 2=Inv?, 5==EMS
    INVERTER_MODULE_H = (1, {'type': Type.UINT32_HIGH})
    INVERTER_MODULE_L = (2, {'type': Type.UINT32_LOW})
    NUM_MPPT_AND_NUM_PHASES = (3, {'type': Type.DUINT8})  # number of MPPTs and phases
    HOLDING_REG004 = 4
    HOLDING_REG005 = 5
    HOLDING_REG006 = 6
    ENABLE_AMMETER = (7, {'type': Type.BOOL})
    FIRST_BATTERY_SERIAL_NUMBER_1_2 = (8, {'type': Type.ASCII})
    FIRST_BATTERY_SERIAL_NUMBER_3_4 = (9, {'type': Type.ASCII})
    FIRST_BATTERY_SERIAL_NUMBER_5_6 = (10, {'type': Type.ASCII})
    FIRST_BATTERY_SERIAL_NUMBER_7_8 = (11, {'type': Type.ASCII})
    FIRST_BATTERY_SERIAL_NUMBER_9_10 = (12, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_1_2 = (13, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_3_4 = (14, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_5_6 = (15, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_7_8 = (16, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_9_10 = (17, {'type': Type.ASCII})
    FIRST_BATTERY_BMS_FIRMWARE_VERSION = 18
    DSP_FIRMWARE_VERSION = 19
    ENABLE_CHARGE_TARGET = (20, {'type': Type.BOOL, 'write_safe': True})
    ARM_FIRMWARE_VERSION = 21
    USB_DEVICE_INSERTED = 22  # (0:none, 1:wifi, 2:disk)
    SELECT_ARM_CHIP = (23, {'type': Type.BOOL})  # False: DSP selected
    VARIABLE_ADDRESS = 24
    VARIABLE_VALUE = (25, {'type': Type.INT16})
    P_GRID_PORT_MAX_OUTPUT = (26, {'unit': Unit.POWER_W})  # Export limit
    BATTERY_POWER_MODE = (27, {'write_safe': True})  # 0:export/max 1:demand/self-consumption
    ENABLE_60HZ_FREQ_MODE = (28, {'type': Type.BOOL})  # 0:50hz
    # battery calibration stages (0:off  1:start/discharge  2:set lower limit  3:charge
    # 4:set upper limit  5:balance  6:set full capacity  7:finish)
    SOC_FORCE_ADJUST = 29
    INVERTER_MODBUS_ADDRESS = (30, {'type': Type.UINT8})  # default 0x11
    HOLDING_REG31 = (31, {})
    HOLDING_REG32 = (32, {})
    USER_CODE = 33
    MODBUS_VERSION = (34, {'scaling': Scaling.CENTI})  # inverter:1.40 EMS:3.40
    SYSTEM_TIME_YEAR = (35, {'write_safe': True})
    SYSTEM_TIME_MONTH = (36, {'write_safe': True})
    SYSTEM_TIME_DAY = (37, {'write_safe': True})
    SYSTEM_TIME_HOUR = (38, {'write_safe': True})
    SYSTEM_TIME_MINUTE = (39, {'write_safe': True})
    SYSTEM_TIME_SECOND = (40, {'write_safe': True})
    ENABLE_DRM_RJ45_PORT = (41, {'type': Type.BOOL})
    CT_ADJUST = (42, {'type': Type.BITFIELD})  # bitfield? 1:negative/reverse polarity of blue CT clamp sensor
    CHARGE_AND_DISCHARGE_SOC = (43, {'type': Type.DUINT8})
    DISCHARGE_SLOT_2_START = (44, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_2_END = (45, {'type': Type.TIME, 'write_safe': True})
    BMS_CHIP_VERSION = 46  # different from 18, 101 seems the norm?
    METER_TYPE = 47  # 0:CT/EM418, 1:EM115
    REVERSE_115_METER_DIRECT = (48, {'type': Type.BOOL})
    REVERSE_418_METER_DIRECT = (49, {'type': Type.BOOL})
    # from beta remote control: Inverter Max Output Active Power Percent
    ACTIVE_POWER_RATE = (50, {'type': Type.PERCENT, 'write_safe': True})
    REACTIVE_POWER_RATE = (51, {'type': Type.PERCENT})
    POWER_FACTOR = (52, {'type': Type.POWER_FACTOR})
    INVERTER_STATE = (53, {'type': Type.DUINT8})  # MSB:auto-restart state, LSB:on/off
    BATTERY_TYPE = 54  # 0:lead acid  1:lithium
    BATTERY_NOMINAL_CAPACITY = (55, {'unit': Unit.CHARGE_AH})
    DISCHARGE_SLOT_1_START = (56, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_1_END = (57, {'type': Type.TIME, 'write_safe': True})
    ENABLE_AUTO_JUDGE_BATTERY_TYPE = (58, {'type': Type.BOOL})
    ENABLE_DISCHARGE = (59, {'type': Type.BOOL, 'write_safe': True})
    V_PV_INPUT_START = (60, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    INVERTER_START_TIME = (61, {'unit': Unit.TIME_S})
    INVERTER_RESTART_DELAY_TIME = (62, {'unit': Unit.TIME_S})
    V_AC_LOW_OUT = (63, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC_HIGH_OUT = (64, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    F_AC_LOW_OUT = (65, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    F_AC_HIGH_OUT = (66, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    V_AC_LOW_OUT_TIME = (67, {})
    V_AC_HIGH_OUT_TIME = (68, {})
    F_AC_LOW_OUT_TIME = (69, {})
    F_AC_HIGH_OUT_TIME = (70, {})
    V_AC_LOW_IN = (71, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC_HIGH_IN = (72, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    F_AC_LOW_IN = (73, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    F_AC_HIGH_IN = (74, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    V_AC_LOW_IN_TIME = (75, {})
    V_AC_HIGH_IN_TIME = (76, {})
    F_AC_LOW_IN_TIME = (77, {})
    F_AC_HIGH_IN_TIME = (78, {})
    V_AC_LOW_C = (79, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC_HIGH_C = (80, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    F_AC_LOW_C = (81, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    F_AC_HIGH_C = (82, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    V_10_MIN_PROTECTION = (83, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    ISO1 = 84
    ISO2 = 85
    # protection events: ground fault circuit interrupter, DC injection
    GFCI_1_I = (86, {'unit': Unit.CURRENT_MA})
    GFCI_1_TIME = (87, {})
    GFCI_2_I = (88, {'unit': Unit.CURRENT_MA})
    GFCI_2_TIME = (89, {})
    DCI_1_I = (90, {'unit': Unit.CURRENT_MA})
    DCI_1_TIME = (91, {})
    DCI_2_I = (92, {'unit': Unit.CURRENT_MA})
    DCI_2_TIME = (93, {})
    CHARGE_SLOT_1_START = (94, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_1_END = (95, {'type': Type.TIME, 'write_safe': True})
    ENABLE_CHARGE = (96, {'type': Type.BOOL, 'write_safe': True})
    V_BATTERY_UNDER_PROTECTION_LIMIT = (97, {'scaling': Scaling.CENTI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_OVER_PROTECTION_LIMIT = (98, {'scaling': Scaling.CENTI, 'unit': Unit.VOLTAGE_V})
    PV1_VOLTAGE_ADJUST = (99, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    PV2_VOLTAGE_ADJUST = (100, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    GRID_R_VOLTAGE_ADJUST = (101, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    GRID_S_VOLTAGE_ADJUST = (102, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    GRID_T_VOLTAGE_ADJUST = (103, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    GRID_POWER_ADJUST = (104, {'unit': Unit.POWER_W})
    BATTERY_VOLTAGE_ADJUST = (105, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    PV1_POWER_ADJUST = (106, {'unit': Unit.POWER_W})
    PV2_POWER_ADJUST = (107, {'unit': Unit.POWER_W})
    BATTERY_LOW_FORCE_CHARGE_TIME = (108, {'unit': Unit.TIME_M})
    ENABLE_BMS_READ = (109, {'type': Type.BOOL})
    BATTERY_SOC_RESERVE = (110, {'type': Type.PERCENT, 'write_safe': True})
    # in beta dashboard: Battery Charge & Discharge Power, but rendered as W (50%=2600W), don't set above this?
    BATTERY_CHARGE_LIMIT = (111, {'type': Type.PERCENT, 'write_safe': True})
    BATTERY_DISCHARGE_LIMIT = (112, {'type': Type.PERCENT, 'write_safe': True})
    ENABLE_BUZZER = (113, {'type': Type.BOOL})
    # in beta dashboard: Battery Cutoff % Limit
    BATTERY_DISCHARGE_MIN_POWER_RESERVE = (114, {'type': Type.PERCENT, 'write_safe': True})
    ISLAND_CHECK_CONTINUE = 115
    CHARGE_TARGET_SOC = (116, {'type': Type.PERCENT, 'write_safe': True})  # when ENABLE_CHARGE_TARGET is enabled
    HOLDING_REG117 = (117, {'type': Type.PERCENT})
    DISCHARGE_SOC_STOP_2 = (118, {'type': Type.PERCENT})
    CHARGE_SOC_STOP_1 = (119, {'type': Type.PERCENT})
    DISCHARGE_SOC_STOP_1 = (120, {'type': Type.PERCENT})
    LOCAL_COMMAND_TEST = (121, {})
    POWER_FACTOR_FUNCTION_MODEL = (122, {})
    FREQUENCY_LOAD_LIMIT_RATE = (123, {})
    ENABLE_LOW_VOLTAGE_FAULT_RIDE_THROUGH = (124, {'type': Type.BOOL})
    ENABLE_FREQUENCY_DERATING = (125, {'type': Type.BOOL})
    ENABLE_ABOVE_6KW_SYSTEM = (126, {'type': Type.BOOL})
    START_SYSTEM_AUTO_TEST = (127, {'type': Type.BOOL})
    ENABLE_SPI = (128, {'type': Type.BOOL})
    PF_CMD_MEMORY_STATE = (129, {})
    # power factor limit line points: LP=load percentage, PF=power factor
    PF_LIMIT_LP1_LP = (130, {'type': Type.PERCENT})
    PF_LIMIT_LP1_PF = (131, {'type': Type.POWER_FACTOR})
    PF_LIMIT_LP2_LP = (132, {'type': Type.PERCENT})
    PF_LIMIT_LP2_PF = (133, {'type': Type.POWER_FACTOR})
    PF_LIMIT_LP3_LP = (134, {'type': Type.PERCENT})
    PF_LIMIT_LP3_PF = (135, {'type': Type.POWER_FACTOR})
    PF_LIMIT_LP4_LP = (136, {'type': Type.PERCENT})
    PF_LIMIT_LP4_PF = (137, {'type': Type.POWER_FACTOR})
    CEI021_V1S = (138, {})
    CEI021_V2S = (139, {})
    CEI021_V1L = (140, {})
    CEI021_V2L = (141, {})
    CEI021_Q_LOCK_IN_POWER = (142, {'type': Type.PERCENT})
    CEI021_Q_LOCK_OUT_POWER = (143, {'type': Type.PERCENT})
    CEI021_LOCK_IN_GRID_VOLTAGE = (144, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    CEI021_LOCK_OUT_GRID_VOLTAGE = (145, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    HOLDING_REG146 = (146, {})
    HOLDING_REG147 = (147, {})
    HOLDING_REG148 = (148, {})
    HOLDING_REG149 = (149, {})
    HOLDING_REG150 = (150, {})
    HOLDING_REG151 = (151, {})
    HOLDING_REG152 = (152, {})
    HOLDING_REG153 = (153, {})
    HOLDING_REG154 = (154, {})
    HOLDING_REG155 = (155, {})
    HOLDING_REG156 = (156, {})
    HOLDING_REG157 = (157, {})
    HOLDING_REG158 = (158, {})
    HOLDING_REG159 = (159, {})
    HOLDING_REG160 = (160, {})
    HOLDING_REG161 = (161, {})
    HOLDING_REG162 = (162, {})
    REBOOT_INVERTER = (163, {'write_safe': True})
    HOLDING_REG164 = (164, {})
    HOLDING_REG165 = (165, {})
    HOLDING_REG166 = (166, {})
    HOLDING_REG167 = (167, {})
    HOLDING_REG168 = (168, {})
    HOLDING_REG169 = (169, {})
    HOLDING_REG170 = (170, {})
    HOLDING_REG171 = (171, {})
    HOLDING_REG172 = (172, {})
    HOLDING_REG173 = (173, {})
    HOLDING_REG174 = (174, {})
    HOLDING_REG175 = (175, {})
    HOLDING_REG176 = (176, {})
    HOLDING_REG177 = (177, {})
    HOLDING_REG178 = (178, {})
    HOLDING_REG179 = (179, {})
    HOLDING_REG180 = (180, {})
    HOLDING_REG181 = (181, {})
    HOLDING_REG182 = (182, {})
    HOLDING_REG183 = (183, {})
    HOLDING_REG184 = (184, {})
    HOLDING_REG185 = (185, {})
    HOLDING_REG186 = (186, {})
    HOLDING_REG187 = (187, {})
    HOLDING_REG188 = (188, {})
    HOLDING_REG189 = (189, {})
    HOLDING_REG190 = (190, {})
    HOLDING_REG191 = (191, {})
    HOLDING_REG192 = (192, {})
    HOLDING_REG193 = (193, {})
    HOLDING_REG194 = (194, {})
    HOLDING_REG195 = (195, {})
    HOLDING_REG196 = (196, {})
    HOLDING_REG197 = (197, {})
    HOLDING_REG198 = (198, {})
    HOLDING_REG199 = (199, {})
    HOLDING_REG200 = (200, {})
    HOLDING_REG201 = (201, {})

    HOLDING_REG240 = (240, {})
    HOLDING_REG241 = (241, {})
    CHARGE_TARGET_SOC_1 = (242, {'type': Type.PERCENT, 'write_safe': True})
    CHARGE_SLOT_2_START = (243, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_2_END = (244, {'type': Type.TIME, 'write_safe': True})
    CHARGE_TARGET_SOC_2 = (245, {'type': Type.PERCENT, 'write_safe': True})
    CHARGE_SLOT_3_START = (246, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_3_END = (247, {'type': Type.TIME, 'write_safe': True})
    CHARGE_TARGET_SOC_3 = (248, {'type': Type.PERCENT, 'write_safe': True})
    CHARGE_SLOT_4_START = (249, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_4_END = (250, {'type': Type.TIME, 'write_safe': True})
    CHARGE_TARGET_SOC_4 = (251, {'type': Type.PERCENT, 'write_safe': True})
    CHARGE_SLOT_5_START = (252, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_5_END = (253, {'type': Type.TIME, 'write_safe': True})
    CHARGE_TARGET_SOC_5 = (254, {'type': Type.PERCENT, 'write_safe': True})
    CHARGE_SLOT_6_START = (255, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_6_END = (256, {'type': Type.TIME, 'write_safe': True})
    CHARGE_TARGET_SOC_6 = (257, {'type': Type.PERCENT, 'write_safe': True})
    CHARGE_SLOT_7_START = (258, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_7_END = (259, {'type': Type.TIME, 'write_safe': True})
    CHARGE_TARGET_SOC_7 = (260, {'type': Type.PERCENT, 'write_safe': True})
    CHARGE_SLOT_8_START = (261, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_8_END = (262, {'type': Type.TIME, 'write_safe': True})
    CHARGE_TARGET_SOC_8 = (263, {'type': Type.PERCENT, 'write_safe': True})
    CHARGE_SLOT_9_START = (264, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_9_END = (265, {'type': Type.TIME, 'write_safe': True})
    CHARGE_TARGET_SOC_9 = (266, {'type': Type.PERCENT, 'write_safe': True})
    CHARGE_SLOT_10_START = (267, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_10_END = (268, {'type': Type.TIME, 'write_safe': True})
    CHARGE_TARGET_SOC_10 = (269, {'type': Type.PERCENT, 'write_safe': True})
    HOLDING_REG270 = (270, {})
    HOLDING_REG271 = (271, {})
    DISCHARGE_TARGET_SOC_1 = (272, {'type': Type.PERCENT, 'write_safe': True})
    HOLDING_REG273 = (273, {})
    HOLDING_REG274 = (274, {})
    DISCHARGE_TARGET_SOC_2 = (275, {'type': Type.PERCENT, 'write_safe': True})
    DISCHARGE_SLOT_3_START = (276, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_3_END = (277, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_TARGET_SOC_3 = (278, {'type': Type.PERCENT, 'write_safe': True})
    DISCHARGE_SLOT_4_START = (279, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_4_END = (280, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_TARGET_SOC_4 = (281, {'type': Type.PERCENT, 'write_safe': True})
    DISCHARGE_SLOT_5_START = (282, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_5_END = (283, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_TARGET_SOC_5 = (284, {'type': Type.PERCENT, 'write_safe': True})
    DISCHARGE_SLOT_6_START = (285, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_6_END = (286, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_TARGET_SOC_6 = (287, {'type': Type.PERCENT, 'write_safe': True})
    DISCHARGE_SLOT_7_START = (288, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_7_END = (289, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_TARGET_SOC_7 = (290, {'type': Type.PERCENT, 'write_safe': True})
    DISCHARGE_SLOT_8_START = (291, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_8_END = (292, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_TARGET_SOC_8 = (293, {'type': Type.PERCENT, 'write_safe': True})
    DISCHARGE_SLOT_9_START = (294, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_9_END = (295, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_TARGET_SOC_9 = (296, {'type': Type.PERCENT, 'write_safe': True})
    DISCHARGE_SLOT_10_START = (297, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_10_END = (298, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_TARGET_SOC_10 = (299, {'type': Type.PERCENT, 'write_safe': True})
    HOLDING_REG300 = (300, {})
    HOLDING_REG301 = (301, {})
    HOLDING_REG302 = (302, {})
    HOLDING_REG303 = (303, {})
    HOLDING_REG304 = (304, {})
    PV_INPUT_MODE = (305, {'write_safe': True})   #0,1 - BOOL?
    HOLDING_REG306 = (306, {})
    HOLDING_REG307 = (307, {})
    HOLDING_REG308 = (308, {})
    HOLDING_REG309 = (309, {})
    HOLDING_REG310 = (310, {})
    LOCAL_CONTROL_MODE = (311, {'write_safe': True})   #0,1,2
    HOLDING_REG312 = (312, {})
    HOLDING_REG313 = (313, {})
    HOLDING_REG314 = (314, {})
    HOLDING_REG315 = (315, {})
    HOLDING_REG316 = (316, {})
    HOLDING_REG317 = (317, {})
    BATTERY_PAUSE_MODE = (318, {'write_safe': True})    #0,1,2,3
    BATTERY_PAUSE_SLOT_START = (319, {'type': Type.TIME, 'write_safe': True})
    BATTERY_PAUSE_SLOT_END = (320, {'type': Type.TIME, 'write_safe': True})
    HOLDING_REG321 = (321, {})
    HOLDING_REG322 = (322, {})
    HOLDING_REG323 = (323, {})
    HOLDING_REG324 = (324, {})
    HOLDING_REG325 = (325, {})
    HOLDING_REG326 = (326, {})
    HOLDING_REG327 = (327, {})
    HOLDING_REG328 = (328, {})
    HOLDING_REG329 = (329, {})
    HOLDING_REG330 = (330, {})
    HOLDING_REG331 = (331, {})
    HOLDING_REG332 = (332, {})
    HOLDING_REG333 = (333, {})
    HOLDING_REG334 = (334, {})
    HOLDING_REG335 = (335, {})
    HOLDING_REG336 = (336, {})
    HOLDING_REG337 = (337, {})
    HOLDING_REG338 = (338, {})
    HOLDING_REG339 = (339, {})
    HOLDING_REG340 = (340, {})
    HOLDING_REG341 = (341, {})
    HOLDING_REG342 = (342, {})
    HOLDING_REG343 = (343, {})
    HOLDING_REG344 = (344, {})
    HOLDING_REG345 = (345, {})
    HOLDING_REG346 = (346, {})
    HOLDING_REG347 = (347, {})
    HOLDING_REG348 = (348, {})
    HOLDING_REG349 = (349, {})
    HOLDING_REG350 = (350, {})
    HOLDING_REG351 = (351, {})
    HOLDING_REG352 = (352, {})
    HOLDING_REG353 = (353, {})
    HOLDING_REG354 = (354, {})
    HOLDING_REG355 = (355, {})
    HOLDING_REG356 = (356, {})
    HOLDING_REG357 = (357, {})
    HOLDING_REG358 = (358, {})
    HOLDING_REG359 = (359, {})

class HoldingRegister_AC(Register):
    """Holding Register definitions."""

    DEVICE_TYPE_CODE = (0, {'type': Type.HEX})  # 0x[01235]xxx where 2=Inv?, 5==EMS
    INVERTER_MODULE_H = (1, {'type': Type.UINT32_HIGH})
    INVERTER_MODULE_L = (2, {'type': Type.UINT32_LOW})
    NUM_MPPT_AND_NUM_PHASES = (3, {'type': Type.DUINT8})  # number of MPPTs and phases
    HOLDING_REG004 = 4
    HOLDING_REG005 = 5
    HOLDING_REG006 = 6
    ENABLE_AMMETER = (7, {'type': Type.BOOL})
    FIRST_BATTERY_SERIAL_NUMBER_1_2 = (8, {'type': Type.ASCII})
    FIRST_BATTERY_SERIAL_NUMBER_3_4 = (9, {'type': Type.ASCII})
    FIRST_BATTERY_SERIAL_NUMBER_5_6 = (10, {'type': Type.ASCII})
    FIRST_BATTERY_SERIAL_NUMBER_7_8 = (11, {'type': Type.ASCII})
    FIRST_BATTERY_SERIAL_NUMBER_9_10 = (12, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_1_2 = (13, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_3_4 = (14, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_5_6 = (15, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_7_8 = (16, {'type': Type.ASCII})
    INVERTER_SERIAL_NUMBER_9_10 = (17, {'type': Type.ASCII})
    FIRST_BATTERY_BMS_FIRMWARE_VERSION = 18
    DSP_FIRMWARE_VERSION = 19
    ENABLE_CHARGE_TARGET = (20, {'type': Type.BOOL, 'write_safe': True})
    ARM_FIRMWARE_VERSION = 21
    USB_DEVICE_INSERTED = 22  # (0:none, 1:wifi, 2:disk)
    SELECT_ARM_CHIP = (23, {'type': Type.BOOL})  # False: DSP selected
    VARIABLE_ADDRESS = 24
    VARIABLE_VALUE = (25, {'type': Type.INT16})
    P_GRID_PORT_MAX_OUTPUT = (26, {'unit': Unit.POWER_W})  # Export limit
    BATTERY_POWER_MODE = (27, {'write_safe': True})  # 0:export/max 1:demand/self-consumption
    ENABLE_60HZ_FREQ_MODE = (28, {'type': Type.BOOL})  # 0:50hz
    # battery calibration stages (0:off  1:start/discharge  2:set lower limit  3:charge
    # 4:set upper limit  5:balance  6:set full capacity  7:finish)
    SOC_FORCE_ADJUST = 29
    INVERTER_MODBUS_ADDRESS = (30, {'type': Type.UINT8})  # default 0x11
    HOLDING_REG31 = (31, {})
    HOLDING_REG32 = (32, {})
    USER_CODE = 33
    MODBUS_VERSION = (34, {'scaling': Scaling.CENTI})  # inverter:1.40 EMS:3.40
    SYSTEM_TIME_YEAR = (35, {'write_safe': True})
    SYSTEM_TIME_MONTH = (36, {'write_safe': True})
    SYSTEM_TIME_DAY = (37, {'write_safe': True})
    SYSTEM_TIME_HOUR = (38, {'write_safe': True})
    SYSTEM_TIME_MINUTE = (39, {'write_safe': True})
    SYSTEM_TIME_SECOND = (40, {'write_safe': True})
    ENABLE_DRM_RJ45_PORT = (41, {'type': Type.BOOL})
    CT_ADJUST = (42, {'type': Type.BITFIELD})  # bitfield? 1:negative/reverse polarity of blue CT clamp sensor
    CHARGE_AND_DISCHARGE_SOC = (43, {'type': Type.DUINT8})
    DISCHARGE_SLOT_2_START = (44, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_2_END = (45, {'type': Type.TIME, 'write_safe': True})
    BMS_CHIP_VERSION = 46  # different from 18, 101 seems the norm?
    METER_TYPE = 47  # 0:CT/EM418, 1:EM115
    REVERSE_115_METER_DIRECT = (48, {'type': Type.BOOL})
    REVERSE_418_METER_DIRECT = (49, {'type': Type.BOOL})
    # from beta remote control: Inverter Max Output Active Power Percent
    ACTIVE_POWER_RATE = (50, {'type': Type.PERCENT, 'write_safe': True})
    REACTIVE_POWER_RATE = (51, {'type': Type.PERCENT})
    POWER_FACTOR = (52, {'type': Type.POWER_FACTOR})
    INVERTER_STATE = (53, {'type': Type.DUINT8})  # MSB:auto-restart state, LSB:on/off
    BATTERY_TYPE = 54  # 0:lead acid  1:lithium
    BATTERY_NOMINAL_CAPACITY = (55, {'unit': Unit.CHARGE_AH})
    DISCHARGE_SLOT_1_START = (56, {'type': Type.TIME, 'write_safe': True})
    DISCHARGE_SLOT_1_END = (57, {'type': Type.TIME, 'write_safe': True})
    ENABLE_AUTO_JUDGE_BATTERY_TYPE = (58, {'type': Type.BOOL})
    ENABLE_DISCHARGE = (59, {'type': Type.BOOL, 'write_safe': True})
    V_PV_INPUT_START = (60, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    INVERTER_START_TIME = (61, {'unit': Unit.TIME_S})
    INVERTER_RESTART_DELAY_TIME = (62, {'unit': Unit.TIME_S})
    V_AC_LOW_OUT = (63, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC_HIGH_OUT = (64, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    F_AC_LOW_OUT = (65, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    F_AC_HIGH_OUT = (66, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    V_AC_LOW_OUT_TIME = (67, {})
    V_AC_HIGH_OUT_TIME = (68, {})
    F_AC_LOW_OUT_TIME = (69, {})
    F_AC_HIGH_OUT_TIME = (70, {})
    V_AC_LOW_IN = (71, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC_HIGH_IN = (72, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    F_AC_LOW_IN = (73, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    F_AC_HIGH_IN = (74, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    V_AC_LOW_IN_TIME = (75, {})
    V_AC_HIGH_IN_TIME = (76, {})
    F_AC_LOW_IN_TIME = (77, {})
    F_AC_HIGH_IN_TIME = (78, {})
    V_AC_LOW_C = (79, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC_HIGH_C = (80, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    F_AC_LOW_C = (81, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    F_AC_HIGH_C = (82, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    V_10_MIN_PROTECTION = (83, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    ISO1 = 84
    ISO2 = 85
    # protection events: ground fault circuit interrupter, DC injection
    GFCI_1_I = (86, {'unit': Unit.CURRENT_MA})
    GFCI_1_TIME = (87, {})
    GFCI_2_I = (88, {'unit': Unit.CURRENT_MA})
    GFCI_2_TIME = (89, {})
    DCI_1_I = (90, {'unit': Unit.CURRENT_MA})
    DCI_1_TIME = (91, {})
    DCI_2_I = (92, {'unit': Unit.CURRENT_MA})
    DCI_2_TIME = (93, {})
    CHARGE_SLOT_1_START = (94, {'type': Type.TIME, 'write_safe': True})
    CHARGE_SLOT_1_END = (95, {'type': Type.TIME, 'write_safe': True})
    ENABLE_CHARGE = (96, {'type': Type.BOOL, 'write_safe': True})
    V_BATTERY_UNDER_PROTECTION_LIMIT = (97, {'scaling': Scaling.CENTI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_OVER_PROTECTION_LIMIT = (98, {'scaling': Scaling.CENTI, 'unit': Unit.VOLTAGE_V})
    PV1_VOLTAGE_ADJUST = (99, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    PV2_VOLTAGE_ADJUST = (100, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    GRID_R_VOLTAGE_ADJUST = (101, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    GRID_S_VOLTAGE_ADJUST = (102, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    GRID_T_VOLTAGE_ADJUST = (103, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    GRID_POWER_ADJUST = (104, {'unit': Unit.POWER_W})
    BATTERY_VOLTAGE_ADJUST = (105, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    PV1_POWER_ADJUST = (106, {'unit': Unit.POWER_W})
    PV2_POWER_ADJUST = (107, {'unit': Unit.POWER_W})
    BATTERY_LOW_FORCE_CHARGE_TIME = (108, {'unit': Unit.TIME_M})
    ENABLE_BMS_READ = (109, {'type': Type.BOOL})
    BATTERY_SOC_RESERVE = (110, {'type': Type.PERCENT, 'write_safe': True})
    # in beta dashboard: Battery Charge & Discharge Power, but rendered as W (50%=2600W), don't set above this?
    BATTERY_CHARGE_LIMIT = (111, {'type': Type.PERCENT, 'write_safe': True})
    BATTERY_DISCHARGE_LIMIT = (112, {'type': Type.PERCENT, 'write_safe': True})
    ENABLE_BUZZER = (113, {'type': Type.BOOL})
    # in beta dashboard: Battery Cutoff % Limit
    BATTERY_DISCHARGE_MIN_POWER_RESERVE = (114, {'type': Type.PERCENT, 'write_safe': True})
    ISLAND_CHECK_CONTINUE = 115
    CHARGE_TARGET_SOC = (116, {'type': Type.PERCENT, 'write_safe': True})  # when ENABLE_CHARGE_TARGET is enabled
    HOLDING_REG117 = (117, {'type': Type.PERCENT})
    DISCHARGE_SOC_STOP_2 = (118, {'type': Type.PERCENT})
    CHARGE_SOC_STOP_1 = (119, {'type': Type.PERCENT})
    DISCHARGE_SOC_STOP_1 = (120, {'type': Type.PERCENT})
    LOCAL_COMMAND_TEST = (121, {})
    POWER_FACTOR_FUNCTION_MODEL = (122, {})
    FREQUENCY_LOAD_LIMIT_RATE = (123, {})
    ENABLE_LOW_VOLTAGE_FAULT_RIDE_THROUGH = (124, {'type': Type.BOOL})
    ENABLE_FREQUENCY_DERATING = (125, {'type': Type.BOOL})
    ENABLE_ABOVE_6KW_SYSTEM = (126, {'type': Type.BOOL})
    START_SYSTEM_AUTO_TEST = (127, {'type': Type.BOOL})
    ENABLE_SPI = (128, {'type': Type.BOOL})
    PF_CMD_MEMORY_STATE = (129, {})
    # power factor limit line points: LP=load percentage, PF=power factor
    PF_LIMIT_LP1_LP = (130, {'type': Type.PERCENT})
    PF_LIMIT_LP1_PF = (131, {'type': Type.POWER_FACTOR})
    PF_LIMIT_LP2_LP = (132, {'type': Type.PERCENT})
    PF_LIMIT_LP2_PF = (133, {'type': Type.POWER_FACTOR})
    PF_LIMIT_LP3_LP = (134, {'type': Type.PERCENT})
    PF_LIMIT_LP3_PF = (135, {'type': Type.POWER_FACTOR})
    PF_LIMIT_LP4_LP = (136, {'type': Type.PERCENT})
    PF_LIMIT_LP4_PF = (137, {'type': Type.POWER_FACTOR})
    CEI021_V1S = (138, {})
    CEI021_V2S = (139, {})
    CEI021_V1L = (140, {})
    CEI021_V2L = (141, {})
    CEI021_Q_LOCK_IN_POWER = (142, {'type': Type.PERCENT})
    CEI021_Q_LOCK_OUT_POWER = (143, {'type': Type.PERCENT})
    CEI021_LOCK_IN_GRID_VOLTAGE = (144, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    CEI021_LOCK_OUT_GRID_VOLTAGE = (145, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    HOLDING_REG146 = (146, {})
    HOLDING_REG147 = (147, {})
    HOLDING_REG148 = (148, {})
    HOLDING_REG149 = (149, {})
    HOLDING_REG150 = (150, {})
    HOLDING_REG151 = (151, {})
    HOLDING_REG152 = (152, {})
    HOLDING_REG153 = (153, {})
    HOLDING_REG154 = (154, {})
    HOLDING_REG155 = (155, {})
    HOLDING_REG156 = (156, {})
    HOLDING_REG157 = (157, {})
    HOLDING_REG158 = (158, {})
    HOLDING_REG159 = (159, {})
    HOLDING_REG160 = (160, {})
    HOLDING_REG161 = (161, {})
    HOLDING_REG162 = (162, {})
    REBOOT_INVERTER = (163, {'write_safe': True})
    HOLDING_REG164 = (164, {})
    HOLDING_REG165 = (165, {})
    HOLDING_REG166 = (166, {})
    HOLDING_REG167 = (167, {})
    HOLDING_REG168 = (168, {})
    HOLDING_REG169 = (169, {})
    HOLDING_REG170 = (170, {})
    HOLDING_REG171 = (171, {})
    HOLDING_REG172 = (172, {})
    HOLDING_REG173 = (173, {})
    HOLDING_REG174 = (174, {})
    HOLDING_REG175 = (175, {})
    HOLDING_REG176 = (176, {})
    HOLDING_REG177 = (177, {})
    HOLDING_REG178 = (178, {})
    HOLDING_REG179 = (179, {})


class InputRegister(Register):
    """Definitions of what registers in the Input Bank represent."""

    INVERTER_STATUS = 0  # 0:waiting 1:normal 2:warning 3:fault 4:flash/fw update
    V_PV1 = (1, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_PV2 = (2, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_P_BUS = (3, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_N_BUS = (4, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC1 = (5, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    E_BATTERY_THROUGHPUT_TOTAL_H = (6, {'type': Type.UINT32_HIGH, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_BATTERY_THROUGHPUT_TOTAL_L = (7, {'type': Type.UINT32_LOW, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    I_PV1 = (8, {'scaling': Scaling.DECI, 'unit': Unit.CURRENT_A})
    I_PV2 = (9, {'scaling': Scaling.DECI, 'unit': Unit.CURRENT_A})
    I_AC1 = (10, {'scaling': Scaling.DECI, 'unit': Unit.CURRENT_A})
    E_PV_TOTAL_H = (11, {'type': Type.UINT32_HIGH, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_PV_TOTAL_L = (12, {'type': Type.UINT32_LOW, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    F_AC1 = (13, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    CHARGE_STATUS = 14  # 2?
    V_HIGHBRIGH_BUS = 15  # high voltage bus?
    PF_INVERTER_OUT = (16, {'type': Type.POWER_FACTOR})  # should be F_? seems to be hovering between 4800-5400
    E_PV1_DAY = (17, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    P_PV1 = (18, {'unit': Unit.POWER_KW})
    E_PV2_DAY = (19, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    P_PV2 = (20, {'unit': Unit.POWER_KW})
    E_GRID_OUT_TOTAL_H = (21, {'type': Type.UINT32_HIGH, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_GRID_OUT_TOTAL_L = (22, {'type': Type.UINT32_LOW, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_SOLAR_DIVERTER = (23, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    P_INVERTER_OUT = (24, {'type': Type.INT16, 'unit': Unit.POWER_W})
    E_GRID_OUT_DAY = (25, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_GRID_IN_DAY = (26, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_INVERTER_IN_TOTAL_H = (27, {'type': Type.UINT32_HIGH, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_INVERTER_IN_TOTAL_L = (28, {'type': Type.UINT32_LOW, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_DISCHARGE_YEAR = (29, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    P_GRID_OUT = (30, {'type': Type.INT16, 'unit': Unit.POWER_W})
    P_EPS_BACKUP = (31, {'unit': Unit.POWER_W})
    E_GRID_IN_TOTAL_H = (32, {'type': Type.UINT32_HIGH, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_GRID_IN_TOTAL_L = (33, {'type': Type.UINT32_LOW, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    INPUT_REG034 = 34
    E_INVERTER_IN_DAY = (35, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_BATTERY_CHARGE_DAY = (36, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_BATTERY_DISCHARGE_DAY = (37, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    INVERTER_COUNTDOWN = (38, {'unit': Unit.TIME_S})
    FAULT_CODE_H = (39, {'type': Type.BITFIELD})
    FAULT_CODE_L = (40, {'type': Type.BITFIELD})
    TEMP_INVERTER_HEATSINK = (41, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    P_LOAD_DEMAND = (42, {'unit': Unit.POWER_W})
    P_GRID_APPARENT = (43, {'unit': Unit.POWER_VA})
    E_INVERTER_OUT_DAY = (44, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_INVERTER_OUT_TOTAL_H = (45, {'type': Type.UINT32_HIGH, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_INVERTER_OUT_TOTAL_L = (46, {'type': Type.UINT32_LOW, 'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    WORK_TIME_TOTAL_H = (47, {'type': Type.UINT32_HIGH, 'unit': Unit.TIME_S})
    WORK_TIME_TOTAL_L = (48, {'type': Type.UINT32_LOW, 'unit': Unit.TIME_S})
    SYSTEM_MODE = 49  # 0:offline, 1:grid-tied
    V_BATTERY = (50, {'scaling': Scaling.CENTI, 'unit': Unit.VOLTAGE_V})
    I_BATTERY = (51, {'type': Type.INT16, 'scaling': Scaling.CENTI, 'unit': Unit.CURRENT_A})
    P_BATTERY = (52, {'type': Type.INT16, 'unit': Unit.POWER_W})
    V_EPS_BACKUP = (53, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    F_EPS_BACKUP = (54, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    TEMP_CHARGER = (55, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    TEMP_BATTERY = (56, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    CHARGER_WARNING_CODE = 57
    I_GRID_PORT = (58, {'scaling': Scaling.CENTI, 'unit': Unit.CURRENT_A})
    BATTERY_PERCENT = (59, {'type': Type.PERCENT})
    V_BATTERY_CELL_01 = (60, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_02 = (61, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_03 = (62, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_04 = (63, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_05 = (64, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_06 = (65, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_07 = (66, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_08 = (67, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_09 = (68, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_10 = (69, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_11 = (70, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_12 = (71, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_13 = (72, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_14 = (73, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_15 = (74, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_CELL_16 = (75, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    TEMP_BATTERY_CELLS_1 = (76, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    TEMP_BATTERY_CELLS_2 = (77, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    TEMP_BATTERY_CELLS_3 = (78, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    TEMP_BATTERY_CELLS_4 = (79, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    V_BATTERY_CELLS_SUM = (80, {'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    TEMP_BMS_MOS = (81, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    V_BATTERY_OUT_H = (82, {'type': Type.UINT32_HIGH, 'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    V_BATTERY_OUT_L = (83, {'type': Type.UINT32_LOW, 'scaling': Scaling.MILLI, 'unit': Unit.VOLTAGE_V})
    BATTERY_FULL_CAPACITY_H = (84, {'type': Type.UINT32_HIGH, 'scaling': Scaling.CENTI, 'unit': Unit.CHARGE_AH})
    BATTERY_FULL_CAPACITY_L = (85, {'type': Type.UINT32_LOW, 'scaling': Scaling.CENTI, 'unit': Unit.CHARGE_AH})
    BATTERY_DESIGN_CAPACITY_H = (86, {'type': Type.UINT32_HIGH, 'scaling': Scaling.CENTI, 'unit': Unit.CHARGE_AH})
    BATTERY_DESIGN_CAPACITY_L = (87, {'type': Type.UINT32_LOW, 'scaling': Scaling.CENTI, 'unit': Unit.CHARGE_AH})
    BATTERY_REMAINING_CAPACITY_H = (88, {'type': Type.UINT32_HIGH, 'scaling': Scaling.CENTI, 'unit': Unit.CHARGE_AH})
    BATTERY_REMAINING_CAPACITY_L = (89, {'type': Type.UINT32_LOW, 'scaling': Scaling.CENTI, 'unit': Unit.CHARGE_AH})
    BATTERY_STATUS_1_2 = (90, {'type': Type.DUINT8})
    BATTERY_STATUS_3_4 = (91, {'type': Type.DUINT8})
    BATTERY_STATUS_5_6 = (92, {'type': Type.DUINT8})
    BATTERY_STATUS_7 = (93, {'type': Type.DUINT8})
    BATTERY_WARNING_1_2 = (94, {'type': Type.DUINT8})
    INPUT_REG095 = 95
    BATTERY_NUM_CYCLES = 96
    BATTERY_NUM_CELLS = 97
    BMS_FIRMWARE_VERSION = 98
    INPUT_REG099 = 99
    BATTERY_SOC = 100
    BATTERY_DESIGN_CAPACITY_2_H = (101, {'type': Type.UINT32_HIGH, 'scaling': Scaling.CENTI, 'unit': Unit.CHARGE_AH})
    BATTERY_DESIGN_CAPACITY_2_L = (102, {'type': Type.UINT32_LOW, 'scaling': Scaling.CENTI, 'unit': Unit.CHARGE_AH})
    TEMP_BATTERY_MAX = (103, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    TEMP_BATTERY_MIN = (104, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    E_BATTERY_DISCHARGE_TOTAL_2 = (105, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_BATTERY_CHARGE_TOTAL_2 = (106, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    INPUT_REG107 = 107
    INPUT_REG108 = 108
    INPUT_REG109 = 109
    BATTERY_SERIAL_NUMBER_1_2 = (110, {'type': Type.ASCII})
    BATTERY_SERIAL_NUMBER_3_4 = (111, {'type': Type.ASCII})
    BATTERY_SERIAL_NUMBER_5_6 = (112, {'type': Type.ASCII})
    BATTERY_SERIAL_NUMBER_7_8 = (113, {'type': Type.ASCII})
    BATTERY_SERIAL_NUMBER_9_10 = (114, {'type': Type.ASCII})
    USB_INSERTED = (115, {'type': Type.BOOL})  # 0X08 = true; 0X00 = false
    INPUT_REG116 = 116
    INPUT_REG117 = 117
    INPUT_REG118 = 118
    INPUT_REG119 = 119
    INPUT_REG120 = 120
    INPUT_REG121 = 121
    INPUT_REG122 = 122
    INPUT_REG123 = 123
    INPUT_REG124 = 124
    INPUT_REG125 = 125
    INPUT_REG126 = 126
    INPUT_REG127 = 127
    INPUT_REG128 = 128
    INPUT_REG129 = 129
    INPUT_REG130 = 130
    INPUT_REG131 = 131
    INPUT_REG132 = 132
    INPUT_REG133 = 133
    INPUT_REG134 = 134
    INPUT_REG135 = 135
    INPUT_REG136 = 136
    INPUT_REG137 = 137
    INPUT_REG138 = 138
    INPUT_REG139 = 139
    INPUT_REG140 = 140
    INPUT_REG141 = 141
    INPUT_REG142 = 142
    INPUT_REG143 = 143
    INPUT_REG144 = 144
    INPUT_REG145 = 145
    INPUT_REG146 = 146
    INPUT_REG147 = 147
    INPUT_REG148 = 148
    INPUT_REG149 = 149
    INPUT_REG150 = 150
    INPUT_REG151 = 151
    INPUT_REG152 = 152
    INPUT_REG153 = 153
    INPUT_REG154 = 154
    INPUT_REG155 = 155
    INPUT_REG156 = 156
    INPUT_REG157 = 157
    INPUT_REG158 = 158
    INPUT_REG159 = 159
    INPUT_REG160 = 160
    INPUT_REG161 = 161
    INPUT_REG162 = 162
    INPUT_REG163 = 163
    INPUT_REG164 = 164
    INPUT_REG165 = 165
    INPUT_REG166 = 166
    INPUT_REG167 = 167
    INPUT_REG168 = 168
    INPUT_REG169 = 169
    INPUT_REG170 = 170
    INPUT_REG171 = 171
    INPUT_REG172 = 172
    INPUT_REG173 = 173
    INPUT_REG174 = 174
    INPUT_REG175 = 175
    INPUT_REG176 = 176
    INPUT_REG177 = 177
    INPUT_REG178 = 178
    INPUT_REG179 = 179
    E_BATTERY_DISCHARGE_TOTAL = (180, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_BATTERY_CHARGE_TOTAL = (181, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_BATTERY_DISCHARGE_DAY_2 = (182, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    E_BATTERY_CHARGE_DAY_2 = (183, {'scaling': Scaling.DECI, 'unit': Unit.ENERGY_KWH})
    INPUT_REG184 = (184, {})
    INPUT_REG185 = (185, {})
    INPUT_REG186 = (186, {})
    INPUT_REG187 = (187, {})
    INPUT_REG188 = (188, {})
    INPUT_REG189 = (189, {})
    INPUT_REG190 = (190, {})
    INPUT_REG191 = (191, {})
    INPUT_REG192 = (192, {})
    INPUT_REG193 = (193, {})
    INPUT_REG194 = (194, {})
    INPUT_REG195 = (195, {})
    INPUT_REG196 = (196, {})
    INPUT_REG197 = (197, {})
    INPUT_REG198 = (198, {})
    INPUT_REG199 = (199, {})
    INPUT_REG200 = (200, {})
    REMOTE_BMS_RESTART = (201, {'type': Type.BOOL})
    INPUT_REG202 = (202, {})
    INPUT_REG203 = (203, {})
    INPUT_REG204 = (204, {})
    INPUT_REG205 = (205, {})
    INPUT_REG206 = (206, {})
    INPUT_REG207 = (207, {})
    INPUT_REG208 = (208, {})
    INPUT_REG209 = (209, {})
    ISO_FAULT_VALUE = (210, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    GFCI_FAULT_VALUE = (211, {'unit': Unit.CURRENT_MA})
    DCI_FAULT_VALUE = (212, {'scaling': Scaling.CENTI, 'unit': Unit.CURRENT_A})
    V_PV_FAULT_VALUE = (213, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC_FAULT_VALUE = (214, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    F_AV_FAULT_VALUE = (215, {'scaling': Scaling.CENTI, 'unit': Unit.FREQUENCY_HZ})
    TEMP_FAULT_VALUE = (216, {'scaling': Scaling.DECI, 'unit': Unit.TEMPERATURE_C})
    INPUT_REG217 = (217, {})
    INPUT_REG218 = (218, {})
    INPUT_REG219 = (219, {})
    INPUT_REG220 = (220, {})
    INPUT_REG221 = (221, {})
    INPUT_REG222 = (222, {})
    INPUT_REG223 = (223, {})
    INPUT_REG224 = (224, {})
    AUTO_TEST_PROCESS_OR_AUTO_TEST_STEP = (225, {'type': Type.BITFIELD})
    AUTO_TEST_RESULT = (226, {})
    AUTO_TEST_STOP_STEP = (227, {})
    INPUT_REG228 = (228, {})
    SAFETY_V_F_LIMIT = (229, {'scaling': Scaling.DECI})
    SAFETY_TIME_LIMIT = (230, {'unit': Unit.TIME_MS})
    REAL_V_F_VALUE = (231, {'scaling': Scaling.DECI})
    TEST_VALUE = (232, {'scaling': Scaling.DECI})
    TEST_TREAT_VALUE = (233, {'scaling': Scaling.DECI})
    TEST_TREAT_TIME = (234, {})
    INPUT_REG235 = (235, {})
    INPUT_REG236 = (236, {})
    INPUT_REG237 = (237, {})
    INPUT_REG238 = (238, {})
    INPUT_REG239 = (239, {})
    V_AC1_M3 = (240, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC2_M3 = (241, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC3_M3 = (242, {'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    I_AC1_M3 = (243, {'scaling': Scaling.CENTI, 'unit': Unit.CURRENT_A})
    I_AC2_M3 = (244, {'scaling': Scaling.CENTI, 'unit': Unit.CURRENT_A})
    I_AC3_M3 = (245, {'scaling': Scaling.CENTI, 'unit': Unit.CURRENT_A})
    GFCI_M3 = (246, {'scaling': Scaling.DECI, 'unit': Unit.CURRENT_MA})
    INPUT_REG247 = (247, {})
    INPUT_REG248 = (248, {})
    INPUT_REG249 = (249, {})
    INPUT_REG250 = (250, {})
    INPUT_REG251 = (251, {})
    INPUT_REG252 = (252, {})
    INPUT_REG253 = (253, {})
    INPUT_REG254 = (254, {})
    INPUT_REG255 = (255, {})
    INPUT_REG256 = (256, {})
    INPUT_REG257 = (257, {})
    V_PV1_LIMIT = (258, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_PV2_LIMIT = (259, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_BUS_LIMIT = (260, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_N_BUS_LIMIT = (261, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC1_LIMIT = (262, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC2_LIMIT = (263, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC3_LIMIT = (264, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    I_PV1_LIMIT = (265, {'type': Type.INT16, 'unit': Unit.CURRENT_MA})
    I_PV2_LIMIT = (266, {'type': Type.INT16, 'unit': Unit.CURRENT_MA})
    I_AC1_LIMIT = (267, {'type': Type.INT16, 'unit': Unit.CURRENT_MA})
    I_AC2_LIMIT = (268, {'type': Type.INT16, 'unit': Unit.CURRENT_MA})
    I_AC3_LIMIT = (269, {'type': Type.INT16, 'unit': Unit.CURRENT_MA})
    P_AC1_LIMIT = (270, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.POWER_W})
    P_AC2_LIMIT = (271, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.POWER_W})
    P_AC3_LIMIT = (272, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.POWER_W})
    DCI_LIMIT = (273, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.CURRENT_MA})
    GFCI_LIMIT = (274, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.CURRENT_MA})
    V_AC1_M3_LIMIT = (275, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC2_M3_LIMIT = (276, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    V_AC3_M3_LIMIT = (277, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.VOLTAGE_V})
    I_AC1_M3_LIMIT = (278, {'type': Type.INT16, 'scaling': Scaling.CENTI, 'unit': Unit.CURRENT_A})
    I_AC2_M3_LIMIT = (279, {'type': Type.INT16, 'scaling': Scaling.CENTI, 'unit': Unit.CURRENT_A})
    I_AC3_M3_LIMIT = (280, {'type': Type.INT16, 'scaling': Scaling.CENTI, 'unit': Unit.CURRENT_A})
    GFCI_M3_LIMIT = (281, {'type': Type.INT16, 'scaling': Scaling.DECI, 'unit': Unit.CURRENT_MA})
    V_BATTERY_LIMIT = (282, {'type': Type.INT16, 'scaling': Scaling.CENTI, 'unit': Unit.VOLTAGE_V})
    INPUT_REG283 = (283, {})
    INPUT_REG284 = (284, {})
    INPUT_REG285 = (285, {})
    INPUT_REG286 = (286, {})
    INPUT_REG287 = (287, {})
    INPUT_REG288 = (288, {})
    INPUT_REG289 = (289, {})
    INPUT_REG290 = (290, {})
    INPUT_REG291 = (291, {})
    INPUT_REG292 = (292, {})
    INPUT_REG293 = (293, {})
    INPUT_REG294 = (294, {})
    INPUT_REG295 = (295, {})
    INPUT_REG296 = (296, {})
    INPUT_REG297 = (297, {})
    INPUT_REG298 = (298, {})
    INPUT_REG299 = (299, {})
    INPUT_REG300 = (300, {})
    INPUT_REG301 = (301, {})
