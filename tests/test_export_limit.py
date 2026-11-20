"""Export_Limit for the models whose limit is not holding register 26, replayed from the real captures.

HR 26 (grid_port_max_power_output) is the export limit on single-phase inverters, but it reads 0 on an EMS and on a
three-phase inverter. Their limits are HR 2071 on the EMS (the same value as Control.Export_Power_Limit) and HR 1102 on
three-phase, with HR 1103 saying whether three-phase export limiting is on. Zero is a real limit (a zero-export site).
"""
from givenergy_modbus.model.register import HR


def details(output):
    """The device's own block in the cache, keyed by its serial number"""
    return next(block for block in output.values() if isinstance(block, dict) and "Invertor_Serial_Number" in block)


def read(session, **registers):
    """One read cycle from the captured state, with some 0x11 holding registers changed first"""
    session.activate(session.state)
    for register, value in registers.items():
        session.plant.register_caches[0x11][HR(int(register[2:]))] = value
    return session.read_cycle()["output"]


def test_three_phase_export_limit_is_hr1102(plants):
    session = plants.get("hybrid_3ph")
    output = read(session)
    assert session.plant.register_caches[0x11][HR(1103)] == 1
    assert details(output)["Export_Limit"] == session.plant.register_caches[0x11][HR(1102)] == 17000


def test_three_phase_export_limit_off_is_the_inverter_rating(plants):
    # With export limiting switched off only the inverter itself limits export
    output = read(plants.get("hybrid_3ph"), HR1103=0)
    block = details(output)
    assert block["Export_Limit"] == block["Invertor_Max_Inv_Rate"]


def test_ems_export_limit_is_hr2071(plants):
    session = plants.get("ems")
    output = read(session)
    assert details(output)["Export_Limit"] == session.plant.register_caches[0x11][HR(2071)] == 9500
    assert details(output)["Export_Limit"] == output["Control"]["Export_Power_Limit"]


def test_zero_export_limit_is_published(plants):
    # A zero-export site: the smoother must not hold on to the previous non-zero limit
    session = plants.get("ems")
    read(session)
    output = session.read_cycle()["output"]
    assert details(output)["Export_Limit"] == 9500
    session.plant.register_caches[0x11][HR(2071)] = 0
    output = session.read_cycle()["output"]
    assert details(output)["Export_Limit"] == 0
