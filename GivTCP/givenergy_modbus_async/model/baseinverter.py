"""
High level interpretation of the inverter modbus registers.

The Inverter itself is the primary class; the others are
supporting enumerations.
"""

from .register import *
from typing import Optional
from .register import (
    Converter as C,
    DynamicDoc,
    HR,
    IR,
    RegisterDefinition as Def,
    RegisterGetter,
)

class BaseInverter(RegisterGetter, metaclass=DynamicDoc):
    # pylint: disable=missing-class-docstring
    # The metaclass turns accesses to __doc__ into calls to
    # _gendoc()  (which we inherit from RegisterGetter)

    _DOC = """Interprets the low-level registers in the inverter as named attributes."""

    # TODO: add register aliases and valid=(min,max) for writable registers
    REGISTER_LUT = {
        #
        # Holding Registers, block 0-59
        #
        "device_type_code": Def(C.hex, None, HR(0)),
        "inverter_max_power": Def(C.hex, C.inverter_max_power, HR(0)),
        "inverter_max_power_new": Def((C.hexfield,2,2), C.inverter_max_power_new, HR(2)),
        "model": Def(C.get_model, None, HR(0),HR(21)),
        "certification_type": Def((C.hexfield,0,2), Certification, HR(2)),
        "battery_max_power": Def(C.battery_max_power, None, HR(0),HR(21)),
        "num_mppt": Def((C.duint8, 0), None, HR(3)),
        "num_phases": Def(C.hex, Phase, HR(0)),
        # HR(4-6) unused
        "enable_ammeter": Def(C.bool, None, HR(7)),
        "first_battery_serial_number": Def(
            C.string, None, HR(8), HR(9), HR(10), HR(11), HR(12)
        ),
        "serial_number": Def(C.string, None, HR(13), HR(14), HR(15), HR(16), HR(17)),
        "first_battery_bms_firmware_version": Def(C.uint16, None, HR(18)),
        "dsp_firmware_version": Def(C.uint16, None, HR(19)),
        "enable_charge_target": Def(C.uint16, Enable, HR(20), valid=(0, 1)),
        "arm_firmware_version": Def(C.uint16, None, HR(21)),
        #"generation": Def(C.generation, Generation, HR(0),HR(21)),
        "firmware_version": Def(C.firmware_version, None, HR(19), HR(21)),
        "usb_device_inserted": Def(C.uint16, UsbDevice, HR(22)),
        "select_arm_chip": Def(C.bool, None, HR(23)),
        "variable_address": Def(C.uint16, None, HR(24)),
        "variable_value": Def(C.uint16, None, HR(25)),
        "grid_port_max_power_output": Def(C.uint16, None, HR(26)),
        "eco_mode": Def(C.uint16, Enable, HR(27), valid=(0, 1)),
        "enable_60hz_freq_mode": Def(C.uint16, Enable, HR(28)),
        "soc_force_adjust": Def(C.uint16, BatteryCalibrationStage, HR(29), valid=(0,3)),
        "modbus_address": Def(C.uint16, None, HR(30)),
        "charge_slot_2": Def(C.timeslot, None, HR(31), HR(32)),
        "charge_slot_2_start": Def(C.uint16, None, HR(31), valid=(0, 2359)),
        "charge_slot_2_end": Def(C.uint16, None, HR(32), valid=(0, 2359)),
        "user_code": Def(C.uint16, None, HR(33)),
        "modbus_version": Def(C.centi, (C.fstr, "0.2f"), HR(34)),
        "system_time": Def(
            C.datetime, None, HR(35), HR(36), HR(37), HR(38), HR(39), HR(40)
        ),
        "enable_drm_rj45_port": Def(C.uint16, Enable, HR(41)),
        "enable_reversed_ct_clamp": Def(C.uint16, Enable, HR(42)),
        "charge_soc": Def((C.duint8, 0), None, HR(43)),
        "discharge_soc": Def((C.duint8, 1), None, HR(43)),
        "discharge_slot_2": Def(C.timeslot, None, HR(44), HR(45)),
        "discharge_slot_2_start": Def(C.uint16, None, HR(44), valid=(0, 2359)),
        "discharge_slot_2_end": Def(C.uint16, None, HR(45), valid=(0, 2359)),
        "bms_firmware_version": Def(C.uint16, None, HR(46)),
        "meter_type": Def(C.uint16, MeterType, HR(47)),
        "enable_reversed_115_meter": Def(C.uint16, Enable, HR(48)),
        "enable_reversed_418_meter": Def(C.uint16, Enable, HR(49)),
        "active_power_rate": Def(C.uint16, None, HR(50)),
        "reactive_power_rate": Def(C.uint16, None, HR(51)),
        "power_factor": Def(C.uint16, None, HR(52)),  # /10_000 - 1
        "enable_inverter_auto_restart": Def((C.duint8, 0), C.bool, HR(53)),
        "enable_inverter": Def((C.duint8, 1), C.bool, HR(53)),
        "battery_type": Def(C.uint16, BatteryType, HR(54)),
        "battery_nominal_capacity": Def(C.battery_capacity, None, HR(55),HR(0)),
        "discharge_slot_1": Def(C.timeslot, None, HR(56), HR(57)),
        "discharge_slot_1_start": Def(C.uint16, None, HR(56), valid=(0, 2359)),
        "discharge_slot_1_end": Def(C.uint16, None, HR(57), valid=(0, 2359)),
        "enable_auto_judge_battery_type": Def(C.uint16, Enable, HR(58)),
        "enable_discharge": Def(C.uint16, Enable, HR(59)),
        #
        # Holding Registers, block 60-119
        #
        "v_pv_start": Def(C.uint16, C.deci, HR(60)),
        "start_countdown_timer": Def(C.uint16, None, HR(61)),
        "restart_delay_time": Def(C.uint16, None, HR(62)),
        # skip protection settings HR(63-93)
        "charge_slot_1": Def(C.timeslot, None, HR(94), HR(95)),
        "charge_slot_1_start": Def(C.uint16, None, HR(94), valid=(0, 2359)),
        "charge_slot_1_end": Def(C.uint16, None, HR(95), valid=(0, 2359)),
        "enable_charge": Def(C.uint16, Enable, HR(96)),
        "battery_low_voltage_protection_limit": Def(C.uint16, C.centi, HR(97)),
        "battery_high_voltage_protection_limit": Def(C.uint16, C.centi, HR(98)),
        # skip voltage adjustment settings 99-104
        "battery_voltage_adjust": Def(C.uint16, C.centi, HR(105)),
        # skip voltage adjustment settings 106-107
        "battery_low_force_charge_time": Def(C.uint16, None, HR(108)),
        "enable_bms_read": Def(C.uint16, Enable, HR(109)),
        "battery_soc_reserve": Def(C.uint16, None, HR(110)),
        "battery_charge_limit": Def(C.uint16, None, HR(111), valid=(0, 50)),
        "battery_discharge_limit": Def(C.uint16, None, HR(112), valid=(0, 50)),
        "enable_buzzer": Def(C.uint16, Enable, HR(113)),
        "battery_discharge_min_power_reserve": Def(
            C.uint16, None, HR(114), valid=(4, 100)
        ),
        # 'island_check_continue': Def(C.uint16, None, HR(115)),
        "charge_target_soc": Def(C.uint16, None, HR(116), valid=(4, 100)),
        "charge_soc_stop_2": Def(C.uint16, None, HR(117)),
        "discharge_soc_stop_2": Def(C.uint16, None, HR(118)),
        "charge_soc_stop_1": Def(C.uint16, None, HR(119)),
        #
        # Holding Registers, block 120-179
        #
        "discharge_soc_stop_1": Def(C.uint16, None, HR(120)),
        "enable_local_command_test": Def(C.uint16, Enable, HR(121)),
        "power_factor_function_model": Def(C.uint16, PowerFactorFunctionModel, HR(122)),
        "frequency_load_limit_rate": Def(C.uint16, None, HR(123)),
        "enable_low_voltage_fault_ride_through": Def(C.uint16, Enable, HR(124)),
        "enable_frequency_derating": Def(C.uint16, Enable, HR(125)),
        "enable_above_6kw_system": Def(C.uint16, Enable, HR(126)),
        "start_system_auto_test": Def(C.bool, None, HR(127)),
        "enable_spi": Def(C.uint16, Enable, HR(128)),
        # skip PF configuration and protection settings 129-166
        "inverter_reboot": Def(C.uint16, None, HR(163)),
        "rtc_enable": Def(C.uint16, Enable, HR(166)),
        "threephase_balance_mode": Def(C.uint16, None, HR(167)),
        "threephase_abc": Def(C.uint16, None, HR(168)),
        "threephase_balance_1": Def(C.uint16, None, HR(169)),
        "threephase_balance_2": Def(C.uint16, None, HR(170)),
        "threephase_balance_3": Def(C.uint16, None, HR(171)),
        # HR(172-174) unused
        "enable_battery_on_pv_or_grid": Def(C.uint16, Enable, HR(175)),
        "debug_inverter": Def(C.uint16, None, HR(176)),
        "enable_ups_mode": Def(C.uint16, Enable, HR(177)),
        "enable_g100_limit_switch": Def(C.bool, None, HR(178)),
        "enable_battery_cable_impedance_alarm": Def(C.bool, None, HR(179)),
        #
        # Holding Registers, block 180-239
        #
        "enable_standard_self_consumption_logic": Def(C.uint16, Enable, HR(199)),
        "cmd_bms_flash_update": Def(C.bool, None, HR(200)),
        # 202-239 - Hot Water Diverter

        # Gen 3 timeslots
        "inverter_errors": Def(C.uint32, C.inverter_fault_code , HR(223),HR(224)),
        "charge_target_soc_1": Def(C.uint16, None, HR(242), valid=(4, 100)),
        "charge_slot_2": Def(C.timeslot, None, HR(243), HR(244)),
        "charge_slot_2_start": Def(C.uint16, None, HR(243), valid=(0, 2359)),
        "charge_slot_2_end": Def(C.uint16, None, HR(244), valid=(0, 2359)),
        "charge_target_soc_2": Def(C.uint16, None, HR(245), valid=(4, 100)),
        "charge_slot_3": Def(C.timeslot, None, HR(246), HR(247)),
        "charge_slot_3_start": Def(C.uint16, None, HR(246), valid=(0, 2359)),
        "charge_slot_3_end": Def(C.uint16, None, HR(247), valid=(0, 2359)),
        "charge_target_soc_3": Def(C.uint16, None, HR(248), valid=(4, 100)),
        "charge_slot_4": Def(C.timeslot, None, HR(249), HR(250)),
        "charge_slot_4_start": Def(C.uint16, None, HR(249), valid=(0, 2359)),
        "charge_slot_4_end": Def(C.uint16, None, HR(250), valid=(0, 2359)),
        "charge_target_soc_4": Def(C.uint16, None, HR(251), valid=(4, 100)),
        "charge_slot_5": Def(C.timeslot, None, HR(252), HR(253)),
        "charge_slot_5_start": Def(C.uint16, None, HR(252), valid=(0, 2359)),
        "charge_slot_5_end": Def(C.uint16, None, HR(253), valid=(0, 2359)),
        "charge_target_soc_5": Def(C.uint16, None, HR(254), valid=(4, 100)),
        "charge_slot_6": Def(C.timeslot, None, HR(255), HR(256)),
        "charge_slot_6_start": Def(C.uint16, None, HR(255), valid=(0, 2359)),
        "charge_slot_6_end": Def(C.uint16, None, HR(256), valid=(0, 2359)),
        "charge_target_soc_6": Def(C.uint16, None, HR(257), valid=(4, 100)),
        "charge_slot_7": Def(C.timeslot, None, HR(258), HR(259)),
        "charge_slot_7_start": Def(C.uint16, None, HR(258), valid=(0, 2359)),
        "charge_slot_7_end": Def(C.uint16, None, HR(259), valid=(0, 2359)),
        "charge_target_soc_7": Def(C.uint16, None, HR(260), valid=(4, 100)),
        "charge_slot_8": Def(C.timeslot, None, HR(261), HR(262)),
        "charge_slot_8_start": Def(C.uint16, None, HR(261), valid=(0, 2359)),
        "charge_slot_8_end": Def(C.uint16, None, HR(262), valid=(0, 2359)),
        "charge_target_soc_8": Def(C.uint16, None, HR(263), valid=(4, 100)),
        "charge_slot_9": Def(C.timeslot, None, HR(264), HR(265)),
        "charge_slot_9_start": Def(C.uint16, None, HR(264), valid=(0, 2359)),
        "charge_slot_9_end": Def(C.uint16, None, HR(265), valid=(0, 2359)),
        "charge_target_soc_9": Def(C.uint16, None, HR(266), valid=(4, 100)),
        "charge_slot_10": Def(C.timeslot, None, HR(267), HR(268)),
        "charge_slot_10_start": Def(C.uint16, None, HR(267), valid=(0, 2359)),
        "charge_slot_10_end": Def(C.uint16, None, HR(268), valid=(0, 2359)),
        "charge_target_soc_10": Def(C.uint16, None, HR(269), valid=(4, 100)),
        "discharge_target_soc_1": Def(C.uint16, None, HR(272), valid=(4, 100)),
        "discharge_target_soc_2": Def(C.uint16, None, HR(275), valid=(4, 100)),
        "discharge_slot_3": Def(C.timeslot, None, HR(276), HR(277)),
        "discharge_slot_3_start": Def(C.uint16, None, HR(276), valid=(0, 2359)),
        "discharge_slot_3_end": Def(C.uint16, None, HR(277), valid=(0, 2359)),
        "discharge_target_soc_3": Def(C.uint16, None, HR(278), valid=(4, 100)),
        "discharge_slot_4": Def(C.timeslot, None, HR(279), HR(280)),
        "discharge_slot_4_start": Def(C.uint16, None, HR(279), valid=(0, 2359)),
        "discharge_slot_4_end": Def(C.uint16, None, HR(280), valid=(0, 2359)),
        "discharge_target_soc_4": Def(C.uint16, None, HR(281), valid=(4, 100)),
        "discharge_slot_5": Def(C.timeslot, None, HR(282), HR(283)),
        "discharge_slot_5_start": Def(C.uint16, None, HR(282), valid=(0, 2359)),
        "discharge_slot_5_end": Def(C.uint16, None, HR(283), valid=(0, 2359)),
        "discharge_target_soc_5": Def(C.uint16, None, HR(284), valid=(4, 100)),
        "discharge_slot_6": Def(C.timeslot, None, HR(285), HR(286)),
        "discharge_slot_6_start": Def(C.uint16, None, HR(285), valid=(0, 2359)),
        "discharge_slot_6_end": Def(C.uint16, None, HR(286), valid=(0, 2359)),
        "discharge_target_soc_6": Def(C.uint16, None, HR(287), valid=(4, 100)),
        "discharge_slot_7": Def(C.timeslot, None, HR(288), HR(289)),
        "discharge_slot_7_start": Def(C.uint16, None, HR(288), valid=(0, 2359)),
        "discharge_slot_7_end": Def(C.uint16, None, HR(289), valid=(0, 2359)),
        "discharge_target_soc_7": Def(C.uint16, None, HR(290), valid=(4, 100)),
        "discharge_slot_8": Def(C.timeslot, None, HR(291), HR(292)),
        "discharge_slot_8_start": Def(C.uint16, None, HR(291), valid=(0, 2359)),
        "discharge_slot_8_end": Def(C.uint16, None, HR(292), valid=(0, 2359)),
        "discharge_target_soc_8": Def(C.uint16, None, HR(293), valid=(4, 100)),
        "discharge_slot_9": Def(C.timeslot, None, HR(294), HR(295)),
        "discharge_slot_9_start": Def(C.uint16, None, HR(294), valid=(0, 2359)),
        "discharge_slot_9_end": Def(C.uint16, None, HR(295), valid=(0, 2359)),
        "discharge_target_soc_9": Def(C.uint16, None, HR(296), valid=(4, 100)),
        "discharge_slot_10": Def(C.timeslot, None, HR(297), HR(298)),
        "discharge_slot_10_start": Def(C.uint16, None, HR(297), valid=(0, 2359)),
        "discharge_slot_10_end": Def(C.uint16, None, HR(298), valid=(0, 2359)),
        "discharge_target_soc_10": Def(C.uint16, None, HR(299), valid=(4, 100)),
        #
        # Holding Registers, block 300-479
        # Single Phase New registers
        #
        "battery_charge_limit_ac": Def(C.uint16, None, HR(313), valid=(0, 100)),
        "battery_discharge_limit_ac": Def(C.uint16, None, HR(314), valid=(0, 100)),
        "battery_pause_mode": Def(C.uint16, BatteryPauseMode, HR(318), valid=(0,3)),
        "battery_pause_slot_1": Def(C.timeslot, None, HR(319), HR(320)),
        "battery_pause_slot_1_start": Def(C.uint16, None, HR(319), valid=(0, 2359)),
        "battery_pause_slot_1_end": Def(C.uint16, None, HR(320), valid=(0, 2359)),
        #
        # Input Registers, block 0-59
        #
        "status": Def(C.uint16, Status, IR(0)),
        "v_pv1": Def(C.deci, None, IR(1)),
        "v_pv2": Def(C.deci, None, IR(2)),
        "v_p_bus": Def(C.deci, None, IR(3)),
        "v_n_bus": Def(C.deci, None, IR(4)),
        "v_ac1": Def(C.deci, None, IR(5)),
        "e_battery_throughput_total": Def(C.uint32, C.deci, IR(6), IR(7)),
        "i_pv1": Def(C.deci, None, IR(8)),
        "i_pv2": Def(C.deci, None, IR(9)),
        "i_ac1": Def(C.deci, None, IR(10)),
        "e_pv_total": Def(C.uint32, C.deci, IR(11), IR(12)),
        "f_ac1": Def(C.centi, None, IR(13)),
        "v_highbrigh_bus": Def(C.deci, None, IR(15)),  ##HV Bus??? (from Givtcp?)
        "e_pv1_day": Def(C.deci, None, IR(17)),
        "p_pv1": Def(C.uint16, None, IR(18)),
        "e_pv2_day": Def(C.deci, None, IR(19)),
        "p_pv2": Def(C.uint16, None, IR(20)),
        "e_grid_out_total": Def(C.uint32, C.deci, IR(21), IR(22)),
        "e_solar_diverter": Def(C.deci, None, IR(23)),
        "p_inverter_out": Def(C.int16, None, IR(24)),
        "e_grid_out_day": Def(C.deci, None, IR(25)),
        "e_grid_in_day": Def(C.deci, None, IR(26)),
        "e_inverter_in_total": Def(C.uint32, C.deci, IR(27), IR(28)),
        "e_discharge_year": Def(C.deci, None, IR(29)),
        "p_grid_out": Def(C.int16, None, IR(30)),
        "p_eps_backup": Def(C.uint16, None, IR(31)),
        "e_grid_in_total": Def(C.uint32, C.deci, IR(32), IR(33)),
        "e_inverter_in_day": Def(C.deci, None, IR(35)),
        "e_battery_charge_today": Def(C.deci, None, IR(36)),
        "e_battery_discharge_today": Def(C.deci, None, IR(37)),
        "inverter_countdown": Def(C.uint16, None, IR(38)),
        # FAULT_CODE_H = (39, {'type': T_BITFIELD})
        # FAULT_CODE_L = (40, {'type': T_BITFIELD})
        "temp_inverter_heatsink": Def(C.deci, None, IR(41)),
        "p_load_demand": Def(C.uint16, None, IR(42)),
        "p_grid_apparent": Def(C.uint16, None, IR(43)),
        "e_inverter_out_day": Def(C.deci, None, IR(44)),
        "e_inverter_out_total": Def(C.uint32, C.deci, IR(45), IR(46)),
        "work_time_total": Def(C.uint32, None, IR(47), IR(48)),
        "system_mode": Def(C.uint16, None, IR(49)),
        "v_battery": Def(C.centi, None, IR(50)),
        "i_battery": Def(C.int16, C.centi, IR(51)),
        "p_battery": Def(C.int16, None, IR(52)),
        "v_eps_backup": Def(C.deci, None, IR(53)),
        "f_eps_backup": Def(C.centi, None, IR(54)),
        "temp_charger": Def(C.deci, None, IR(55)),
        "temp_battery": Def(C.deci, None, IR(56)),
        "battery_errors": Def(C.battery_fault_code, None, IR(56)),
        "i_grid_port": Def(C.centi, None, IR(58)),
        "battery_percent": Def(C.uint16, None, IR(59)),
        "e_battery_discharge_total_2": Def(C.deci, None, HR(180)),
        "e_battery_charge_total_2": Def(C.deci, None, IR(181)),
        "e_battery_discharge_today_2": Def(C.deci, None, IR(182)),
        "e_battery_charge_today_2": Def(C.deci, None, IR(183)),
        #
        # Input Registers, block 240-300
        # Gen3
        #
        "p_combined_generation":Def(C.uint32,None,IR(247),IR(248))

        #
        # Input Registers, block 1600-1631
        # Gateway
        #
    }
    
    @classmethod
    def lookup_writable_register(cls, name: str, value: Optional[int] = None):
        """
        If the named register is writable and value is in range, return index.
        """

        regdef = cls.REGISTER_LUT[name]
        if regdef.valid is None:
            raise ValueError(f'{name} is not writable')
        if len(regdef.registers) > 1:
            raise NotImplementedError('wide register')

        if value is not None:
            if value < regdef.valid[0] or value > regdef.valid[1]:
                raise ValueError(f'{value} out of range for {name}')

            if regdef.valid[1] == 2359:
                # As a special case, assume this register is a time
                if value % 100 >= 60:
                    raise ValueError(f'{value} is not a valid time')

        return regdef.registers[0]._idx  # pylint: disable=protected-access
