"""Local extensions to givenergy-modbus, applied when this module is imported (GivLUT imports it).

Battery pause mode and the pause slot (HR 318-320) on Gen 1 (newer firmware) and Gen 2 hybrids.
givenergy-modbus only allows these writes on models with the AC config block (AC, All-in-One), and only
reads HR 300-359 on those models, because older hybrids time out on that block (#162). Hybrids on newer
firmware do support pause mode: GivTCP's previous modbus library found the HR 300 block on them and
wrote pause mode successfully (britkat1980/giv_tcp#441).

This adds, for supported hybrids only:
- HR 318-320 to the registers the client may write, and
- a read of just HR 318-320 after each load_config(), so the current pause mode and slot are known.

Remove this once givenergy-modbus supports pause mode on hybrids (docs/upstream-givenergy-modbus-requests.md,
item 1).
"""
import logging

from givenergy_modbus.client.client import Client
from givenergy_modbus.model import manifest
from givenergy_modbus.model.inverter import Model
from givenergy_modbus.pdu import ReadHoldingRegistersRequest

logger = logging.getLogger("read_logger")     # GivTCP's main log (GivLUT.logger)

PAUSE_REGISTERS = frozenset({318, 319, 320})     # pause mode, pause slot start, pause slot end
# Lowest Gen 1 ARM firmware known to support pause mode (the firmware that added real-time control)
GEN1_PAUSE_MIN_ARM_FW = 187

def pause_supported(model, arm_fw):
    """True for the hybrids this patch enables pause mode on"""
    if model == Model.HYBRID_GEN2:
        return True
    if model == Model.HYBRID_GEN1:
        return arm_fw is not None and int(arm_fw) >= GEN1_PAUSE_MIN_ARM_FW
    return False

# --- writes ------------------------------------------------------------------------------------------------

_library_write_safe_registers = manifest.write_safe_registers

def _write_safe_registers(model, arm_fw=None):
    safe = _library_write_safe_registers(model, arm_fw)
    if pause_supported(model, arm_fw):
        safe = safe | PAUSE_REGISTERS
    return safe

# The client looks this up on the manifest module for every write (Client._resolve_write_safe)
manifest.write_safe_registers = _write_safe_registers

# --- reads -------------------------------------------------------------------------------------------------

_library_load_config = Client.load_config

async def _read_pause_registers(client):
    caps = client.plant.capabilities
    if caps is None or not pause_supported(caps.device_type, caps.arm_firmware_version):
        return
    if getattr(client, "_givtcp_pause_read_failed", False):
        return      # the inverter didn't answer before, so don't log the same error every full refresh
    try:
        await client._execute_reads(
            [ReadHoldingRegistersRequest(base_register=318, register_count=3, device_address=caps.inverter_address)],
            timeout=2.0, retries=1, retry_delay=0.5)
    except Exception as e:
        client._givtcp_pause_read_failed = True
        logger.warning("Battery pause mode registers (HR 318-320) could not be read, so the current pause mode won't "
                       "be shown (pause controls can still be set): " + str(e))

async def _load_config(self, *args, **kwargs):
    try:
        return await _library_load_config(self, *args, **kwargs)
    finally:
        # Also after a partially failed load_config: the pause registers are a separate read
        await _read_pause_registers(self)

Client.load_config = _load_config
