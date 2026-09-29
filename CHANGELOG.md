# Change Log

All notable changes to GivTCP are documented in this file.

## [3.5.66] - 2026-09-29

### Added
- **Log viewer** in the web UI, under Logs in the header menu. It has a tab for each log in `/config/GivTCP/logs`: startup, each inverter's main, write and REST logs, and the EV charger logs. An "All logs" tab merges them into one timeline, with a coloured label showing which log each entry came from.
- In the viewer you can pick a rotated day, filter by level or text, follow new lines as they're written, load earlier lines and download a log file.
- Only the log files are served. Nothing else in `/config/GivTCP`, such as `allsettings.json`, can be reached through the viewer.

## [3.5.64] - 2026-09-29

Key changes since the last dev build published on the `dev3` branch (3.5.22).

### Changed
- GivTCP now uses the published [givenergy-modbus](https://github.com/dewet22/givenergy-modbus) library (v2.12.0) instead of its own bundled copy. This brings more reliable modbus communication and better support for newer models. Some controls the new library can't write yet now fail with a clear message instead of an error (see [docs/upstream-givenergy-modbus-requests.md](docs/upstream-givenergy-modbus-requests.md)).
- Inverter details are detected once and saved per serial number, so later start-ups skip the full detect. GivTCP detects again automatically if the saved details stop matching the inverter.
- The config page lists inverters so you can add or remove them, with no fixed limit of five. Inverters found by the last network scan are shown so you can add them in one click. Slots 1–5 keep REST ports 6345–6349, and slot 6 onwards start at 6356.
- Saving from the config page no longer resets settings the page doesn't manage back to their defaults.
- The config page now runs inside the Home Assistant sidebar (ingress) and no longer needs opening in a new tab by IP address.
- The web pages have a new header menu (Config, Readme, Settings Guide, Datapoints, Dashboard) and restyled pages to match the config page.
- Redis now only listens on localhost.

### Added
- **Time picker controls for timeslots** in Home Assistant 2026.5 or later, alongside the existing drop-downs. For example, "Charge start slot 1" sits next to "Charge start time slot 1". Both stay in sync.
- **Settings Guide and Datapoints pages** in the web UI, generated from [docs/SETTINGS-GUIDE.md](docs/SETTINGS-GUIDE.md) and the new [docs/DATAPOINTS.md](docs/DATAPOINTS.md), which describes every value GivTCP publishes.
- **REST request log**: each REST request and its result are written to their own log file alongside the main log.
- **Data age stat** (`Data_Age`): shows how old the inverter data is, so values held from the last good read can be spotted.
- Better support for HV Gen 3, three-phase, All-in-One, EMS and Gateway systems, including battery counts and stack details for HV batteries.

### Fixed
- **Today energy stats stuck at midnight.** Load and Self Consumption Today, and the Day/Night cost stats, could keep yesterday's value if no poll landed in the exact minute of midnight. They now reset when the inverter's date changes, even after a missed poll, a restart over midnight or clock drift. The midnight "zero" message, which could double-count in the HA Energy dashboard, has been removed.
- **Leftover pause entities on older inverters.** Battery Pause Mode and the pause timeslots are now removed from Home Assistant on inverters that don't support them (Gen 1 hybrid, AC).
- **Car Charge Boost over MQTT** used the wrong payload key. It now reports clearly that the library can't set it yet.
- **EMS discharge target SOC** can now be set over MQTT.
- **Three-phase Force Charge, Force Discharge and AC Charge** can now be set over REST.
- **Export Power Limit** now shows in Watts in HA, instead of as an amp slider.
- **Battery pause slot changes** now show in HA immediately, instead of after the next full read.
- HV Gen 3 inverters are no longer labelled "All-in-One".
- Charge rate on large battery banks no longer jumps to 50% at the inverter maximum.
- The limits used to filter bad readings are higher, so large systems aren't wrongly rejected: 20 kW battery power for parallel All-in-Ones, 100 kWh/day for homes with heat pumps and EVs.
- Unused slots with a 0% target are no longer published, which stops repeated HA errors.
- If InfluxDB is unavailable, polling carries on instead of stalling for minutes.
- If processing a poll fails, the last good data is republished instead of entities going unavailable.

### Removed
- Lite query mode and its settings.
