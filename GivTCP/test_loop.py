import asyncio
from givenergy_modbus_async.client.client import Client, commands
from givenergy_modbus_async.model.plant import Plant
import sys, os, logging
from typing import Callable, Optional
import datetime

logger=logging.getLogger()

async def watch_plant(
        handler: Optional[Callable] = None,
        refresh_period: float = 15.0,
        full_refresh_period: float = 60,
        timeout: float = 3,
        retries: int = 5,
        passive: bool = False,
    ):
        totalTimeoutErrors=0
        """Refresh data about the Plant."""
        try:
            client=Client("192.168.2.4",8899)
            await client.connect()
            logger.critical("Detecting inverter characteristics...")
            await client.detect_plant()
            await client.refresh_plant(True, number_batteries=client.plant.number_batteries,meter_list=client.plant.meter_list)
            #await client.close()
            logger.debug ("Running full refresh")
            if handler:
                try:
                    handler(client.plant)
                except Exception:
                    e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
                    logger.error ("Error in calling handler: "+str(e))
        except Exception:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error ("Error in inital detect/refresh: "+str(e))
            await client.close()
            return
        
        # set last full_refresh time
        lastfulltime=datetime.datetime.now()
        lastruntime=datetime.datetime.now()
        timeoutErrors=0
        while True:
            try:
                timesincelast=datetime.datetime.now()-lastruntime
                if timesincelast.total_seconds() < refresh_period:
                    await asyncio.sleep(1)
                    #if refresh period hasn't expired then just keep looping back up to write check
                    continue
                if not passive:
                    #Check time since last full_refresh
                    timesincefull=datetime.datetime.now()-lastfulltime
                    if timesincefull.total_seconds() > full_refresh_period:      #always run full refresh for Gateway
                        fullRefresh=True
                        logger.debug ("Running full refresh")
                        lastfulltime=datetime.datetime.now()
                    else:
                        fullRefresh=False
                        logger.debug ("Running partial refresh")
                    try:
                        #await client.connect()
                        reqs = commands.refresh_plant_data(fullRefresh, client.plant.number_batteries, slave_addr=client.plant.slave_address,isHV=client.plant.isHV,additional_holding_registers=client.plant.additional_holding_registers,additional_input_registers=client.plant.additional_input_registers)
                        result= await client.execute(
                            reqs, timeout=timeout, retries=retries, return_exceptions=True
                        )
                        #await client.close()
                        hasTimeout=False
                        for res in result:
                            if isinstance(res,TimeoutError):
                                hasTimeout=True
                                logger.error("Timeout Error: "+str(res))
                                raise Exception(res)
                        timeoutErrors=0     # Reset timeouts if all is good this run
                        logger.debug("Data get was successful, now running handler if needed: ")
                        lastruntime=datetime.datetime.now()
                    except Exception:
                        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
                        totalTimeoutErrors=totalTimeoutErrors+1
                        # Publish the new total timeout errors
                    if handler:
                        try:
                            handler(client.plant)
                        except Exception:
                            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
                            logger.error ("Error in calling handler: "+str(e))
            except Exception:
                f=sys.exc_info()
                e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
                logger.error ("Error in Watch Loop: "+str(e))
                await client.close()

def savestats(plant: Plant):
    with open("D:/v3testdata.txt","a") as outp:
        outp.write(datetime.datetime.now().isoformat()+": Grid Power is: "+str(plant.inverter.p_grid_out)+str("\n"))


async def self_run():
    # re-run everytime watch_plant Dies
    while True:
        try:
            logger.info("Starting watch_plant loop...")
            await watch_plant(handler=savestats, refresh_period=15,full_refresh_period=120)
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error("Error in self_run. Re-running watch_plant: "+str(e))
            await asyncio.sleep(2)

def start():
    asyncio.run(self_run())

if __name__ == '__main__':
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])