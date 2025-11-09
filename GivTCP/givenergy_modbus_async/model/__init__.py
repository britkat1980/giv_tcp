"""
The data model that represents a GivEnergy system.

From a modbus perspective, devices present themselves as collections
of 16-bit numbered registers. An instance of *Plant* is used to cache
the values of these registers for the various devices (inverter and
batteries) making up your system.

Then from the plant you can access an Inverter and an array of Battery
instances - these interpret the low-level modbus registers as higher-level
python datatypes.

Note that the model package provides read-only access to the state of
the system.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import IntEnum
from typing import TYPE_CHECKING
import json

if TYPE_CHECKING:
    from .register_cache import (
        RegisterCache,
    )


class DefaultUnknownIntEnum(IntEnum):
    """Enum that returns unknown instead of blowing up."""

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN  # type: ignore[attr-defined] # must be defined in subclasses because of Enum limits


@dataclass
class TimeSlot:
    """Dataclass to represent a time slot, with a start and end time."""

    start: time
    end: time

    @classmethod
    def from_components(
        cls, start_hour: int, start_minute: int, end_hour: int, end_minute: int
    ):
        """Shorthand for the individual datetime.time constructors."""
        return cls(time(start_hour, start_minute), time(end_hour, end_minute))

    @classmethod
    def from_repr(cls, start: int | str, end: int | str):
        """Converts from human-readable/ASCII representation: '0034' -> 00:34."""
        if isinstance(start, int):
            start = f"{start:04d}"
            # Check values for all timeslots meet 0..59 criteria
            start_hour = (lambda v: (int(v) if 0 <= int(v) <= 59 else 0) if isinstance(v, (int, str)) else 0)(int(start[:-2]))
            start_minute = (lambda v: (int(v) if 0 <= int(v) <= 59 else 0) if isinstance(v, (int, str)) else 0)(int(start[-2:]))
        if isinstance(end, int):
            end = f"{end:04d}"
            end_hour = (lambda v: (int(v) if 0 <= int(v) <= 59 else 0) if isinstance(v, (int, str)) else 0)(int(end[:-2]))
            end_minute = (lambda v: (int(v) if 0 <= int(v) <= 59 else 0) if isinstance(v, (int, str)) else 0)(int(end[-2:]))
        try:
            return cls(time(start_hour, start_minute), time(end_hour, end_minute))
        except Exception:
            # if there's garbage data return a TimeSlot with None values
            return cls(None, None)

    def to_list(self) -> list:
        """Return [start, end]. Times are returned as time objects or None."""
        return [self.start, self.end]

    def to_json(self) -> str:
        """Return a small JSON object with HH:MM strings or null for empty times."""
        def fmt(t):
            return t.strftime("%H:%M") if t else None
        slot = {"start": fmt(self.start), "end": fmt(self.end)}
        return json.dumps(slot)
    
    def to_dict(self) -> str:
        """Return a small JSON object with HH:MM strings or null for empty times."""
        def fmt(t):
            return t.strftime("%H:%M") if t else None
        slot={}
        slot['start'] =  fmt(self.start)
        slot["end"] = fmt(self.end)
        return slot
