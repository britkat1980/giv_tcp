"""Local extensions to givenergy-modbus, applied when this module is imported (GivLUT imports it).

Writes givenergy-modbus doesn't allow yet, each enabled only on the models it applies to, plus a read the
library doesn't do. Each one was written by GivTCP's previous modbus library (givenergy_modbus_async), and
each has a request open upstream (docs/upstream-givenergy-modbus-requests.md, item number in brackets):

- Battery pause mode, HR 318, and pause slot, HR 319-320 [1]. The library allows these on no model.
  Pause mode and slot on the All-in-One, Gateway, Gen 2, Gen 3 and HV Gen 3. Pause mode only on Gen 1 from
  ARM firmware 187 (britkat1980/giv_tcp#441), which rejects reads and writes of the slot registers, and on
  the AC from ARM firmware 200 (confirmed by a user), as neither has a pause slot. Three-phase and the
  EMS have no pause functions. The library only reads HR 300-359 on models with the AC config block
  (AC, All-in-One), because older hybrids time out on that block (#162), so this also reads just
  HR 318-320 (just HR 318 where there's no slot) after each load_config() on the others, so the current
  pause mode and slot are known.
- Per-slot charge/discharge target SOC, HR 242-269 / 272-299 (every third register), on models with the
  10-slot layout and on three-phase [2]. The library reads these on 10-slot models but has no writer. On
  three-phase it doesn't read HR 240-299 at all (slots 3-10 and their targets), so this also reads that
  block after each load_config() there.
- Three-phase charge/discharge rate, HR 1110 / 1108 [3]. The library reads these but only allows the
  single-phase AC rate registers (HR 313/314).
- Gateway charge/discharge rate, HR 313 / 314 [3]. The Gateway controls the All-in-Ones behind it, and these
  are its rate controls (givenergy-modbus#373), but the library only reads and allows them on models with the
  AC config block. This also reads HR 313-314 after each load_config() on the Gateway, so the current rates
  are known.
- EMS car charge boost, HR 2073, 0-22000 W [10]. The library reads it but has no writer.
- Battery pack current, IR 95 [13]. The library reports it on every model, but it only holds a real value
  from BMS firmware 3022/4009 on Gen 3 and AC inverters above ARM firmware 214, and reads 0 elsewhere. This
  clears it to None everywhere else.
- HV battery modules in the second and later stacks [14]. The library looks for them at the next device
  addresses after the first stack's (0x55+ after a 5-module stack), which don't answer
  (britkat1980/giv_tcp#611). As in the old library, every stack's module k is at 0x50 + k and the stack is
  picked by register offset, 120 per stack, so this also reads those and decodes the modules from them.

Remove each one once the library supports it.
"""
import logging

from givenergy_modbus.client import client as client_module
from givenergy_modbus.client.client import Client
from givenergy_modbus.exceptions import RefreshPartiallySucceeded
from givenergy_modbus.model import manifest
from givenergy_modbus.model.hv_bcu import Bmu, decode_cells_temps_serial
from givenergy_modbus.model.inverter import Model
from givenergy_modbus.model.plant import Plant
from givenergy_modbus.model.register_cache import RegisterCache
from givenergy_modbus.pdu import ReadHoldingRegistersRequest, WriteHoldingRegisterRequest
from givenergy_modbus.pdu import write_registers

logger = logging.getLogger("read_logger")     # GivTCP's main log (GivLUT.logger)

PAUSE_MODE_REGISTER = 318
PAUSE_SLOT_REGISTERS = frozenset({319, 320})     # pause slot start, pause slot end
PAUSE_REGISTERS = frozenset({PAUSE_MODE_REGISTER}) | PAUSE_SLOT_REGISTERS
# Lowest Gen 1 ARM firmware known to support pause mode (the firmware that added real-time control)
GEN1_PAUSE_MIN_ARM_FW = 187
# Lowest AC-coupled ARM firmware confirmed by users to support pause mode
AC_PAUSE_MIN_ARM_FW = 200

PAUSE_MODELS = frozenset({Model.ALL_IN_ONE, Model.GATEWAY, Model.HYBRID_GEN2, Model.HYBRID_GEN3,
                          Model.HYBRID_HV_GEN3})

# Per-slot target SOC: slot N at base + 3*(N-1), matching the library's charge/discharge_target_soc_N reads
SLOT_TARGET_BASE = {"charge": 242, "discharge": 272}
SLOT_TARGET_REGISTERS = frozenset(base + 3 * i for base in SLOT_TARGET_BASE.values() for i in range(10))

THREE_PHASE_AC_LIMIT = {"charge": 1110, "discharge": 1108}
GATEWAY_AC_LIMIT = frozenset({313, 314})     # AC charge limit, AC discharge limit
EMS_CAR_CHARGE_BOOST = 2073
CAR_CHARGE_BOOST_MAX = 22000

def pause_registers(model, arm_fw):
    """The pause registers this model can write"""
    if model == Model.AC:
        if arm_fw is not None and int(arm_fw) >= AC_PAUSE_MIN_ARM_FW:
            return frozenset({PAUSE_MODE_REGISTER})
        return frozenset()
    if model in PAUSE_MODELS:
        return PAUSE_REGISTERS
    if model == Model.HYBRID_GEN1 and arm_fw is not None and int(arm_fw) >= GEN1_PAUSE_MIN_ARM_FW:
        # Mode only: a Gen 1 rejects writes to HR 319-320, and a read including them
        return frozenset({PAUSE_MODE_REGISTER})
    return frozenset()

def _has_pause_slot(caps):
    return PAUSE_SLOT_REGISTERS <= pause_registers(caps.device_type, caps.arm_firmware_version)

def _pause_read_needed(model, arm_fw):
    # The library reads HR 300-359, which includes the pause registers, on models with the AC config block
    return bool(pause_registers(model, arm_fw)) and not manifest.has_capability("has_ac_config_block", model)

# --- writes ------------------------------------------------------------------------------------------------

def _extra_write_registers(model, arm_fw):
    extra = set(pause_registers(model, arm_fw))
    if model is not None and (manifest.has_extended_slots(model, arm_fw) or manifest.has_capability("is_three_phase", model)):
        extra |= SLOT_TARGET_REGISTERS
    if manifest.has_capability("is_three_phase", model):
        extra |= set(THREE_PHASE_AC_LIMIT.values())
    if manifest.has_capability("is_gateway", model):
        extra |= GATEWAY_AC_LIMIT
    if manifest.has_capability("is_ems", model):
        extra.add(EMS_CAR_CHARGE_BOOST)
    return extra

# The Gateway has the 10-slot block (HR 240-299: slots 3-10 and every slot's target SOC) like every model but
# AC 3.0 and Gen 1/2 (GivEnergy register map v4.1.6), and answers it, but the library gives it the 2-slot map.
# has_extended_slots() reads this set on every call, so this one change gives the Gateway the 10-slot reads,
# slot map and slot writes (and, below, the target SOC writes) (#577)
manifest._EXTENDED_SLOT_MODELS = manifest._EXTENDED_SLOT_MODELS | {Model.GATEWAY}

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
    ("pause", lambda caps: _pause_read_needed(caps.device_type, caps.arm_firmware_version) and _has_pause_slot(caps), 318, 3,
     "the current pause mode won't be shown (pause controls can still be set)"),
    # Where there's no pause slot the inverter rejects a read that includes HR 319-320, so read the mode alone
    ("pause mode", lambda caps: _pause_read_needed(caps.device_type, caps.arm_firmware_version) and not _has_pause_slot(caps), 318, 1,
     "the current pause mode won't be shown (it can still be set)"),
    ("three-phase slots", lambda caps: caps.is_three_phase and not manifest.has_extended_slots(caps.device_type, caps.arm_firmware_version),
     240, 60, "charge/discharge slots 3-10 and their target SOCs won't be shown (they can still be set)"),
    ("Gateway rates", lambda caps: caps.is_gateway, 313, 2,
     "the current charge/discharge rates won't be shown (they can still be set)"),
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

# --- battery pack current ----------------------------------------------------------------------------------

# IR 95 (Im_Avg, i_battery) only holds the pack's current from BMS firmware 3022 (3xxx) or 4009 (4xxx), and only
# Gen 3 and AC inverters above ARM firmware 214 pass it on (GivEnergy, britkat1980/giv_tcp#605). Everywhere else
# it reads 0 whatever the current, so it's cleared to None rather than report a misleading 0A
BMS_CURRENT_MODELS = frozenset({Model.HYBRID_GEN3, Model.AC})
BMS_CURRENT_MIN_ARM_FW = 215

def bms_current_inverter(model, arm_fw):
    """True if this inverter passes on each battery pack's current"""
    return model in BMS_CURRENT_MODELS and arm_fw is not None and int(arm_fw) >= BMS_CURRENT_MIN_ARM_FW

def bms_current_firmware(bms_fw):
    """True if a pack's BMS firmware reports its current"""
    return bms_fw is not None and (3022 <= bms_fw < 4000 or bms_fw >= 4009)

_library_batteries = Plant.batteries

def _batteries(self):
    batteries = _library_batteries.fget(self)
    caps = self.capabilities
    inverter = bms_current_inverter(caps.device_type, caps.arm_firmware_version) if caps else False
    return [b if b.i_battery is None or (inverter and bms_current_firmware(b.bms_firmware_version))
            else b.model_copy(update={"i_battery": None}) for b in batteries]

Plant.batteries = property(_batteries)

# --- HV battery modules in the second and later stacks -----------------------------------------------------

# Every stack's module k answers at 0x50 + k, with stack n's registers (n from 0) at IR 60-119 + 120*n
# (GivEnergy register map: register = base + 120 * (BCU address - 0x70)). The library gives stack 2 onwards
# the next device addresses with no offset, so their modules never read (#611)
HV_BMU_BASE_ADDRESS = 0x50
HV_STACK_REGISTER_STRIDE = 120
# A stack module read that fails this many polls in a row isn't asked for again until GivTCP restarts
HV_STACK_MODULE_MAX_FAILURES = 3

def _offset_layout(caps, offset, first_addr, k):
    # Stack 1 is the same in both layouts, and where the library's address for a module answered at detect
    # (hv_bmu_addresses holds those), keep the library's layout for it
    return offset != 0 and first_addr + k not in caps.hv_bmu_addresses

def hv_stack_module_banks(caps):
    """(device address, base register, count) for each stack module read the library doesn't do"""
    if caps is None or not caps.is_hv or caps.device_type is Model.ALL_IN_ONE:
        return []
    banks = []
    first_addr = HV_BMU_BASE_ADDRESS
    for offset, modules in caps.bcu_stacks:
        for k in range(modules):
            if _offset_layout(caps, offset, first_addr, k):
                banks.append((HV_BMU_BASE_ADDRESS + k, 60 + HV_STACK_REGISTER_STRIDE * offset, 60))
        first_addr += modules
    return banks

_library_refresh_banks = client_module._refresh_banks

def _refresh_banks(caps):
    banks = _library_refresh_banks(caps)
    return banks + [b for b in hv_stack_module_banks(caps) if b not in banks]

# _refresh_ranges() looks this up on the client module on every refresh
client_module._refresh_banks = _refresh_banks

_library_hv_stacks = Plant.hv_stacks

def _hv_stacks(self):
    stacks = _library_hv_stacks.fget(self)
    caps = self.capabilities
    if not stacks or not caps.is_hv or caps.device_type is Model.ALL_IN_ONE:
        return stacks
    first_addr = HV_BMU_BASE_ADDRESS
    for stack, (offset, modules) in zip(stacks, caps.bcu_stacks):
        for k in range(min(modules, len(stack.bmus))):
            if _offset_layout(caps, offset, first_addr, k):
                cache = self.register_caches.get(HV_BMU_BASE_ADDRESS + k, RegisterCache())
                data = decode_cells_temps_serial(cache, base=HV_STACK_REGISTER_STRIDE * offset)
                data["bmu_index"] = k
                stack.bmus[k] = Bmu.model_validate(data)
        first_addr += modules
    return stacks

Plant.hv_stacks = property(_hv_stacks)

def track_stack_module_reads(client, failures):
    """Stop asking for a stack module read that keeps failing, so it doesn't cost a timeout every poll"""
    banks = hv_stack_module_banks(client.plant.capabilities)
    if not banks:
        return
    failed = {(f.device_address, f.base_register) for f in failures}
    counts = client.__dict__.setdefault("_givtcp_stack_module_failures", {})
    for addr, base, count in banks:
        if (addr, base) not in failed:
            counts.pop((addr, base), None)
            continue
        counts[(addr, base)] = counts.get((addr, base), 0) + 1
        if counts[(addr, base)] == HV_STACK_MODULE_MAX_FAILURES:
            client.plant.mark_absent(addr, "IR", base, count)
            logger.warning("HV battery module registers IR " + str(base) + "-" + str(base + count - 1) + " at 0x"
                           + format(addr, "02x") + " failed " + str(HV_STACK_MODULE_MAX_FAILURES)
                           + " polls in a row, so that module's cell data won't be shown")

_library_refresh = Client.refresh

async def _refresh(self, *args, **kwargs):
    try:
        result = await _library_refresh(self, *args, **kwargs)
    except RefreshPartiallySucceeded as e:
        track_stack_module_reads(self, e.failures)
        raise
    track_stack_module_reads(self, [])
    return result

Client.refresh = _refresh
