import logging
from abc import ABC

from ..codec import PayloadDecoder
from .base import (
    BasePDU,
    ClientIncomingMessage,
    ClientOutgoingMessage,
)

_logger = logging.getLogger(__name__)


class TransparentMessage(BasePDU, ABC):
    """Root of the hierarchy for 2/Transparent PDUs."""

    function_code = 2
    transparent_function_code: int

    slave_address: int
    error: bool
    padding: int
    check: int

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.slave_address = kwargs.get("slave_address", 0x31)
        self.error = kwargs.get("error", False)
        self.padding = kwargs.get("padding", 0x08)  # this does seem significant
        self.check = kwargs.get("check", 0x0000)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _logger.debug(f"TransparentMessage.__init_subclass__({cls.__name__})")

    def __str__(self) -> str:
        def format_kv(key, val):
            if val is None:
                val = "?"
            elif key == "slave_address":
                # if val == 0x32:
                #     return None
                val = f"0x{val:02x}"
            elif key == "register_count" and val == 60:
                return None
            # elif key in ('check', 'padding'):
            #     val = f'0x{val:04x}'
            # elif key == 'raw_frame':
            #     return f'raw_frame={len(val)}b'
            elif key == "nulls":
                return f"nulls=[0]*{len(val)}"
            elif key in (
                "inverter_serial_number",
                "data_adapter_serial_number",
                "error",
                "check",
                "padding",
                "register_values",
                "raw_frame",
                "_builder",
            ):
                return None
            return f"{key}={val}"

        args = []
        if self.error:
            args += ["ERROR"]
        args += [format_kv(k, v) for k, v in vars(self).items()]

        return (
            f"{self.function_code}:{getattr(self, 'transparent_function_code', '_')}/"
            f"{self.__class__.__name__}({' '.join([a for a in args if a is not None])})"
        )

    def _encode_function_data(self):
        self._builder.add_64bit_uint(self.padding)
        self._builder.add_8bit_uint(self.slave_address)
        self._builder.add_8bit_uint(self.transparent_function_code)
        # self._update_check_code()

    @classmethod
    def decode_main_function(
        cls, decoder: PayloadDecoder, **attrs
    ) -> "TransparentMessage":
        attrs["data_adapter_serial_number"] = decoder.decode_string(10)
        attrs["padding"] = decoder.decode_64bit_uint()
        attrs["slave_address"] = decoder.decode_8bit_uint()
        transparent_function_code = decoder.decode_8bit_uint()
        if transparent_function_code > 135:
#         if transparent_function_code & 0x80:
            _logger.critical("Function code response was: "+str(transparent_function_code))
            error = True
            transparent_function_code &= 0x7F
        else:
            error = False
        attrs["error"] = error

        if issubclass(cls, TransparentResponse):
            attrs["inverter_serial_number"] = decoder.decode_string(10)

        decoder_class = cls.lookup_transparent_function_decoder(
            transparent_function_code
        )
        return decoder_class.decode_transparent_function(decoder, **attrs)

    @classmethod
    def lookup_transparent_function_decoder(
        cls, transparent_function_code: int
    ) -> type["TransparentMessage"]:
        raise NotImplementedError()

    @classmethod
    def decode_transparent_function(
        cls, decoder: PayloadDecoder, **attrs
    ) -> "TransparentMessage":
        raise NotImplementedError()

    def ensure_valid_state(self) -> None:  # flake8: D102
        """Sanity check our internal state."""
        # if self.padding != 0x8A:
        #     _logger.debug(f'Expected padding 0x8a, found 0x{self.padding:02x} instead')

    def _update_check_code(self) -> None:
        """Recalculate CRC of the PDU message."""
        raise NotImplementedError()

    def _extra_shape_hash_keys(self):
        return (self.slave_address,)


class TransparentRequest(TransparentMessage, ClientOutgoingMessage, ABC):
    """Root of the hierarchy for Transparent Request PDUs."""

    @classmethod
    def lookup_transparent_function_decoder(
        cls, transparent_function_code: int
    ) -> type["TransparentRequest"]:
        from .import (
            ReadMeterProductRegistersRequest,
            ReadHoldingRegistersRequest,
            ReadInputRegistersRequest,
            WriteHoldingRegisterRequest,
        )

        if transparent_function_code == 3:
            return ReadHoldingRegistersRequest
        elif transparent_function_code == 4:
            return ReadInputRegistersRequest
        elif transparent_function_code == 6:
            return WriteHoldingRegisterRequest
        elif transparent_function_code == 22:
            return ReadMeterProductRegistersRequest
        else:
            raise NotImplementedError(
                f"TransparentRequest function #{transparent_function_code} decoder"
            )

    def expected_response(self) -> "TransparentResponse":
        """Create a template of a correctly shaped Response expected for this Request."""
        raise NotImplementedError()


class TransparentResponse(TransparentMessage, ClientIncomingMessage, ABC):
    """Root of the hierarchy for Transparent Response PDUs."""

    inverter_serial_number: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._set_attribute_if_present("inverter_serial_number", **kwargs)

    def _encode_function_data(self):
        super()._encode_function_data()
        self._builder.add_string(self.inverter_serial_number, 10)

    @classmethod
    def lookup_transparent_function_decoder(
        cls, transparent_function_code: int
    ) -> type["TransparentResponse"]:
        from .import (
            NullResponse,
            ReadMeterProductRegistersResponse,
            ReadHoldingRegistersResponse,
            ReadInputRegistersResponse,
            WriteHoldingRegisterResponse,
        )

        if transparent_function_code == 0:
            return NullResponse
        elif transparent_function_code == 3:
            return ReadHoldingRegistersResponse
        elif transparent_function_code == 4:
            return ReadInputRegistersResponse
        elif transparent_function_code == 6:
            return WriteHoldingRegisterResponse
        elif transparent_function_code == 134:       #Accept as the broken Gen1 BPM response
            _logger.debug("Function code 86 recieved. Gracefully handled")
            return WriteHoldingRegisterResponse
        elif transparent_function_code == 22:        #This is meter product responses - currently unused
            return ReadMeterProductRegistersResponse
        else:
            raise NotImplementedError(
                f"TransparentResponse function #{transparent_function_code} decoder"
            )

    def _update_check_code(self):
        if hasattr(self, "check"):
            # Until we know how Responses' CRCs are calculated there's nothing we can do here; self.check stays 0x0000
            _logger.warning(
                "Unable to recalculate checksum, using whatever value was set"
            )
            self._builder.add_16bit_uint(self.check)


__all__ = ()
