# GivTCP test harness

Runs GivTCP's real code against each GivEnergy device model, with no hardware, broker or Redis needed. It
checks that a change made for one model doesn't break another.

## What it covers

For each device model in [harness/devices.py](harness/devices.py):

- **Detect and read cycles.** The givenergy-modbus client detects and polls a mock plant served from a real
  wire capture ([fixtures/captures](fixtures/captures/README.md)). GivTCP then processes and publishes two read
  cycles. The tests record GivTCP's output (the `/getCache` data), the MQTT topics it publishes, the Home
  Assistant entities it creates, and any warnings or errors it logs.
- **Every control, through every entry point** ([harness/catalogue.py](harness/catalogue.py)):
  - `direct`: the `write.py` function, called the way the read loop calls it.
  - `rest`: a POST to the REST API. The read loop runs the queued command and the reply goes back to the caller.
  - `mqtt`: a message on the control topic. The read loop runs the queued command.

  Each result records GivTCP's reply, the registers written to the plant, any revert jobs scheduled, and any
  warnings or errors logged. The writes go through the library's per-model write checks, as they would on a
  real inverter.

The results are compared with [golden/](golden/), one JSON file per model. `test_catalogue_coverage.py` fails if
a write function, REST route or MQTT topic is added without a case in the catalogue.

## Running

```
pip install -r requirements-dev.txt
python -m pytest                          # everything, about 20 minutes
python -m pytest -k hybrid_gen2           # one model, about 2 minutes
python -m pytest -k "gateway and rest"    # one model, one entry point
python -m pytest tests/test_read_cycle.py # read cycles only, about 2.5 minutes
```

Each model takes about 15 seconds to start, because detect probes for devices that aren't there.

## When a result changes

A failure means GivTCP now behaves differently from the recorded result for that model. If the change is
intended, record the new behaviour and review the change to `tests/golden/*.json` like any other diff:

```
python -m pytest -k hybrid_gen2 --update-golden
git diff tests/golden
```

The golden files record the current behaviour, including behaviour that's wrong. A fix therefore shows up as a
golden change too, which the diff makes visible.

## How it works

- [harness/env.py](harness/env.py) points GivTCP's settings, cache and config directory
  (`GIVTCP_CONFIG_DIR`) at a temporary directory. It never touches a real install or your own
  `GivTCP/settings.py`.
- [harness/plant.py](harness/plant.py) runs a `givenergy_modbus.testing.MockPlant` that records register writes.
  It runs on an event loop in a background thread, as GivTCP's read loop does, and calls
  `read.processWriteRequests()` for queued REST and MQTT commands.
- [harness/fakes.py](harness/fakes.py) records MQTT publishes and HA discovery instead of sending them, replaces
  the RQ queue, and fixes GivTCP's clock at 2026-06-15 12:00 so time-based results don't change between runs.

## Adding a device model

Capture it with `givenergy-cli capture` (which redacts serial numbers). Save the capture in `fixtures/captures/`
as `<name>.capture`, add it to `DEVICES` in `harness/devices.py`, then run `python -m pytest -k <name> --update-golden`.
