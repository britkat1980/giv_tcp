import asyncio
import logging
import socket
from asyncio import Future, Queue, StreamReader, StreamWriter, Task
from typing import Callable, Dict, List, Optional, Tuple

from . import commands
from ..exceptions import (
    CommunicationError,
    ExceptionBase,
)
from ..framer import (
    ClientFramer,
    Framer,
)
from ..model.plant import Plant
from ..pdu import (
    HeartbeatRequest,
    TransparentRequest,
    TransparentResponse,
    WriteHoldingRegisterResponse,
)

_logger = logging.getLogger(__name__)


class Client:
    """Asynchronous client utilising long-lived connections to a network device."""

    framer: Framer
    expected_responses: "Dict[int, Future[TransparentResponse]]" = {}
    plant: Plant
    # refresh_count: int = 0
    # debug_frames: Dict[str, Queue]
    connected = False
    reader: StreamReader
    writer: StreamWriter
    network_consumer_task: Task
    network_producer_task: Task

    tx_queue: "Queue[Tuple[bytes, Optional[Future]]]"

    def __init__(self, host: str, port: int, connect_timeout: float = 2.0) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.framer = ClientFramer()
        self.plant = Plant()
        self.tx_queue = Queue(maxsize=20)
        # self.debug_frames = {
        #     'all': Queue(maxsize=1000),
        #     'error': Queue(maxsize=1000),
        # }

    async def connect(self) -> None:
        """Connect to the remote host and start background tasks."""
        try:
            connection = asyncio.open_connection(
                host=self.host, port=self.port, flags=socket.TCP_NODELAY
            )
            self.reader, self.writer = await asyncio.wait_for(
                connection, timeout=self.connect_timeout
            )
        except OSError as e:
            raise CommunicationError(
                f"Error connecting to {self.host}:{self.port}"
            ) from e
        self.network_consumer_task = asyncio.create_task(
            self._task_network_consumer(), name="network_consumer"
        )
        self.network_producer_task = asyncio.create_task(
            self._task_network_producer(), name="network_producer"
        )
        # asyncio.create_task(self._task_dump_queues_to_files(), name='dump_queues_to_files'),
        self.connected = True
        _logger.info("Connection established to %s:%d", self.host, self.port)

    async def close(self) -> None:
        """Disconnect from the remote host and clean up tasks and queues."""
        if not self.connected:
            return

        _logger.debug("Disconnecting and cleaning up")

        self.connected = False

        if self.tx_queue:
            while not self.tx_queue.empty():
                _, future = self.tx_queue.get_nowait()
                if future:
                    future.cancel()

        if self.network_producer_task:
            self.network_producer_task.cancel()

        if hasattr(self, "writer") and self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            del self.writer

        if self.network_producer_task:
            self.network_consumer_task.cancel()

        if hasattr(self, "reader") and self.reader:
            self.reader.feed_eof()
            self.reader.set_exception(RuntimeError("cancelling"))
            del self.reader

        self.expected_responses = {}
        # self.debug_frames = {
        #     'all': Queue(maxsize=1000),
        #     'error': Queue(maxsize=1000),
        # }

    async def refresh_plant(
        self,
        full_refresh: bool = True,
        number_batteries: int = 0,
        meter_list: list[int] = [],
        bcu_list: list[tuple]=[],
        timeout: float = 3,
        retries: int = 5,
        return_exceptions: bool = False,
    ) -> Plant:
        """Refresh data about the Plant."""

        reqs = commands.refresh_plant_data(
            full_refresh, number_batteries, isHV=self.plant.isHV, 
            additional_holding_registers=self.plant.additional_holding_registers,
            additional_input_registers=self.plant.additional_input_registers, 
            slave_addr=self.plant.slave_address,meter_list=meter_list,bcu_list=bcu_list
        )
        await self.execute(reqs, timeout=timeout, retries=retries, return_exceptions=return_exceptions)
        return self.plant

    async def watch_plant(
        self,
        handler: Optional[Callable] = None,
        refresh_period: float = 15.0,
        max_batteries: int = 5,
        timeout: float = 1.0,
        retries: int = 0,
        passive: bool = False,
    ):
        """Refresh data about the Plant."""
        await self.connect()
        await self.refresh_plant(True, max_batteries=max_batteries)
        self.plant.detect_batteries()
        while True:
            if handler:
                handler(self.plant)
            await asyncio.sleep(refresh_period)
            if not passive:
                reqs = commands.refresh_plant_data(False, self.plant.number_batteries)
                await self.execute(
                    reqs, timeout=timeout, retries=retries, return_exceptions=True
                )

    async def get_bcus(self) -> None:
        """Determine the number of BCUs available in a device by getting BAMS data.
        """
        from ..model.register import IR
        from ..pdu import ReadInputRegistersRequest
        
        # Get BAM data at 0xA0
        self.plant.bcu_list=[]      #reset to no bcus at start of discovery
        req=[]
        req.append(
            ReadInputRegistersRequest(
                base_register=60, register_count=5, slave_address=0xA0
            ))
        await self.execute(req,timeout=2, retries=3, return_exceptions=True)
        self.plant.number_bcus = self.plant.register_caches[0xA0][IR(61)]
        req=[]
        for bcu_num in range(self.plant.number_bcus):
            req.append(
            ReadInputRegistersRequest(
                base_register=60, register_count=60, slave_address=0x70+bcu_num
            ))
        await self.execute(req,timeout=2, retries=3, return_exceptions=True)
        for bcu_num in range(self.plant.number_bcus):
            val=self.plant.register_caches[0x70+bcu_num][IR(64)]
            self.plant.bcu_list.append([bcu_num,val])

    async def detect_plant(
        self,
        timeout: int = 3,
        retries: int = 10,
        additional: bool=True) -> None:
        """Detect inverter capabilities that influence how subsequent 
        requests are made."""

        _logger.info("Detecting plant")
        from ..model.register import Model
        # Refresh the core set of registers that work across all inverters
        #await self.refresh_plant(True, timeout=timeout, retries=retries)
        
        #Force 0x11 slave address only during detect
        self.plant.slave_address=0x11
        self.plant.isHV = False
        
        await self.refresh_plant(True, number_batteries=0, retries=retries, timeout=timeout)

        _logger.info("Plant Detected")

############ Check what other devices need 0x11 ###############
        #find model depending on device type
        if not self.plant.inverter == None:
            self.plant.device_type=self.plant.inverter.model
            
        elif not self.plant.gateway == None:
            self.plant.device_type=self.plant.gateway.model
        elif not self.plant.ems == None:
            self.plant.device_type=self.plant.ems.model

        if self.plant.device_type in (Model.ALL_IN_ONE, Model.AC_3PH, Model.HYBRID_3PH):
            self.plant.isHV = True
            meter_list=[1,2,3,4,5,6,7,8]
        else:
            self.plant.isHV= False
            meter_list=[]

        #### Set whether a device has batteries and then count them if they are allowed ####
        if self.plant.device_type in (Model.EMS,Model.GATEWAY):
            self.plant.number_batteries=0
        else:
            if self.plant.device_type in (Model.AC, Model.HYBRID):
                self.plant.slave_address = 0x31
            #### Determine how many BCUs and then define the battery locations to look for, then set plant.number_bcus ####
            if self.plant.isHV:
                await self.get_bcus()
            
            #### Get max num of batteries for each BCU then test if they are valid ####
            await self.refresh_plant(True, number_batteries=6, meter_list=meter_list, bcu_list=self.plant.bcu_list, retries=retries, timeout=timeout, return_exceptions=True) #set return exceptions to true to allow meters to not be found
            self.plant.detect_batteries()
            self.plant.detect_meters()
        
            # Use that to detect the number of batteries
        _logger.debug("Batteries detected: %d", self.plant.number_batteries)
        _logger.debug("Meters detected: %d", len(self.plant.meter_list))
        _logger.debug("Slave address in use: "+ str(self.plant.slave_address))

        #Get Meter Product Info


        # Some devices support additional registers
        # When unsupported, devices appear to simple ignore requests
        
############ What register sets should we look for????
        if additional:

            # Set additional registers based on model
            additional_registers=Model.add_regs(self.plant.device_type.value)
            possible_additional_input_registers=additional_registers[0]
            possible_additional_holding_registers=additional_registers[1]

            #possible_additional_input_registers = [2040]
            for ir in possible_additional_input_registers:
                try:
                    reqs = commands.refresh_additional_input_registers(ir,self.plant.slave_address)
                    await self.execute(reqs, timeout=timeout, retries=3)
                    _logger.info(
                        "Detected additional input register support (base_register=%d)",
                        ir,
                    )
                    self.plant.additional_input_registers.append(ir)
                except asyncio.TimeoutError:
                    _logger.debug(
                        "Inverter did not respond to input register query (base_register=%d)",
                        ir,
                    )
            _logger.info("Additional Input Registers: "+str(self.plant.additional_input_registers))


            #possible_additional_holding_registers = [180, 240, 300, 360, 2040]
            for hr in possible_additional_holding_registers:
                try:
                    if hr == 2040:      #For EMS there are only 36 regs in the 2040 block
                        reqs = commands.refresh_additional_holding_registers(hr,self.plant.slave_address,36)
                    else:
                        reqs = commands.refresh_additional_holding_registers(hr,self.plant.slave_address)
                    await self.execute(reqs, timeout=timeout, retries=3)
                    _logger.info(
                        "Detected additional holding register support (base_register=%d)",
                        hr,
                    )
                    self.plant.additional_holding_registers.append(hr)
                except asyncio.TimeoutError:
                    _logger.debug(
                        "Inverter did not respond to holding register query (base_register=%d)",
                        hr,
                    )
            _logger.info("Additional Holding Registers: "+str(self.plant.additional_holding_registers))

    async def one_shot_command(
        self, requests: list[TransparentRequest], timeout=1.5, retries=0
    ) -> None:
        """Run a single set of requests and return."""
        await self.connect()
        await self.execute(requests, timeout=timeout, retries=retries)


    # The i/o activity is co-ordinated by two background tasks:
    # - the consumer reads from the socket, responds to heartbeat requests,
    #   and sends register updates to the plant
    # - the producer takes requests from tx_queue and writes them to the socket
    #
    # In detail:
    #  the application task calls client.send_request_and_await_response()
    #  - this constructs a couple of 'future' objects, which are used for signalling
    #  - it constructs an object to represent the expected response, and
    #    adds it to the expected_responses dict with one of the futures
    #  - it then adds the request to tx_queue, with the other future, and awaits that future
    #  - when the producer has written the request to the socket, it marks the future as complete
    #  - this reawakens the application task.
    #
    #  the application now waits for the future attached to the expected response, with a timeout
    #  - if the response arrives, the consumer worker receives it and signals the future
    #  the application then retries on timeout, or is done.
    #
    #  Entries don't seem to be removed from expected_responses dict.
    #  Instead, when an entry is reused for a new request, if the existing
    #  future was not signalled, it gets cancelled.
    #
    #  client.execute() takes an array of requests, and creates one coroutine per request, to run
    #  send_request_and_await_response in parallel. They happen in random order ?


    async def _task_network_consumer(self):
        """Task for orchestrating incoming data."""
        try:
            while hasattr(self, "reader") and self.reader and not self.reader.at_eof():
                frame = await self.reader.read(300)
                # await self.debug_frames['all'].put(frame)
                for message in self.framer.decode(frame):
                    _logger.debug("Processing %s", message)
                    if isinstance(message, ExceptionBase):
                        _logger.warning(
                            "Expected response never arrived but resulted in exception: %s",
                            message,
                        )
                        continue
                    if isinstance(message, HeartbeatRequest):
                        _logger.debug("Responding to HeartbeatRequest")
                        await self.tx_queue.put(
                            (message.expected_response().encode(), None)
                        )
                        continue
                    if not isinstance(message, TransparentResponse):
                        _logger.warning(
                            "Received unexpected message type for a client: %s", message
                        )
                        continue
                    if isinstance(message, WriteHoldingRegisterResponse):
                        if message.error:
                            _logger.warning("%s", message)
                        else:
                            _logger.info("%s", message)

                    future = self.expected_responses.get(message.shape_hash())

                    if future and not future.done():
                        future.set_result(message)
                    # try:
                    self.plant.update(message)
                    # except RegisterCacheUpdateFailed as e:
                    #     # await self.debug_frames['error'].put(frame)
                    #     _logger.debug(f'Ignoring {message}: {e}')
            _logger.debug(
                "network_consumer reader at EOF, cannot continue, closing connection"
            )
        except Exception as e:
             _logger.error(
                "network_consumer reader exception {}", e
            )
        finally:
            await self.close()

    async def _task_network_producer(self, tx_message_wait: float = 0.25):
        """Producer loop to transmit queued frames with an appropriate delay."""
        while hasattr(self, "writer") and self.writer and not self.writer.is_closing():
            message, future = await self.tx_queue.get()
            self.writer.write(message)
            await self.writer.drain()
            self.tx_queue.task_done()
            if future:
                future.set_result(True)
            await asyncio.sleep(tx_message_wait)
        _logger.debug(
            "network_producer writer is closing, cannot continue, closing connection"
        )
        await self.close()

    # async def _task_dump_queues_to_files(self):
    #     """Task to periodically dump debug message frames to disk for debugging."""
    #     while True:
    #         await asyncio.sleep(30)
    #         if self.debug_frames:
    #             os.makedirs('debug', exist_ok=True)
    #             for name, queue in self.debug_frames.items():
    #                 if not queue.empty():
    #                     async with aiofiles.open(f'{os.path.join("debug", name)}_frames.txt', mode='a') as str_file:
    #                         await str_file.write(f'# {arrow.utcnow().timestamp()}\n')
    #                         while not queue.empty():
    #                             item = await queue.get()
    #                             await str_file.write(item.hex() + '\n')

    def execute(
        self,
        requests: list[TransparentRequest],
        timeout: float,
        retries: int,
        return_exceptions: bool = False,
    ) -> "Future[List[TransparentResponse]]":
        """Helper to perform multiple requests in parallel."""
        return asyncio.gather(
            *[
                self.send_request_and_await_response(
                    m, timeout=timeout, retries=retries
                )
                for m in requests
            ],
            return_exceptions=return_exceptions,
        )

    async def send_request_and_await_response(
        self, request: TransparentRequest, timeout: float, retries: int
    ) -> TransparentResponse:
        """Send a request to the remote, await and return the response."""
        raw_frame = request.encode()

        # mark the expected response
        expected_response = request.expected_response()
        expected_shape_hash = expected_response.shape_hash()

        tries = 0
        while tries <= retries:
            tries += 1
            existing_response_future = self.expected_responses.get(expected_shape_hash)
            if existing_response_future and not existing_response_future.done():
                _logger.debug(
                    "Cancelling existing in-flight request and replacing: %s", request
                )
                existing_response_future.cancel()
            response_future: Future[
                TransparentResponse
            ] = asyncio.get_event_loop().create_future()
            self.expected_responses[expected_shape_hash] = response_future

            frame_sent = asyncio.get_event_loop().create_future()
            await self.tx_queue.put((raw_frame, frame_sent))
            await asyncio.wait_for(
                frame_sent, timeout=self.tx_queue.qsize() + 1
            )  # this should only happen if the producer task is stuck

            _logger.debug("Request sent (attempt %d): %s", tries, request)

            try:
                await asyncio.wait_for(response_future, timeout=timeout)
                if response_future.done():
                    response = response_future.result()
                    if tries > 1:
                        _logger.debug("Received %s after %d attempts", response, tries)
                    if response.error:
                        _logger.error("Received error response, retrying: %s", response)
                    else:
                        return response
            except asyncio.TimeoutError:
                await asyncio.sleep(0.5)
                pass

            if tries <= retries:
                _logger.debug(
                    "Timeout awaiting %s, attempting retry %d of %d",
                    expected_response,
                    tries,
                    retries,
                )

        _logger.debug(
            "Timeout awaiting %s after %d tries at %ds, giving up",
            expected_response,
            tries,
            timeout,
        )
        raise asyncio.TimeoutError()
