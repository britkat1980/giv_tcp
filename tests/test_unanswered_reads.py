"""#673: optional reads the inverter's firmware doesn't answer, and pause mode on firmware that doesn't have it."""
import asyncio
import json
import logging
import types

from givenergy_modbus.model import manifest
from givenergy_modbus.model.inverter import Model

import modbus_patches
from startfiles import keptOnStart


def test_pause_only_on_firmware_that_has_it():
    # Gen 1: the 1xx line from 187 (4xx is the older line, eg. ARM 451 doesn't answer HR 318). AC: 2xx, not 5xx
    assert modbus_patches.pause_registers(Model.HYBRID_GEN1, 187) == {318}
    assert modbus_patches.pause_registers(Model.HYBRID_GEN1, 191) == {318}
    assert modbus_patches.pause_registers(Model.HYBRID_GEN1, 451) == set()
    assert modbus_patches.pause_registers(Model.HYBRID_GEN1, 175) == set()
    assert modbus_patches.pause_registers(Model.AC, 212) == {318}
    assert modbus_patches.pause_registers(Model.AC, 520) == set()


def test_pause_not_written_on_old_gen1_firmware():
    # The library allows HR 318 on Gen 1 ARM 187-499; GivTCP's gate replaces it
    assert 318 not in manifest.write_safe_registers(Model.HYBRID_GEN1, 451)
    assert 318 in manifest.write_safe_registers(Model.HYBRID_GEN1, 191)
    assert {313, 314} <= manifest.write_safe_registers(Model.HYBRID_GEN1, 451)


def gen1(arm_fw, answers):
    # A Gen 1 whose AC rate read (HR 313-314) is answered or not, counting the attempts
    calls = []
    async def execute_reads(reqs, **kwargs):
        calls.append(reqs[0].base_register)
        if not answers:
            raise TimeoutError("no answer")
    caps = types.SimpleNamespace(device_type=Model.HYBRID_GEN1, arm_firmware_version=arm_fw, inverter_address=0x11,
                                 is_three_phase=False, is_gateway=False)
    return types.SimpleNamespace(plant=types.SimpleNamespace(capabilities=caps), _execute_reads=execute_reads), calls


def polls(client, n):
    for _ in range(n):
        asyncio.run(modbus_patches._extra_reads(client))


def test_unanswered_read_saved_and_not_tried_after_a_restart(unanswered_reads, caplog):
    client, calls = gen1(451, answers=False)
    with caplog.at_level(logging.INFO, logger=modbus_patches.logger.name):
        polls(client, 4)
    assert calls == [313, 313, 313]
    assert json.loads(unanswered_reads.read_text()) == {"firmware": 451, "reads": ["AC rates"]}
    assert "Not trying again on this firmware (451), delete " in caplog.text
    # After a restart: a new plant, and nothing tried or logged at info
    modbus_patches._extra_read_failures.clear()
    modbus_patches._unanswered_loaded.clear()
    caplog.clear()
    client, calls = gen1(451, answers=False)
    with caplog.at_level(logging.INFO, logger=modbus_patches.logger.name):
        polls(client, 3)
    assert calls == [] and not caplog.records


def test_three_phase_keyed_on_its_firmware_string(unanswered_reads):
    # A three-phase inverter's ARM firmware register reads 0, so the library has None: the firmware string is used,
    # once it's been read
    client, calls = gen1(None, answers=False)
    client.plant.inverter = types.SimpleNamespace(firmware_version=None)
    polls(client, 3)
    assert not unanswered_reads.exists()          # not known yet, so not saved under no firmware
    client.plant.inverter.firmware_version = "D0.3171-A0.3200"
    polls(client, 1)
    assert json.loads(unanswered_reads.read_text()) == {"firmware": "D0.3171-A0.3200", "reads": ["AC rates"]}


def test_tried_again_on_other_firmware(unanswered_reads):
    unanswered_reads.write_text(json.dumps({"firmware": 451, "reads": ["AC rates"]}))
    client, calls = gen1(191, answers=True)
    polls(client, 1)
    assert 313 in calls


def test_answered_reads_not_saved(unanswered_reads):
    client, calls = gen1(191, answers=True)
    polls(client, 3)
    assert not unanswered_reads.exists()


def test_kept_on_restart():
    assert keptOnStart("SA2150G149_unanswered.json")
