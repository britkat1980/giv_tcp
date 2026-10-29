#!/usr/bin/env python3
"""PALM - PV Active Load Manager."""

import palm_settings as stgs
from palm_utils import GivEnergyObj, SolcastObj, t_to_mins
import time

# Debug switch (if True) is used to run palm_Soc outside the HA environment for test purpses
DEBUG_SW = False
if DEBUG_SW:
    import logging

else:
    from GivLUT import GivLUT, GivQueue  # pylint: disable=import-error

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
# This code sets overnight charge point, based on SolCast forecast & actual usage
#
###########################################

# Changelog:
# v0.8.3aSoC   28/Jul/22 Branch from palm - SoC only
# ...
# v0.10.0      21/Jun/23 Added multi-day averaging for usage calcs
# v1.0.0       28/Jul/23 Align with palm v1.0.0: 48-hour forecast, minor bugfixes
# v1.1.0       06/Aug/23 Split out generic functions as palm_utils.py

PALM_VERSION = "v1.1.0SoC"
# -*- coding: utf-8 -*-
# pylint: disable=logging-not-lazy


def GivTCP_write_soc(cmd: str):
    """Write SoC target directly to GivEnergy inverter. Fallback to API write"""

    # The write is queued for the read loop, which sends it on its own connection, as REST and MQTT commands are.
    # setChargeTarget() needs the read loop's device, so calling it from here always failed and PALM silently used
    # the cloud instead (#682)
    if cmd == "set_soc":  # Sets target SoC to value
        try:
            logger.info("Setting Charge Target to: "+ str(inverter.tgt_soc)+ "%")
            GivLUT.queue_write("setChargeTarget", {'chargeToPercent': inverter.tgt_soc})
        except Exception as e:
            logger.error("Couldn't queue the Charge Target write, so setting it through the GivEnergy cloud: "+type(e).__name__+": "+str(e))
            inverter.set_mode("set_soc")

    elif cmd == "set_soc_winter":  # Restore default overnight charge params
        try:
            logger.debug("Setting Charge Target to: 100%")
            GivLUT.queue_write("setChargeTarget", {'chargeToPercent': 100})
        except Exception as e:
            logger.error("Couldn't queue the Charge Target write, so setting it through the GivEnergy cloud: "+type(e).__name__+": "+str(e))
            inverter.set_mode("set_soc_winter")

    else:
        logger.critical("direct_write: Command not recognised")


if __name__ == '__main__':

    if DEBUG_SW:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("PALM")
    else:
        logger = GivLUT.logger

    # Set time variables
    stgs.pg.long_t_now: str = time.strftime("%d-%m-%Y %H:%M:%S %z", time.localtime())
    stgs.pg.month: str = stgs.pg.long_t_now[3:5]
    stgs.pg.t_now: str = stgs.pg.long_t_now[11:]
    stgs.pg.t_now_mins: int = t_to_mins(stgs.pg.t_now)

    logger.info("PALM... PV Automated Load Manager: "+ str(PALM_VERSION))
    logger.info("Timestamp: "+ str(stgs.pg.long_t_now))

    # Initialise inverter object (GivEnergy)
    inverter: GivEnergyObj = GivEnergyObj()

    # Initialise PV prediction object (Solcast)
    pv_forecast: SolcastObj = SolcastObj()
    PV_WEIGHT = stgs.Solcast.weight

    # Download inverter load history
    inverter.get_load_hist()

    # Download and parse PV forecast
    pv_forecast.update()

    # Compute target SoC and write directly to register in GivEnergy inverter
    logger.info("Forecast weighting: "+ str(PV_WEIGHT))
    GivTCP_write_soc(inverter.compute_tgt_soc(pv_forecast, PV_WEIGHT, True))

    # Send plot data to logfile in CSV format
    logger.debug("SoC Chart Data - Start. Paste these lines into a spreadsheet to create a plot of SoC")
    i = 0
    while i < 5:
        logger.debug(inverter.plot[i])
        i += 1
    logger.debug("SoC Chart Data - End")

# End of main
