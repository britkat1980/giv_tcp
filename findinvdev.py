import logging
import asyncio
from GivTCP.findInvertor import findInvertor
from GivTCP.givenergy_modbus_async.client.client import Client
logger = logging.getLogger(__name__)

subnet="172.16.10.185"
invList={}
inverterStats={}

async def getInvDeets2(HOST):
    try:
        Stats={}
        client=Client(HOST,8899,3)
        await client.connect()
        await client.detect_plant(additional=False)
        
        SN= client.plant.inverter.serial_number
        #logger.debug("Deets retrieved from found Inverter are: "+str(stats))
        #SN=stats[2]
        gen=client.plant.inverter.generation
        model=client.plant.inverter.model
        fw=client.plant.inverter.arm_firmware_version
        numbats=client.plant.number_batteries
        Stats['Serial_Number']=SN
        Stats['Firmware']=fw
        Stats['Model']=model
        Stats['Generation']=gen
        Stats['Number_of_Batteries']=numbats
        Stats['IP_Address']=HOST
        logger.info(f'Inverter {str(SN)} which is a {str(gen.name.capitalize())} - {str(model.name.capitalize())} with {str(numbats)} batteries has been found at: {str(HOST)}')
        return Stats
    except:
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