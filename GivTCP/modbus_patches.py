"""Local extensions to givenergy-modbus, applied when this module is imported (GivLUT imports it).

GivTCP runs britkat1980/givenergy-modbus: 2.13.0 with GivTCP's upstream requests merged, each open as a pull
request on dewet22/givenergy-modbus. The fork already does these, so they're no longer patched here: the Gateway's
10-slot map, its HR 300-359 read and its HR 313/314 rate writes; charge slot 2 at HR 243/244 on 10-slot models;
per-slot target SOC writes; three-phase rate writes (HR 1110/1108); the EMS car charge boost (HR 2073); and the
EMS's IR 0-59 poll.

What's left, each with a request open upstream (docs/upstream-givenergy-modbus-requests.md, item number in brackets):

- Battery pause mode, HR 318, and pause slot, HR 319-320 [1]. The fork allows these on the All-in-One (mode and
  slot), and mode only on the AC from ARM firmware 200 and Gen 1 from ARM 187 to 499. GivTCP also allows mode and
  slot on the Gateway, Gen 2, Gen 3, HV Gen 3 and All in One-HY, as 3.5 did, and mode on Gen 1 from ARM 187 with
  no upper limit (britkat1980/giv_tcp#441): a Gen 1 rejects reads and writes of the slot registers. Three-phase and
  the EMS have no pause functions. The library only reads HR 300-359 on models with the AC config block (AC,
  All-in-One) and on the Gateway, because older hybrids time out on that block (#162), so this also reads just
  HR 318-320 (just HR 318 where there's no slot) after each load_config() on the others, so the current
  pause mode and slot are known.
- Three-phase slots 3-10 and their target SOCs, HR 240-299 [2]. The library doesn't read them on three-phase
  models, so this reads that block after each load_config() there.
- Hybrid Gen 1, Gen 3 and All in One-HY AC charge/discharge rate, HR 313 / 314 [20]. GivTCP 3.5 read and wrote them
  on every hybrid that answered HR 300-359, and owners used them (britkat1980/giv_tcp#630, #645), but the library
  only reads and allows them on models with the AC config block and on the Gateway. This also reads HR 313-314
  after each load_config() on these models, so the rates are shown again, and stops trying if they don't answer.
- Battery pack current, IR 95 [13]. The library reports it on every model, but it only holds a real value
  from BMS firmware 3020/4009 on Gen 3 and AC inverters from ARM firmware 214, and reads 0 elsewhere. This
  clears it to None everywhere else.
- HV battery modules in the second and later stacks [14]. The library looks for them at the next device
  addresses after the first stack's (0x55+ after a 5-module stack), which don't hold their data
  (britkat1980/giv_tcp#611 on HV Gen 3, #614 on three-phase, where detect still lists those addresses). As in the
  old library, every stack's module k is at 0x50 + k and the stack is picked by register offset, 120 per stack,
  so this reads and decodes them from there instead.
- The All in One-HY (DTC 0x82xx) is read as single-phase [18]. The library lists it as three-phase, so it was
  read with the three-phase registers (HR/IR 1000+), which it rejects (britkat1980/giv_tcp#621). GivTCP 3.5's
  library read every 0x8xxx device single-phase, and the library's own notes say the residential All-in-One
  rejects the 1000-range reads.
- HV battery module cell data is only re-read on full refreshes (read.py sets skip_banks between them), as each
  module is a read of its own and cell voltages and temperatures don't need updating every poll (#614).

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
from givenergy_modbus.pdu import ReadHoldingRegistersRequest

logger = logging.getLogger("read_logger")     # GivTCP's main log (GivLUT.logger)

PAUSE_MODE_REGISTER = 318
PAUSE_SLOT_REGISTERS = frozenset({319, 320})     # pause slot start, pause slot end
PAUSE_REGISTERS = frozenset({PAUSE_MODE_REGISTER}) | PAUSE_SLOT_REGISTERS
# Lowest Gen 1 ARM firmware known to support pause mode (the firmware that added real-time control)
GEN1_PAUSE_MIN_ARM_FW = 187
# Lowest AC-coupled ARM firmware confirmed by users to support pause mode
AC_PAUSE_MIN_ARM_FW = 200

PAUSE_MODELS = frozenset({Model.ALL_IN_ONE, Model.GATEWAY, Model.HYBRID_GEN2, Model.HYBRID_GEN3,
                          Model.HYBRID_HV_GEN3, Model.ALL_IN_ONE_HYBRID})     # All in One-HY: used in 3.5 (#647)

AC_LIMIT = frozenset({313, 314})     # AC charge limit, AC discharge limit
# Hybrids that take the AC limit (HR 313/314), as they did in 3.5 (#630, #645)
AC_LIMIT_HYBRIDS = frozenset({Model.HYBRID_GEN1, Model.HYBRID_GEN3, Model.ALL_IN_ONE_HYBRID})

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
    # The library reads HR 300-359, which includes the pause registers, on models with the AC config block and on
    # the Gateway
    return bool(pause_registers(model, arm_fw)) and not (manifest.has_capability("has_ac_config_block", model)
                                                         or manifest.has_capability("is_gateway", model))

# --- writes ------------------------------------------------------------------------------------------------

def _extra_write_registers(model, arm_fw):
    extra = set(pause_registers(model, arm_fw))
    if model in AC_LIMIT_HYBRIDS:
        extra |= AC_LIMIT
    return extra

# The All in One-HY (0x82xx) is single-phase (#621). CAPABILITIES["is_three_phase"] chooses the inverter class
# (select_inverter), the register banks polled and the settings read, and is looked up on every call
manifest.CAPABILITIES["is_three_phase"] = manifest.CAPABILITIES["is_three_phase"] - {Model.ALL_IN_ONE_HYBRID}

_library_write_safe_registers = manifest.write_safe_registers

def _write_safe_registers(model, arm_fw=None):
    return _library_write_safe_registers(model, arm_fw) | _extra_write_registers(model, arm_fw)

# The client checks each write against this per-model set (Client._resolve_write_safe looks it up on the
# manifest module for every write). HR 313/314 and 318-320 are already in the PDU's global WRITE_SAFE_REGISTERS
manifest.write_safe_registers = _write_safe_registers

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
    ("AC rates", lambda caps: caps.device_type in AC_LIMIT_HYBRIDS, 313, 2,
     "the current AC charge/discharge rates won't be shown (they can still be set)"),
]

# An extra read that fails this many times in a row isn't tried again until GivTCP restarts, as the inverter doesn't
# support it. Fewer are a busy or briefly offline dongle: on a Gen 1 that answers HR 318 fine, one failed read
# stopped the pause mode being read (and its value updating) for the rest of the session
EXTRA_READ_MAX_FAILURES = 3
_extra_read_failures = {}       # per plant, which outlives a replaced client: {id(plant): {read name: failures in a row}}

async def _extra_reads(client):
    caps = client.plant.capabilities
    if caps is None:
        return
    failures = _extra_read_failures.setdefault(id(client.plant), {})
    for name, applies, base, count, lost in EXTRA_READS:
        if failures.get(name, 0) >= EXTRA_READ_MAX_FAILURES or not applies(caps):
            continue
        regs = "HR " + str(base) + "-" + str(base + count - 1)
        try:
            await client._execute_reads(
                [ReadHoldingRegistersRequest(base_register=base, register_count=count, device_address=caps.inverter_address)],
                timeout=3.0, retries=2, retry_delay=0.5)
            if failures.pop(name, 0):
                logger.debug("Registers " + regs + " read again after failing")
        except Exception as e:
            fails = failures[name] = failures.get(name, 0) + 1
            if fails >= EXTRA_READ_MAX_FAILURES:
                # Info, not a warning: these are optional, and some firmware doesn't answer them (eg. HR 313-314 on Gen 1
                # ARM 451, #655), so it would warn on every restart about something that needs no action
                logger.info("Registers " + regs + " could not be read " + str(fails) + " times in a row, so " + lost +
                               ". Not trying again until GivTCP restarts: " + str(e))
            else:
                # The value read last time is kept, and it's read again with the next full refresh
                logger.debug("Registers " + regs + " could not be read this time (" + str(fails) + " in a row): " + str(e))

async def _load_config(self, *args, **kwargs):
    try:
        result = await _library_load_config(self, *args, **kwargs)
    except RefreshPartiallySucceeded:
        # Some settings were read, so the inverter is answering: the extra reads are separate reads
        await _extra_reads(self)
        raise
    # Not after RefreshFailed or a lost connection: nothing answered, so they would only be more requests to a dongle
    # that isn't responding, sent before GivTCP counts the failed poll
    await _extra_reads(self)
    return result

Client.load_config = _load_config

# --- battery pack current ----------------------------------------------------------------------------------

# IR 95 (Im_Avg, i_battery, signed: negative while charging) only holds the pack's current from BMS firmware 3020
# (3xxx) or 4009 (4xxx), and only Gen 3 and AC inverters from ARM firmware 214 pass it on. GivEnergy said BMS 3022
# and ARM above 214 (britkat1980/giv_tcp#605), but an AC on ARM 214 with packs on BMS 3020 reports it (#616).
# Everywhere else it reads 0 whatever the current, so it's cleared to None rather than report a misleading 0A
BMS_CURRENT_MODELS = frozenset({Model.HYBRID_GEN3, Model.AC})
BMS_CURRENT_MIN_ARM_FW = 214
BMS_CURRENT_MIN_BMS_FW = 3020

def bms_current_inverter(model, arm_fw):
    """True if this inverter passes on each battery pack's current"""
    return model in BMS_CURRENT_MODELS and arm_fw is not None and int(arm_fw) >= BMS_CURRENT_MIN_ARM_FW

def bms_current_firmware(bms_fw):
    """True if a pack's BMS firmware reports its current"""
    return bms_fw is not None and (BMS_CURRENT_MIN_BMS_FW <= bms_fw < 4000 or bms_fw >= 4009)

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
    # Stack 1 is the same in both layouts. Later stacks use the offset layout even where detect listed the
    # library's address: on a three-phase with two stacks it did, but those never held the modules' data (#614)
    return offset != 0

def _hv(caps):
    return caps is not None and caps.is_hv and caps.device_type is not Model.ALL_IN_ONE

def hv_stack_module_banks(caps):
    """(device address, base register, count) for each stack module read the library doesn't do"""
    if not _hv(caps):
        return []
    banks = []
    first_addr = HV_BMU_BASE_ADDRESS
    for offset, modules in caps.bcu_stacks:
        for k in range(modules):
            if _offset_layout(caps, offset, first_addr, k):
                banks.append((HV_BMU_BASE_ADDRESS + k, 60 + HV_STACK_REGISTER_STRIDE * offset, 60))
        first_addr += modules
    return banks

def _library_only_banks(caps):
    # The library's reads of the later stacks' modules at the next addresses after the first stack's, replaced by
    # the offset reads above. Not an address that's also one of the first stack's modules
    if not _hv(caps) or len(caps.bcu_stacks) < 2:
        return set()
    first = {HV_BMU_BASE_ADDRESS + k for offset, n in caps.bcu_stacks if offset == 0 for k in range(n)}
    return {(a, 60, 60) for a in caps.hv_bmu_addresses if a not in first}

def hv_module_banks(caps):
    """Every HV battery module read, in the order Plant.hv_stacks lists the modules (#614)"""
    if not _hv(caps):
        return []
    banks = []
    for offset, n in caps.bcu_stacks:
        base = 60 + HV_STACK_REGISTER_STRIDE * offset
        banks += [(HV_BMU_BASE_ADDRESS + k, base, 60) for k in range(n)]
    return banks

# Module reads to leave out of the next refresh. read.py sets this for polls between full refreshes, to the
# modules that already have data: their cell data doesn't need updating every poll, and each is a read (#614)
skip_banks = set()

_library_refresh_banks = client_module._refresh_banks

def _refresh_banks(caps):
    dropped = _library_only_banks(caps)
    banks = [b for b in _library_refresh_banks(caps) if b not in dropped]
    banks += [b for b in hv_stack_module_banks(caps) if b not in banks]
    return [b for b in banks if b not in skip_banks]

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
