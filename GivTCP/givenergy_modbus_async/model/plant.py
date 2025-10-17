
import logging

from .battery import Battery
from .hvbcu import BCU
from .hvbmu import BMU
from .ems import EMS
from .gateway import Gateway
from .threephase import ThreePhaseInverter
from .meter import Meter, MeterProduct
from .inverter import Inverter
from .register import Model
from .register import HR, IR
from .register_cache import (
    RegisterCache,
)
from ..pdu import (
    ClientIncomingMessage,
    NullResponse,
    ReadHoldingRegistersResponse,
    ReadInputRegistersResponse,
    TransparentResponse,
    WriteHoldingRegisterResponse,
)

_logger = logging.getLogger(__name__)


class Plant:
    """Representation of a complete GivEnergy plant."""

    register_caches: dict[int, RegisterCache] = {}
    additional_holding_registers: list[int] = []
    additional_input_registers: list[int] = []
    inverter_serial_number: str = ""
    data_adapter_serial_number: str = ""
    number_batteries: int = 0
    meter_list: list[int] = [1]
    number_bcus: int = 0
    bcu_list: list[tuple] = []
    slave_address: int = 0x31
    isHV: bool = True
    device_type: Model

    def __init__(self) -> None:
        if not self.register_caches:
            self.register_caches = {self.slave_address: RegisterCache()}

    def update(self, pdu: ClientIncomingMessage):
        """Update the Plant state from a PDU message."""
        if not isinstance(pdu, TransparentResponse):
            _logger.debug(f"Ignoring non-Transparent response {pdu}")
            return
        if isinstance(pdu, NullResponse):
            _logger.debug(f"Ignoring Null response {pdu}")
            return
        if pdu.error:
            _logger.debug(f"Ignoring error response {pdu}")
            return
        _logger.debug(f"Handling {pdu}")

        if pdu.slave_address in (0x11, 0x00):
            # rewrite cloud and mobile app responses to "normal" inverter address
            slave_address = self.slave_address
        else:
            slave_address = pdu.slave_address

        if slave_address not in self.register_caches:
            _logger.debug(
                f"First time encountering slave address 0x{slave_address:02x}"
            )
            self.register_caches[slave_address] = RegisterCache()

        self.inverter_serial_number = pdu.inverter_serial_number
        self.data_adapter_serial_number = pdu.data_adapter_serial_number

        if isinstance(pdu, ReadHoldingRegistersResponse):
            self.register_caches[slave_address].update(
                {HR(k): v for k, v in pdu.to_dict().items()}
            )
            self.register_caches[slave_address]['serial_number']=pdu.inverter_serial_number
        elif isinstance(pdu, ReadInputRegistersResponse):
            self.register_caches[slave_address].update(
                {IR(k): v for k, v in pdu.to_dict().items()}
            )
            self.register_caches[slave_address]['serial_number']=pdu.inverter_serial_number
        elif isinstance(pdu, WriteHoldingRegisterResponse):
            if pdu.register == 0:
                _logger.warning(f"Ignoring, likely corrupt: {pdu}")
            else:
                self.register_caches[slave_address].update(
                    {HR(pdu.register): pdu.value}
                )
                self.register_caches[slave_address]['serial_number']=pdu.inverter_serial_number

    def detect_batteries(self) -> None:
        """Determine the number of batteries based on whether the register data is valid.

        Since we attempt to decode register data in the process, it's possible for an
        exception to be raised.
        """
        if self.inverter.model in [Model.EMS, Model.GATEWAY, Model.PV]:
            self.number_batteries=0
            return
        if self.isHV:
            self.number_batteries=0
            for bcu in self.bcu_list:
                self.number_batteries+=bcu[1]
                #self.number_batteries=BCU(self.register_caches[0x70]).get('number_of_module')
        else:
            i = 0
            for i in range(6):
                try:
                    assert Battery(self.register_caches[i + 0x32]).is_valid()
                except (KeyError, AssertionError):
                    break
            self.number_batteries = i

    def detect_meters(self) -> None:
        """Determine the number of meters based on whether the register data is valid.

        Since we attempt to decode register data in the process, it's possible for an
        exception to be raised.
        """
        # Do a LUT test first to speed things up
        meter_list=[]
        i = 1
        for i in range(8):
            try:
                assert Meter(self.register_caches[i + 0x01]).is_valid()
                meter_list.append(i+1)
            except (KeyError, AssertionError):
                continue
        self.meter_list = meter_list


    @property
    def inverter(self) -> Inverter:     #Would an AIO Class make sense here?
        """Return Inverter model for the Plant."""
        if hex(self.register_caches[self.slave_address][HR(0)])[2:3]=="4":
            return ThreePhaseInverter(self.register_caches[self.slave_address])
        elif hex(self.register_caches[self.slave_address][HR(0)])[2:3] in ("2","3","8"):
            return Inverter(self.register_caches[self.slave_address])
    
#    @property
#    def threephaseinverter(self) -> Inverter:
#        """Return 3ph Inverter model for the Plant."""
#        return ThreePhaseInverter(self.register_caches[self.slave_address])
    
    @property
    def ems(self) -> EMS:
        """Return EMS model for the Plant."""
        if hex(self.register_caches[self.slave_address][HR(0)])[2:3]=="5":
            return EMS(self.register_caches[self.slave_address])
    
    @property
    def gateway(self) -> Gateway:
        """Return Gateway model for the Plant."""
        if hex(self.register_caches[self.slave_address][HR(0)])[2:3]=="7":
            return Gateway(self.register_caches[self.slave_address])

    @property
    def HVStack(self) -> list:
        stacks=[]
        if self.isHV:
            for bcu in self.bcu_list:
                stack=[]
                stack.append(BCU(self.register_caches[bcu[0] + 0x70]))
                bmus=[]
                for bmu in range(bcu[1]):
                    bmus.append(BMU(self.register_caches[bmu + 0x50],bcu[0]))
                stack.append(bmus)
                stacks.append(stack)
        return stacks

    @property
    def batteries(self) -> list[Battery]:
        """Return LV Battery models for the Plant."""
        if not self.isHV:
            return [
                Battery(self.register_caches[i + 0x32])
                for i in range(self.number_batteries)
            ]
        
    @property
    def meters(self) -> dict[Meter]:
        """Return Meter models for the Plant."""
        temp={}
        for i in self.meter_list:
            if i in self.register_caches:
                temp[i]=Meter(self.register_caches[i + 0x00])
        return temp
    
    @property
    def meterproduct(self) -> list[Meter]:
        """Return Meter models for the Plant."""
        temp=[]
        for i in self.meter_list:
            if i in self.register_caches:
                temp[i]=MeterProduct(self.register_caches[i + 0x01])
        return temp