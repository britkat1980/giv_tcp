from __future__ import annotations

import logging
import sys
import time as t
from datetime import datetime, time
from typing import Mapping, Sequence

from pymodbus.client.sync import ModbusTcpClient

from givenergy_modbus.modbus import GivEnergyModbusTcpClient
from givenergy_modbus.model.plant import Plant
from givenergy_modbus.model.register import HoldingRegister,HoldingRegister_AC, InputRegister  # type: ignore
from givenergy_modbus.model.register_cache import RegisterCache

_logger = logging.getLogger(__package__)

DEFAULT_SLEEP = 0.5


class GivEnergyClient:
    """Client for end users to conveniently access GivEnergy inverters."""

    def __init__(self, host: str, port: int = 8899, modbus_client: ModbusTcpClient = None):
        self.host = host
        self.port = port
        if modbus_client is None:
            modbus_client = GivEnergyModbusTcpClient(host=self.host, port=self.port)
        self.modbus_client = modbus_client

    def __repr__(self):
        return f"GivEnergyClient({self.host}:{self.port}))"

    def fetch_register_pages(
        self,
        pages: Mapping[type[HoldingRegister | HoldingRegister_AC | InputRegister], Sequence[int]],
        register_cache: RegisterCache,
        slave_address: int = 0x31,
        sleep_between_queries: float = DEFAULT_SLEEP,
    ) -> None:
        """Reload all inverter data from the device."""
        for register, base_registers in pages.items():
            for base_register in base_registers:
                data = self.modbus_client.read_registers(register, base_register, 60, slave_address=slave_address)
                register_cache.set_registers(register, data)
                t.sleep(sleep_between_queries)

    def refresh_plant(self, plant: Plant, isAIO: bool, isAC: bool, full_refresh: bool, sleep_between_queries=DEFAULT_SLEEP):
        """Refresh the internal caches for a plant. Optionally refresh only data that changes frequently."""
        inverter_registers = {
            InputRegister: [0, 180],
        }

        if full_refresh:
            if isAC:
                inverter_registers[HoldingRegister_AC] = [0, 60, 120]
            else:
                inverter_registers[HoldingRegister] = [0, 60, 120, 240, 300]

        #How do I know which inverter I'm connecting to from inside the library...
        if isAIO:
            self.fetch_register_pages(
                inverter_registers, plant.inverter_rc, slave_address=0x11, sleep_between_queries=sleep_between_queries
            )
            _logger.debug("Inverter is AIO so using the 0x11 slave_address")
        elif isAC:
            self.fetch_register_pages(
                inverter_registers, plant.inverter_rc_ac, slave_address=0x31, sleep_between_queries=sleep_between_queries
            )
        else:
            self.fetch_register_pages(
                inverter_registers, plant.inverter_rc, slave_address=0x31, sleep_between_queries=sleep_between_queries
            )
            _logger.debug("Inverter is normal so using the 0x31 slave_address")
        if isAIO:
            for i, battery_rc in enumerate(plant.batteries_rcs):
                self.fetch_register_pages(
                    {InputRegister: [60]},
                    battery_rc,
                    slave_address=0x32 + i,
                    sleep_between_queries=sleep_between_queries,
                )
        else:
            for i, battery_rc in enumerate(plant.batteries_rcs):
                self.fetch_register_pages(
                    {InputRegister: [60]},
                    battery_rc,
                    slave_address=0x32 + i,
                    sleep_between_queries=sleep_between_queries,
                )

    def get_inverter_stats(self):
        try:
            SN={}
            regs=self.modbus_client.read_holding_registers(0,22)
            DTC=hex(regs[0])[-4:] #plant.inverter.device_type_code
            SN_1=bytes.fromhex(hex(regs[13])[2:]).decode("ASCII")
            SN_2=bytes.fromhex(hex(regs[14])[2:]).decode("ASCII")
            SN_3=bytes.fromhex(hex(regs[15])[2:]).decode("ASCII")
            SN_4=bytes.fromhex(hex(regs[16])[2:]).decode("ASCII")
            SN_5=bytes.fromhex(hex(regs[17])[2:]).decode("ASCII")
            SN=SN_1+SN_2+SN_3+SN_4+SN_5 #SN=plant.inverter.inverter_serial_number
            FW=regs[21] #plant.inverter.arm_firmware_version
            return DTC,FW,SN
        except:
            return ("ERROR: "+str(sys.exc_info()))

    def enable_charge_target(self, target_soc: int):
        """Sets inverter to stop charging when SOC reaches the desired level. Also referred to as "winter mode"."""
        if target_soc > 100:
            target_soc=100
        elif target_soc<4:
            target_soc=4

        if target_soc == 100:
            self.disable_charge_target()
        else:
            self.modbus_client.write_holding_register(HoldingRegister.ENABLE_CHARGE_TARGET, True)
            self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC, target_soc)

    def enable_charge_target_2(self, target_soc: int, slot: int):
        """Sets inverter to stop charging when SOC reaches the desired level. Also referred to as "winter mode"."""
        if target_soc > 100:
            target_soc=100
        elif target_soc<4:
            target_soc=4

        if target_soc == 100:
            self.disable_charge_target()
        else:
            self.modbus_client.write_holding_register(HoldingRegister.ENABLE_CHARGE_TARGET, True)
            if slot==1:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_1, target_soc)
            if slot==2:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_2, target_soc)
            if slot==3:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_3, target_soc)
            if slot==4:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_4, target_soc)
            if slot==5:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_5, target_soc)
            if slot==6:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_6, target_soc)
            if slot==7:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_7, target_soc)
            if slot==8:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_8, target_soc)
            if slot==9:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_9, target_soc)
            if slot==10:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC_10, target_soc)



    def reboot_inverter(self):
        """Reboot Invertor"""
        ### WARNING - MODIFYING THIS FUNCTION TO USE ANY OTHER VALUE THAN 100 WILL BRICK YOUR INVERTOR... DON'T DO IT!
        self.modbus_client.write_holding_register(HoldingRegister.REBOOT_INVERTER, 100)

    def disable_charge_target(self):
        """Removes SOC limit and target 100% charging."""
        self.modbus_client.write_holding_register(HoldingRegister.ENABLE_CHARGE_TARGET, False)
        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC, 100)

    def enable_charge(self):
        """Set the battery to charge, depending on the mode and slots set."""
        self.modbus_client.write_holding_register(HoldingRegister.ENABLE_CHARGE, True)

    def disable_charge(self):
        """Disable the battery from charging."""
        self.modbus_client.write_holding_register(HoldingRegister.ENABLE_CHARGE, False)

    def enable_discharge(self):
        """Set the battery to discharge, depending on the mode and slots set."""
        self.modbus_client.write_holding_register(HoldingRegister.ENABLE_DISCHARGE, True)

    def disable_discharge(self):
        """Set the battery to not discharge at all."""
        self.modbus_client.write_holding_register(HoldingRegister.ENABLE_DISCHARGE, False)

    def set_battery_discharge_mode_max_power(self):
        """Set the battery to discharge at maximum power (export) when discharging."""
        self.modbus_client.write_holding_register(HoldingRegister.BATTERY_POWER_MODE, 0)

    def set_battery_discharge_mode_demand(self):
        """Set the battery to discharge to match demand (no export) when discharging."""
        self.modbus_client.write_holding_register(HoldingRegister.BATTERY_POWER_MODE, 1)

#    def set_charge_slot_1(self, times: tuple[time, time]):
#        """Set first charge slot times."""
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_START, int(times[0].strftime('%H%M')))
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_END, int(times[1].strftime('%H%M')))

#    def set_charge_slot_start_1(self, timeslot: time):
#        """Set first charge slot start time."""
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_START, int(timeslot.strftime('%H%M')))

#    def set_charge_slot_end_1(self, timeslot: time):
#        """Set first charge slot end time."""
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_END, int(timeslot.strftime('%H%M')))

#    def reset_charge_slot_1(self):
#        """Reset first charge slot times to zero/disabled."""
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_START, 0)
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_END, 0)

#    def set_charge_slot_2(self, times: tuple[time, time]):
#        """Set second charge slot times."""
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_2_START, int(times[0].strftime('%H%M')))
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_2_END, int(times[1].strftime('%H%M')))

#    def reset_charge_slot_2(self):
#        """Reset second charge slot times to zero/disabled."""
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_2_START, 0)
#        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_2_END, 0)

#    def set_discharge_slot_1(self, times: tuple[time, time]):
#        """Set first discharge slot times."""
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_START, int(times[0].strftime('%H%M')))
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_END, int(times[1].strftime('%H%M')))

#    def set_discharge_slot_start_1(self, timeslot: time):
#        """Set first charge slot start time."""
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_START, int(timeslot.strftime('%H%M')))

#    def set_discharge_slot_end_1(self, timeslot: time):
#        """Set first charge slot end time."""
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_END, int(timeslot.strftime('%H%M')))

#    def reset_discharge_slot_1(self):
#        """Reset first discharge slot times to zero/disabled."""
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_START, 0)
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_END, 0)

#    def set_discharge_slot_2(self, times: tuple[time, time]):
#        """Set second discharge slot times."""
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_START, int(times[0].strftime('%H%M')))
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_END, int(times[1].strftime('%H%M')))

#    def set_discharge_slot_start_2(self, timeslot: time):
#        """Set first charge slot start time."""
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_START, int(timeslot.strftime('%H%M')))

#    def set_discharge_slot_end_2(self, timeslot: time):
#        """Set first charge slot end time."""
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_END, int(timeslot.strftime('%H%M')))

#    def reset_discharge_slot_2(self):
#        """Reset first discharge slot times to zero/disabled."""
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_START, 0)
#        self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_END, 0)

    def set_discharge_slot_start(self, slot: int, timeslot: time):
        """Set discharge slot start time, for any slot 1-10."""
        #  slot n = 276+((n-3)*3)
        if 1 <=slot <=10:
            if slot==1:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_START, int(timeslot.strftime('%H%M')))
            elif slot==2:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_START, int(timeslot.strftime('%H%M')))
            elif slot==3:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_3_START, int(timeslot.strftime('%H%M')))
            elif slot==4:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_4_START, int(timeslot.strftime('%H%M')))
            elif slot==5:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_5_START, int(timeslot.strftime('%H%M')))
            elif slot==6:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_6_START, int(timeslot.strftime('%H%M')))
            elif slot==7:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_7_START, int(timeslot.strftime('%H%M')))
            elif slot==8:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_8_START, int(timeslot.strftime('%H%M')))
            elif slot==9:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_9_START, int(timeslot.strftime('%H%M')))
            elif slot==10:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_10_START, int(timeslot.strftime('%H%M')))
        else:
            raise ValueError(f'Specified slot ({slot}) is not in [1-10]')

    def set_discharge_slot_end(self, slot: int, timeslot: time):
        """Set discharge slot start time, for any slot 3-10."""
        #  slot n = 277+((n-3)*3)
        if 1 <=slot <=10:
            if slot==1:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_END, int(timeslot.strftime('%H%M')))
            elif slot==2:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_END, int(timeslot.strftime('%H%M')))
            elif slot==3:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_3_END, int(timeslot.strftime('%H%M')))
            elif slot==4:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_4_END, int(timeslot.strftime('%H%M')))
            elif slot==5:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_5_END, int(timeslot.strftime('%H%M')))
            elif slot==6:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_6_END, int(timeslot.strftime('%H%M')))
            elif slot==7:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_7_END, int(timeslot.strftime('%H%M')))
            elif slot==8:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_8_END, int(timeslot.strftime('%H%M')))
            elif slot==9:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_9_END, int(timeslot.strftime('%H%M')))
            elif slot==10:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_10_END, int(timeslot.strftime('%H%M')))
        else:
            raise ValueError(f'Specified slot ({slot}) is not in [1-10]%')

    def set_discharge_slot(self, slot: int, times: tuple[time, time]):
        """Set discharge slot time, for any slot 3-10."""
        #  slot n = 276+((n-3)*3)
        if 1 <=slot <=10:
            if slot==1:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_START, int(times[0].strftime('%H%M')))
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_1_END, int(times[1].strftime('%H%M')))
            elif slot==2:
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_START, int(times[0].strftime('%H%M')))
                self.modbus_client.write_holding_register(HoldingRegister.DISCHARGE_SLOT_2_END, int(times[1].strftime('%H%M')))
            else:
                self.modbus_client.write_holding_register(HoldingRegister(276+((slot-3)*3)), int(times[0].strftime('%H%M')))
                self.modbus_client.write_holding_register(HoldingRegister(277+((slot-3)*3)), int(times[1].strftime('%H%M')))
        else:
            raise ValueError(f'Specified slot ({slot}) is not in [1-10]%')

    def set_charge_slot_start(self, slot: int, timeslot: time):
        """Set discharge slot start time, for any slot 2-10."""
        #  slot n = 243+((n-2)*3)
        if 1 <=slot <=10:
            if slot==1:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_START, int(timeslot.strftime('%H%M')))
            else:
                self.modbus_client.write_holding_register(HoldingRegister(243+((slot-2)*3)), int(timeslot.strftime('%H%M')))
        else:
            raise ValueError(f'Specified slot ({slot}) is not in [1-10]%')

    def set_charge_slot_end(self, slot: int, timeslot: time):
        """Set discharge slot start time, for any slot 2-10."""
        #  slot n = 244+((n-2)*3)
        if 1 <=slot <=10:
            if slot==1:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_END, int(timeslot.strftime('%H%M')))
            else:
                self.modbus_client.write_holding_register(HoldingRegister(244+((slot-2)*3)), int(timeslot.strftime('%H%M')))
        else:
            raise ValueError(f'Specified slot ({slot}) is not in [1-10]%')

    def set_charge_slot(self, slot: int, times: tuple[time, time]):
        """Set charge slot time, for any slot 2-10."""
        if 1 <=slot <=10:
            if slot==1:
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_START, int(times[0].strftime('%H%M')))
                self.modbus_client.write_holding_register(HoldingRegister.CHARGE_SLOT_1_END, int(times[1].strftime('%H%M')))
            else:
                self.modbus_client.write_holding_register(HoldingRegister(243+((slot-2)*3)), int(times[0].strftime('%H%M')))
                self.modbus_client.write_holding_register(HoldingRegister(244+((slot-2)*3)), int(times[1].strftime('%H%M')))
        else:
            raise ValueError(f'Specified slot ({slot}) is not in [1-10]%')

    def set_pause_slot_start(self, timeslot: time):
        """Set first charge slot start time."""
        self.modbus_client.write_holding_register(HoldingRegister.BATTERY_PAUSE_SLOT_START, int(timeslot.strftime('%H%M')))

    def set_pause_slot_end(self, timeslot: time):
        """Set first charge slot end time."""
        self.modbus_client.write_holding_register(HoldingRegister.BATTERY_PAUSE_SLOT_END, int(timeslot.strftime('%H%M')))

    def set_mode_dynamic(self):
        """Set system to Dynamic / Eco mode.

        This mode is designed to maximise use of solar generation. The battery will charge when
        there is excess power being generated from your solar panels. The battery will store and hold this energy
        until your demand increases. The system will try and balance the use of solar and battery so that you are
        importing and exporting as little energy as possible. This mode is useful if you want to maximise
        self-consumption of renewable generation and minimise the amount of energy drawn from the grid.
        """
        self.set_battery_discharge_mode_demand()  # r27=1
        self.set_shallow_charge(4)  # r110=4
        self.disable_discharge()  # r59=0

    def set_mode_storage(
        self, slot_1: tuple[time, time] = (time(hour=16), time(hour=7)), slot_2: tuple[time, time] = None, export=False
    ):
        """Set system to storage mode with specific discharge slots(s).

        This mode stores excess solar generation during the day and holds that energy ready for use later in the day.
        By default, the battery will start to discharge from 4pm-7am to cover energy demand during typical peak hours.
        This mode is particularly useful if you get charged more for your electricity at certain times to utilise the
        battery when it is most effective. If the second time slot isn't specified, it will be cleared.

        You can optionally also choose to export excess energy: instead of discharging to meet only your home demand,
        the battery will discharge at full power and any excess will be exported to the grid. This is useful if you
        have a variable export tariff (e.g. Agile export) and you want to target the peak times of day (e.g. 4pm-7pm)
        when it is both most expensive to import and most valuable to export energy.
        """
        if export:
            self.set_battery_discharge_mode_max_power()  # r27=0
        else:
            self.set_battery_discharge_mode_demand()  # r27=1
        # Remove this line to allow discharge
        #self.set_shallow_charge(100)  # r110=100
        self.enable_discharge()  # r59=1
        self.set_discharge_slot_1(slot_1)  # r56=1600, r57=700
        if slot_2:
            self.set_discharge_slot_1(slot_2)  # r56=1600, r57=700
        else:
            self.reset_discharge_slot_2()

    def set_datetime(self, dt: datetime):
        """Set the date & time of the inverter."""
        self.modbus_client.write_holding_register(HoldingRegister.SYSTEM_TIME_YEAR, dt.year)
        self.modbus_client.write_holding_register(HoldingRegister.SYSTEM_TIME_MONTH, dt.month)
        self.modbus_client.write_holding_register(HoldingRegister.SYSTEM_TIME_DAY, dt.day)
        self.modbus_client.write_holding_register(HoldingRegister.SYSTEM_TIME_HOUR, dt.hour)
        self.modbus_client.write_holding_register(HoldingRegister.SYSTEM_TIME_MINUTE, dt.minute)
        self.modbus_client.write_holding_register(HoldingRegister.SYSTEM_TIME_SECOND, dt.second)

    def set_discharge_enable(self, mode: bool):
        """Set the battery to discharge."""
        self.modbus_client.write_holding_register(HoldingRegister.ENABLE_DISCHARGE, int(mode))

    def set_shallow_charge(self, val: int):
        """Set the minimum level of charge to keep."""
        # TODO what are valid values? 4-100?
        self.modbus_client.write_holding_register(HoldingRegister.BATTERY_SOC_RESERVE, val)

    def set_active_power_rate(self, val: int):
        """Set the mmaximum inverter power rate."""
        # TODO what are valid values? 0-100?
        self.modbus_client.write_holding_register(HoldingRegister.ACTIVE_POWER_RATE, val)

    def set_battery_charge_limit(self, val: int):
        """Set the battery charge power limit as percentage. 50% (2.6 kW) is the maximum for most inverters."""
        if not 0 <= val <= 50:
            raise ValueError(f'Specified Charge Limit ({val}%) is not in [0-50]%')
        self.modbus_client.write_holding_register(HoldingRegister.BATTERY_CHARGE_LIMIT, val)

    def set_battery_discharge_limit(self, val: int):
        """Set the battery discharge power limit as percentage. 50% (2.6 kW) is the maximum for most inverters."""
        if not 0 <= val <= 50:
            raise ValueError(f'Specified Discharge Limit ({val}%) is not in [0-50]%')
        self.modbus_client.write_holding_register(HoldingRegister.BATTERY_DISCHARGE_LIMIT, val)

    def set_battery_power_reserve(self, val: int):
        """Set the battery power reserve to maintain."""
        # TODO what are valid values?
        self.modbus_client.write_holding_register(HoldingRegister.BATTERY_DISCHARGE_MIN_POWER_RESERVE, val)

    def set_battery_target_soc(self, val: int):
        """Set the target SOC when the battery charges."""
        # TODO what are valid values?
        self.modbus_client.write_holding_register(HoldingRegister.CHARGE_TARGET_SOC, val)

    def set_pv_input_mode(self, val: int):
        """Set MPPT Tracking mode."""
        # TODO what are valid values?
        if val in [0,1]:
            self.modbus_client.write_holding_register(HoldingRegister.PV_INPUT_MODE, val)
        else:
            raise ValueError(f'Specified Mode ({val}) is not in [0,1]%')

    def set_battery_pause_mode(self, val: int):
        """Set the forbid flag for charge/discharge."""
        # TODO what are valid values?
        if val in [0,1,2,3]:
            self.modbus_client.write_holding_register(HoldingRegister.BATTERY_PAUSE_MODE, val)
        else:
            raise ValueError(f'Specified Mode ({val}) is not in [0,1]')

    def set_local_control_mode(self, val: int):
        """Set the priority of output."""
        # TODO what are valid values?
        if val in [0,1,2]:
            self.modbus_client.write_holding_register(HoldingRegister.LOCAL_CONTROL_MODE, val)
        else:
            raise ValueError(f'Specified Mode ({val}) is not in [0,1]%')
