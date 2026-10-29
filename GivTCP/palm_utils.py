#!/usr/bin/env python3
"""PALM - PV Active Load Manager."""

import time
import json
from datetime import datetime, timedelta
from typing import Tuple, List
import logging
## import matplotlib.pyplot as plt
import requests
import palm_settings as stgs

logger = logging.getLogger(__name__)

# Load history from the GivEnergy API's data points: records per page, and the most pages read for one day (a
# day of 30-second records is about 2,900)
LOAD_HIST_PAGE_SIZE = 2000
LOAD_HIST_MAX_PAGES = 10
# A day's history is only used if it runs to at least 9pm (minutes after midnight), the time PALM starts
# counting today
LOAD_HIST_MIN_COVERAGE_MINS = 1260
# The counter resets in the first readings after midnight (minutes): a drop before this is that reset
LOAD_HIST_RESET_WINDOW_MINS = 60

# This software in any form is covered by the following Open Source BSD license:
#
# Copyright 2023, Steve Lewis
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted
# provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions
# and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of
# conditions and the following disclaimer in the documentation and/or other materials provided
# with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY
# WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

###########################################
# This code provides several functions:
# 1. Collection of generation/consumption data from GivEnergy API & upload to PVOutput
# 2. Load management - lights, excess power dumping, etc
# 3. Setting overnight charge point, based on SolCast forecast & actual usage
###########################################

# Changelog:
# v0.6.0    12/Feb/22 First cut at GivEnergy interface
# ...
# v0.10.0   21/Jun/23 Added multi-day averaging for usage calcs
# v1.0.0    15/Jul/23 Random start time, Solcast data correction, IO compatibility, 48-hour fcast
# v1.1.0    06/Aug/23 Split out generic functions as palm_utils.py, remove randomised start time
# v1.1.0a   11/Nov/23 Fixed resume operation after daytime charging, bugfix for chart generation

PALM_VERSION = "v1.1.0a"
# -*- coding: utf-8 -*-
# pylint: disable=logging-not-lazy
# pylint: disable=consider-using-f-string

class GivEnergyObj:
    """Class for GivEnergy inverter"""

    def __init__(self):
        sys_item = {'time': '',
                    'solar': {'power': 0, 'arrays':
                                  [{'array': 1, 'voltage': 0, 'current': 0, 'power': 0},
                                   {'array': 2, 'voltage': 0, 'current': 0, 'power': 0}]},
                    'grid': {'voltage': 0, 'current': 0, 'power': 0, 'frequency': 0},
                    'battery': {'percent': 0, 'power': 0, 'temperature': 0},
                    'inverter': {'temperature': 0, 'power': 0, 'output_voltage': 0, \
                        'output_frequency': 0, 'eps_power': 0},
                    'consumption': 0}
        self.sys_status: List[str] = [sys_item] * 5

        meter_item = {'time': '',
                      'today': {'solar': 0, 'grid': {'import': 0, 'export': 0},
                                'battery': {'charge': 0, 'discharge': 0}, 'consumption': 0},
                      'total': {'solar': 0, 'grid': {'import': 0, 'export': 0},
                                'battery': {'charge': 0, 'discharge': 0}, 'consumption': 0}}
        self.meter_status: List[str] = [meter_item] * 5

        self.read_time_mins: int = -100
        self.line_voltage: float = 0
        self.grid_power: int = 0
        self.grid_energy: int = 0
        self.pv_power: int = 0
        self.pv_energy: int = 0
        self.batt_power: int = 0
        self.consumption: int = 0
        self.soc: int = 0
        self.base_load = stgs.GE.base_load
        self.tgt_soc = 100
        self.cmd_list = stgs.GE.Command_list['data']
        self.plot = [""] * 5

        logger.debug("Valid inverter commands:")
        for line in self.cmd_list:
            logger.debug(str(line['id'])+ "- "+ str(line['name']))

    def get_latest_data(self):
        """Download latest data from GivEnergy."""

        utc_timenow_mins = t_to_mins(time.strftime("%H:%M:%S", time.gmtime()))
        if (utc_timenow_mins > self.read_time_mins + 5 or
            utc_timenow_mins < self.read_time_mins):  # Update every 5 minutes plus day rollover

            url = stgs.GE.url + "system-data/latest"
            key = stgs.GE.key
            headers = {
                'Authorization': 'Bearer  ' + key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            try:
                resp = requests.request('GET', url, headers=headers, timeout=10)
            except requests.exceptions.RequestException as error:
                logger.error(error)
                return

            if len(resp.content) > 100:
                for i in range(4, -1, -1):  # Right shift old data
                    if i > 0:
                        self.sys_status[i] = self.sys_status[i - 1]
                    else:
                        try:
                            self.sys_status[i] = \
                                json.loads(resp.content.decode('utf-8'))['data']
                        except Exception:
                            logger.error("Error reading GivEnergy sys status "+ stgs.pg.t_now)
                            logger.error(resp.content)
                            self.sys_status[i] = self.sys_status[i + 1]
                if stgs.pg.loop_counter == 0:  # Pack array on startup
                    i = 1
                    while i < 5:
                        self.sys_status[i] = self.sys_status[0]
                        i += 1
                self.read_time_mins = t_to_mins(self.sys_status[0]['time'][11:])
                self.line_voltage = float(self.sys_status[0]['grid']['voltage'])
                self.grid_power = -1 * int(self.sys_status[0]['grid']['power'])  # -ve = export
                self.pv_power = int(self.sys_status[0]['solar']['power'])
                self.batt_power = int(self.sys_status[0]['battery']['power'])  # -ve = charging
                self.consumption = int(self.sys_status[0]['consumption'])
                self.soc = int(self.sys_status[0]['battery']['percent'])

            url = stgs.GE.url + "meter-data/latest"
            try:
                resp = requests.request('GET', url, headers=headers, timeout=10)
            except requests.exceptions.RequestException as error:
                logger.error(error)
                return

            if len(resp.content) > 100:
                for i in range(4, -1, -1):  # Right shift old data
                    if i > 0:
                        self.meter_status[i] = self.meter_status[i - 1]
                    else:
                        try:
                            self.meter_status[i] = \
                                json.loads(resp.content.decode('utf-8'))['data']
                        except Exception:
                            logger.error("Error reading GivEnergy meter status "+ stgs.pg.t_now)
                            logger.error(resp.content)
                            self.meter_status[i] = self.meter_status[i + 1]
                if stgs.pg.loop_counter == 0:  # Pack array on startup
                    i = 1
                    while i < 5:
                        self.meter_status[i] = self.meter_status[0]
                        i += 1

                self.pv_energy = int(self.meter_status[0]['today']['solar'] * 1000)

                # Daily grid energy must be >=0 for PVOutput.org (battery charge >= midnight value)
                self.grid_energy = max(int(self.meter_status[0]['today']['consumption'] * 1000), 0)

    def get_load_hist(self):
        """Download historical consumption data from GivEnergy and pack array for next SoC calc"""

        def get_load_hist_records(day: str):
            """Every data point the GivEnergy API has for a day, from all its pages, or None if it can't be read"""
            url = stgs.GE.url + "data-points/"+ day
            headers = {
                'Authorization': 'Bearer  ' + stgs.GE.key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            records = []
            for page in range(1, LOAD_HIST_MAX_PAGES + 1):
                params = {'page': str(page), 'pageSize': str(LOAD_HIST_PAGE_SIZE)}
                try:
                    resp = requests.request('GET', url, headers=headers, params=params, timeout=10)
                except requests.exceptions.RequestException as error:
                    logger.error(error)
                    return None
                if resp.status_code != 200:
                    logger.error("Invalid response: "+ str(resp.status_code))
                    return None
                try:
                    history = json.loads(resp.content.decode('utf-8'))
                except ValueError:
                    logger.error("Unreadable load history for "+ day)
                    return None
                data = history.get('data') if isinstance(history, dict) else None
                if not isinstance(data, list):
                    break
                records += data
                # The API returns as many records a day as the inverter logged (eg. every 30s), over several pages
                meta = history.get('meta') or {}
                last_page = meta.get('last_page') if isinstance(meta, dict) else None
                if (last_page is not None and page >= int(last_page)) or len(data) < LOAD_HIST_PAGE_SIZE:
                    break
            return records

        def get_load_hist_day(offset: int):
            """Half-hourly load for a single day (kWh), or None if the day's history doesn't cover the day"""

            day_delta = offset if (stgs.pg.t_now_mins > 1260) else offset + 1  # Today if >9pm
            day_start = (datetime.now() - timedelta(day_delta)).replace(hour=0, minute=0, second=0, microsecond=0)
            day = datetime.strftime(day_start, '%Y-%m-%d')
            records = get_load_hist_records(day)
            if not records:
                return None

            # Each record's today.consumption is the day's consumption so far. Place each one by its own time:
            # the API's interval isn't fixed (5 minutes on some systems, 30 seconds on others, #684). Records
            # without a time are taken as 5 minutes apart from midnight, as the API used to return
            readings = []
            for index, record in enumerate(records):
                try:
                    energy = float(record['today']['consumption'])
                except (KeyError, TypeError, ValueError):
                    continue
                when = record.get('time') if isinstance(record, dict) else None
                if when:
                    try:
                        local = datetime.fromisoformat(str(when).replace('Z', '+00:00')).astimezone().replace(tzinfo=None)
                    except ValueError:
                        continue
                    minutes = (local - day_start).total_seconds() / 60
                    # Not the previous or next day's: the counter resets at midnight
                    if 0 <= minutes < 24 * 60:
                        readings.append((minutes, energy))
                elif index * 5 <= 24 * 60:      # the 289th (index 288) is the end of the day
                    readings.append((index * 5, energy))
            readings.sort()
            if not readings or readings[-1][0] < LOAD_HIST_MIN_COVERAGE_MINS:
                logger.warning("Load history for "+ day+ " ends at "+ (t_to_hrs(int(readings[-1][0])) if readings else "00:00")+
                               ", so it's not used for the load forecast")
                return None

            # The day's first readings can still hold the previous day's total until the counter resets: in the
            # first hour, a drop is that reset, so the readings before it aren't today's (#684)
            for index in range(len(readings) - 1, 0, -1):
                if readings[index][0] < LOAD_HIST_RESET_WINDOW_MINS and readings[index][1] < readings[index - 1][1]:
                    readings = readings[index:]
                    break
            # The counter can't come down later in the day, so a reading higher than every one after it is spurious
            # (eg. a stale previous day's total) and is skipped, rather than held for the rest of the day
            later = float('-inf')
            kept = []
            for minutes, energy in reversed(readings):
                if not kept or energy <= later:
                    kept.append((minutes, energy))
                    later = max(later, energy)
            readings = kept[::-1]

            # The day's consumption at the end of each half hour. Running maximum: the counter only rises during a
            # day, so a stale reading lower than the one before it is ignored
            load_array = [0.0] * 48
            reading = 0
            so_far = prev = 0.0
            for slot in range(48):
                end = (slot + 1) * 30
                while reading < len(readings) and readings[reading][0] <= end:
                    so_far = max(so_far, readings[reading][1])
                    reading += 1
                if readings[-1][0] < end - 30:
                    break       # no data for this half hour (today, after 9pm): left at 0, as before
                load_array[slot] = round(so_far - prev, 2)
                prev = so_far
            return load_array

        load_hist_array = [0] * 48
        acc_load = [0] * 48
        total_weight: float = 0

        i: int = 0
        while i < len(stgs.GE.load_hist_weight):
            if stgs.GE.load_hist_weight[i] > 0:
                logger.debug("Processing load history for day -"+ str(i + 1))
                load_hist_array = get_load_hist_day(i)
                if load_hist_array is None:
                    # Missing or incomplete history isn't a day with no load, so leave it out (#684)
                    i += 1
                    continue
                j = 0
                while j < 48:
                    acc_load[j] += load_hist_array[j] * stgs.GE.load_hist_weight[i]
                    acc_load[j] = round(acc_load[j], 2)
                    j += 1
                total_weight += stgs.GE.load_hist_weight[i]
                logger.debug(str(acc_load)+ " total weight: "+ str(total_weight))
            else:
                logger.debug("Skipping load history for day -"+ str(i + 1)+ " (weight <= 0)")
            i += 1

        if total_weight == 0:
            if not any(w > 0 for w in stgs.GE.load_hist_weight):
                logger.error("Configuration error: incorrect daily weightings")
            else:
                logger.warning("No complete load history from the GivEnergy API, so the load forecast uses the "
                               "previous load profile")
            # Keep the profile PALM already has (the default one at first), rather than forecast no load at all
            return

        # Calculate averages and write results
        i = 0
        while i < 48:
            self.base_load[i] = round(acc_load[i]/total_weight, 1)
            i += 1
        logger.debug("Load Calc Summary: "+ str(self.base_load))

    def set_mode(self, cmd: str):
        """Configures inverter operating mode"""

        def set_inverter_register(register: str, value: str):
            """Exactly as it says"""

            # Validate command against list in settings
            cmd_name = ""
            valid_cmd = False
            for line in self.cmd_list:
                if line['id'] == int(register):
                    cmd_name = line['name']
                    valid_cmd = True
                    break

            if valid_cmd is False:
                logger.critical("write attempt to invalid inverter register: "+ str(register))
                return

            url = stgs.GE.url + "settings/"+ register + "/write"
            key = stgs.GE.key
            headers = {
                'Authorization': 'Bearer  ' + key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            payload = {
                'value': value
            }
            resp = "TEST"
            if not stgs.pg.test_mode:
                try:
                    resp = requests.request('POST', url, headers=headers, json=payload, timeout=10)
                except requests.exceptions.RequestException as error:
                    logger.error(error)
                    return
                if resp.status_code != 201:
                    logger.error("Invalid response: "+ str(resp.status_code))
                    return

            logger.info("Setting Register "+ str(register)+ " ("+ str(cmd_name) + ") to "+
                        str(value)+ "   Response: "+ str(resp))

            time.sleep(3)  # Allow data on GE server to settle

            # Readback check
            url = stgs.GE.url + "settings/"+ register + "/read"
            key = stgs.GE.key
            headers = {
                'Authorization': 'Bearer  ' + key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            payload = {}

            try:
                resp = requests.request('POST', url, headers=headers, json=payload, timeout=10)
            except resp.exceptions.RequestException as error:
                logger.error(error)
                return
            if resp.status_code != 201:
                logger.error("Invalid response: "+ str(resp.status_code))
                return

            returned_cmd = json.loads(resp.content.decode('utf-8'))['data']['value']
            if str(returned_cmd) == str(value):
                logger.debug("Successful register read: "+ str(register)+ " = "+ str(returned_cmd))
            else:
                logger.error("Readback failed on GivEnergy API... Expected " +
                    str(value) + ", Read: "+ str(returned_cmd))

        if cmd == "set_soc":  # Sets target SoC to value
            set_inverter_register("77", str(self.tgt_soc))
            if stgs.GE.start_time != "":
                start_time = t_to_hrs(t_to_mins(stgs.GE.start_time))
                set_inverter_register("64", start_time)
            if stgs.GE.end_time != "":
                set_inverter_register("65", stgs.GE.end_time)

        elif cmd == "set_soc_winter":  # Restore default overnight charge params
            set_inverter_register("77", "100")
            if stgs.GE.start_time != "":
                start_time = t_to_hrs(t_to_mins(stgs.GE.start_time))
                set_inverter_register("64", stgs.GE.start_time)
            if stgs.GE.end_time_winter != "":
                set_inverter_register("65", stgs.GE.end_time_winter)

        elif cmd == "charge_now":
            set_inverter_register("77", "100")
            set_inverter_register("64", "00:01")
            set_inverter_register("65", "23:59")

        elif cmd == "charge_now_soc":
            set_inverter_register("77", str(self.tgt_soc))
            set_inverter_register("64", "00:01")
            set_inverter_register("65", "23:59")

        elif cmd == "pause":
            set_inverter_register("72", "0")
            set_inverter_register("73", "0")

        elif cmd == "pause_charge":
            set_inverter_register("72", "0")

        elif cmd == "pause_discharge":
            set_inverter_register("73", "0")

        elif cmd == "resume":
            set_inverter_register("72", "3000")
            set_inverter_register("73", "3000")
            self.set_mode("set_soc")

        elif cmd == "test":
            logger.debug("Test set_mode")

        else:
            logger.error("unknown inverter command: "+ cmd)

    def compute_tgt_soc(self, gen_fcast, weight: int, commit: bool) -> str:
        """Compute overnight SoC target"""

        # Winter months = 100%
        if stgs.pg.month in stgs.GE.winter and commit:  # No need for sums...
            logger.info("winter month, SoC set to 100")
            self.tgt_soc = 100
            return "set_soc_winter"

        # Quick check for valid generation data
        if gen_fcast.pv_est50_day[0] == 0:
            logger.error("Missing generation data, SoC set to 100")
            self.tgt_soc = 100
            return "set_soc"

        # Solcast provides 3 estimates (P10, P50 and P90). Compute individual weighting
        # factors for each of the 3 estimates from the weight input parameter, using a
        # triangular approximation for simplicity

        weight = min(max(weight,10),90)  # Range check
        wgt_10 = max(0, 50 - weight)
        if weight > 50:
            wgt_50 = 90 - weight
        else:
            wgt_50 = weight - 10
        wgt_90 = max(0, weight - 50)

        logger.debug("")
        logger.debug("{:<20} {:>10} {:>10} {:>10} {:>10}  {:>10} {:>10}".format("SoC Calc;",
            "Day", "Hour", "Charge", "Cons", "Gen", "SoC"))

        # Definitions for export of SoC forecast in chart form
        plot_x = ["Time"]
        plot_y1 = ["Calculated SoC"]
        plot_y2 = ["Adjusted SoC"]
        plot_y3 = ["Max"]
        plot_y4 = ["Reserve"]

        if stgs.GE.end_time != "":
            end_charge_period = int(stgs.GE.end_time[0:2]) * 2
        else:
            end_charge_period = 8

        batt_max_charge: float = stgs.GE.batt_max_charge
        batt_charge: float = [0] * 98
        reserve_energy = batt_max_charge * stgs.GE.batt_reserve / 100
        max_charge_pcnt = [0] * 2
        min_charge_pcnt = [0] * 2

        # The clever bit:
        # Start with battery at reserve %. For each 30-minute slot of the coming day, calculate
        # the battery charge based on forecast generation and historical usage. Capture values
        # for maximum charge and also the minimum charge value at any time before the maximum.

        day = 0
        diff = 0
        while day < 2:  # Repeat for tomorrow and next day
            batt_charge[0] = max_charge = min_charge = reserve_energy
            est_gen = 0
            i = 0
            while i < 48:
                if i <= end_charge_period:  # Battery is in AC Charge mode
                    total_load = 0
                    batt_charge[i] = batt_charge[0]
                else:
                    total_load = self.base_load[i]
                    est_gen = (gen_fcast.pv_est10_30[day*48 + i] * wgt_10 +
                        gen_fcast.pv_est50_30[day*48 + i] * wgt_50 +
                        gen_fcast.pv_est90_30[day*48 + i] * wgt_90) / (wgt_10 + wgt_50 + wgt_90)
                    batt_charge[i] = (batt_charge[i - 1] +
                        max(-1 * stgs.GE.charge_rate,
                        min(stgs.GE.charge_rate, (est_gen - total_load))))

                # Capture min charge on lowest point on down-slope before charge reaches 100%
                # or max charge if on an up slope after overnight charge
                if (batt_charge[i] <= batt_charge[i - 1] and
                    max_charge < batt_max_charge):
                    min_charge = min(min_charge, batt_charge[i])
                elif i > end_charge_period:  # Charging after overnight boost
                    max_charge = max(max_charge, batt_charge[i])

                logger.debug("{:<20} {:>10} {:>10} {:>10} {:>10}  {:>10} {:>10}".format("SoC Calc;",
                    day, t_to_hrs(i * 30), round(batt_charge[i], 2), round(total_load, 2),
                    round(est_gen, 2), int(100 * batt_charge[i] / batt_max_charge)))

                plot_x.append(t_to_hrs((day*48 + i) * 30))  # Time
                plot_y1.append(int(100 * batt_charge[i]/batt_max_charge))  # Baseline SoC line
                plot_y3.append(100)  # Upper limit line
                plot_y4.append(stgs.GE.batt_reserve)  # Lower limit line

                i += 1

            max_charge_pcnt[day] = int(100 * max_charge / batt_max_charge)
            min_charge_pcnt[day] = int(100 * min_charge / batt_max_charge)

            day += 1

        # low_soc is the minimum SoC target. Provide more buffer capacity in shoulder months
        # when load is likely to be more variable, e.g. heating
        if stgs.pg.month in stgs.GE.shoulder:
            low_soc = int(stgs.GE.max_soc_target)
        else:
            low_soc = int(stgs.GE.min_soc_target)

        max_charge_pc = max_charge_pcnt[0]
        min_charge_pc = min_charge_pcnt[0]

        # We now have the four values of max & min charge for tomorrow & overmorrow
        # Check if overmorrow is better than tomorrow and there is opportunity to reduce target
        # to avoid residual charge at the end of the day in anticipation of a sunny day.
        # Reduce the target by implying that there will be more than forecast generation
        if max_charge_pcnt[1] > 100 and  max_charge_pcnt[0] < 100:
            logger.info("Overmorrow correction enabled")
            max_charge_pc += int((max_charge_pcnt[1] - 100) / 2)
        else:
            logger.info("Overmorrow correction not needed/enabled")

        # The really clever bit: reduce the target SoC to the greater of:
        #     The surplus above 100% for max_charge_pcnt
        #     The value needed to achieve the stated spare capacity at minimum charge point
        #     The preset minimum value
        tgt_soc = max(100 - max_charge_pc, (low_soc - min_charge_pc), low_soc)
        # Range check the resulting value
        tgt_soc = int(min(tgt_soc, 100))  # Limit range to 100%

        # Produce y2 = adjusted plot
        day = 0
        diff = tgt_soc
        while day < 2:
            i = 0
            while i < 48:
                if day == 1 and i == 0:
                    diff = plot_y2[48] - plot_y1[49]
                if plot_y1[day*48 + i + 1] + diff > 100:  # Correct for SoC > 100%
                    diff = 100 - plot_y1[day*48 + i + 1]  # Bugfix v1.1.0a
                plot_y2.append(plot_y1[day*48 + i + 1] + diff)
                i += 1
            day += 1

        # Store plot data
        self.plot[0] = str(plot_x)
        self.plot[1] = str(plot_y1)
        self.plot[2] = str(plot_y2)
        self.plot[3] = str(plot_y3)
        self.plot[4] = str(plot_y4)

        logger.debug("{:<25} {:>10} {:>10} {:>10} {:>10} {:>10}".format("SoC Calc Summary;",
            "Max Charge", "Min Charge", "Max %", "Min %", "Target SoC"))
        logger.debug("{:<25} {:>10} {:>10} {:>10} {:>10} {:>10}".format("SoC Calc Summary;",
            round(max_charge, 2), round(min_charge, 2),
            max_charge_pc, min_charge_pc, tgt_soc))
        logger.debug("{:<25} {:>10} {:>10} {:>10} {:>10} {:>10}".format("SoC (Adjusted);",
            round(max_charge, 2), round(min_charge, 2),
            max_charge_pc + tgt_soc, min_charge_pc + tgt_soc, "\n"))

        if commit:
            self.tgt_soc = tgt_soc
            return "set_soc"

        return "test"

# End of GivEnergyObj() class definition

class SolcastObj:
    """Stores daily Solcast data."""

    def __init__(self):
        # Skeleton solcast summary array
        self.pv_est10_day: [int] = [0] * 7
        self.pv_est50_day: [int] = [0] * 7
        self.pv_est90_day: [int] = [0] * 7

        self.pv_est10_30: [int] = [0] * 96
        self.pv_est50_30: [int] = [0] * 96
        self.pv_est90_30: [int] = [0] * 96

    def update(self):
        """Updates forecast generation from Solcast."""

        def get_solcast(url) -> Tuple[bool, str]:
            """Download latest Solcast forecast."""

            solcast_url = url + stgs.Solcast.cmd + "&api_key="+ stgs.Solcast.key
            try:
                resp = requests.get(solcast_url, timeout=5)
                resp.raise_for_status()
            except requests.exceptions.RequestException as error:
                logger.error(error)
                return False, ""
            if resp.status_code != 200:
                logger.error("Invalid response: "+ str(resp.status_code))
                return False, ""

            if len(resp.content) < 50:
                logger.warning("Warning: Solcast data missing/short")
                logger.warning(resp.content)
                return False, ""

            solcast_data = json.loads(resp.content.decode('utf-8'))
            logger.debug(str(solcast_data))

            return True, solcast_data
        #  End of get_solcast()

        # Download latest data for each array, abort if unsuccessful
        result, solcast_data_1 = get_solcast(stgs.Solcast.url_se)
        if not result:
            logger.warning("Error; Problem with Solcast data, using previous values (if any)")
            return

        if stgs.Solcast.url_sw != "":  # Two arrays are specified
            logger.debug("url_sw = '"+str(stgs.Solcast.url_sw)+"'")
            result, solcast_data_2 = get_solcast(stgs.Solcast.url_sw)
            if not result:
                logger.warning("Error; Problem with Solcast data, using previous values (if any)")
                return
        else:
            logger.debug("No second array")

        logger.info("Successful Solcast download.")

        # Combine forecast for PV arrays & align data with day boundaries
        pv_est10 = [0] * 10080
        pv_est50 = [0] * 10080
        pv_est90 = [0] * 10080

        if stgs.Solcast.url_sw != "":  # Two arrays are specified
            forecast_lines = min(len(solcast_data_1['forecasts']), \
                len(solcast_data_2['forecasts'])) - 1
        else:
            forecast_lines = len(solcast_data_1['forecasts']) - 1
        interval = int(solcast_data_1['forecasts'][0]['period'][2:4])
        solcast_offset = t_to_mins(solcast_data_1['forecasts'][0]['period_end'][11:16]) \
            - interval - 60

        # Check for BST and convert to local time to align with GivEnergy data
        if time.strftime("%z", time.localtime()) == "+0100":
            logger.debug("Applying BST offset to Solcast data")
            solcast_offset += 60

        i = solcast_offset
        cntr = 0
        while i < solcast_offset + forecast_lines * interval:
            try:
                pv_est10[i] = int(solcast_data_1['forecasts'][cntr]['pv_estimate10'] * 1000)
                pv_est50[i] = int(solcast_data_1['forecasts'][cntr]['pv_estimate'] * 1000)
                pv_est90[i] = int(solcast_data_1['forecasts'][cntr]['pv_estimate90'] * 1000)
            except Exception:
                logger.error("Error: Unexpected end of Solcast data (array #1). i="+ \
                    str(i)+ "cntr="+ str(cntr))
                break

            if i > 1 and i % interval == 0:
                cntr += 1
            i += 1

        if stgs.Solcast.url_sw != "":  # Two arrays are specified
            i = solcast_offset
            cntr = 0
            while i < solcast_offset + forecast_lines * interval:
                try:
                    pv_est10[i] += int(solcast_data_2['forecasts'][cntr]['pv_estimate10'] * 1000)
                    pv_est50[i] += int(solcast_data_2['forecasts'][cntr]['pv_estimate'] * 1000)
                    pv_est90[i] += int(solcast_data_2['forecasts'][cntr]['pv_estimate90'] * 1000)
                except Exception:
                    logger.error("Error: Unexpected end of Solcast data (array #2). i="+ \
                        str(i)+ "cntr="+ str(cntr))
                    break

                if i > 1 and i % interval == 0:
                    cntr += 1
                i += 1

        if solcast_offset > 720:  # Forget about current day as it's already afternoon
            offset = 1440 - 90
        else:
            offset = 0

        i = 0
        while i < 7:  # Summarise daily forecasts
            start = i * 1440 + offset + 1
            end = start + 1439
            self.pv_est10_day[i] = round(sum(pv_est10[start:end]) / 60000, 3)
            self.pv_est50_day[i] = round(sum(pv_est50[start:end]) / 60000, 3)
            self.pv_est90_day[i] = round(sum(pv_est90[start:end]) / 60000, 3)
            i += 1

        i = 0
        while i < 96:  # Calculate half-hourly generation
            start = i * 30 + offset + 1
            end = start + 29
            self.pv_est10_30[i] = round(sum(pv_est10[start:end])/60000, 3)
            self.pv_est50_30[i] = round(sum(pv_est50[start:end])/60000, 3)
            self.pv_est90_30[i] = round(sum(pv_est90[start:end])/60000, 3)
            i += 1

        timestamp = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        logger.debug("PV Estimate 10% (hrly, 7 days) / kWh; "+ timestamp+ "; "+
            str(self.pv_est10_30[0:47])+ str(self.pv_est10_day[0:6]))
        logger.debug("PV Estimate 50% (hrly, 7 days) / kWh; "+ timestamp+ "; "+
            str(self.pv_est50_30[0:47])+ str(self.pv_est50_day[0:6]))
        logger.debug("PV Estimate 90% (hrly, 7 days) / kWh; "+ timestamp+ "; "+
            str(self.pv_est90_30[0:47])+ str(self.pv_est90_day[0:6]))

# End of SolcastObj() class definition

def t_to_mins(time_in_hrs: str) -> int:
    """Convert times from HH:MM format to mins after midnight."""

    try:
        time_in_mins = 60 * int(time_in_hrs[0:2]) + int(time_in_hrs[3:5])
        return time_in_mins
    except Exception:
        return 0

#  End of t_to_mins()

def t_to_hrs(time_in: int) -> str:
    """Convert times from mins after midnight format to HH:MM."""

    try:
        hours = int(time_in // 60)
        mins = int(time_in - hours * 60)
        time_in_hrs = '{:02d}{}{:02d}'.format(hours, ":", mins)
        return time_in_hrs
    except Exception:
        return "00:00"

#  End of t_to_hrs()

# End of palm_utils
