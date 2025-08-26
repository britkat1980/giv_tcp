"""
High level interpretation of the CT meters modbus registers.

The Meter itself is the primary class; the others are
supporting enumerations.
"""

from .register import *

from .register import (
    Converter as DT,
    DynamicDoc,
    RegisterDefinition as Def,
    IR, MR,
    RegisterGetter,
)


class Meter(RegisterGetter, metaclass=DynamicDoc):
    # pylint: disable=missing-class-docstring
    # The metaclass turns accesses to __doc__ into calls to
    # _gendoc()  (which we inherit from RegisterGetter)
    # Uses function_code 0x04
    # Slave_addr 0x01-0x08

    _DOC = """Meter presents all meter attributes as python types."""

    REGISTER_LUT = {
        # Input Registers, block 60-119
        "v_phase_1": Def(DT.deci, None, IR(60)),
        "v_phase_2": Def(DT.deci, None, IR(61)),
        "v_phase_3": Def(DT.deci, None, IR(62)),
        "i_phase_1": Def(DT.centi, None, IR(63)),
        "i_phase_2": Def(DT.centi, None, IR(64)),
        "i_phase_3": Def(DT.centi, None, IR(65)),
        "i_ln": Def(DT.centi, None, IR(66)),
        "i_total": Def(DT.centi, None, IR(67)),
        "p_active_phase_1": Def(DT.int16, None, IR(68)),
        "p_active_phase_2": Def(DT.int16, None, IR(69)),
        "p_active_phase_3": Def(DT.int16, None, IR(70)),
        "p_active_total": Def(DT.int16, None, IR(71)),
        "p_reactive_phase_1": Def(DT.int16, None, IR(72)),
        "p_reactive_phase_2": Def(DT.int16, None, IR(73)),
        "p_reactive_phase_3": Def(DT.int16, None, IR(74)),
        "p_reactive_total": Def(DT.int16, None, IR(75)),
        "p_apparent_phase_1": Def(DT.int16, None, IR(76)),
        "p_apparent_phase_2": Def(DT.int16, None, IR(77)),
        "p_apparent_phase_3": Def(DT.int16, None, IR(78)),
        "p_apparent_total": Def(DT.int16, None, IR(79)),
        "pf_phase_1": Def(DT.milli, None, IR(80)),
        "pf_phase_2": Def(DT.milli, None, IR(81)),
        "pf_phase_3": Def(DT.milli, None, IR(82)),
        "pf_total": Def(DT.milli, None, IR(83)),
        "frequency": Def(DT.centi, None, IR(84)),
        "e_import_active": Def(DT.deci, None, IR(85)),
        "e_import_reactive": Def(DT.deci, None, IR(86)),
        "e_export_active": Def(DT.deci, None, IR(87)),
        "e_export_reactive": Def(DT.deci, None, IR(88)),
    }

    def is_valid(self) -> bool:
        """Try to detect if a meter exists based on its attributes."""
        return self.get('v_phase_1') not in (
            None,
            "",
            "\x00",
            "  ",
            0,
        )

class MeterProduct(RegisterGetter, metaclass=DynamicDoc):
    # pylint: disable=missing-class-docstring
    # The metaclass turns accesses to __doc__ into calls to
    # _gendoc()  (which we inherit from RegisterGetter)
    # Uses function_code 0x16
    # Slave_addr 0x01-0x08

    _DOC = """Meter presents all meter attributes as python types."""

    REGISTER_LUT = {
        # Input Registers, block 60-119
        "serial_number": Def(DT.string, None, MR(60), MR(61)),
        "factory_code": Def(DT.string, None, MR(62), MR(63)),
        "meter_type": Def(DT.uint16, None, MR(64)),
        "hardware_version": Def(DT.uint16, None, MR(65)),
        "software_version": Def(DT.uint16, None, MR(66)),
        "modbus_id": Def(DT.uint16, None, MR(67)),
        "baud_rate": Def(DT.uint16, None, MR(68)),
    }

    def is_valid(self) -> bool:
        """Try to detect if a meter exists based on its attributes."""
        return self.get('serial_number') not in (
            None,
            "",
            "\x00\x00",
            "  ",
        )
