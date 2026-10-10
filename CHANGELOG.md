# Change Log

All notable changes to GivTCP are documented in this file.

## [Unreleased]

### Added
- **Power flow entities on three-phase inverters**, from the meter's import and export and the battery's charge and discharge power.

### Fixed
- **Power flow entities** (Solar to House, Battery to Grid and the rest) are now worked out the same way on every model, and fixed:
  - **Solar to House was never above 0 on PV-only inverters.**
  - **Grid to Battery could be negative**, or more than the import, when a little power was imported while solar covered the battery.
  - **The house flows could add up to more than the load.** Each source is now shared out in turn (solar to the house first, then the battery, then the grid), and each flow is limited by what's left at both ends. Small imbalances from inverter losses are left out rather than counted twice.
  - **Solar to Battery could show while the battery wasn't charging.**
  - **Gateway:** flows were only published with more than one All-in-One, and the whole poll could fail if none reported a state of charge.
- **Battery pause mode stopped updating after "Registers HR 318-318 could not be read"**. GivTCP reads a few settings the library doesn't (the pause mode, and on some models the pause slot, three-phase slots and Gateway rates) after each full refresh. One failed read, as happens now and then when the dongle is busy, stopped that read for the rest of the session, so Home Assistant kept showing the old pause mode, even on inverters that answer it normally. Now a failed read is tried again with the next full refresh (with a longer timeout), and is only given up after 3 failures in a row. The value read last time is kept meanwhile, and the warning is only logged when it's given up.

## [3.6.0-beta7] - 2026-10-09

Changes since 3.6.0-beta6.

### Added
- **Pause When Inverter Stops Responding**, set per inverter on the config page (`recovery_pause_N`, seconds, 0 = off, the default) (#610, thanks @lancer73). Some dongles crash when they're sent more requests while they're struggling, and only recover if left alone for a while. With this set, a poll or reconnect that gets no response is retried at the normal poll interval rather than sooner. If that fails too, GivTCP closes the connection and sends the inverter nothing for this many seconds, then reconnects. The same applies when GivTCP can't connect at startup. Polls where only some reads fail don't count, as the inverter is still answering. During the pause:
  - Stats/status is set to `paused`, so Predbat and automations can tell why there are no updates. The next good poll sets it back to `online`.
  - Write commands sent over REST are answered straight away with "not sent", rather than timing out after 15 seconds. Callers such as Predbat retry, and the retries would otherwise all be sent as soon as the pause ends.
  - Other write commands (MQTT, and scheduled ones such as the end of a force charge) are sent once the pause is over, without duplicates.
  - The check that restarts a stuck read loop allows for the pause, so it doesn't restart it partway through.
  - Each pause, rather than each failed reconnect, counts towards the restart after 10 failures (to pick up a changed IP address).

  With it off, nothing changes.

### Fixed
- **Second HV battery stack on three-phase inverters: no module data, and 6 wasted reads every poll** (#614). Detect listed the second stack's modules at the next addresses after the first stack's, but those never return its data, so GivTCP polled them every cycle for nothing. As 3.5 did, and as GivTCP already did for HV Gen 3 when detect didn't list them (#611), the second and later stacks' modules are now always read at the first stack's addresses, at that stack's register offset.
- **"Inverter clock is N minutes behind" when it isn't** (#614). The inverter's clock is only read on full refreshes, but was compared with the time it was checked, so a longer full refresh interval looked like a clock running behind. It's now compared with the time it was read.
- **`Task exception was never retrieved ... network_consumer ... TimeoutError: [Errno 110]`** logged some time after a reconnect (#613). When GivTCP replaced a modbus client whose connection had died, the library's `close()` stopped partway on the dead socket and left the old client's reader task running. That task later failed with nothing to handle its error. GivTCP now always stops the old client's tasks and handles their errors. It was only log noise: GivTCP had already reconnected.
- **"Removed N retained MQTT messages for entities not supported by this inverter" on every restart** (#612). On AC and All-in-One inverters, GivTCP removed the PV string voltage and current entities, which these models don't have, then created them again straight away, so the next restart removed them again. They're no longer created. The message also listed every entity the model can't have, not just the ones it removed, so the count didn't match the list. It now names only what it removed. Entities you've disabled in Home Assistant aren't removed by this: Home Assistant keeps disabled entities, so delete them in Settings → Entities.

### Changed
- **Lighter polling on HV systems** (#614). Each HV battery module is a read of its own (12 on two 6-module stacks), so a poll on a three-phase inverter with two stacks was 24 reads, keeping its dongle busy for about a third of each 30-second cycle. The module reads (cell voltages and temperatures) are now only repeated on full refreshes, once each module has been read. The stack values (SOC, power, voltage, energy) come from each stack's BCU, which is still read every poll.
- **"Reconnected to the inverter after N failed attempts" is only logged when it took longer than a read cycle.** A reconnect within one read cycle costs no data, so it's now logged at debug level.

## [3.6.0-beta6] - 2026-10-04

Changes since 3.6.0-beta5.

### Changed
- **Clearer log when an inverter doesn't respond at startup.** When the network scan found an inverter that then didn't answer, GivTCP logged a full traceback for each attempt. It now logs one line per attempt, for example "No response from inverter at 192.168.2.201 (connected, but it didn't answer)", then an error saying the inverter has been skipped. Unexpected errors still give the details. The connection is now also closed after a failed attempt.

### Fixed
- **HV second battery stack: BMS Temperature stuck and no module data** (#611). The stack's BMS Temperature is the average of its modules' temperature sensors, but no module in the second or later stacks was read. givenergy-modbus looks for them at the next device addresses after the first stack's, which don't answer. As in 3.5, GivTCP now reads every stack's modules at the same addresses as the first stack's, at that stack's register offset, so the second stack's BMS Temperature, cell voltages and cell temperatures are back. If one of these reads fails 3 polls in a row, GivTCP stops asking for it until it restarts, so it doesn't slow every poll.
- **`removedisco: Error connecting to MQTT Broker: RuntimeError: dictionary changed size during iteration`** at startup (#609). Before republishing the Home Assistant discovery messages, GivTCP clears any that have changed. It worked through the retained messages while new ones were still arriving, including GivTCP's own state messages, so the cleanup often stopped partway. It now works through a copy. The cleanup also only ran when GivTCP had just removed entities the inverter doesn't support, which most models don't have, because it relied on that step to collect the retained messages. It now collects them itself, so changed discovery messages (and old ones on a V3 upgrade) are cleared on every model. The error message no longer blames the MQTT broker connection.
- **"Inverter data could not be processed" for 4-5 minutes after a restart** (#608). If the inverter settings (holding registers) couldn't be read when GivTCP connected, often because the inverter was still recovering, they weren't tried again until the next full refresh (every 4 minutes by default), and the failure was only logged at debug level. Until then every poll failed and the data from before the restart was republished. Now the first poll comes after 10 seconds and is a full refresh, and a full refresh that misses some settings is repeated on the next 3 polls. The failure is logged as a warning.
- **One missing setting no longer loses the whole poll** (#608). Battery Type, Meter Type, Status, DC Status and Battery Calibration Status are left out until they can be read, rather than failing the poll and republishing old data, so the live power and energy data still updates. If none of the inverter settings have been read yet, the log now says "Inverter settings not read yet" rather than giving a `TypeError`.
- **"Battery ... has returned no valid data" logged every poll.** It's now logged once when a battery or module has returned no data for 3 polls, then at debug level.
- **Set Charge Target and Enable Charge Target wrote more than they should** since the move to the v2 library. Set Charge Target also turned on the charge schedule (HR 96, or AC charge on three-phase) and set the charge target's enable flag (HR 20), and for a 100% target cleared that flag instead, so setting 100% turned the charge target off. Enable Charge Target also wrote the target, and for a 100% target cleared the flag rather than setting it. When it ran in the same batch as a new target, it put back the target from before. Both now write only what they did before v2: the target (HR 116, or HR 1111 on three-phase) and the enable flag (HR 20). Enable and Disable Charge Target also update the published state straight away, so a consumer reading it back, such as Predbat, no longer reports `REST failed to enableChargeTarget`. As in 3.5, Set Charge Target no longer turns the charge target on by itself: automations that only set the target should also turn on Enable Charge Target (Predbat already does).
- **HV Gen 3 battery charge/discharge rate showed 5,100 W at full rate rather than 6,000 W** (#604). The rate is set as a percentage of the battery's capacity (0.5C at most), and since beta 5 GivTCP converted it to watts using the modules' usable 3.4 kWh each, so full rate on a 3-module stack showed as 5,100 W. A user measured about 5.8 kW discharging and 6.1 kW charging at that setting: the percentage is of the modules' Ah rating (52 Ah each, 4.16 kWh at 80 V), not their usable capacity. GivTCP now converts using that, published as Battery Rate Capacity kWh, so full rate shows 6,000 W, and Predbat's 6,000 W reads back as 6,000 W rather than 5,100 W (which made it retry). Battery Capacity kWh is still 10.2 kWh for the SOC kWh and time remaining.

## [3.6.0-beta5] - 2026-10-03

Changes since 3.6.0-beta4.

### Changed
- **Clearer logging when the inverter drops the connection.** Some dongles go offline for a few seconds now and then (a restart or lost Wi-Fi), which also closes the connection and makes the next one or two reconnects fail. The connection-closed log line no longer says GivTCP has already reconnected, and it gives the time since the last traffic without implying that idle time was the cause. The first two failed reconnects are now warnings rather than errors, and once GivTCP reconnects after failures it logs how long that took, for example "Reconnected to the inverter after 2 failed attempts (8.2s after the connection was lost)".
- **Old log files keep the `.log` extension** (#606). Each day's log is now saved as, for example, `log_inv_1.2026-10-03.log` rather than `log_inv_1.log.2026-10-03`, so it can be attached to a GitHub issue as it is. Logs already saved the old way are renamed when GivTCP starts. The log viewer shows both, and only the last 7 days are kept as before.

### Fixed
- **Wrong inverter model shown on the config page** with more than one inverter (#599). 3.5 saved each inverter's model under its position in the network scan rather than its own slot, so two inverters could swap models. 3.6 only rewrote the models when auto scan was on, so the swap carried over. GivTCP now takes each inverter's model from its saved capabilities at startup, and logs any it corrects. The model is also passed to that inverter's read and write processes, which use it for some model-specific checks, so these now get the right one too.
- **HV Gen 3 battery capacity too high** (#604): a 3-module stack showed 15.96 kWh rather than 10.2 kWh. The library multiplies the battery's Ah by the All-in-One's 307 V, as it groups HV Gen 3 with the All-in-One. Battery Capacity is now 3.4 kWh (each module's rating) × the modules in all stacks, so 10.2 kWh for 3 modules. SOC kWh, the charge/discharge time remaining and the percentage-to-watts conversion for the power controls all use this figure, so they change too.
- **Battery BMS Current always 0 A, now Battery Discharge Current** (#605). Each battery pack's current is only reported by BMS firmware 3022 (or 4009 in the 4xxx range) onwards, and only Gen 3 and AC inverters above ARM firmware 214 pass it on (confirmed by GivEnergy). Everywhere else it read 0 A. It's now only published where it's reported, and removed from Home Assistant on inverters that can't report it. It only measures discharge, so it's renamed Battery Discharge Current to tell it apart from the inverter's Battery Current. The old Battery BMS Current entities are removed.
- **`IndexError: list index out of range (startup.py:92)` during the network scan** (#604). GivTCP checks each device on the EV charger port by reading its clock, and some other Modbus devices answer with fewer registers. Those are now skipped as not being an EV charger.

## [3.6.0-beta4] - 2026-10-03

Changes since 3.6.0-beta3.

### Changed
- **Fewer Modbus reconnects, and far less logging about them** (#604). Many inverter dongles close a connection after about 10 seconds without traffic. GivTCP reconnected straight away each time, only for that connection to be closed too, and logged two lines per reconnect, one of them CRITICAL. It now reconnects only when there's a poll or a write to send, and logs routine reconnects at debug level. Instead it logs how long the connection was idle the first time the inverter closes it, then a summary every 5 minutes. A drop within 2 seconds of traffic is counted separately, as it points to something other than an idle timeout.
- **"Only report battery data" now keeps the inverter's controls** (renamed "Only report battery data and controls"). Before 3.6 the setting was ignored, so these inverters published everything. Since beta 1 it left only the battery data, which removed controls such as Battery Pause Mode and Battery Discharge Rate that automations behind an EMS rely on (#591). The EMS has no battery pause or rate control of its own. The setting only ever filtered what was published: the inverter is still polled in full, as it always has been.
- **HV Gen 3 maximum battery rate now follows the stack size** (#604). It's the battery current limit (25 A on the 8 kW, 30 A on the 10 kW) × 80 V per module × modules in one stack, capped at the inverter's rated battery power. A 3-module stack on an 8 kW inverter is 6000 W, as the GivEnergy portal shows, rather than 8000 W. Parallel stacks don't add voltage, so two stacks of 4 on a 10 kW inverter are 9600 W.

### Fixed
- **Battery pause slot errors on Gen 1 hybrids** (e.g. `WriteHoldingRegisterResponse(ERROR 319 ...)` when Predbat sets the pause slot). Gen 1 has battery pause mode but no pause slot, and its firmware rejects writes to HR 319-320 and any read that includes them. GivTCP no longer offers the pause slot on Gen 1, so its HA entities are removed, and it reads the pause mode register on its own instead of with the slot registers, so the current mode should now show. A request to set the pause slot on any inverter without one (Gen 1, AC, three-phase, EMS) is now refused with "this inverter has no battery pause slot", and REST refuses it straight away rather than sending it to the inverter.

## [3.6.0-beta3] - 2026-10-03

Changes since 3.6.0-beta2.

### Added
- **Warning when an inverter's clock is out** by 5 minutes or more (logged once a day). The inverter resets its Today energy counters at midnight by its own clock, so a clock left on GMT in summer makes them reset at 01:00 in Home Assistant (#601). Use the Sync Time button, or the GivEnergy portal, to correct it.

### Fixed
- **Load Energy Today/Total too high on hybrid inverters** (Gen 1, Gen 2, Gen 3, Gen 4 and HV Gen 3) since the move to the v2 library (dev builds from May 2026 and the 3.6 betas). The library only reports the model family, so hybrids got the AC-coupled formula, which adds the PV generation that a hybrid's inverter output already includes. Load Total jumped up by the lifetime PV total, and every day's Load included that day's PV again. Hybrids use the correct formula again, as in 3.5. **On those builds, Load Energy Total drops once to the correct value.** Home Assistant takes that drop as a meter reset, so the Energy dashboard will show one large spike in that hour, to correct in Developer Tools → Statistics. Upgrading straight from 3.5 isn't affected.
- **Sync Time could set the inverter an hour out**: it used the container's own clock, which can be UTC (e.g. Docker without `TZ`). It now uses GivTCP's configured timezone.
- **Battery Charge/Discharge Energy Total showing 0 or nothing** on Gen 1, Gen 2 and AC inverters in the 3.6 betas (#600). They are read from the first battery's BMS again, as in 3.5, and from the inverter's registers when the BMS has none (some Gen 1 firmware). If neither has them they are left out rather than published as 0, because Home Assistant takes a drop to 0 as a meter reset and counts the whole total again when it comes back.
- **EVC log, and the main inverter log, could keep writing to a rotated file** after midnight (#566). The EVC loops, and every REST and MQTT process (through the EVC code they load), used a log handler that isn't safe with several processes. They now use the same shared handler as the write log, which follows the new file when another process rotates it.
- **Force Charge doing nothing on inverters with 10 charge slots** (Gen 3, All-in-One, HV Gen 3) when the SOC was already above slot 1's own target (#576). The inverter stops at the lower of the charge target and slot 1's target, and Force Charge only set the first. It now sets slot 1's target to 100% too, and puts it back when Force Charge ends.
- **Gateway charge/discharge target SOC 1-10 always empty** (#577). The Gateway has the 10-slot block (HR 240-299) like other models, but the library doesn't read it there, so the targets were never filled in. Values left over from 3.5 (published as 0) then stayed in Home Assistant, which rejected them as out of range. GivTCP now treats the Gateway as a 10-slot device, so the targets show real values, and charge/discharge slots 3-10 and every slot's target SOC can be set on it.

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
