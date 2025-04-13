# version 2023.08.07
"""
Settings file for use with palm.py: Compatible with v0.9, v0.10, v1.0.x and v1.1.x
"""
from settings import GiV_Settings
from GivLUT import GivLUT
import pickle
from os.path import exists
import os

class pg:
    """PALM global variable definitions. Used by palm_utils and project-specific wrappers"""

    test_mode: bool = False
    debug_mode: bool = False
    once_mode: bool = False
    long_t_now: str = ""
    month: str = ""
    t_now: str = ""
    t_now_mins: int = 0
    loop_counter: int = 0  # 1 minute minor frame. "0" = initialise
    pvo_tstamp: int = 0  # Records value of loop_counter when PV data last written
    palm_version: str = ""

# User settings for GivEnergy inverter API
class GE:
    enable = True
    # Modify url with system name in place of CExxxxxx and paste API key generated on GivEnergy web portal in place of xxxx
    url = "https://api.givenergy.cloud/v1/inverter/"+GiV_Settings.serial_number+"/"
#    key = str(os.getenv('GEAPI'))
    key = str(GiV_Settings.GE_API)
    
    # Most users will not need to touch that many of the pre-configured settings below
    
    # Disable SoC calculation in the winter months as consumption >> generation
    # winter = ["01", "02", "11", "12"]
#    winter = os.getenv('PALM_WINTER').split(',')
    winter = str(GiV_Settings.PALM_WINTER).split(',')

    # Throttle SoC calculation in shoulder months as consumption can vary with heating coming on, etc
    # shoulder = ["03", "04", "09", "10"]
#    shoulder = os.getenv('PALM_SHOULDER').split(',')
    shoulder = str(GiV_Settings.PALM_SHOULDER).split(',')

    # Lower limit for state of charge (summertime)
    #min_soc_target = 25
#    min_soc_target = int(os.getenv('PALM_MIN_SOC_TARGET'))
    min_soc_target = int(GiV_Settings.PALM_MIN_SOC_TARGET)

    # Lower limit for SoC limit in shoulder months
    #max_soc_target = 45
#    max_soc_target = int(os.getenv('PALM_MAX_SOC_TARGET'))
    max_soc_target = int(GiV_Settings.PALM_MAX_SOC_TARGET)

    # Battery reserve for power cuts (minmum of 4%)
    #batt_reserve = 4
#    batt_reserve = int(os.getenv('PALM_BATT_RESERVE'))
    batt_reserve = int(GiV_Settings.PALM_BATT_RESERVE)


    # Inverter charge/discharge rate in kW, INVERTER_MAX_BAT_RATE is in Watts
    #if exists(GivLUT.regcache):      # if there is a cache then grab it
    #    with GivLUT.cachelock:
    #        with open(GivLUT.regcache, 'rb') as inp:
    regCacheStack=GivLUT.get_regcache()
    if not regCacheStack == []:
        multi_output_old = regCacheStack[-1]
        charge_rate=float(multi_output_old[GiV_Settings.serial_number]['Invertor_Max_Bat_Rate'])/1000
        batt_capacity=float(multi_output_old[GiV_Settings.serial_number]['Battery_Capacity_kWh'])
    else:
        charge_rate=2.5
        # Nominal battery capacity
        batt_capacity = 10.4

    # Usable proportion of battery (100% less reserve and any charge limit)
    #batt_utilisation = 0.85
#    batt_utilisation = float(os.getenv('PALM_BATT_UTILISATION'))
    batt_utilisation = float(GiV_Settings.PALM_BATT_UTILISATION)

    batt_max_charge = batt_capacity * batt_utilisation

    # Default data for base load. Overwritten by actual data if available
    base_load = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.2, \
                 0.2, 0.2, 0.2, 0.3, 0.2, 0.2, 0.1, 0.3, 0.3, 0.2, 0.3, 0.8, 0.6, 0.3, 0.3, 0.2, \
                 0.2, 0.2, 0.2, 0.6, 0.6, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]

    # Load history is a weighted average of actual load from previous days.
    # Uncomment required settings or make your own using positive integers only. Examples:
    # Most recent day only
    load_hist_weight = [1] # Need to declare this even if using environment variables, just to instantiate the property
    # 3-day average
    # load_hist_weight = [1, 1, 1]
    # 7-day average
    # load_hist_weight = [1, 1, 1, 1, 1, 1, 1]
    # Same day last week - useful if, say, Monday is always wash-day
    # load_hist_weight = [0, 0, 0, 0, 0, 0, 1]
    # Weighted average (a more extreme example)
    # load_hist_weight = [4, 2, 2, 1, 1, 1, 1]

    # Pull in load history weighting from environment variables.
#    tmp_load_hist_weight = str(os.getenv('LOAD_HIST_WEIGHT'))
    tmp_load_hist_weight = str(GiV_Settings.LOAD_HIST_WEIGHT)
    load_hist_weight = [int(elem) for elem in tmp_load_hist_weight.split(',') if elem.strip().isnumeric()]

    # Start time for Overnight Charge
#    start_time = os.getenv('NIGHTRATESTART')
    start_time = GiV_Settings.night_rate_start

    # End time for Overnight Charge
#    end_time = os.getenv('DAYRATESTART')
    end_time = GiV_Settings.day_rate_start
    Command_list={}
    Command_list['data']=""


# SolCast PV forecast generator. Up to two arrays are supported with a forecast for each
class Solcast:
    def isBlank (myString):
        return not (myString and myString.strip())
    
    enable = True
#    key = str(os.getenv('SOLCASTAPI'))
#    url_se = "https://api.solcast.com.au/rooftop_sites/"+str(os.getenv('SOLCASTSITEID'))
    key = str(GiV_Settings.SOLCASTAPI)
    url_se = "https://api.solcast.com.au/rooftop_sites/"+str(GiV_Settings.SOLCASTSITEID)
    
    # For single array installation uncomment the line below and comment out the subsequent line
    #url_sw = ""
#    if not isBlank(str(os.getenv('SOLCASTSITEID2'))):
#        url_sw = "https://api.solcast.com.au/rooftop_sites/"+str(os.getenc('SOLCASTSITEID2'))   
    if not isBlank(str(GiV_Settings.SOLCASTSITEID2)):
        url_sw = "https://api.solcast.com.au/rooftop_sites/"+str(GiV_Settings.SOLCASTSITEID2)
    else:
        url_sw = ""

#    weight = int(os.getenv('PALM_WEIGHT'))  # Confidence factor for forecast (range 10 to 90)
    weight = int(GiV_Settings.PALM_WEIGHT)
 
    cmd = "/forecasts?format=json"

GE_Command_list = {
    "data": [
        {
            "id": 17,
            "name": "Enable AC Charge Upper % Limit",
            "validation": "Value must be either true or false"
        },
        {
            "id": 24,
            "name": "Enable Eco Mode",
            "validation": "Value must be either true or false"
        },
        {
            "id": 28,
            "name": "AC Charge 2 Start Time",
            "validation": "Value format should be HH:mm. Use correct time range for hour and minutes"
        },
        {
            "id": 29,
            "name": "AC Charge 2 End Time",
            "validation": "Value format should be HH:mm. Use correct time range for hour and minutes"
        },
        {
            "id": 41,
            "name": "DC Discharge 2 Start Time",
            "validation": "Value format should be HH:mm. Use correct time range for hour and minutes"
        },
        {
            "id": 42,
            "name": "DC Discharge 2 End Time",
            "validation": "Value format should be HH:mm. Use correct time range for hour and minutes"
        },
        {
            "id": 47,
            "name": "Inverter Max Output Active Power Percent",
            "validation": "Value must be between 0 and 100"
        },
        {
            "id": 53,
            "name": "DC Discharge 1 Start Time",
            "validation": "Value format should be HH:mm. Use correct time range for hour and minutes"
        },
        {
            "id": 54,
            "name": "DC Discharge 1 End Time",
            "validation": "Value format should be HH:mm. Use correct time range for hour and minutes"
        },
        {
            "id": 56,
            "name": "Enable DC Discharge",
            "validation": "Value must be either true or false"
        },
        {
            "id": 64,
            "name": "AC Charge 1 Start Time",
            "validation": "Value format should be HH:mm. Use correct time range for hour and minutes"
        },
        {
            "id": 65,
            "name": "AC Charge 1 End Time",
            "validation": "Value format should be HH:mm. Use correct time range for hour and minutes"
        },
        {
            "id": 66,
            "name": "AC Charge Enable",
            "validation": "Value must be either true or false"
        },
        {
            "id": 71,
            "name": "Battery Reserve % Limit",
            "validation": "Value must be between 4 and 100"
        },
        {
            "id": 72,
            "name": "Battery Charge Power",
            "validation": "Value must be between 0 and 3000"
        },
        {
            "id": 73,
            "name": "Battery Discharge Power",
            "validation": "Value must be between 0 and 3000"
        },
        {
            "id": 75,
            "name": "Battery Cutoff % Limit",
            "validation": "Value must be between 4 and 100"
        },
        {
            "id": 77,
            "name": "AC Charge Upper % Limit",
            "validation": "Value must be between 0 and 100"
        },
        {
            "id": 83,
            "name": "Restart Inverter",
            "validation": "Value can only be 100"
        },
        {
            "id": 258,
            "name": "Force Off Grid",
            "validation": "Value must be either true or false"
        }
    ]
}
