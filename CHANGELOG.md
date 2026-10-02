# Change Log

All notable changes to GivTCP are documented in this file.

## [Unreleased]

### Added
- **Warning when an inverter's clock is out** by 5 minutes or more (logged once a day). The inverter resets its Today energy counters at midnight by its own clock, so a clock left on GMT in summer makes them reset at 01:00 in Home Assistant (#601). Use the Sync Time button, or the GivEnergy portal, to correct it.

### Fixed
- **Sync Time could set the inverter an hour out**: it used the container's own clock, which can be UTC (e.g. Docker without `TZ`). It now uses GivTCP's configured timezone.
- **Battery Charge/Discharge Energy Total showing 0 or nothing** on Gen 1, Gen 2 and AC inverters in the 3.6 betas (#600). They are read from the first battery's BMS again, as in 3.5, and from the inverter's registers when the BMS has none (some Gen 1 firmware). If neither has them they are left out rather than published as 0, because Home Assistant takes a drop to 0 as a meter reset and counts the whole total again when it comes back.

## [3.6.0-beta2] - 2026-10-02

Changes since 3.6.0-beta1.

### Added
- **"Timeslot entities in Home Assistant" setting** to keep the drop-downs, the time pickers or both for each timeslot. The type turned off is removed from Home Assistant (#603).
- **Startup logs where each meter and battery was found** (the `bcu_stacks` and `hv_bmus` addresses), to diagnose batteries that are found but return no data.

### Changed
- **"Only report battery data" now takes effect.** Before 3.6 this inverter setting was ignored, so every inverter published all its data. Inverters with it ticked (usually AC or hybrid inverters behind an EMS or Gateway) now publish only their battery details, and their inverter-level entities and controls stop updating. Untick it on the config page to keep them. Startup logs which inverters have it on (#591).
- **Smaller Docker image**: unused packages (pandas, numpy, scapy and others) are no longer installed.

### Fixed
- **Model shown as "All_in_one" for HV Gen 3 hybrids**, and their battery charge/discharge rate capped at 6,000 W instead of 10,000 W. GivTCP now uses the model the library resolves at detection (e.g. Hybrid_gen1, Hybrid_hv_gen3) for the Invertor_Type, timeslot count and battery rate (#603).
- **Battery charge/discharge rate stopping just short of the maximum** (e.g. 2976W instead of 3000W on an AC 3.0). The rate is set as a whole percent of battery capacity, and rounding to the nearest percent could land below the maximum. Asking for the maximum, or more, now sets the smallest percent that reaches it, as the GivEnergy portal does, rather than 50% (which can throttle large battery banks, #562).
- **Inverter shown as the wrong model on the config page** in multi-inverter setups (#599). Detected capabilities are cached per serial number and were trusted from then on, so a cache saved from another inverter (e.g. while two inverters' IP addresses were swapped) gave an inverter the wrong model. Startup now checks the cached model against the inverter's own model code and firmware, and re-detects if they differ. The read loop no longer saves capabilities when the inverter at the IP address isn't the one in the settings, and logs an error instead.
- **REST API restarting every minute** (#602). When the REST server stopped, its worker processes were left running and held the port, so every restart failed. Restarts now stop the whole process group. The log says why it stopped, and the REST server's own errors go to `rest_gunicorn_inv_N.log` (and `rest_gunicorn_settings.log`), which the log viewer shows.
- **"No module named 'givenergy_modbus_async'" after upgrading from 3.5** (#599). Cached data saved by the old library couldn't be read. GivTCP now sets an unreadable cache file aside (renamed to `.unreadable`) and starts afresh, instead of failing.
- **Empty "Combined Generation Power" sensor on HV Gen 3**: it is only created when the inverter provides a value.

## [3.6.0-beta1] - 2026-10-01

Key changes since the last dev build published on the `dev3` branch (3.5.22).

### Changed
- GivTCP now uses the published [givenergy-modbus](https://github.com/dewet22/givenergy-modbus) library (v2.13.0) instead of its own bundled copy. This brings more reliable modbus communication and better support for newer models. Controls the library can't write yet fail with a clear message (see [docs/upstream-givenergy-modbus-requests.md](docs/upstream-givenergy-modbus-requests.md)).
- **Hybrid HV Gen 3** inverters are now read and controlled as single-phase inverters, which is what they are, and are no longer labelled "All-in-One". Before, they were read with the three-phase layout, so values such as SOC and PV power could show as 0, and controls wrote to three-phase registers. Their Home Assistant entities change to the single-phase set, and the old three-phase ones are removed.
- **AC and All-in-One**: the PV string voltage and current entities are removed. On these models the registers don't hold real string readings (on the All-in-One the "PV voltage" was the grid voltage).
- **Set Charge Rate AC / Discharge Rate AC** now work on the All-in-One as well as the AC.
- **Faster network scan.** Inverters and EV chargers are found in one pass, scanning the host's own /24 first. A large network such as a /16 takes a few minutes rather than up to two hours, and networks larger than a /16 are limited to the /16 around the host.
- Inverter details are detected once and saved per serial number, so later start-ups skip the full detect. GivTCP detects again automatically if the saved details stop matching the inverter.
- The config page lists inverters so you can add or remove them, with no fixed limit of five. Inverters found by the last network scan are shown so you can add them in one click. Slots 1–5 keep REST ports 6345–6349, and slot 6 onwards start at 6356.
- Saving from the config page no longer resets settings the page doesn't manage back to their defaults.
- The config page now runs inside the Home Assistant sidebar (ingress) and no longer needs opening in a new tab by IP address.
- The config page works on a phone in portrait: the sections show as wrapping buttons, with a new Welcome button, and the section navigation and Previous/Save/Next buttons stay at the top while you scroll (thanks @jim-ip).
- The web pages have a new header menu (Config, Readme, Settings Guide, Datapoints, Dashboard, Logs) and restyled pages to match the config page.
- Routine messages (detecting the inverter, reconnecting, publishing discovery) are no longer logged as critical.
- Redis now only listens on localhost.

### Added
- **Log viewer** in the web UI, under Logs in the header menu. It has a tick box for each log in `/config/GivTCP/logs`: startup, each inverter's main, write and REST logs, and the EV charger logs. Tick one log to see it on its own, or any combination to merge them into one timeline, with a coloured label showing which log each entry came from. You can pick a rotated day, filter by level or text, follow new lines as they're written, load earlier lines and download a log file. Only the log files are served: nothing else in `/config/GivTCP`, such as `allsettings.json`, can be reached through the viewer.
- **Time picker controls for timeslots** in Home Assistant 2026.5 or later, alongside the existing drop-downs. For example, "Charge start slot 1" sits next to "Charge start time slot 1". Both stay in sync.
- **Settings Guide and Datapoints pages** in the web UI, generated from [docs/SETTINGS-GUIDE.md](docs/SETTINGS-GUIDE.md) and the new [docs/DATAPOINTS.md](docs/DATAPOINTS.md), which describes every value GivTCP publishes.
- **REST request log**: each REST request and its result are written to their own log file alongside the main log. Settings requests are never logged in full, as they can contain passwords, and full data dumps are logged by size only.
- **Battery Pause Mode and the pause timeslot on Gen 1 (firmware 187 or later), Gen 2, Gen 3 and HV Gen 3 hybrids, the All-in-One and the Gateway, and Battery Pause Mode on AC-coupled inverters (firmware 200 or later).** givenergy-modbus doesn't support them on these models yet, so GivTCP adds them itself until it does.
- **Per-slot charge and discharge target SOC** on inverters with 10 time slots (newer Gen 3, Gen 4, All-in-One, HV Gen 3) and on three-phase inverters, where charge/discharge slots 3-10 are now also read, **charge and discharge rate on three-phase inverters**, and **Car Charge Boost on the EMS**. givenergy-modbus doesn't support these yet, so GivTCP adds them itself until it does.
- **Data age stat** (`Data_Age`): shows how old the inverter data is, so values held from the last good read can be spotted.
- **Battery charge and discharge MOS state** entities, showing whether each battery's charge and discharge switches are open or closed: for each HV battery stack and each LV battery (thanks @plandregan).
- Better support for HV Gen 3, three-phase, All-in-One, EMS and Gateway systems, including battery counts and stack details for HV batteries.

### Fixed
- **Gateway controls** all failed with an error such as `'GatewayV1' object has no attribute 'set_enable_discharge'`. They now work.
- **Inverter data failed to process**, and nothing was published, when some holding registers couldn't be read: for example the Gateway's charge/discharge limits, the battery reserve, charge target or a timeslot, or the inverter clock. The last good values are used instead.
- If processing a poll fails for any other reason, the last good data is republished instead of entities going unavailable.
- **Today energy stats stuck at midnight.** Load and Self Consumption Today, and the Day/Night cost stats, could keep yesterday's value if no poll landed in the exact minute of midnight. They now reset when the inverter's date changes, even after a missed poll, a restart over midnight or clock drift. The midnight "zero" message, which could double-count in the HA Energy dashboard, has been removed.
- **Eco (Paused)** battery mode, and reverting a Force Charge on three-phase inverters, failed with `CancelledError`. A command that wrote the same register twice cancelled its own first write; now only the last write to each register is sent.
- **Force Export** put your discharge slot 1 times into charge slot 1 when it ended, and left discharge slot 1 set to the export window. It now restores discharge slot 1.
- **Export (Paused)** could be chosen as the battery mode but was rejected, so ending a Force Export started from that mode also failed.
- **Force Charge / Force Export** didn't revert when some of the settings they save couldn't be read. They now restore the settings that were read.
- **Cancelling Force Charge / Force Export** from REST or MQTT failed, and dropped any other pending controls.
- **Cancelling Temp Pause Charge / Discharge** from REST returned a server error.
- **Enable Discharge** (REST and MQTT) did nothing. It now sets the battery reserve: back to the saved reserve to enable, or to 100% to disable.
- **Set Date and Time** always failed.
- **Set PV Input Mode** was silently ignored. It now reports that givenergy-modbus can't write it yet.
- **Car Charge Boost over MQTT** used the wrong payload key.
- **EMS discharge target SOC** can now be set over MQTT.
- **Three-phase Force Charge, Force Discharge and AC Charge** can now be set over REST.
- Several controls could fail with an error that dropped every other pending control and left a REST caller waiting for a timeout: Set Charge/Discharge Rate and Set Eco Mode on EMS, and Force Charge/Export before any inverter data had been read. They now fail with a clear message.
- **Gateway battery power had the wrong sign**: discharging showed as charging, and the reverse. The same applied to the Gateway's inverter and Liberty power, the battery power flows, the charge/discharge time remaining, and each All-in-One's inverter power shown through the Gateway.
- **Predbat saw a frozen inverter clock on the Gateway and EMS.** In the REST `/readData` and `/getCache` output, `raw.invertor` had no `serial_number` on these models, which Predbat uses to find the inverter's details. Predbat then kept the last inverter time and battery capacity it had read, and warned of a growing clock skew.
- **Charge and discharge rate on the Gateway** (Set Charge/Discharge Rate, their AC versions, and Temp Pause Charge/Discharge) failed with `not yet supported by givenergy-modbus for Gateway inverters`, and the current rates weren't shown. The Gateway sets them for the All-in-Ones behind it, through the AC charge/discharge limit, as before 3.5.23.
- Force Charge, Force Export and Temp Pause failed on models whose data didn't include the settings they save for reverting (three-phase battery reserve, EMS charge rate).
- A control that isn't available on your inverter model now says so ("not available for Ems inverters"), rather than giving an `AttributeError`. This covers, for example, three-phase-only controls on single-phase inverters, inverter controls on the EMS, and Force Charge/Export on the EMS.
- A control sent at the same moment as the read loop checked for requests could be lost, along with any other pending requests.
- **Leftover pause entities on older inverters.** Battery Pause Mode and the pause timeslots are now removed from Home Assistant on inverters that don't support them (older Gen 1 hybrids, three-phase and EMS; the pause timeslots on the AC, which has Battery Pause Mode but no timeslot).
- **Force Charge and Force Export on the AC and All-in-One** failed with `HR(318) is not permitted`, because givenergy-modbus doesn't allow pause mode writes on them.
- Gen 1 Home Assistant discovery failed on the battery BMS current entity, so no entities were created.
- **Export Power Limit** now shows in Watts in HA, instead of as an amp slider.
- **Battery pause slot changes** now show in HA immediately, instead of after the next full read.
- The Settings Guide page opened the settings API instead of the guide.
- The config page could load blank in Chrome after an update, because the browser kept an old copy of the page that pointed at files that no longer exist. The page is no longer cached (thanks @jim-ip).
- The Smart Target setting was ignored and followed the Dynamic Tariff setting instead (thanks @jim-ip).
- Charge rate on large battery banks no longer jumps to 50% at the inverter maximum.
- The limits used to filter bad readings are higher, so large systems aren't wrongly rejected: 20 kW battery power for parallel All-in-Ones, 100 kWh/day for homes with heat pumps and EVs.
- Unused slots with a 0% target are no longer published, which stops repeated HA errors.
- If InfluxDB is unavailable, polling carries on instead of stalling for minutes.

### Removed
- Lite query mode and its settings.
