"""Detect only finds the batteries that answer while it runs, so one made during a timeout mustn't save an inverter
without its batteries: they'd never be polled again, so nothing would ever show the capabilities were wrong"""
import asyncio
import os
import pickle
import types

from givenergy_modbus.model.inverter import Model
from givenergy_modbus.model.plant import PlantCapabilities

import read
from harness import env

def aio(modules):
    # An All in One as detect saves it, with its battery modules if they answered
    return PlantCapabilities(device_type=Model.ALL_IN_ONE, inverter_address=0x11, arm_firmware_version=620,
                             bcu_stacks=[(0, modules)] if modules else [],
                             aio_battery_module_addresses=[0x50+i for i in range(modules)])

def aio_hybrid(bcus):
    # An All in One-HY with 4 packs on each of its BCUs (1-3) that answered, each pack at its own BMU address
    return PlantCapabilities(device_type=Model.ALL_IN_ONE_HYBRID, inverter_address=0x11, arm_firmware_version=620,
                             bcu_stacks=[(i, 4) for i in range(bcus)],
                             hv_bmu_addresses=[0x50+i for i in range(4*bcus)])

def fake_client(detected):
    plant = types.SimpleNamespace(inverter=types.SimpleNamespace(serial_number="AA1111A111"), capabilities=None)
    async def detect():
        plant.capabilities = detected
    return types.SimpleNamespace(plant=plant, detect=detect)

def save(caps):
    with open(read.capsFile(), 'wb') as outp:
        pickle.dump(caps, outp, pickle.HIGHEST_PROTOCOL)

def saved():
    with open(read.capsFile(), 'rb') as inp:
        return pickle.load(inp)

def setup_function():
    env.configure(serial_number="AA1111A111")
    if os.path.exists(read.capsFile()):
        os.remove(read.capsFile())
    read.capsSuspect = False
    read.lostBatteryDetects = 0
    read.noBatteryDetects = 0

def teardown_function():
    setup_function()

def test_aio_without_batteries_not_saved():
    client = fake_client(aio(0))
    asyncio.run(read.detectPlant(client, force=True))
    assert not os.path.exists(read.capsFile())
    assert read.capsSuspect      # so the read loop detects again

def test_aio_without_batteries_keeps_saved():
    save(aio(4))
    client = fake_client(aio(0))
    asyncio.run(read.detectPlant(client, force=True))
    assert client.plant.capabilities == aio(4)
    assert saved() == aio(4)

def test_cached_aio_without_batteries_detects_again():
    save(aio(0))
    client = fake_client(aio(4))
    assert asyncio.run(read.detectPlant(client)) is False     # didn't use the cache
    assert saved() == aio(4)
    assert not read.capsSuspect

def test_fewer_batteries_needs_two_detects():
    save(aio(4))
    client = fake_client(aio(3))
    asyncio.run(read.detectPlant(client, force=True))
    assert client.plant.capabilities == aio(4) and saved() == aio(4)
    asyncio.run(read.detectPlant(client, force=True))
    assert client.plant.capabilities == aio(3) and saved() == aio(3)
    assert not read.capsSuspect

def test_detect_finding_batteries_again_clears_count():
    save(aio(4))
    asyncio.run(read.detectPlant(fake_client(aio(3)), force=True))
    asyncio.run(read.detectPlant(fake_client(aio(4)), force=True))
    asyncio.run(read.detectPlant(fake_client(aio(3)), force=True))
    assert saved() == aio(4)     # the two lower detects weren't in a row

def test_aio_hybrid_without_batteries_not_saved():
    save(aio_hybrid(3))
    client = fake_client(aio_hybrid(0))
    asyncio.run(read.detectPlant(client, force=True))
    assert client.plant.capabilities == aio_hybrid(3) and saved() == aio_hybrid(3)
    assert read.capsSuspect

def test_aio_hybrid_missing_bcu_needs_two_detects():
    # A BCU that times out loses its 4 packs
    save(aio_hybrid(3))
    client = fake_client(aio_hybrid(2))
    asyncio.run(read.detectPlant(client, force=True))
    assert client.plant.capabilities == aio_hybrid(3) and saved() == aio_hybrid(3)
    asyncio.run(read.detectPlant(client, force=True))
    assert saved() == aio_hybrid(2)

def test_aio_hybrid_more_batteries_saved():
    save(aio_hybrid(1))
    asyncio.run(read.detectPlant(fake_client(aio_hybrid(2)), force=True))
    assert saved() == aio_hybrid(2) and not read.capsSuspect

def test_missing_pack_on_answering_bcu_needs_two_detects():
    # The BCU still reports 4 packs, but one pack didn't answer
    save(aio_hybrid(1))
    partial = aio_hybrid(1).model_copy(update={"hv_bmu_addresses": [0x50, 0x51, 0x52]})
    client = fake_client(partial)
    asyncio.run(read.detectPlant(client, force=True))
    assert client.plant.capabilities == aio_hybrid(1) and saved() == aio_hybrid(1)

def hv_gen3(packs):
    # A Gen 3 HV hybrid: up to 4 BCUs, each with up to 6 packs at their own BMU addresses
    return PlantCapabilities(device_type=Model.HYBRID_HV_GEN3, inverter_address=0x11, arm_firmware_version=620,
                             bcu_stacks=[(i, n) for i, n in enumerate(packs)],
                             hv_bmu_addresses=[0x50+i for i in range(sum(packs))])

def test_hv_gen3_lost_bcu_or_pack_needs_two_detects():
    for partial in (hv_gen3([6, 6, 6]), hv_gen3([6, 6, 6, 5])):
        setup_function()
        save(hv_gen3([6, 6, 6, 6]))
        client = fake_client(partial)
        asyncio.run(read.detectPlant(client, force=True))
        assert client.plant.capabilities == hv_gen3([6, 6, 6, 6]) and saved() == hv_gen3([6, 6, 6, 6])
        asyncio.run(read.detectPlant(client, force=True))
        assert saved() == partial

def lv(model, batteries):
    # A single-phase inverter with its LV batteries, as detect saves it
    return PlantCapabilities(device_type=model, inverter_address=0x11, arm_firmware_version=449,
                             lv_battery_addresses=[0x32+i for i in range(batteries)])

def test_ac_without_batteries_not_saved():
    # An AC-coupled inverter is only there for its battery (#660)
    save(lv(Model.AC, 1))
    client = fake_client(lv(Model.AC, 0))
    asyncio.run(read.detectPlant(client, force=True))
    assert client.plant.capabilities == lv(Model.AC, 1) and saved() == lv(Model.AC, 1)
    assert read.capsSuspect

def test_hybrid_without_batteries_saved_but_checked_again():
    # A hybrid can run without a battery, so it's saved, but detected again later in case it didn't answer (#655)
    asyncio.run(read.detectPlant(fake_client(lv(Model.HYBRID_GEN1, 0)), force=True))
    assert saved() == lv(Model.HYBRID_GEN1, 0) and read.capsSuspect
    asyncio.run(read.detectPlant(fake_client(lv(Model.HYBRID_GEN1, 1)), force=True))
    assert saved() == lv(Model.HYBRID_GEN1, 1) and not read.capsSuspect

def test_cached_hybrid_without_batteries_checked_again():
    save(lv(Model.HYBRID_GEN2, 0))
    client = fake_client(lv(Model.HYBRID_GEN2, 1))
    assert asyncio.run(read.detectPlant(client)) is True       # uses the cache...
    assert read.capsSuspect                                      # ...but the read loop will detect again

def test_no_battery_fitted_stops_checking():
    # "No battery fitted" ticked: a hybrid that really has none isn't detected again every few minutes to hourly
    env.configure(serial_number="AA1111A111", No_Battery=True)
    asyncio.run(read.detectPlant(fake_client(lv(Model.HYBRID_GEN4, 0)), force=True))
    assert saved() == lv(Model.HYBRID_GEN4, 0) and not read.capsSuspect
    read.capsSuspect = False
    assert asyncio.run(read.detectPlant(fake_client(lv(Model.HYBRID_GEN4, 0)))) is True     # the cached ones
    assert not read.capsSuspect

def test_no_battery_fitted_doesnt_apply_to_built_in_batteries():
    # An All in One always has batteries, so none found still means they didn't answer
    env.configure(serial_number="AA1111A111", No_Battery=True)
    asyncio.run(read.detectPlant(fake_client(aio(0)), force=True))
    assert not os.path.exists(read.capsFile()) and read.capsSuspect

def test_hybrid_without_batteries_stops_being_checked():
    # Without "No battery fitted" ticked, a hybrid that keeps detecting with no batteries is taken to have none after
    # NO_BATTERY_DETECTS detects in a row, rather than re-detected hourly for ever (#665)
    for i in range(read.NO_BATTERY_DETECTS):
        asyncio.run(read.detectPlant(fake_client(lv(Model.HYBRID_GEN4, 0)), force=True))
        assert read.capsSuspect == (i < read.NO_BATTERY_DETECTS - 1)
    read.capsSuspect = False
    assert asyncio.run(read.detectPlant(fake_client(lv(Model.HYBRID_GEN4, 0)))) is True      # the cached ones: not suspect
    assert not read.capsSuspect
    asyncio.run(read.detectPlant(fake_client(lv(Model.HYBRID_GEN4, 1)), force=True))         # a battery that answers
    assert saved() == lv(Model.HYBRID_GEN4, 1) and read.noBatteryDetects == 0

