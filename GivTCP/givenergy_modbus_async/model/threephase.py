"""
High level interpretation of the Three Phase inverter modbus registers.

The 3PH Inverter itself is the primary class; the others are
supporting enumerations.
"""

from .register import *
from .baseinverter import BaseInverter
from typing import Optional
from .register import (
    Converter as C,
    DynamicDoc,
    HR,
    IR,
    RegisterDefinition as Def,
    RegisterGetter,
)
    

class ThreePhaseInverter(RegisterGetter, metaclass=DynamicDoc):
    # pylint: disable=missing-class-docstring
    # The metaclass turns accesses to __doc__ into calls to
    # _gendoc()  (which we inherit from RegisterGetter)

    _DOC = """Interprets the low-level registers in the inverter as named attributes."""

    # TODO: add register aliases and valid=(min,max) for writable registers

    NEW_LUT = {
        #
        # Three Phase Holding Registers 1000-1124
        #
        #"generation": Def(C.generation, None, HR(0),HR(21)),
        "set_command_save": Def(C.bool, None, HR(1001)),
        "active_rate": Def(C.uint16, None, HR(1002)),
        "reactive_rate": Def(C.uint16, None, HR(1003)),
        "set_power_factor": Def(C.uint16, None, HR(1004)),
        "grid_connect_time": Def(C.uint16, None, HR(1007)),
        "grid_reconnect_time": Def(C.uint16, None, HR(1008)),
        "grid_connect_slope": Def(C.deci, None, HR(1009)),
        "com_baud_rate": Def(C.uint16, None, HR(1010)),
        "grid_reconnect_slope": Def(C.uint16, None, HR(1011)),
        "inverter_max_power": Def((C.hexfield,0), C.threeph_inverter_max_power, HR(1012)),
        "battery_type": Def((C.hexfield,1), BatteryType, HR(1012)),
        #"battery_max_power": Def((C.hexfield,2), C.battery_max_power, HR(1012)),
        "Inverter_Type": Def((C.hexfield,1), InverterType, HR(1013)),
        "meter_fail_enable": Def(C.uint16, None, HR(1017)),
        "v_grid_low_limit_1": Def(C.deci, None, HR(1018)),
        "v_grid_high_limit_1": Def(C.deci, None, HR(1019)),
        "f_grid_low_limit_1": Def(C.centi, None, HR(1020)),
        "f_grid_high_limit_1": Def(C.centi, None, HR(1021)),
        "v_grid_low_limit_2": Def(C.deci, None, HR(1022)),
        "v_grid_high_limit_2": Def(C.deci, None, HR(1023)),
        "f_grid_low_limit_2": Def(C.centi, None, HR(1024)),
        "f_grid_high_limit_2": Def(C.centi, None, HR(1025)),
        "v_grid_low_limit_3": Def(C.deci, None, HR(1026)),
        "v_grid_high_limit_3": Def(C.deci, None, HR(1027)),
        "f_grid_low_limit_3": Def(C.centi, None, HR(1028)),
        "f_grid_high_limit_3": Def(C.centi, None, HR(1029)),
        "v_grid_low_limit_cee": Def(C.deci, None, HR(1030)),
        "v_grid_high_limit_cee": Def(C.deci, None, HR(1031)),
        "f_grid_low_limit_cee": Def(C.centi, None, HR(1032)),
        "f_grid_high_limit_cee": Def(C.centi, None, HR(1033)),
        "time_grid_low_voltage_limit_1": Def(C.centi, None, HR(1034)),
        "time_grid_high_voltage_limit_1": Def(C.centi, None, HR(1035)),
        "time_grid_low_voltage_limit_2": Def(C.centi, None, HR(1036)),
        "time_grid_high_voltage_limit_2": Def(C.centi, None, HR(1037)),
        "time_grid_low_freq_limit_1": Def(C.centi, None, HR(1038)),
        "time_grid_high_freq_limit_1": Def(C.centi, None, HR(1039)),
        "time_grid_low_freq_limit_2": Def(C.centi, None, HR(1040)),
        "time_grid_high_freq_limit_2": Def(C.centi, None, HR(1041)),
        "v_10min_protect": Def(C.deci, None, HR(1042)),
        "pf_model": Def(C.uint16, PowerFactorFunctionModel, HR(1043)),
        "f_over_derate_start": Def(C.centi, None, HR(1045)),
        "f_over_derate_slope": Def(C.uint16, None, HR(1046)),
        "q_lockin_power": Def(C.uint16, None, HR(1047)),
        "pf_lock_in_voltage": Def(C.deci, None, HR(1049)),
        "pf_lock_out_voltage": Def(C.deci, None, HR(1050)),
        "f_under_derate_slope": Def(C.milli, None, HR(1051)),
        "v_reactive_delay_time": Def(C.milli, None, HR(1052)),
        "time_over_freq_delay_time": Def(C.centi, None, HR(1053)),
        "pf_limit_load_1": Def(C.uint16, None, HR(1054)),
        "pf_limit_pf_1": Def(C.uint16, None, HR(1055)),
        "pf_limit_load_2": Def(C.uint16, None, HR(1056)),
        "pf_limit_pf_2": Def(C.uint16, None, HR(1057)),
        "pf_limit_load_3": Def(C.uint16, None, HR(1058)),
        "pf_limit_pf_3": Def(C.uint16, None, HR(1059)),
        "pf_limit_load_4": Def(C.uint16, None, HR(1060)),
        "pf_limit_pf_4": Def(C.uint16, None, HR(1061)),
        "p_export_limit": Def(C.deci, None, HR(1063)),
        "f_under_derate_start": Def(C.centi, None, HR(1064)),
        "f_under_derate_end": Def(C.centi, None, HR(1065)),
        "f_over_derate_end": Def(C.centi, None, HR(1066)),
        "time_under_freq_derate_delay": Def(C.centi, None, HR(1067)),
        "f_over_derate_stop": Def(C.centi, None, HR(1069)),
        "f_over_derate_recovery_delay": Def(C.centi, None, HR(1070)),
        "zero_current_low_voltage": Def(C.deci, None, HR(1071)),
        "zero_current_high_voltage": Def(C.deci, None, HR(1072)),
        "f_power_on_recovery": Def(C.centi, None, HR(1073)),
        "f_under_derate_stop": Def(C.centi, None, HR(1074)),
        "f_under_derate_recovery_delay": Def(C.centi, None, HR(1075)),
        #"pv_input_mode": Def(C.uint16, PVInputMode, HR(1077)),
        "battery_power_cutoff": Def(C.uint16, None, HR(1078)),
        "ac_power_derate_delay": Def(C.centi, None, HR(1079)),
        "battery_type": Def(C.uint16, BatteryType, HR(1080)),
        "max_charge_current": Def(C.uint16, None, HR(1088)),
        "v_battery_LV": Def(C.deci, None, HR(1089)),
        "v_battery_CV": Def(C.deci, None, HR(1090)),
        "lead_acid_number": Def(C.deci, None, HR(1091)),
        "drms_enable": Def(C.uint16, None, HR(1093)),
        "aging_test": Def(C.uint16, None, HR(1098)),
        "bypass_enable": Def(C.uint16, None, HR(1100)),
        "npe_enable": Def(C.uint16, None, HR(1101)),
        "unbalance_output_enable": Def(C.bool, None, HR(1104)),
        "backup_enable": Def(C.uint16, Enable, HR(1105)),
        "v_backup_nominal": Def(C.nominal_voltage, None, HR(1106)),
        "f_backup_nominal": Def(C.nominal_frequency, None, HR(1107)),
        "battery_discharge_limit_ac": Def(C.uint16, None, HR(1108)),
        "battery_soc_reserve": Def(C.uint16, None, HR(1109)),
        "battery_charge_limit_ac": Def(C.uint16, None, HR(1110)),
        "charge_target_soc": Def(C.uint16, None, HR(1111)),
        "ac_charge_enable": Def(C.uint16, Enable, HR(1112)),
        "charge_slot_1": Def(C.timeslot, None, HR(1113),HR(1114)),
        "charge_slot_1_start": Def(C.uint16, None, HR(1113), valid=(0, 2359)),
        "charge_slot_1_end": Def(C.uint16, None, HR(1114), valid=(0, 2359)),
        "charge_slot_2": Def(C.timeslot, None, HR(1115),HR(1116)),
        "charge_slot_2_start": Def(C.uint16, None, HR(1115), valid=(0, 2359)),
        "charge_slot_2_end": Def(C.uint16, None, HR(1116), valid=(0, 2359)),
        "load_compensation_enable": Def(C.uint16, Enable, HR(1117)),
        "discharge_slot_1": Def(C.timeslot, None, HR(1118), HR(1119)),
        "discharge_slot_1_start": Def(C.uint16, None, HR(1118), valid=(0, 2359)),
        "discharge_slot_1_end": Def(C.uint16, None, HR(1119), valid=(0, 2359)),
        "discharge_slot_2": Def(C.timeslot, None, HR(1120), HR(1121)),
        "discharge_slot_2_start": Def(C.uint16, None, HR(1120), valid=(0, 2359)),
        "discharge_slot_2_end": Def(C.uint16, None, HR(1121), valid=(0, 2359)),
        "enable_discharge": Def(C.uint16, Enable, HR(1122)),
        "force_charge_enable": Def(C.uint16, Enable, HR(1123)),
        "battery_maintenance_mode": Def(C.uint16, BatteryMaintenance, HR(1124)),    
        #
        # Input Registers, block 1000-1060 - PV
        #

        "v_pv1": Def(C.deci, None, IR(1001)),
        "v_pv2": Def(C.deci, None, IR(1002)),
        "i_pv1": Def(C.deci, None, IR(1009)),
        "i_pv2": Def(C.deci, None, IR(1010)),
        "p_pv1": Def(C.uint32, C.deci, IR(1017),IR(1018)),
        "p_pv2": Def(C.uint32, C.deci, IR(1019),IR(1020)),
        #
        # Input Registers, block 1060-1120 - Grid
        #
        "v_ac1": Def(C.deci, None, IR(1061)),
        "v_ac2": Def(C.deci, None, IR(1062)),
        "v_ac3": Def(C.deci, None, IR(1063)),
        "i_ac1": Def(C.deci, None, IR(1064)),
        "i_ac2": Def(C.deci, None, IR(1065)),
        "i_ac3": Def(C.deci, None, IR(1066)),
        "f_ac1": Def(C.centi, None, IR(1067)),
        "power_factor": Def(C.int16, None, IR(1068)),
        "p_inverter_out": Def(C.int32, C.deci, IR(1069),IR(1070)),
        "p_inverter_ac_charge": Def(C.uint32, C.deci, IR(1071),IR(1072)),
        "p_grid_apparent": Def(C.uint32, C.deci, IR(1073),IR(1074)),
        "system_mode": Def(C.bool, SystemMode, IR(1075)),
        "status": Def(C.uint16, Status, IR(1076)),
        "start_delay_time": Def(C.uint16, None, IR(1077)),
        "p_meter_import": Def(C.uint32, C.deci, IR(1079),IR(1080)),
        "p_meter_export": Def(C.uint32, C.deci, IR(1081),IR(1082)),
        "p_load_ac1": Def(C.deci, None, IR(1083)),
        "p_load_ac2": Def(C.deci, None, IR(1084)),
        "p_load_ac3": Def(C.deci, None, IR(1085)),
        "p_load_all": Def(C.uint32, C.deci, IR(1089),IR(1090)),
        "p_out_ac1": Def(C.deci, None, IR(1091)),
        "p_out_ac2": Def(C.deci, None, IR(1092)),
        "p_out_ac3": Def(C.deci, None, IR(1093)),
        "v_out_ac1": Def(C.deci, None, IR(1094)),
        "v_out_ac2": Def(C.deci, None, IR(1095)),
        "v_out_ac3": Def(C.deci, None, IR(1096)),
        
        #
        # Input Registers, block 1120-1140 - Battery
        #

        "battery_priority": Def(C.uint16, BatteryPriority, IR(1120)),
        "battery_type": Def(C.int16, BatteryType, IR(1121)),
        "dc_status": Def(C.uint16, Status, IR(1124)),
        "t_inverter": Def(C.deci, None, IR(1128)),
        "t_boost": Def(C.deci, None, IR(1129)),
        "t_buck_boost": Def(C.deci, None, IR(1130)),
        "v_battery_bms": Def(C.deci, None, IR(1131)),
        "battery_soc": Def(C.uint16, None, IR(1132)),
        "v_battery_pcs": Def(C.deci, None, IR(1133)),
        "v_dc_bus": Def(C.deci, None, IR(1134)),
        "v_inv_bus": Def(C.deci, None, IR(1135)),
        "p_battery_discharge": Def(C.uint32, C.deci, IR(1136),IR(1137)),
        "p_battery_charge": Def(C.uint32, C.deci, IR(1138),IR(1139)),
        "i_battery": Def(C.int16, C.deci, IR(1140)),
        
        #
        # Input Registers, block 1180-1240 - EPS
        #
        "f_nominal_eps": Def(C.centi, None, IR(1180)),
        "v_eps_ac1": Def(C.deci, None, IR(1181)),
        "v_eps_ac2": Def(C.deci, None, IR(1182)),
        "v_eps_ac3": Def(C.deci, None, IR(1183)),
        "i_eps_ac1": Def(C.deci, None, IR(1184)),
        "i_eps_ac2": Def(C.deci, None, IR(1185)),
        "i_eps_ac3": Def(C.deci, None, IR(1186)),
        "p_eps_ac1": Def(C.uint32, C.deci, IR(1187),IR(1188)),
        "p_eps_ac2": Def(C.uint32, C.deci, IR(1189),IR(1190)),
        "p_eps_ac3": Def(C.uint32, C.deci, IR(1191),IR(1192)),
        
        #
        # Input Registers, block 1240-1300 - Power
        #
        "p_export": Def(C.uint32, C.deci, IR(1240),IR(1241)),
        "p_meter2": Def(C.uint32, C.deci, IR(1244),IR(1245)),

        #
        # Input Registers, block 1000-1360 - Fault
        #
        "inverter_fault_codes_0": Def((C.inverter_fault_code2,0), None, IR(1300)),
        "inverter_fault_codes_1": Def((C.inverter_fault_code2,1), None, IR(1301)),
        "inverter_fault_codes_2": Def((C.inverter_fault_code2,2), None, IR(1302)),
        "inverter_fault_codes_3": Def((C.inverter_fault_code2,3), None, IR(1303)),
        "inverter_fault_codes_4": Def((C.inverter_fault_code2,4), None, IR(1304)),
        "inverter_fault_codes_5": Def((C.inverter_fault_code2,5), None, IR(1305)),
        "inverter_fault_codes_6": Def((C.inverter_fault_code2,6), None, IR(1306)),
        "inverter_fault_codes_7": Def((C.inverter_fault_code2,7), None, IR(1307)),
        "tph_arm_firmware_version": Def(C.string, None, IR(1327)),
        "ac_dsp_firmware_version": Def(C.string, None, IR(1325)),
        "dc_dsp_firmware_version": Def(C.string, None, IR(1326)),
        "tph_firmware_version": Def(C.string, None, IR(1320), IR(1321), IR(1322), IR(1323), IR(1324)),
        "firmware_version": Def(C.firmware_version, None, IR(1325), IR(1327)),
        "tph_software_version": Def(C.string, None, IR(1317), IR(1318), IR(1319)),
        #
        # Input Registers, block 1360-1413 - Energy
        #
        "e_inverter_out_today": Def(C.uint32, C.deci, IR(1360),IR(1361)),
        "e_inverter_out_total": Def(C.uint32, C.deci, IR(1362),IR(1363)),
        "e_pv1_today": Def(C.uint32, C.deci, IR(1366),IR(1367)),
        "e_pv1_total": Def(C.uint32, C.deci, IR(1368),IR(1369)),
        "e_pv2_today": Def(C.uint32, C.deci, IR(1370),IR(1371)),
        "e_pv2_total": Def(C.uint32, C.deci, IR(1372),IR(1373)),
        "e_pv_total": Def(C.uint32, C.deci, IR(1374),IR(1375)),
        "e_ac_charge_today": Def(C.uint32, C.deci, IR(1376),IR(1377)),
        "e_ac_charge_total": Def(C.uint32, C.deci, IR(1378),IR(1379)),
        "e_import_today": Def(C.uint32, C.deci, IR(1380),IR(1381)),
        "e_import_total": Def(C.uint32, C.deci, IR(1382),IR(1383)),
        "e_export_today": Def(C.uint32, C.deci, IR(1384),IR(1385)),
        "e_export_total": Def(C.uint32, C.deci, IR(1386),IR(1387)),
        "e_battery_discharge_today": Def(C.uint32, C.deci, IR(1388),IR(1389)),
        "e_battery_discharge_total": Def(C.uint32, C.deci, IR(1390),IR(1391)),
        "e_battery_charge_today": Def(C.uint32, C.deci, IR(1392),IR(1393)),
        "e_battery_charge_total": Def(C.uint32, C.deci, IR(1394),IR(1395)),
        "e_load_today": Def(C.uint32, C.deci, IR(1396),IR(1397)),
        "e_load_total": Def(C.uint32, C.deci, IR(1398),IR(1399)),
        "e_export2_today": Def(C.uint32, C.deci, IR(1400),IR(1401)),
        "e_export2_total": Def(C.uint32, C.deci, IR(1402),IR(1403)),
        "e_pv_today": Def(C.uint32, C.deci, IR(1412),IR(1413)),

    }
    REGISTER_LUT=dict(BaseInverter.REGISTER_LUT, **NEW_LUT)

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
