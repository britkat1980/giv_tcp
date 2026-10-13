"""Hybrid Gen 1, Gen 3 and All in One-HY AC charge/discharge rate: HR 313/314, as GivTCP 3.5 read and wrote, which
the library only reads and allows on models with the AC config block (#630, #645)"""
import pytest
from givenergy_modbus.model import manifest
from givenergy_modbus.model.inverter import Model

import modbus_patches  # noqa: F401
import write

def registers(requests):
    return [(r.register, r.value) for r in requests]

def test_write_allowed():
    assert {313, 314} <= manifest.write_safe_registers(Model.HYBRID_GEN1, 449)
    assert {313, 314} <= manifest.write_safe_registers(Model.HYBRID_GEN3, 303)
    assert {313, 314} <= manifest.write_safe_registers(Model.ALL_IN_ONE_HYBRID, 6)
    assert not {313, 314} & manifest.write_safe_registers(Model.HYBRID_GEN2, 450)    # unconfirmed, still refused

@pytest.mark.parametrize("inverter_type", ["Hybrid_gen1", "Hybrid_gen3", "All_in_one_hybrid"])
def test_rate_commands(monkeypatch, inverter_type):
    monkeypatch.setattr(write.GiV_Settings, "inverter_type", inverter_type, raising=False)
    assert registers(write.acLimit("charge", 100)) == [(313, 100)]
    assert registers(write.acLimit("discharge", 11)) == [(314, 11)]
    monkeypatch.setattr(write.GiV_Settings, "inverter_type", "Hybrid_gen2", raising=False)
    with pytest.raises(NotImplementedError):
        write.acLimit("charge", 100)

def test_rates_read():
    # Read after each full refresh, so the AC rate entities exist and show the inverter's value
    from givenergy_modbus.model.plant import PlantCapabilities
    read = {m: [(base, count) for name, applies, base, count, _ in modbus_patches.EXTRA_READS
                if applies(PlantCapabilities(device_type=m))] for m in (Model.HYBRID_GEN1, Model.HYBRID_GEN2,
                                                                       Model.HYBRID_GEN3, Model.ALL_IN_ONE_HYBRID)}
    assert (313, 2) in read[Model.HYBRID_GEN1] and (313, 2) in read[Model.HYBRID_GEN3]
    assert (313, 2) in read[Model.ALL_IN_ONE_HYBRID]
    assert (313, 2) not in read[Model.HYBRID_GEN2]
