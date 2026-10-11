import logging
import asyncio
from GivTCP.findInvertor import findInvertor
from givenergy_modbus.client.client import Client
logger = logging.getLogger(__name__)

subnet="172.16.10.185"
invList={}
inverterStats={}

async def getInvDeets2(HOST):
    # As startup.getInvDeets, with givenergy-modbus v2: detect() resolves the model and the attached devices
    try:
        Stats={}
        client=Client(HOST,8899,3)
        await client.connect()
        caps=await client.detect()
        ident=client.plant.inverter
        SN=ident.serial_number
        model=caps.device_type
        fw=ident.arm_firmware_version
        # number_batteries only counts LV batteries; HV/three-phase/AIO batteries are modules
        numbats=max(len(caps.lv_battery_addresses), sum(n for _,n in caps.bcu_stacks), len(caps.aio_battery_module_addresses), len(caps.hv_bmu_addresses))
        try:
            await client.close()
        except Exception:
            pass
        Stats['Serial_Number']=SN
        Stats['Firmware']=fw
        Stats['Model']=model
        Stats['Number_of_Batteries']=numbats
        Stats['IP_Address']=HOST
        logger.info(f'Inverter {str(SN)} which is a {str(model.name.capitalize())} with {str(numbats)} batteries has been found at: {str(HOST)}')
        return Stats
    except Exception:
        logger.debug("Gathering inverter details for " + str(HOST) + " failed.")
        return None

list={}
count=0
while len(list)<=0:
    if count<2:
        logger.info("INV- Scanning network ("+str(count+1)+"):"+str(subnet))
        list=findInvertor(subnet)
        if len(list)>0: break
        count=count+1
    else:
        break
if list:
    logger.info(str(len(list))+" Inverters found on "+str(subnet)+" - "+str(list))
    invList.update(list)
    for inv in invList:
        deets={}
        logger.info("Getting inverter stats for: "+str(invList[inv]))
        count=0
        while not deets:
            if count<2:
                deets=asyncio.run(getInvDeets2(invList[inv]))
                #deets=getInvDeets2(invList[inv])
                if deets:
                    inverterStats[inv]=deets
                    logger.info(deets)
                #else:
                #    logger.error("Unable to interrogate inverter to get base details")
                count=count+1
            else:
                break
if len(invList)==0:
    logger.info("No inverters found...")
else:
    logger.info("inverters found...")