"""Runs GivTCP against a MockPlant served from a wire capture.

The mock plant and the givenergy-modbus client live on an event loop in a background thread, as they do in
GivTCP's read loop, so REST calls (which block waiting for the read loop's response) can run on the test thread.
"""
import asyncio
import json
import threading
import time
from pathlib import Path

from givenergy_modbus.client.client import Client
from givenergy_modbus.model.register import HR
from givenergy_modbus.testing import MockPlant

from harness import env
from harness.fakes import recorder

class LoopThread:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="plant-loop", daemon=True)
        self.thread.start()

    def run(self, coro, timeout=120):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

class RecordingMockPlant(MockPlant):
    """MockPlant that records every register write it acknowledges"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.writes = []

    def _ack_write(self, req):
        self.writes.append([req.device_address, req.register, req.value])
        return super()._ack_write(req)

class PlantSession:
    """One device model: a mock plant, a connected client, and GivTCP's state after two read cycles"""
    def __init__(self, key, device, loop):
        import read
        self.key = key
        self.device = device
        self.loop = loop
        self.settings = dict(serial_number=key.upper()[:10], inverter_type=device.model.name.capitalize())
        self.mock = RecordingMockPlant.from_capture(device.path)
        if device.identity:     # the whole HR(0-59) block must be present for detect to read it
            for reg in range(60):
                self.mock.devices[0x11][HR(reg)] = device.identity.get(reg, 0)
        host, port = loop.run(self.mock.start())
        self.client = Client(host, port)
        loop.run(self.client.connect())
        env.clear_state()
        self.activate()
        loop.run(read.detectPlant(self.client, force=True))
        self.read_failures = loop.run(read.readPlant(self.client, True))
        self.settings["numBatteries"] = read.batteryCount(self.client.plant)
        self.activate()
        self.cycles = [self.read_cycle(), self.read_cycle(refresh=True)]
        self.state = env.snapshot_state()
        self.registers = {addr: dict(cache) for addr, cache in self.plant.register_caches.items()}

    @property
    def plant(self):
        return self.client.plant

    @property
    def device_type(self):
        return self.plant.capabilities.device_type

    def activate(self, state=None):
        """Make this the plant GivTCP talks to, optionally resetting its state files"""
        import GivLUT as givlut_module
        env.configure(**self.settings)
        givlut_module._client = self.client
        if state is not None:
            env.restore_state(state)
            self._restore_registers()
        recorder.clear()
        self.mock.writes.clear()

    def _restore_registers(self):
        # The client updates its register copy from each acknowledged write, so put back the post-read values
        # or one test's writes would change what the next test's command reads (eg. the current charge target)
        caches = self.plant.register_caches
        for addr in list(caches):
            if addr not in self.registers:
                del caches[addr]
        for addr, values in self.registers.items():
            if addr in caches:
                caches[addr].clear()
                caches[addr].update(values)
            else:
                from givenergy_modbus.model.register_cache import RegisterCache
                caches[addr] = RegisterCache(values)

    def read_cycle(self, refresh=False):
        """One poll of the read loop: refresh the registers, then GivTCP's processing and publishing (runAll2)"""
        import read
        recorder.clear()
        if refresh:
            self.loop.run(read.readPlant(self.client, False))
        started = time.monotonic()
        output = read.runAll2(self.plant)
        try:
            output = json.loads(output)
        except (TypeError, ValueError):
            pass
        return dict(output=output, mqtt=list(recorder.mqtt), discovery=list(recorder.discovery),
                    removed=list(recorder.removed), logs=list(recorder.logs), seconds=time.monotonic() - started)

    # --- writes ------------------------------------------------------------------------------------------------

    def run_case(self, entry, steps, api=None):
        """Run a catalogue case (see harness.catalogue) from this plant's post-read state. entry is "direct",
        "rest" or "mqtt". Returns the outcome of each step: GivTCP's result, the registers written to the plant,
        jobs scheduled and warnings/errors logged"""
        self.activate(self.state)
        outcomes = []
        for target, payload in steps:
            if payload == "@job":       # run the revert job the previous step scheduled, as the RQ worker would
                if not recorder.jobs:
                    outcomes.append(dict(skipped="the previous step scheduled no job"))
                    continue
                payload = recorder.jobs[-1][2][1]
            recorder.clear()
            self.mock.writes.clear()
            if entry == "direct":
                outcome = self._call_write(target, payload)
            elif entry == "rest":
                outcome = self._call_rest(api, target, payload)
            else:
                outcome = self._call_mqtt(target, payload)
            # Writes still in flight when the command returned belong to this step, not the next test
            pending = self._drain()
            outcome["writes"] = [list(w) for w in self.mock.writes]
            if pending:
                outcome["still_sending_after_return"] = pending
            outcomes.append(outcome)
        return outcomes

    def _drain(self, timeout=5.0):
        """Wait for the client to finish sending; returns the number of frames still unsent or unanswered"""
        async def wait():
            deadline = time.monotonic() + timeout
            while True:
                pending = self.client.tx_queue.qsize() + sum(
                    1 for f in list(self.client.expected_responses.values()) if not f.done())
                if pending == 0 or time.monotonic() > deadline:
                    return pending
                await asyncio.sleep(0.05)
        return self.loop.run(wait())

    def _outcome(self, **extra):
        return extra | dict(writes=[list(w) for w in self.mock.writes],
                            jobs=[[d, f] for d, f, _ in recorder.jobs], logs=[list(l) for l in recorder.logs])

    def device_for_writes(self):
        # As read.processWriteRequests picks it
        return self.plant.ems if self.plant.capabilities.is_ems else self.plant.inverter

    def _call_write(self, command, payload):
        """Call a write.py function directly, as the read loop does"""
        import inspect
        import write
        from giverrors import errDetail
        func = getattr(write, command)
        try:
            if inspect.iscoroutinefunction(func):
                result = self.loop.run(func(self.device_for_writes(), payload, True))
            else:
                result = func(self.device_for_writes(), payload, True)
        except Exception:
            # Not caught by the write function itself: the read loop would log it and drop every queued request
            return self._outcome(raised=errDetail())
        return self._outcome(result=_json(result))

    def _pump(self, until, timeout=10):
        """Run the read loop's write handling until `until()` is true"""
        import read
        from GivLUT import GivLUT
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Wait until the request is fully written: REST and MQTT write the queue file in place, and the
            # read loop drops every queued request if it reads a partly written file
            if _queued(GivLUT.writerequests) is not None:
                self.loop.run(read.processWriteRequests(self.client))
            if until():
                return True
            time.sleep(0.02)
        return False

    def _call_rest(self, api, route, payload):
        """POST to a REST control endpoint, while the read loop handles the queued write"""
        box = {}
        def post():
            box["response"] = api.post(route, json=payload)
        t = threading.Thread(target=post, daemon=True)
        t.start()
        self._pump(lambda: not t.is_alive())
        t.join(30)
        resp = box.get("response")
        if resp is None:
            return self._outcome(status=None, result="<no response>")
        return self._outcome(status=resp.status_code, result=_json(resp.get_data(as_text=True)))

    def _call_mqtt(self, topic, payload):
        """Deliver an MQTT control message, then let the read loop handle the queued write"""
        import mqtt
        from GivLUT import GivLUT
        msg = type("Msg", (), {"topic": "GivEnergy/control/" + self.settings["serial_number"] + "/" + topic,
                               "payload": str(payload).encode("utf-8")})()
        mqtt.GivMQTT.on_message(None, None, msg)
        queued = _queued(GivLUT.writerequests) or []
        self._pump(lambda: not Path(GivLUT.writerequests).exists())
        return self._outcome(queued=queued)

def _json(text):
    """GivTCP's results are JSON strings, and some are JSON inside JSON"""
    for _ in range(2):
        try:
            text = json.loads(text)
        except (TypeError, ValueError):
            break
    return text

def _queued(path):
    """The queued write requests, or None if there is no complete queue file"""
    import pickle
    try:
        with open(path, "rb") as inp:
            return [[c, _plain(p)] for c, p, _ in pickle.load(inp)]
    except (OSError, EOFError, pickle.UnpicklingError):
        return None

def _plain(payload):
    return json.loads(json.dumps(payload, default=str))

class Plants:
    """Starts each device's session on first use and keeps it for the whole test run"""
    def __init__(self):
        self.loop = LoopThread()
        self.sessions = {}

    def get(self, key):
        from harness.devices import DEVICES
        if key not in self.sessions:
            self.sessions[key] = PlantSession(key, DEVICES[key], self.loop)
        session = self.sessions[key]
        session.activate(session.state)
        return session
