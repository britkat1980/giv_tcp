#########################################
#         modbus find inverters         #
#########################################

## Finds hosts with the inverter modbus port (8899) open. See netscan.py

import sys
try:
    from GivTCP.netscan import scan, as_list, INVERTER_PORT
except ImportError:
    from netscan import scan, as_list, INVERTER_PORT

def findInvertor(subnet):
    return as_list(scan(subnet, ports=(INVERTER_PORT,))[INVERTER_PORT])

if __name__ == '__main__':
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])
