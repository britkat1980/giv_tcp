"""Frame spacing for test clients connected to mock inverters."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class FramePacing:
    enabled: bool = False
    delay: float = 0.25
    jitter: float = 0.1

    def __post_init__(self):
        for name in ('delay', 'jitter'):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f'frame {name} must be finite, non-negative seconds')

    def client_options(self):
        return dict(tx_message_wait=self.delay if self.enabled else 0,
                    tx_jitter=self.jitter if self.enabled else 0)


def from_config(config):
    mode = config.getoption('frame_pacing')
    values = {}
    for name in ('delay', 'jitter'):
        override = config.getoption('frame_' + name)
        value = config.getini('givtcp_frame_' + name) if override is None else override
        try:
            values[name] = float(value)
        except (TypeError, ValueError):
            raise ValueError(f'frame {name} must be finite, non-negative seconds') from None
    return FramePacing(enabled=config.getini('givtcp_frame_pacing') if mode is None else mode == 'on',
                       **values)
