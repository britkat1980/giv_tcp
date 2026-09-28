import asyncio
from givenergy_modbus.client.client import Client
from givenergy_modbus.client import commands
from givenergy_modbus.model import TimeSlot
from givenergy_modbus.model.inverter import Model

async def main():
    client = Client(host="192.168.2.3", port=8899)
    await client.connect()

    # Read current state first (needed for slot_map)
    await client.refresh_plant(full_refresh=True)
    plant = client.plant

    # Write configuration to the device
    await client.one_shot_command(commands.set_charge_target(80))
    # set a charging slot from 00:30 to 04:30; slot_map selects correct registers for this model
    await client.one_shot_command(
        commands.set_charge_slot(1, TimeSlot.from_components(0, 30, 4, 30), plant.inverter.slot_map)
    )
    # set the inverter to charge from excess solar and discharge to meet demand
    await client.one_shot_command(commands.set_mode_dynamic())

    assert plant.inverter_serial_number == 'SA1234G567'
    assert plant.inverter.model == Model.HYBRID
    assert plant.inverter.enable_charge_target
    assert plant.inverter.charge_slot_1 == TimeSlot.from_components(0, 30, 4, 30)
    assert plant.inverter.model_dump() == {
        'serial_number': 'SA1234G567',
        'device_type_code': '3001',
        'charge_slot_1': TimeSlot.from_components(0, 30, 4, 30),
    }
    assert plant.inverter.model_dump_json() == '{"serial_number": "SA1234G567", "device_type_code": "3001", ...'

    assert plant.batteries[0].serial_number == 'BG1234G567'
    assert plant.batteries[0].v_cell_01 == 3.117
    assert plant.batteries[0].model_dump() == {
        'bms_firmware_version': 3005,
        'cap_design': 160.0,

    }
    assert plant.batteries[0].model_dump_json() == '{"serial_number": "BG1234G567", "v_cell_01": 3.117, ...'

    await client.close()

asyncio.run(main())