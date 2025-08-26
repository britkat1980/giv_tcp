# version 2022.01.31
from influxdb_client import InfluxDBClient, WriteApi, WriteOptions
import logging
from logging.handlers import TimedRotatingFileHandler
from settings import GiV_Settings

logger = logging.getLogger("GivTCP_Influx_"+str(GiV_Settings.givtcp_instance))
logging.basicConfig(format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
if GiV_Settings.Debug_File_Location!="":
    fh = TimedRotatingFileHandler(GiV_Settings.Debug_File_Location, when='D', interval=1, backupCount=7)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
if GiV_Settings.Log_Level.lower()=="debug":
    logger.setLevel(logging.DEBUG)
elif GiV_Settings.Log_Level.lower()=="info":
    logger.setLevel(logging.INFO)
elif GiV_Settings.Log_Level.lower()=="critical":
    logger.setLevel(logging.CRITICAL)
elif GiV_Settings.Log_Level.lower()=="warning":
    logger.setLevel(logging.WARNING)
else:
    logger.setLevel(logging.ERROR)


class GivInflux():

    def line_protocol(SN,readings):
        return '{},tagKey={} {}'.format(SN,'GivReal', readings)

    def make_influx_string(datastr):
        new_str=datastr.replace(" ","_")
        new_str=new_str.lower()
        return new_str

    def stringSafe(data):
        output=str(data)
        if isinstance(data,str):
            output="\""+str(data)+"\""
        return output

    def publish(SN,data):
        output_str=""
        power_output = data['Power']['Power']
        logging.debug("Creating Power string for InfluxDB")
        for key in power_output:
            if not power_output[key] == None:
                output_str=output_str+str(GivInflux.make_influx_string(key))+'='+GivInflux.stringSafe(power_output[key])+','
        flow_output = data['Power']['Flows']
        logging.debug("Creating Power Flow string for InfluxDB")
        for key in flow_output:
            if not flow_output[key] == None:
                output_str=output_str+str(GivInflux.make_influx_string(key))+'='+GivInflux.stringSafe(flow_output[key])+','
        energy_today = data['Energy']['Today']
        logging.debug("Creating Energy/Today string for InfluxDB")
        for key in energy_today:
            if not energy_today[key] == None:
                output_str=output_str+str(GivInflux.make_influx_string(key))+'='+GivInflux.stringSafe(energy_today[key])+','

        energy_total = data['Energy']['Total']
        logging.debug("Creating Energy/Total string for InfluxDB")
        for key in energy_total:
            if not energy_total[key] == None:
                output_str=output_str+str(GivInflux.make_influx_string(key))+'='+GivInflux.stringSafe(energy_total[key])+','

        logging.debug("Data sending to Influx is: "+ output_str[:-1])
        data1=GivInflux.line_protocol(SN,output_str[:-1])
        influxdb_debug = False
        if GiV_Settings.Log_Level.lower()=="debug":
            influxdb_debug = True
        _db_client = InfluxDBClient(url=GiV_Settings.influxURL, token=GiV_Settings.influxToken, org=GiV_Settings.influxOrg, debug=influxdb_debug)
        _write_api = _db_client.write_api(write_options=WriteOptions(batch_size=1))
        _write_api.write(bucket=GiV_Settings.influxBucket, record=data1)
        logging.info("Written to InfluxDB")

        _write_api.close()
        _db_client.close()
