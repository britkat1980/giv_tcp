# version 2023.05.30
# palm_settings.py file for use with palm.py and palm_soc.py
#
# IMPORTANT
# For palm_soc.py only enter parameters in the first part of the file and ignore the entries below the horizontal line
from settings import GiV_Settings
import os

# User settings for GivEnergy inverter API
class GE:
    enable = True
    # Modify url with system name in place of CExxxxxx and paste API key generated on GivEnergy web portal in place of xxxx
    url = "https://api.givenergy.cloud/v1/inverter/"+GiV_Settings.serial_number+"/"
    key = str(os.getenv('GEAPI'))
    
    # Most users will not need to touch that many of the pre-configured settings below
    
    # Disable SoC calculation in the winter months as consumption >> generation
    # winter = ["01", "02", "11", "12"]
    winter = os.getenv('PALM_WINTER').split(',')

    # Throttle SoC calculation in shoulder months as consumption can vary with heating coming on, etc
    # shoulder = ["03", "04", "09", "10"]
    shoulder = os.getenv('PALM_SHOULDER').split(',')

    # Lower limit for state of charge (summertime)
    #min_soc_target = 25
    min_soc_target = int(os.getenv('PALM_MIN_SOC_TARGET'))

    # Lower limit for SoC limit in shoulder months
    #max_soc_target = 45
    max_soc_target = int(os.getenv('PALM_MAX_SOC_TARGET'))

    # Battery reserve for power cuts (minmum of 4%)
    #batt_reserve = 4
    batt_reserve = int(os.getenv('PALM_BATT_RESERVE'))

    # Nominal battery capacity
    #batt_capacity = 10.4
    #batt_capacity = float(os.getenv('PALM_BATT_CAPACITY')) 

    # Usable proportion of battery (100% less reserve and any charge limit)
    #batt_utilisation = 0.85
    batt_utilisation = float(os.getenv('PALM_BATT_UTILISATION'))

    #batt_max_charge = batt_capacity * batt_utilisation

    # Inverter charge/discharge rate in kW
    #charge_rate = 2.5
    #charge_rate = float(os.getenv('PALM_CHARGE_RATE'))

    # Default data for base load. Overwritten by actual data if available
    base_load = [0.3, 2, 0.3, 0.3, 0.3, 0.5, 1.7, 1.8, 2.6, 1.5, 0.5, 2.5,\
        1.3, 1, 1.5, 0.5, 0.3, 1, 1.5, 1, 0.6, 0.5, 0.5, 0.3]

    # Start time for Overnight Charge
    start_time = os.getenv('NIGHTRATESTART')

    # End time for Overnight Charge
    end_time = os.getenv('DAYRATESTART')


# SolCast PV forecast generator. Up to two arrays are supported with a forecast for each
class Solcast:
    enable = True
    key = str(os.getenv('SOLCASTAPI'))
    url_se = "https://api.solcast.com.au/rooftop_sites/"+str(os.getenv('SOLCASTSITEID'))
    
    # For single array installation uncomment the line below and comment out the subsequent line
    #url_sw = ""
    if str(os.getenv('SOLCASTSITEID2')).strip() != "":
        url_sw = "https://api.solcast.com.au/rooftop_sites/"+str(os.getenv('SOLCASTSITEID2'))
    else:
        url_sw = ""

    weight = int(os.getenv('PALM_WEIGHT'))  # Confidence factor for forecast (range 10 to 90)

    cmd = "/forecasts?format=json"
