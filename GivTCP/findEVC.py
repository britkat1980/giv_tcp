#########################################
#         modbus find inverters         #
#   ver 3.0.1 enable/disable modbus     #
#   call                                #
#########################################

## Create a modbus call which connects, gets SN, DTC and FW to determine what type it is


from threading import Thread, Lock
import ipaddress
from time import perf_counter
from time import sleep
import sys
import socket
import logging
logger=logging.getLogger()
class Threader:
    """
    This is a class that calls a list of functions in a limited number of
    threads. It uses locks to make sure the data is thread safe.
    This class also provides a lock called: `<Threader>.print_lock`
    """
    def __init__(self, threads=30):
        self.thread_lock = Lock()
        self.functions_lock = Lock()
        self.functions = []
        self.threads = []
        self.nthreads = threads
        self.running = True
        self.print_lock = Lock()

    def stop(self) -> None:
        # Signal all worker threads to stop
        self.running = False

    def append(self, function, *args) -> None:
        # Add the function to a list of functions to be run
        self.functions.append((function, args))

    def start(self) -> None:
        # Create a limited number of threads
        for i in range(self.nthreads):
            thread = Thread(target=self.worker, daemon=True)
            # We need to pass in `thread` as a parameter so we
            # have to use `<threading.Thread>._args` like this:
            thread._args = (thread, )
            self.threads.append(thread)
            thread.start()

    def join(self) -> None:
        # Joins the threads one by one until all of them are done.
        for thread in self.threads:
            thread.join()

    def worker(self, thread:Thread) -> None:
        # While we are running and there are functions to call:
        while self.running and (len(self.functions) > 0):
            # Get a function
            with self.functions_lock:
                function, args = self.functions.pop(0)
            # Call that function
            function(*args)

        # Remove the thread from the list of threads.
        # This may cause issues if the user calls `<Threader>.join()`
        # But I haven't seen this problem while testing/using it.
        with self.thread_lock:
            self.threads.remove(thread)

def findEVC(subnet):
    network = ipaddress.IPv4Network(subnet, strict=False)
    PORT = 502
    start = perf_counter()
    # I didn't need a timeout of 1 so I used 0.1
    socket.setdefaulttimeout(0.1)

    error_dict = {}
    invlist = {}
    def connect(hostname, port):
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex((hostname, port))
        with threader.print_lock:
            if result == 0:
                invlist[len(invlist)+1]=hostname       

    # add more or less threads to complete your scan
    threader = Threader(20)
    for ip in network.hosts():
        threader.append(connect, str(ip), PORT)
    threader.start()
    threader.join()
    logger.debug("evcList (inside): "+str(invlist))
    return(invlist)

def start():
    findEVC("192.168.2.83/24")

if __name__ == '__main__':
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])
