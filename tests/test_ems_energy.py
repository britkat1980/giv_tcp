"""EMS energy from IR 0-59, replayed from real EMS captures: the generation meters (#637), and the replies with every total
zero that the dongle sometimes relays, which mustn't be published as zeros"""
import asyncio
from pathlib import Path

from givenergy_modbus.framer import ClientFramer
from givenergy_modbus.model.inverter import Model
from givenergy_modbus.model.plant import Plant, PlantCapabilities
from givenergy_modbus.pdu.read_registers import ReadInputRegistersResponse

import read

SHARED = Path(__file__).parent / "fixtures" / "captures" / "shared"

def replay(name):
    """The EMS_IR_VALUES after each IR 0-59 reply in the capture, each with the output before it as `previous`"""
    plant = Plant()
    plant.capabilities = PlantCapabilities(device_type=Model.EMS)
    results, previous = [], {}
    async def run():
        nonlocal previous
        for line in open(SHARED / name):
            stamp, direction, frame = line.split()
            if direction != "rx":
                continue
            async for pdu in ClientFramer().decode(bytes.fromhex(frame)):
                plant.update(pdu)
                if isinstance(pdu, ReadInputRegistersResponse) and pdu.device_address == 0x11 and pdu.base_register == 0:
                    values = read.emsIRValues(plant.register_caches[0x11], previous)
                    results.append((pdu.register_values, values))
                    previous = {"Energy": {"Total": values["Total"], "Today": values["Today"]}, "Power": values["Power"]}
    asyncio.run(run())
    return results

def test_generation_meters():
    # #638: inverter out today 20.4 kWh, the generation meter 5.0 kWh
    _, values = replay("ems_arm1036_issue638.capture")[0]
    assert values["Today"]["Generation_Energy_Today_kWh"] == 5.0
    assert values["Today"]["Inverter_Out_Energy_Today_kWh"] == 20.4
    assert values["Total"]["Generation_Energy_Total_kWh"] == 12199.3
    assert values["Total"]["Inverter_Out_Energy_Total_kWh"] == 18832.3

def test_blank_reply_keeps_previous():
    results = replay("ems_arm1036_issue632.capture")
    blank = [i for i, (regs, _) in enumerate(results) if not any(regs[r] for r in (6, 7, 11, 12, 21, 22, 27, 28, 32, 33))]
    assert blank and blank[0] > 0
    before, during = results[blank[0] - 1][1], results[blank[0]][1]
    assert during == before
    assert during["Total"]["Inverter_Out_Energy_Total_kWh"] == 18394.2
