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

## Coverage reports

From the repository root, after installing `requirements-dev.txt`:

```
python -m coverage run -m pytest
python -m coverage report -m
python -m coverage html
python -m coverage xml
python -m coverage json
python tests/check_coverage.py coverage.json
```

Open `htmlcov/index.html` for a per-file report with missing lines and branches. `coverage.xml` is a
Cobertura report for coverage services. The configuration measures Python application code in `GivTCP/`
and the root startup/discovery scripts, including modules the tests never import. It excludes the test
harness and the manual `GivTCP/test_loop.py` script. It does not measure the JavaScript frontends.
Tests that extract startup functions into a separate script do not measure execution of the original
`startup.py` file, so their behavior checks will not appear as covered lines there. The startup runtime
tests additionally execute the complete original script with simulated container paths, processes,
Supervisor replies and network clients, including bounded watchdog iterations.

The service tests cover EVC register decoding and charging controls, EVC MQTT and Home Assistant discovery,
PALM consumption history and solar forecasts, outlier smoothing, Influx output, settings endpoints, and
network scanning. External services are replaced with fakes; files are written only in temporary directories.

You can pass pytest selectors after `pytest` for a quicker check, but that report represents only the
selected tests. Each coverage run replaces the previous results. Run the full suite for a baseline.

The **Tests and coverage** GitHub Actions workflow runs on pushes and pull requests on Linux and Windows.
Startup tests copy the simulated container config if Windows denies symlinks; portable log-handler tests
cover reopening and rollover without relying on POSIX open-file rename behavior. The 70% per-file gate
applies on both platforms.
Each run summary shows a per-file coverage table, and the **python-coverage-ubuntu-latest** and
**python-coverage-windows-latest** artifacts contain HTML, XML and JSON reports (retained
for 14 days). Download and extract it, then open `htmlcov/index.html`. Reports are also generated when
tests fail; those results may be incomplete. CI requires **at least 70% in every measured file**, using
coverage.py's combined line-and-branch percentage. The check uses unrounded values and runs after report
upload so reports remain available if a file falls below the target. A high overall average cannot mask
an under-tested file. Run the gate after the full suite; focused runs intentionally cover fewer files.

GitHub's native PR coverage comparisons additionally require Code Quality on a supported plan and an
upload via `actions/upload-code-coverage`. The XML report is ready for that integration; the current
workflow uses summaries and artifacts without requiring Code Quality or a third-party service.

## Reviewing results

The tests pass when GivTCP behaves as recorded in `tests/golden/`, even where the recorded behaviour is an
error. There are two reports:

- **What changed.** Each failing test lists only the values that changed, one per line (`path: old -> new`).
  At the end of the run, a summary lists every changed result, grouped by model.
- **What GivTCP gets wrong.** `--problems` lists every error in the golden results, grouped by message, with
  the models and controls it affects. It's split into errors to fix (crashes and wrong behaviour) and controls
  that aren't supported on a model. The report reads the golden files, so a quick run is enough:

  ```
  python -m pytest tests/test_catalogue_coverage.py --problems
  ```

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
  Session teardown closes every client and mock server, awaits remaining tasks, then stops and closes the
  event loop and joins its thread, so network tasks cannot be abandoned at interpreter shutdown.
- [harness/fakes.py](harness/fakes.py) records MQTT publishes and HA discovery instead of sending them, replaces
  the RQ queue, and fixes GivTCP's clock at 2026-06-15 12:00 so time-based results don't change between runs.

## Adding a device model

Capture it with `givenergy-cli capture` (which redacts serial numbers). Save the capture in `fixtures/captures/`
as `<name>.capture`, add it to `DEVICES` in `harness/devices.py`, then run `python -m pytest -k <name> --update-golden`.
