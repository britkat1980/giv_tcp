#########################################
#     network scan for GivEnergy devices #
#########################################

## Async TCP connect scan. Probes every host on every port in a single pass, with a bounded
## number of connections in flight, so an empty address only costs one timeout per port

import asyncio
import ipaddress
import logging
from time import perf_counter

logger = logging.getLogger()

INVERTER_PORT = 8899
EVC_PORT = 502
TIMEOUT = 0.75          # seconds per connect - WiFi dongles in power save can be slow to answer
MAX_CONCURRENCY = 512   # each probe to an empty address sends an ARP broadcast, keep this sane
MIN_PREFIX = 16         # never scan more than a /16 (65,536 addresses)

def _concurrency():
    # Keep well inside the open file limit (HA add-on containers can be as low as 1024)
    try:
        import resource
        soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        return max(32, min(MAX_CONCURRENCY, soft - 128))
    except Exception:
        return 256

async def _probe(ip, port, timeout):
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except (OSError, asyncio.TimeoutError):
        return False

async def _scan(targets, ports, timeout):
    found = {port: [] for port in ports}
    jobs = ((str(ip), port) for ip in targets for port in ports)   # lazy, no 131k task list

    async def worker():
        for ip, port in jobs:
            if await _probe(ip, port, timeout):
                found[port].append(ip)

    await asyncio.gather(*(worker() for _ in range(_concurrency())))
    for port in found:
        found[port].sort(key=ipaddress.IPv4Address)
    return found

def _targets(subnet):
    """Return (local /24 hosts, remaining hosts) for the subnet, capped at a /16 around the host"""
    iface = ipaddress.IPv4Interface(subnet)
    network = iface.network
    if network.prefixlen < MIN_PREFIX:
        logger.info("Network "+str(network)+" is larger than a /"+str(MIN_PREFIX)+", only scanning the /"+str(MIN_PREFIX)+" around this host")
        network = ipaddress.IPv4Interface(str(iface.ip)+"/"+str(MIN_PREFIX)).network
    if network.prefixlen >= 24:
        return list(network.hosts()), []
    local = ipaddress.IPv4Interface(str(iface.ip)+"/24").network
    rest = (ip for ip in network.hosts() if ip not in local)
    return list(local.hosts()), rest

def scan(subnet, ports=(INVERTER_PORT, EVC_PORT), timeout=TIMEOUT):
    """
    Scan subnet (e.g. "192.168.1.10/16") for hosts with any of the given TCP ports open.
    The host's own /24 is scanned first; the rest of a larger network is only scanned
    if no inverter (or, when not scanning for inverters, nothing at all) was found there.
    Returns {port: [ip, ...]}
    """
    start = perf_counter()
    local, rest = _targets(subnet)
    found = asyncio.run(_scan(local, ports, timeout))
    wanted = INVERTER_PORT if INVERTER_PORT in ports else None
    nothing = not found[wanted] if wanted else not any(found.values())
    if nothing and rest:
        logger.info("Nothing found on local /24, scanning the rest of "+str(subnet)+" (this may take a few minutes)...")
        more = asyncio.run(_scan(rest, ports, timeout))
        for port in ports:
            found[port].extend(more[port])
    logger.debug("Scan of "+str(subnet)+" took "+str(round(perf_counter()-start, 1))+"s - "+str(found))
    return found

def as_list(ips):
    # Legacy format used by the startup scripts: {1: ip, 2: ip, ...}
    return {i+1: ip for i, ip in enumerate(ips)}
