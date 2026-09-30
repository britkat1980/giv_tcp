"""The device models the harness runs against, each served from a real wire capture (see fixtures/captures)."""
from dataclasses import dataclass, field
from pathlib import Path

from givenergy_modbus.model.inverter import Model

CAPTURES = Path(__file__).resolve().parents[1] / "fixtures" / "captures"

@dataclass
class Device:
    capture: str
    model: Model                # what detect() must resolve the capture to
    identity: dict = field(default_factory=dict)   # HR(0-59) overrides at 0x11, for captures without an identity block

    @property
    def path(self):
        return CAPTURES / self.capture

def _serial(text):
    data = text.encode("latin1").ljust(10, b"\0")
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, 10, 2)]

DEVICES = {
    "hybrid_gen1": Device("hybrid_gen1.capture", Model.HYBRID_GEN1),
    "hybrid_gen2": Device("hybrid_gen2.capture", Model.HYBRID_GEN2),
    "ac": Device("ac.capture", Model.AC),
    "all_in_one": Device("all_in_one.capture", Model.ALL_IN_ONE),
    "ems": Device("ems.capture", Model.EMS),
    "gateway": Device("gateway.capture", Model.GATEWAY),
    "hybrid_3ph": Device("hybrid_3ph.capture", Model.HYBRID_3PH),
    # Steady-state capture with no HR(0-59): add the identity block its README records (DTC 0x8102, ARM 295)
    "hybrid_hv_gen3": Device("hybrid_hv_gen3.capture", Model.HYBRID_HV_GEN3, identity={
        0: 0x8102, **dict(zip(range(8, 13), _serial("SH2000G000"))), **dict(zip(range(13, 18), _serial("SH2000G000"))),
        19: 3000, 21: 295}),
}
