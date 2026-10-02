"""Stand-ins for GivTCP's external services: the MQTT broker, Home Assistant discovery and the RQ/Redis queue.
Everything GivTCP sends to them is recorded, so tests can check it."""
import asyncio
import datetime as _dt
import itertools
import logging
import re
import time
import types

class Recorder:
    def __init__(self):
        self.clear()

    def clear(self):
        self.mqtt = []          # (topic, payload) published by GivMQTT
        self.discovery = []     # [topic, payload] discovery messages sent by HA_Discovery
        self.removed = []       # entities discovery asked HA to remove
        self.jobs = []          # (delay_seconds, function, args) scheduled on the RQ queue
        self.logs = []          # (logger, level, message) at WARNING or above

recorder = Recorder()

real_wrong_inverter = [None]     # read.wrongInverter, which install() replaces

class FakeMqttClient:
    connected_flag = True

    def publish(self, topic, payload=None, qos=0, retain=False):
        recorder.mqtt.append((topic, payload))

    def disconnect(self, *args, **kwargs):
        pass

    def loop_stop(self, *args, **kwargs):
        pass

class FakeJob:
    def __init__(self, id):
        self.id = id

class FakeRegistry(list):
    def remove(self, jobid, *args, **kwargs):
        if jobid in self:
            super().remove(jobid)

    def requeue(self, jobid, at_front=False):
        self.remove(jobid)

class FakeQueue:
    def __init__(self):
        self.scheduled_job_registry = FakeRegistry()
        self._ids = itertools.count(1)

    def enqueue_in(self, delay, func, *args, **kwargs):
        job = FakeJob("job" + str(next(self._ids)))
        recorder.jobs.append((delay.total_seconds(), getattr(func, "__name__", str(func)), list(args)))
        self.scheduled_job_registry.append(job.id)
        return job

# GivTCP's own clock, for results that depend on the time of day (force charge slots, rate periods, date sync)
FROZEN_NOW = _dt.datetime(2026, 6, 15, 12, 0, 0)

class _FrozenMeta(type):
    def __instancecheck__(cls, obj):
        return isinstance(obj, _dt.datetime)    # so isinstance(x, datetime.datetime) still holds for real datetimes

class FrozenDateTime(_dt.datetime, metaclass=_FrozenMeta):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW.replace(tzinfo=tz) if tz else FROZEN_NOW

    @classmethod
    def today(cls):
        return FROZEN_NOW

def _frozen_datetime_module():
    module = types.ModuleType("datetime")
    module.__dict__.update(vars(_dt))
    module.datetime = FrozenDateTime
    return module

class _LogRecorder(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)

    def emit(self, record):
        recorder.logs.append((record.name, record.levelname, normalise(record.getMessage())))

def normalise(text):
    """Remove what changes between runs or code edits from messages: source line numbers, job ids and timings"""
    text = re.sub(r"(\.py):\d+", r"\1:N", str(text))
    text = re.sub(r"\(\d+ms\)", "(Nms)", text)
    text = re.sub(r" - \d+\)$", " - N)", text)     # processData's "(Exception: message - <line number>)"
    return re.sub(r"job\d+", "jobN", text)

def install():
    """Patch the loaded GivTCP modules to use the fakes. Call after harness.env.bootstrap()"""
    import GivLUT as givlut_module
    import HA_Discovery
    import mqtt
    import read
    import write

    client = FakeMqttClient()
    mqtt.GivMQTT.get_connection = lambda: client
    mqtt.GivMQTT.wait_for_connection = lambda timeout=5: True
    mqtt._mqttclient = client

    def send(array, SN):
        recorder.discovery.extend(array)
        return []           # nothing left unpublished
    HA_Discovery.HAMQTT.sendDiscoMsg = send
    HA_Discovery.CheckDisco.removedisco = lambda SN, messages: None
    HA_Discovery.CheckDisco.removeunsupported = lambda SN, items: recorder.removed.extend(items)
    HA_Discovery.CheckDisco.cleartopics = lambda topics: recorder.removed.extend(topics)
    HA_Discovery.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time)

    read.updateFirstRun = lambda SN: None     # it edits the settings.py next to read.py (the developer's own)
    real_wrong_inverter[0] = read.wrongInverter
    read.wrongInverter = lambda client: None  # the harness settings use made-up serials (see test_detect_serial.py)
    givlut_module.GivQueue.q = FakeQueue()

    read.datetime = _frozen_datetime_module()
    write.datetime = FrozenDateTime

    # write.py waits between some steps for a real inverter to settle; the mock doesn't need it
    async def no_wait(delay, result=None):
        return result
    fast_asyncio = types.ModuleType("asyncio")
    fast_asyncio.__dict__.update(vars(asyncio))
    fast_asyncio.sleep = no_wait
    write.asyncio = fast_asyncio

    handler = _LogRecorder()
    logging.getLogger().addHandler(handler)
    for name, logger in list(logging.Logger.manager.loggerDict.items()):
        if isinstance(logger, logging.Logger) and not logger.propagate:
            logger.addHandler(handler)
