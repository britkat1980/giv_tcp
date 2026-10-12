"""Hybrid Gen 3 AC charge/discharge rate: HR 313/314, as GivTCP 3.5 wrote, which the library only allows on models
with the AC config block (#630)"""
import pytest
from givenergy_modbus.model import manifest
from givenergy_modbus.model.inverter import Model

import modbus_patches  # noqa: F401
import write

def registers(requests):
    return [(r.register, r.value) for r in requests]

def test_write_allowed():
    assert {313, 314} <= manifest.write_safe_registers(Model.HYBRID_GEN3, 303)
    assert not {313, 314} & manifest.write_safe_registers(Model.HYBRID_GEN2, 450)    # unconfirmed, still refused

def test_rate_commands(monkeypatch):
    monkeypatch.setattr(write.GiV_Settings, "inverter_type", "Hybrid_gen3", raising=False)
    assert registers(write.acLimit("charge", 100)) == [(313, 100)]
    assert registers(write.acLimit("discharge", 80)) == [(314, 80)]
    monkeypatch.setattr(write.GiV_Settings, "inverter_type", "Hybrid_gen2", raising=False)
    with pytest.raises(NotImplementedError):
        write.acLimit("charge", 100)
