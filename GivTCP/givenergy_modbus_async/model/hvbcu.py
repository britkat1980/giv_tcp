"""
High level interpretation of the HV Battery Control Unit (BCU) modbus registers.

The BCU itself is the primary class; the others are
supporting enumerations.
"""

from .register import (
    Converter as DT,
    DynamicDoc,
    RegisterDefinition as Def,
    IR,
    HR,
    RegisterGetter,
)

"""
Addr:0x70~0x8F
Register start address = (Register base NO) + 240  * (BAMS_Addr  -  0x90);
"""

class BCU(RegisterGetter, metaclass=DynamicDoc):
    # pylint: disable=missing-class-docstring
    # The metaclass turns accesses to __doc__ into calls to
    # _gendoc()  (which we inherit from RegisterGetter)

    _DOC = """Interprets the low-level registers in the inverter as named attributes."""

    # TODO: add register aliases and valid=(min,max) for writable registers
    REGISTER_LUT = {
        # Input Registers, block 60-119
        "pack_software_version": Def(
            DT.gateway_version, None, IR(60), IR(61), IR(62), IR(63)),
        "number_of_module": Def(DT.uint16, None, IR(64)),
        "cells_per_module": Def(DT.uint16, None, IR(65)),
        "cluster_cell_voltage": Def(DT.uint16, None, IR(67)),
        "cluster_cell_temperature": Def(DT.uint16, None, IR(68)),
        "status": Def(DT.uint16, None, IR(70)),
        "battery_voltage": Def(DT.deci, None, IR(73)),
        "load_voltage": Def(DT.deci, None, IR(74)),
        "battery_current": Def(DT.int16, DT.deci, IR(76)),
        "battery_power": Def(DT.milli, None, IR(79)),
        "battery_soc_max": Def((DT.duint8, 0), None, IR(80)),
        "battery_soc_min": Def((DT.duint8, 1), None, IR(80)),
        "battery_soh": Def(DT.uint16, None, IR(81)),
        "charge_energy_total": Def(DT.uint32, DT.deci, IR(82),IR(83)),
        "discharge_energy_total": Def(DT.uint32, DT.deci, IR(84),IR(85)),
        "charge_capacity_total": Def(DT.uint32, None, IR(86),IR(87)),
        "discharge_capacity_total": Def(DT.uint32, None, IR(88),IR(89)),
        "charge_energy_today": Def(DT.uint32, DT.deci, IR(90),IR(91)),
        "discharge_energy_today": Def(DT.uint32, DT.deci, IR(92),IR(93)),
        "charge_capacity_today": Def(DT.uint32, None, IR(94),IR(95)),
        "discharge_capacity_today": Def(DT.uint32, None, IR(96),IR(97)),
        "battery_nominal_capacity": Def(DT.deci, DT.battery_capacity_hv, IR(98)),
        "battery_nominal_capacity_ah": Def(DT.deci, None, IR(98)),
        "remaining_battery_capacity": Def(DT.deci, DT.battery_capacity_hv, IR(99)),
        "remaining_battery_capacity_ah": Def(DT.deci, None, IR(99)),
        "number_of_cycles": Def(DT.deci, None, IR(100)),
        "min_discharge_voltage": Def(DT.deci, None, IR(102)),
        "min_charge_voltage": Def(DT.deci, None, IR(103)),
        "min_discharge_current": Def(DT.deci, None, IR(104)),
        "min_charge_current": Def(DT.deci, None, IR(105)),
    }

    def is_valid(self) -> bool:
        """Try to detect if a battery exists based on its attributes."""
        return self.get('pack_software_version') not in (
            None,
            "",
            "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
            "          ",
        )

