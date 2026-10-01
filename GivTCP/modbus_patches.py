"""Local extensions to givenergy-modbus, applied when this module is imported (GivLUT imports it).

Writes givenergy-modbus doesn't allow yet, each enabled only on the models it applies to, plus a read the
library doesn't do. Each one was written by GivTCP's previous modbus library (givenergy_modbus_async), and
each has a request open upstream (docs/upstream-givenergy-modbus-requests.md, item number in brackets):

- Battery pause mode and pause slot, HR 318-320, on Gen 1 (ARM firmware 187+) and Gen 2 hybrids [1].
  The library only allows these on models with the AC config block (AC, All-in-One), and only reads
  HR 300-359 on those, because older hybrids time out on that block (#162). This also reads just
  HR 318-320 after each load_config() on these hybrids, so the current pause mode and slot are known.
- Per-slot charge/discharge target SOC, HR 242-269 / 272-299 (every third register), on models with the
  10-slot layout and on three-phase [2]. The library reads these on 10-slot models but has no writer. On
  three-phase it doesn't read HR 240-299 at all (slots 3-10 and their targets), so this also reads that
  block after each load_config() there.
- Three-phase charge/discharge rate, HR 1110 / 1108 [3]. The library reads these but only allows the
  single-phase AC rate registers (HR 313/314).
- EMS car charge boost, HR 2073, 0-22000 W [10]. The library reads it but has no writer.

Remove each one once the library supports it.
"""
import logging

from givenergy_modbus.client.client import Client
from givenergy_modbus.model import manifest
from givenergy_modbus.model.inverter import Model
from givenergy_modbus.pdu import ReadHoldingRegistersRequest, WriteHoldingRegisterRequest
from givenergy_modbus.pdu import write_registers

logger = logging.getLogger("read_logger")     # GivTCP's main log (GivLUT.logger)

PAUSE_REGISTERS = frozenset({318, 319, 320})     # pause mode, pause slot start, pause slot end
# Lowest Gen 1 ARM firmware known to support pause mode (the firmware that added real-time control)
GEN1_PAUSE_MIN_ARM_FW = 187

# Per-slot target SOC: slot N at base + 3*(N-1), matching the library's charge/discharge_target_soc_N reads
SLOT_TARGET_BASE = {"charge": 242, "discharge": 272}
SLOT_TARGET_REGISTERS = frozenset(base + 3 * i for base in SLOT_TARGET_BASE.values() for i in range(10))

THREE_PHASE_AC_LIMIT = {"charge": 1110, "discharge": 1108}
EMS_CAR_CHARGE_BOOST = 2073
CAR_CHARGE_BOOST_MAX = 22000

def pause_supported(model, arm_fw):
    """True for the hybrids this patch enables pause mode on"""
    if model == Model.HYBRID_GEN2:
        return True
    if model == Model.HYBRID_GEN1:
        return arm_fw is not None and int(arm_fw) >= GEN1_PAUSE_MIN_ARM_FW
    return False

# --- writes ------------------------------------------------------------------------------------------------

def _extra_write_registers(model, arm_fw):
    extra = set()
    if pause_supported(model, arm_fw):
        extra |= PAUSE_REGISTERS
    if model is not None and (manifest.has_extended_slots(model, arm_fw) or manifest.has_capability("is_three_phase", model)):
        extra |= SLOT_TARGET_REGISTERS
    if manifest.has_capability("is_three_phase", model):
        extra |= set(THREE_PHASE_AC_LIMIT.values())
    if manifest.has_capability("is_ems", model):
        extra.add(EMS_CAR_CHARGE_BOOST)
    return extra

_library_write_safe_registers = manifest.write_safe_registers

def _write_safe_registers(model, arm_fw=None):
    return _library_write_safe_registers(model, arm_fw) | _extra_write_registers(model, arm_fw)

# The client checks each write against this per-model set (Client._resolve_write_safe looks it up on the
# manifest module for every write)...
manifest.write_safe_registers = _write_safe_registers
# ...and the PDU checks it against this global set. Adding to it doesn't allow anything on its own, as the
# per-model set above still has to include the register
write_registers.WRITE_SAFE_REGISTERS.update(SLOT_TARGET_REGISTERS, {EMS_CAR_CHARGE_BOOST})

def slot_target_soc(kind, slot, target):
    """Write the target SOC for charge or discharge slot 1-10"""
    slot, target = int(slot), int(target)
    if kind not in SLOT_TARGET_BASE:
        raise ValueError("No per-slot " + str(kind) + " target SOC on inverters")
    if not 1 <= slot <= 10:
        raise ValueError("Slot (" + str(slot) + ") must be 1-10")
    if not 4 <= target <= 100:
        raise ValueError("Target SOC (" + str(target) + ") must be 4-100%")
    return [WriteHoldingRegisterRequest(SLOT_TARGET_BASE[kind] + 3 * (slot - 1), target)]

def three_phase_ac_limit(kind, percent):
    """Write the three-phase charge or discharge rate, as a percentage of the inverter's battery rate"""
    percent = int(percent)
    if not 1 <= percent <= 100:      # as the library's single-phase AC limits: the inverter rejects 0
        raise ValueError("Rate (" + str(percent) + "%) must be 1-100%")
    return [WriteHoldingRegisterRequest(THREE_PHASE_AC_LIMIT[kind], percent)]

def car_charge_boost(watts):
    """Write the EMS car charge boost, in W"""
    watts = int(float(watts))
    if not 0 <= watts <= CAR_CHARGE_BOOST_MAX:
        raise ValueError("Car charge boost (" + str(watts) + "W) must be 0-" + str(CAR_CHARGE_BOOST_MAX) + "W")
    return [WriteHoldingRegisterRequest(EMS_CAR_CHARGE_BOOST, watts)]

# --- reads -------------------------------------------------------------------------------------------------

_library_load_config = Client.load_config

# Extra reads after load_config(): (name, test on the capabilities, base register, count, what's lost if it fails)
EXTRA_READS = [
    ("pause", lambda caps: pause_supported(caps.device_type, caps.arm_firmware_version), 318, 3,
     "the current pause mode won't be shown (pause controls can still be set)"),
    ("three-phase slots", lambda caps: caps.is_three_phase and not manifest.has_extended_slots(caps.device_type, caps.arm_firmware_version),
     240, 60, "charge/discharge slots 3-10 and their target SOCs won't be shown (they can still be set)"),
]

async def _extra_reads(client):
    caps = client.plant.capabilities
    if caps is None:
        return
    failed = client.__dict__.setdefault("_givtcp_failed_reads", set())
    for name, applies, base, count, lost in EXTRA_READS:
        if name in failed or not applies(caps):
            continue        # skip a read the inverter didn't answer before, rather than log the same error every time
        try:
            await client._execute_reads(
                [ReadHoldingRegistersRequest(base_register=base, register_count=count, device_address=caps.inverter_address)],
                timeout=2.0, retries=1, retry_delay=0.5)
        except Exception as e:
            failed.add(name)
            logger.warning("Registers HR " + str(base) + "-" + str(base + count - 1) + " could not be read, so " + lost + ": " + str(e))

async def _load_config(self, *args, **kwargs):
    try:
        return await _library_load_config(self, *args, **kwargs)
    finally:
        # Also after a partially failed load_config: these are separate reads
        await _extra_reads(self)

Client.load_config = _load_config
