"""HV battery modules in the second and later stacks are read at 0x50 + k, offset 120 registers per stack (#611)"""
import types

import modbus_patches
from givenergy_modbus.client import client as client_module
from givenergy_modbus.exceptions import ReadFailure
from givenergy_modbus.model.inverter import Model
from givenergy_modbus.model.plant import Plant, PlantCapabilities
from givenergy_modbus.model.register import IR
from givenergy_modbus.model.register_cache import RegisterCache

def caps(stacks, hv_bmu_addresses):
    return PlantCapabilities(device_type=Model.HYBRID_HV_GEN3, bcu_stacks=stacks, hv_bmu_addresses=hv_bmu_addresses)

def module_registers(base, serial, temp):
    # Cell voltages at IR 60+, temperatures (deci) at IR 90+ and the serial at IR 114-118, offset by base
    regs = {IR(base + 60 + i): 3300 for i in range(24)}
    regs.update({IR(base + 90 + i): temp for i in range(12)})
    raw = serial.encode().ljust(10, b"\0")
    regs.update({IR(base + 114 + j): int.from_bytes(raw[2 * j:2 * j + 2], "big") for j in range(5)})
    return regs

def plant_with(capabilities, modules):
    # modules: {(device address, base): (serial, temp)}
    plant = Plant()
    plant.capabilities = capabilities
    plant.register_caches[0x70] = RegisterCache()
    plant.register_caches[0x71] = RegisterCache()
    for (addr, base), (serial, temp) in modules.items():
        plant.register_caches.setdefault(addr, RegisterCache()).update(module_registers(base, serial, temp))
    return plant

def test_second_stack_polled_at_offset():
    # The #611 system: two 5-module stacks, only the first stack's modules answered at detect (0x50-0x54)
    banks = client_module._refresh_banks(caps([(0, 5), (1, 5)], [0x50, 0x51, 0x52, 0x53, 0x54]))
    assert [(a, b, c) for a, b, c in banks if 0x50 <= a < 0x70] == \
        [(0x50 + k, 60, 60) for k in range(5)] + [(0x50 + k, 180, 60) for k in range(5)]

def test_single_stack_unchanged():
    assert modbus_patches.hv_stack_module_banks(caps([(0, 3)], [0x50, 0x51, 0x52])) == []

def test_three_phase_two_stacks_use_offset_layout():
    # #614: on a three-phase with two 6-module stacks, detect listed 0x56-0x5b, which never held stack 2's data.
    # 3.5 (the old library) read stack 2 at 0x50-0x55, IR 180-239, so use that and don't poll 0x56-0x5b
    c = PlantCapabilities(device_type=Model.HYBRID_3PH, bcu_stacks=[(0, 6), (1, 6)], hv_bmu_addresses=list(range(0x50, 0x5c)))
    modules = [(a, b, n) for a, b, n in client_module._refresh_banks(c) if 0x50 <= a < 0x70]
    assert modules == [(0x50 + k, 60, 60) for k in range(6)] + [(0x50 + k, 180, 60) for k in range(6)]

def test_module_reads_left_out_when_skipped():
    c = caps([(0, 2), (1, 2)], [0x50, 0x51])
    assert modbus_patches.hv_module_banks(c) == [(0x50, 60, 60), (0x51, 60, 60), (0x50, 180, 60), (0x51, 180, 60)]
    modbus_patches.skip_banks = set(modbus_patches.hv_module_banks(c))
    try:
        assert not [b for b in client_module._refresh_banks(c) if 0x50 <= b[0] < 0x70]
        assert (0x70, 60, 60) in client_module._refresh_banks(c)       # the stacks' BCUs are still read
    finally:
        modbus_patches.skip_banks = set()

def test_second_stack_modules_decoded():
    plant = plant_with(caps([(0, 2), (1, 2)], [0x50, 0x51]), {
        (0x50, 0): ("BG2300A001", 200), (0x51, 0): ("BG2300A002", 210),
        (0x50, 120): ("BG2300B001", 250), (0x51, 120): ("BG2300B002", 260)})
    stacks = plant.hv_stacks
    assert [b.serial_number for b in stacks[0].bmus] == ["BG2300A001", "BG2300A002"]
    assert [b.serial_number for b in stacks[1].bmus] == ["BG2300B001", "BG2300B002"]
    assert [b.bmu_index for b in stacks[1].bmus] == [0, 1]
    assert stacks[1].bmus[0].t_cell_01 == 25.0

def test_failing_module_read_dropped_after_three_polls():
    capabilities = caps([(0, 1), (1, 1)], [0x50])
    client = types.SimpleNamespace(plant=plant_with(capabilities, {}))
    failure = [ReadFailure(0x50, "ReadInputRegistersRequest", 180, 60)]
    for _ in range(2):
        modbus_patches.track_stack_module_reads(client, failure)
    assert client.plant.block_present(0x50, "IR", 180, 60) is not False
    modbus_patches.track_stack_module_reads(client, [])        # a good poll resets the count
    for _ in range(3):
        modbus_patches.track_stack_module_reads(client, failure)
    assert client.plant.block_present(0x50, "IR", 180, 60) is False

def test_partial_refresh_skips_modules_with_data():
    import read
    plant = plant_with(caps([(0, 2), (1, 2)], [0x50, 0x51]), {
        (0x50, 0): ("BG2300A001", 200), (0x51, 0): ("BG2300A002", 210), (0x50, 120): ("BG2300B001", 250)})
    # Stack 2 module 2 has no data yet, so it's still read
    assert read.hvModulesRead(plant) == {(0x50, 60, 60), (0x51, 60, 60), (0x50, 180, 60)}

def test_clock_compared_with_when_it_was_read(caplog):
    from harness import fakes
    import datetime
    import logging
    import read
    read._clockWarned = None
    now = datetime.datetime.now(read.GivLUT.timezone)
    read_at = now - datetime.timedelta(minutes=4)
    with caplog.at_level(logging.WARNING, logger=read.logger.name):
        fakes.real_check_clock[0](read_at.isoformat(), read_at)          # right when read: no warning
        assert not [r for r in caplog.records if "Inverter clock" in r.getMessage()]
        fakes.real_check_clock[0]((read_at - datetime.timedelta(minutes=20)).isoformat(), read_at)
    assert [r for r in caplog.records if "20 minutes behind" in r.getMessage()]
