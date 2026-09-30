#########################################
#            modbus find EVCs           #
#########################################

## Finds hosts with the EVC modbus port (502) open. See netscan.py

import sys
import logging
try:
    from GivTCP.netscan import scan, as_list, EVC_PORT
except ImportError:
    from netscan import scan, as_list, EVC_PORT
logger=logging.getLogger()

def findEVC(subnet):
    evclist = as_list(scan(subnet, ports=(EVC_PORT,))[EVC_PORT])
    logger.debug("evcList (inside): "+str(evclist))
    return evclist

def start():
    result=findEVC("192.168.3.83/24")
    print("EVC List: "+str(result))

if __name__ == '__main__':
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])
