## GivTCP — quick orientation for AI coding agents

This file gives targeted, actionable pointers so an AI coding agent can be productive immediately in this repo.

1) Big picture
- Purpose: a daemon that polls GivEnergy inverters (via Modbus over TCP), publishes data via MQTT/REST and exposes control APIs. See `README.md` and `startup.py` for the run-time flow.
- Major components:
  - device comms / polling: `GivTCP/read.py` (watch loop, reconnection, full vs partial refresh)
  - control/write: `GivTCP/write.py` (builds Modbus write commands via `givenergy_modbus_async.client.commands`)
  - runtime wiring / globals: `GivTCP/GivLUT.py` (file paths, locks, `GivClientAsync` helper, `GivQueue` for RQ)
  - REST/API surface: `GivTCP/REST.py` (many POST endpoints that push write requests and read responses)
  - startup/packaging: `startup.py` constructs `/config/GivTCP/allsettings.json` and detects Home Assistant Supervisor environment.

2) Data flow & IPC patterns (critical)
- Settings originate from `/config/GivTCP/allsettings.json` (created from `settings.json` by `startup.py`). The runtime frequently imports `from settings import GiV_Settings` and sometimes reloads using `importlib.reload(settings)` (see `write.updateControlCache`).
- Read loop (`read.py::watch_plant`) polls the inverter and:
  - reads `GivLUT.writerequests` (pickle file `writerequests.pkl`) to perform writes
  - writes REST responses to `GivLUT.restresponse` (JSON) and uses `GivLUT.restlock` for locking
  - publishes data to MQTT and writes regcache (`GivLUT.regcache`) as pickles
- Write requests are queued by creating/updating `writerequests.pkl`; the read loop processes them and returns results via `restresponse.json`.
- Many files and state are stored as pickles under `GiV_Settings.cache_location` (see `GivLUT.regcache`, `rateData_*`, `rawdata_*`, etc.). Locking is handled by files (`.regcache_lockfile_*`) and `GivLUT` locks—be careful modifying these flows.

3) Runtime & developer workflows
- Recommended dev bootstrap (local):
  - create a Python venv and install dependencies: `pip install -r requirements.txt` (repo root has `requirements.txt`).
  - Redis is required for RQ (default connection `127.0.0.1:6379`)—start a local Redis during development.
  - Run the service: `python startup.py` will initialize settings and start the usual processes in a single process for development debugging.
  - Start the background worker separately to process queued jobs: `python GivTCP/worker.py` (this launches an RQ worker connected to Redis).
  - The REST API is implemented in `GivTCP/REST.py`; it is normally started by the runtime — for quick tests, run `python startup.py` which wires everything together.

4) Integration points & external deps
- Uses `givenergy_modbus_async` heavily for Modbus read/write commands. Look at `read.py` and `write.py` for how `commands.refresh_plant_data()` and `commands.*` are used.
- MQTT: see `GivTCP/mqtt.py` (broker publishes and control topics). The project assumes Home Assistant add-on environment if `SUPERVISOR_TOKEN` exists (checked in `startup.py`).
- Redis + RQ: `GivLUT.GivQueue` and `GivTCP/worker.py` expect Redis at `127.0.0.1:6379`.

5) Project-specific conventions & pitfalls
- Global settings are a module (`settings.GiV_Settings`) rather than a config object. Many modules import `GiV_Settings` at import-time, so edits to `allsettings.json` typically require a restart or `importlib.reload` pattern used in `write.py`.
- IPC via pickles and lock-files is pervasive. Concurrency issues can occur if you manipulate files outside the existing helpers — prefer using `GivLUT.get_regcache()` and `GivLUT.put_regcache()`.
- REST control pattern: call POST endpoints in `GivTCP/REST.py` (e.g. `/setChargeTarget`) with JSON payloads. This appends to `writerequests.pkl`; the read loop executes commands and writes a single-response JSON object to `restresponse.json`.
- Timezone: when running as an add-on, `startup.py` uses Supervisor timezone via API; otherwise `TZ` env or default `Europe/London`.

6) Where to look first when editing or extending
- New device register logic / telemetry mapping: `GivTCP/read.py` and `GivTCP/GivLUT.py` (look for `raw_to_pub`, `entity lookup`, and `get_regcache` usage).
- New control endpoints: add to `GivTCP/REST.py` and implement command in `GivTCP/write.py` using `givenergy_modbus_async.client.commands`.
- Tests / quick smoke: there are no unit tests—use a local run with mock inverter IP (or on-device integration) and verify that `regCache_*.pkl`, `writerequests.pkl` and `restresponse.json` get created as expected.

7) Small concrete examples
- Trigger a charge target change via REST: POST `/setChargeTarget` JSON {"chargeToPercent":"45"} — this demonstrates the writerequests -> read loop -> restresponse pattern (see `GivTCP/REST.py` and `GivTCP/write.py`).
- Inspect caching: inspect `GiV_Settings.cache_location + '/regCache_<instance>.pkl'` and use `GivLUT.get_regcache()` to read safely.

If anything in this doc is unclear or you want more detail for a specific task (tests, running the Flask app separately, or creating unit tests for the Modbus command wrappers), tell me which area to expand and I will update this file.
