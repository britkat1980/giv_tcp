"""Local extensions to givenergy-modbus, applied when this module is imported (GivLUT imports it).

Battery pause mode (HR 318) and the pause slot (HR 319-320). givenergy-modbus doesn't allow these writes
on any model, and only reads HR 300-359 on models with the AC config block (AC, All-in-One), because older
hybrids time out on that block (#162). GivTCP's previous modbus library wrote them successfully on:
- the AC: pause mode only, as it has no pause slot,
- the All-in-One, Gateway and Gen 2/Gen 3/HV Gen 3 hybrids: pause mode and slot,
- Gen 1 hybrids on newer firmware: pause mode and slot (britkat1980/giv_tcp#441).
Three-phase inverters and the EMS have no pause functions.

The Gateway also has the AC charge/discharge limit (HR 313/314), which givenergy-modbus neither reads nor
allows writing there, as it only does on models with the AC config block. The Gateway controls the AIOs behind
it, and these are its charge/discharge rate controls (givenergy-modbus#373). GivTCP's previous modbus library
read and wrote them, and they're in givenergy-modbus's own Gateway capture (gateway_gaaa0014).

This adds:
- the supported pause registers to the registers the client may write, and
- on the models the library doesn't read them on, a read of just HR 318-320 after each load_config(), so
  the current pause mode and slot are known, and
- on the Gateway, HR 313/314 to the registers the client may write, with the read widened to HR 313-320 so
  the current rates are known too.

Remove this once givenergy-modbus supports pause mode on these models and the AC charge/discharge limit on
the Gateway (docs/upstream-givenergy-modbus-requests.md, items 1 and 3).
"""
import logging

from givenergy_modbus.client.client import Client
from givenergy_modbus.model import manifest
from givenergy_modbus.model.inverter import Model
from givenergy_modbus.pdu import ReadHoldingRegistersRequest

logger = logging.getLogger("read_logger")     # GivTCP's main log (GivLUT.logger)

PAUSE_MODE_REGISTER = 318
PAUSE_SLOT_REGISTERS = frozenset({319, 320})     # pause slot start, pause slot end
PAUSE_REGISTERS = frozenset({PAUSE_MODE_REGISTER}) | PAUSE_SLOT_REGISTERS
GATEWAY_AC_LIMIT_REGISTERS = frozenset({313, 314})     # AC charge limit, AC discharge limit
# Lowest Gen 1 ARM firmware known to support pause mode (the firmware that added real-time control)
GEN1_PAUSE_MIN_ARM_FW = 187

PAUSE_MODELS = frozenset({Model.ALL_IN_ONE, Model.GATEWAY, Model.HYBRID_GEN2, Model.HYBRID_GEN3,
                          Model.HYBRID_HV_GEN3})

def pause_registers(model, arm_fw):
    """The pause registers this model can write"""
    if model == Model.AC:
        return frozenset({PAUSE_MODE_REGISTER})
    if model in PAUSE_MODELS:
        return PAUSE_REGISTERS
    if model == Model.HYBRID_GEN1 and arm_fw is not None and int(arm_fw) >= GEN1_PAUSE_MIN_ARM_FW:
        return PAUSE_REGISTERS
    return frozenset()

def _pause_read_needed(model, arm_fw):
    # The library reads HR 300-359, which includes the pause registers, on models with the AC config block
    return bool(pause_registers(model, arm_fw)) and not manifest.has_capability("has_ac_config_block", model)

# --- writes ------------------------------------------------------------------------------------------------

_library_write_safe_registers = manifest.write_safe_registers

def _write_safe_registers(model, arm_fw=None):
    safe = _library_write_safe_registers(model, arm_fw) | pause_registers(model, arm_fw)
    if model == Model.GATEWAY:
        safe = safe | GATEWAY_AC_LIMIT_REGISTERS
    return safe

# The client looks this up on the manifest module for every write (Client._resolve_write_safe)
manifest.write_safe_registers = _write_safe_registers

# --- reads -------------------------------------------------------------------------------------------------

_library_load_config = Client.load_config

async def _read_pause_registers(client):
    caps = client.plant.capabilities
    if caps is None or not _pause_read_needed(caps.device_type, caps.arm_firmware_version):
        return
    if getattr(client, "_givtcp_pause_read_failed", False):
        return      # the inverter didn't answer before, so don't log the same error every full refresh
    if caps.device_type == Model.GATEWAY:
        base, what, shown = 313, "AC charge/discharge limit and battery pause mode registers (HR 313-320)", \
            "the current charge/discharge rates and pause mode"
    else:
        base, what, shown = 318, "Battery pause mode registers (HR 318-320)", "the current pause mode"
    try:
        await client._execute_reads(
            [ReadHoldingRegistersRequest(base_register=base, register_count=321-base,
                                         device_address=caps.inverter_address)],
            timeout=2.0, retries=1, retry_delay=0.5)
    except Exception as e:
        client._givtcp_pause_read_failed = True
        logger.warning(what + " could not be read, so " + shown + " won't be shown (the controls can still be set): "
                       + str(e))

async def _load_config(self, *args, **kwargs):
    try:
        return await _library_load_config(self, *args, **kwargs)
    finally:
        # Also after a partially failed load_config: the pause registers are a separate read
        await _read_pause_registers(self)

Client.load_config = _load_config
