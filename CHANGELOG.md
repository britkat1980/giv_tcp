# GivTCP 3.6.9

Changes since 3.6.8.

### Added
- **Sync Time for a Gateway with a single All in One** (#680, thanks @ProphetOfDoom). The Gateway's controls were only added with two or more All in Ones in parallel, so with one there was no way to set its clock (eg. after the clocks change). Sync Time is now there on every Gateway.
- **Lite mode**, set per inverter on the config page (`lite_query_N`, off by default), for HV battery stacks (three-phase and HV Gen 3; not the All-in-One) (#676, thanks @lancer73). The inverter passes every read of a battery stack (its BCU) or battery module on to the battery, and on some systems that seems to be more than the inverter keeps up with. In lite mode each module is only read until it has data, and each stack only on full refreshes once it has data. The inverter's own battery figures (SOC, battery power, current and voltage) are still read every poll. On three-phase, SOC kWh is worked out from the inverter's SOC and the stacks' capacity, so it still updates every poll. Module and stack values usually still update, as the dongle reads them itself for the GivEnergy cloud and passes the answers on to GivTCP: see the README, "Timeouts and an unresponsive inverter".
- **Wait After Connecting**, set per inverter on the config page (`connect_delay_N`, seconds, 0 = off, the default) (#676). Some dongles don't answer requests sent straight after a connection opens, so the first poll after a restart or a recovery pause failed. With this set, GivTCP waits this long after every new connection before its first request. Keep it below the time the dongle leaves an idle connection open (often about 10 seconds), or the dongle closes the connection first: see the README, "Timeouts and an unresponsive inverter".
- **Connection settings in the log at startup.** When Lite mode, Wait After Connecting or Pause When Inverter Stops Responding is on, GivTCP says so once at startup (at info level), so a log shows which of them were in use.

### Changed
- **GivTCP now uses [britkat1980/givenergy-modbus](https://github.com/britkat1980/givenergy-modbus)**, a fork of givenergy-modbus 2.13.0 with GivTCP's requests merged, while they wait to be accepted upstream. Several of GivTCP's own patches to the library are now done by the library instead:
  - the Gateway's 10-slot map, and its charge and discharge rates;
  - charge slot 2 on 10-slot models;
  - per-slot target SOC writes;
  - three-phase rate writes;
  - the EMS's Car Charge Boost and its energy totals.

  Nothing you'd notice should change. The EMS and Gateway now publish their model, firmware, serial number and clock under `raw/`, and the EMS also publishes its energy counters there. The library also removes serial numbers and IP addresses from frames it can't decode, as GivTCP's Share Device now does (#668). It also closes a connection cleanly when the dongle has already dropped it.

### Fixed
- **PALM (Smart Target) never set the charge target locally** (#682, thanks @amcburney). Its write called a function that now needs the read loop's connection, so it failed every time, and PALM quietly fell back to the GivEnergy cloud without saying why. PALM now queues the write for the read loop, as REST and MQTT commands are, and logs the reason if it ever has to use the cloud instead.
- **Connection messages missing from the log file.** Messages about opening and replacing the Modbus connection (eg. "Modbus connect attempt 1/3 failed", "Failed to establish Modbus connection", "Replacing the modbus client after...", and with debug logging "Connected, waiting 10s before the first request") were written to a separate logger without the log file handler. They never reached the log file, warnings and errors only the add-on's console, and debug lines nowhere at all. They now go to GivTCP's main log like everything else.
- **Share Device could leave a dongle's serial number and IP addresses in the capture** (#668). The Modbus library only removes them from frames it can decode, and one a dongle sent that it couldn't (a status frame) was written as it came. GivTCP now also checks every frame before it's saved, zeroing the end of anything shaped like a serial number and every digit of anything shaped like an IP address. If you've shared a capture, it's worth checking it doesn't contain these.
- **Max battery charge/discharge rate too high for small LV batteries** (#679, thanks @jamesremuscat). The battery rate is set as a percentage of the battery's capacity, at most 50%, so a 5.2 kWh battery can't charge or discharge faster than about 2.6 kW, even on a 3.6 kW inverter. GivTCP reported the inverter's 3600W as the maximum, so Predbat asked for it, read back less and kept retrying. It's now 50% of the battery's capacity where that's lower, as GivTCP 2.x reported, and setting a rate above it says what was actually set.
- **Every poll failing with "TypeError: '>' not supported between instances of 'NoneType' and 'int'"** on some single-phase and AC inverters (#675, #677, thanks @lancer73). Some inverters report the grid or output frequency 10 times too high (for example 500.0 for 50 Hz), which GivTCP has always divided by 10. Since 3.6, the Modbus library treats a frequency outside 40-70 Hz as invalid and gives none, and GivTCP's check then failed the whole poll, so only the cached data from before was republished. GivTCP now reads the frequency from the register itself in that case and corrects it as before. A frequency that hasn't been read yet is left out rather than failing the poll.
- **A settings block the inverter never answers turned most polls into full refreshes** (#675, #677). If some settings couldn't be read, GivTCP made the next 3 polls full refreshes too (#608). For a block an inverter doesn't support, such as the AC configuration block (HR 300) on some AC inverters, that repeated after every scheduled full refresh, so with a 30 second poll about 4 polls in 6 were full refreshes, each waiting for that block to time out. A block that hasn't answered once since GivTCP started now only gets those retries once. It's still read with every scheduled full refresh, and gets the retries again once it has answered.
- **The first polls after a recovery pause failing, starting another pause.** After Pause When Inverter Stops Responding, GivTCP reconnected with the same Modbus client. On a three-phase hybrid that client got no answers after the pause, and then failed straight away without sending anything, which counted as the inverter still not responding, while a restart of GivTCP connected first time. As after 5 failed reads and at startup (#615), the pause now starts with a new client, so it reconnects as a restart would.
- **Extra requests to an inverter that isn't answering.** After each full refresh GivTCP reads a few settings the Modbus library doesn't (pause mode, three-phase slots 3-10, AC and Gateway rates). It did so even when the settings read had got no answer at all, sending a dongle that isn't responding up to 3 more attempts of 3 seconds for each of them, before the failed poll was counted (and so before Pause When Inverter Stops Responding could start). They're now only read when the inverter answered at least some of the settings.
- **Home Assistant reporting that GivTCP didn't stop cleanly** (#676). GivTCP now handles the stop signal, stops its processes in order (Redis last, after the processes that use it) and exits cleanly.
- **"App 'GivTCP' uses deprecated map option 'config'" in the Supervisor log** (#676). The add-on now maps Home Assistant's config folder with `homeassistant_config`, at `/config` as before.

# GivTCP 3.6.8

Changes since 3.6.7.

### Fixed
- **Force Export cleared Discharge Slot 2 and didn't put it back** (#662, thanks @bigbadbenw). Setting the export slot also cleared slot 2, which the revert doesn't restore. Force Export now leaves slot 2 alone.
- **Load Energy Today counted again at midnight on some nights** (#669, #670, thanks @m47een). The inverter doesn't reset all its Today counters on the same poll (PV Today can reset a few seconds before the others), so a poll in between calculated Load as yesterday's total less PV, which Home Assistant counted as a reset, then again at the real one: 25-40 kWh of phantom load. Load and Self Consumption Today are now held for that poll.
- **Hybrids without a battery re-detected every hour** (#665, thanks @plandregan). Since 3.6.7, a hybrid with no batteries found is checked again for them, in case its battery didn't answer. A new **No battery fitted** setting (with each inverter's settings on the config page) stops that, and without it GivTCP now stops checking by itself after 5 detects in a row find none, until it restarts. The re-detect is logged at info rather than as a warning.

# GivTCP 3.6.7

Changes since 3.6.6.

### Fixed
- **AC inverters and hybrids with batteries missing** (#655, #660). As for the All in One (#650), a battery that didn't answer while GivTCP detected the inverter was left out and never polled. An AC inverter (which always has a battery) with none detected isn't saved, and a Gen 1-4 hybrid with none is checked again from time to time, waiting longer each time (up to an hour), in case its battery didn't answer. To fix it straight away, delete `/config/GivTCP/<serial>_caps.pkl` and restart.
- **Battery Charge/Discharge Energy Total jumping after a restart** (#652, thanks @gcoan). Until a battery has been read after a restart, GivTCP used the inverter's own totals, which are a different figure, then went back to the battery's. They're now left out until the battery has been read.
- **Load Energy Today still dipping just after midnight** (#654, thanks @m47een). Rounding dips in the first 5 minutes after midnight got through, which Home Assistant counts as meter resets at those small values. Load's dips are now held back at midnight too.
- **All in One-HY: battery pause controls removed** (#647, thanks @mimikm). They're available again, as in 3.5.
- **Gen 2 (and other models): Predbat's export or discharge target "failing" and retrying** (#658). A per-slot discharge target only exists on models with 10 time slots (not AC 3.0 or Gen 1/2), and an export target only on the EMS. GivTCP now reports these as skipped rather than failed, so they aren't retried every poll.
- Registers some firmware doesn't answer (eg. the AC charge/discharge rates on a Gen 1 at ARM 451) are now logged at info, not as a warning on every restart (#655).
- **All in One batteries missing until the capabilities were deleted** (#650, thanks @plandregan). If a battery didn't answer while GivTCP detected the inverter, it saved the inverter without it and never polled it again. GivTCP no longer saves an All-in-One or All in One-HY with no batteries, needs two detects in a row before accepting fewer batteries, and keeps re-detecting while some may be missing (waiting longer each time, up to an hour).
- **Force Charge, Force Export and the temporary pauses not reverting after a restart** (#656, thanks @plandregan). Their revert was only scheduled in Redis, which is cleared when GivTCP restarts, so the forced settings stayed. GivTCP now keeps a copy and, when it starts, runs any revert that came due while it was down and reschedules the rest.
- **One inverter going offline restarted GivTCP for every inverter** (#657, thanks @plandregan). After 10 failed connections GivTCP restarted the whole add-on to look for the inverter at a new IP address. Now only that inverter looks: it scans its network for its serial number, moves to the new address if it finds it (and saves it), and otherwise keeps retrying, while the other inverters carry on.
- **Force Charge, Force Export and the temporary pauses showed 0 minutes left when they ran past midnight.** Their end time was saved without a date. It's now saved in full (and an end time saved by an earlier version is still read).
- **EV charger: reading the inverter's data could fail** while the inverter was saving it, so the EVC's solar and grid-limit modes missed that update.

### Changed
- **GivTCP's processes share their data more safely.** The register cache is now saved in one step, so it can always be read without waiting, and the few places that change it in place use a proper lock rather than a lock file, which two processes could both take, could be left behind, and made REST calls wait in half-second steps. The settings file uses the same lock. Force Charge/Export and the pauses keep their running jobs through one set of helpers, and the battery value calculation no longer needs a touch file to run once a half hour.
- **Much less written to disk.** GivTCP's register cache (`regCache_N.pkl`) kept the last 31 outputs, for outlier detection that was removed in 3.6, but everything only uses the latest. It now keeps just that, so each poll writes about 18 KB per inverter instead of about 570 KB (around 1.6 GB a day at a 30s poll, which matters on an SD card). The battery value stats (`battery_N.pkl`) are only saved when they change, and two files nothing read (`rawdata_N.pkl` and `invippkl.pkl`) are gone.
- **Docker: a new docker-compose.yml for running GivTCP outside Home Assistant.** It uses the released image (`britkat/giv_tcp-ma`, not the dev build), sets the timezone properly, keeps settings, captures and logs in a `config` folder next to the file, and uses host networking so GivTCP can find your inverters. It explains every port, and how to use Docker Desktop (Windows/macOS) or a bridge network instead. If you already run GivTCP in Docker, point the volume at your existing settings folder. The README's Docker instructions are updated to match.
- The "Publishing Home Assistant Discovery messages for N new entities" message on every restart is now only logged at Debug level, and says what it is: discovery for data that wasn't in GivTCP's first read, usually the battery modules (which the Modbus library only gives once a second read confirms them). The entities aren't new to Home Assistant: it just updates the ones it has.

# GivTCP 3.6.6

Changes since 3.6.5.

### Fixed
- **Hybrid Gen 1 and All in One-HY: Battery Charge Rate AC and Battery Discharge Rate AC missing, or couldn't be set** ("NotImplementedError: Setting the AC discharge rate is not yet supported", #645, thanks @mimikm). 3.5 read and wrote these (HR 313/314) on every hybrid that answered them, but the new Modbus library only does on AC and All-in-One models, so the entities weren't created and setting them failed. GivTCP now reads and writes them again on the Gen 1, Gen 3 and All in One-HY. The Hybrid Gen 3, which could already set them since 3.6.4, now also shows the inverter's current values. If an inverter doesn't answer the read, GivTCP stops trying after 3 attempts and logs a warning, and the rates can still be set.

# GivTCP 3.6.5

Changes since 3.6.4.

### Fixed
- **EMS: energy totals dropping to 0 for one poll.** The EMS's dongle sometimes passes on a reply to the GivEnergy cloud with every energy value 0, and since 3.6.4 GivTCP published those zeros, which Home Assistant takes for a meter reset, putting a large spike in the Energy dashboard. GivTCP now keeps the previous values when that happens.
- **EMS: Generation Energy Today and Total showed the same as Inverter Out** (#637, thanks @rhino77777). They were read from registers that hold the inverters' output, as in 3.5. They're now the generation meters' figures. Generation Energy Total drops to the meter's own total, so its statistics in the Energy dashboard may show one step on the day you update.
- **Load and Self Consumption Today not resetting at midnight, sometimes for the whole day** (#639, thanks @JRascagneres, who also fixed the most common case in #640). These are calculated by GivTCP, which held them at their highest value to stop rounding dips. If the inverter's counters reset when GivTCP didn't expect it, eg. before it had read the inverter's clock after midnight, yesterday's totals stayed until today's passed them or GivTCP restarted. Now only dips of a counter tick or two are held back, so a reset always goes through on the same poll as the other Today values. The lifetime Load and Self Consumption totals get the same change, so a single wrong high reading can no longer stick.
- **Today values bouncing back to yesterday's figure just after midnight.** A reply still carrying yesterday's figure (eg. a stale one) could undo the reset, and Home Assistant would count yesterday's total again. For 15 minutes after a Today value resets, a return to the value before the reset is ignored.
- The Day/Night cost stats reset at midnight using the same corrected inverter clock.

### Changed
- **Battery Only now also publishes the inverter's own details and status** (#634). Battery Only (on an inverter's settings, for All-in-Ones behind a Gateway or inverters behind an EMS) didn't take effect before 3.6, and since 3.6 it left out everything but the batteries, controls and timeslots, including Invertor Time, firmware and temperature. Home Assistant kept showing the last values from before the update, so the time looked frozen. Those details, and the Stats (status, last updated), are published again. The inverter's power and energy, which the Gateway or EMS also reports, are still left out.

# GivTCP 3.6.4

Changes since 3.6.3.

### Fixed
- **EMS: energy totals and today values not updating, and Generation Energy Total showing solar power.** Since 3.6, the new Modbus library doesn't read the EMS's energy registers, so GivTCP stopped publishing its Generation, Inverter In/Out, Import and Export energy (total and today) and Total Power. Home Assistant kept showing the last values from 3.5, and today values didn't reset at midnight. Generation Energy Total was also read from the wrong register, which holds a power in W. GivTCP now reads them again, as in 3.5. Generation Energy Total jumps back to the real total, so its statistics in the Energy dashboard may show one large step on the day you update.
- **All in One-HY: "Error processing Inverter data: TypeError: '<' not supported between instances of 'NoneType' and 'float'" every poll** (#628). The Modbus library has no battery power rating for the All in One-HY, which every poll needed. GivTCP now estimates it from the battery stack, as for the HV Gen 3, within the inverter's rating, and a missing rating on any model no longer stops the poll.
- **Gen 1 (and others): battery module entities never created in Home Assistant** (#629, thanks @bigchriselmer-ui). Home Assistant discovery was only sent for the first data GivTCP read, and the Modbus library only gives battery modules once a second read confirms them. GivTCP now sends discovery for any new data as it appears, so the modules' devices and entities are created after the second poll.
- **Hybrid Gen 3: Battery Charge Rate AC and Battery Discharge Rate AC couldn't be set** ("NotImplementedError: Setting the AC charge rate is not yet supported", #630, thanks @JRascagneres). They're written to HR 313/314 again, as in 3.5.

### Documentation
- Timeslot drop-downs take the time as `HH:MM:SS` in automations, and the time pickers as `HH:MM` (#633).

# GivTCP 3.6.3

Changes since 3.6.2.

### Added
- **Share Device page** in the web UI. It captures a few minutes of an inverter's Modbus data, with serial numbers and IP addresses removed by the givenergy-modbus library, so it can be shared to help GivTCP support more devices. GivTCP keeps working as normal while it runs. When it's done you can download the file and open a GitHub issue with your device's model, firmware and batteries filled in, to attach it to. Nothing is sent anywhere unless you attach the file yourself. The capture is also available over REST (`/RESTn/captureDevice` and `/RESTn/captureStatus`).

### Fixed
- **All in One-HY (device type 0x82xx): no data, with "Error processing Three Phase data"** (#621). The new Modbus library treats the All in One-HY as a three-phase inverter, so it was read with three-phase registers, which it rejects, and every poll failed. It's now read as single-phase, as in 3.5, with 10 charge/discharge slots and the hybrid Load calculation. On three-phase inverters, a missing PV reading also no longer fails the whole poll.

# GivTCP 3.6.2

Changes since 3.6.1.

### Fixed
- **Home Assistant entities deleted and recreated, resetting their entity ID.** Before republishing discovery, GivTCP deleted any entity whose config had changed, so Home Assistant recreated it with GivTCP's default entity ID. Entities with an older ID (for example from GivTCP 2.x, such as `sensor.givtcp_<serial>_invertor_details_givtcp_invertor_temperature`) or one you'd renamed were reset, and lost any name, area or icon you'd given them. A comparison bug made every temperature sensor (anything in °C) count as changed, so they were deleted and recreated on every restart. GivTCP now leaves existing entities alone: Home Assistant updates them in place when their config changes. Old entities are still removed on a V3 upgrade, and entities your inverter doesn't support are still removed. If an entity ID was reset on 3.6 or 3.6.1, change it back in Settings → Entities.

# GivTCP 3.6.1

Changes since 3.6.0.

### Fixed
- **PV-only (string) inverters: no data, with "unsupported operand type(s) for +: 'float' and 'NoneType'" every poll** (#618). The new Modbus library stores the PV inverter's Inverter Energy Total under a different name, and GivTCP was still reading the old, empty one, which made every poll fail. It now reads the right value, and one missing energy total can no longer stop the whole poll.
- **Charge Slot 2 couldn't be set on inverters with 10 charge slots, and read back wrong** (#619, thanks @JRascagneres). On Gen 3 (newer firmware), Gen 4, HV Gen 3, All-in-One and Gateway, charge slot 2 is at HR 243/244, as in 3.5, but the new library used the older HR 31/32, which these inverters reject (`WriteHoldingRegisterResponse(ERROR 32 ...)`). Charge slot 2 is now read and written at HR 243/244.

# GivTCP 3.6.0

Release notes for anyone upgrading from **GivTCP 3.5**. Please report problems on [GitHub](https://github.com/britkat1980/giv_tcp/issues), with a debug log if you can.

## New Modbus library

GivTCP now uses the published [givenergy-modbus](https://github.com/dewet22/givenergy-modbus) library (v2), in place of its own bundled copy of the older library. This is the biggest change in 3.6. It brings:

- **More reliable communication**, with better handling of dropped connections, retries and bad reads.
- **Better support for newer models**, including HV Gen 3, three-phase, All-in-One, EMS and Gateway systems.
- **Accurate model detection.** Each inverter's model and devices (batteries, meters, battery stacks) are detected once and saved, so later restarts are quicker. GivTCP detects again if the saved details stop matching the inverter.

Some controls aren't in the library yet. GivTCP adds them itself until it does (pause mode, per-slot target SOC, three-phase rates and others), and any it can't do fail with a clear message rather than an error.

## Upgrading from 3.5: what changes

- **Gateway energy totals jump by 1000 times once.** 3.5 published the Gateway's energy totals (Import, Export, PV, Load, Battery Charge/Discharge, Parallel Total Charge/Discharge, and each All-in-One's AC Charge/Discharge) in MWh, though labelled kWh. They're now in kWh, so they go from, for example, 12.68 to 12,682.7. For any of them used in the Energy dashboard, Home Assistant will show one very large spike in the hour you upgrade: correct it in Developer Tools → Statistics.
- **HV Gen 3 hybrids** are now read and controlled as single-phase inverters, which is what they are, rather than with the three-phase layout (which could show SOC and PV power as 0). Their Home Assistant entities change to the single-phase set, and the old ones are removed. They're no longer labelled "All-in-One".
- **AC and All-in-One:** the PV string voltage, current and power entities are removed, as these models can only measure the total from the PV inverter. PV Power (the total) remains.
- **Battery BMS Current** is renamed **Battery Pack Current**. It's each battery pack's own current from its BMS, negative while charging, and is only shown where the inverter (Gen 3 or AC from ARM firmware 214) and battery firmware (BMS 3020 or 4009 onwards) report it. Elsewhere it always read 0 A. Update any automations or dashboards that used the old name.
- **"Only report battery data and controls"** now takes effect. 3.5 ignored this setting. Inverters with it ticked (usually behind an EMS or Gateway) now publish only their battery data and controls. Untick it on the config page to publish everything.
- **The config page runs in the Home Assistant sidebar**, so it no longer needs opening by IP address. It lists inverters with no limit of five. Slots 1–5 keep REST ports 6345–6349; slot 6 onwards starts at 6356.
- **Raw register data on MQTT** (Print Raw, always on in the add-on) is published as one topic per register, for example `raw/invertor/battery_soc`, rather than the whole inverter or battery as one string.
- **Entities GivTCP no longer provides** are removed from Home Assistant automatically. Home Assistant keeps ones you've disabled, though, so delete those yourself in Settings → Entities (a restart of Home Assistant may be needed before it offers to).
- Data cached by 3.5 can't be read by the new library. It's set aside automatically and GivTCP starts afresh.

## New features

- **Log viewer** in the web UI: view, merge, filter and download each log, including rotated days.
- **Time picker controls for timeslots** (Home Assistant 2026.5 or later), alongside the drop-downs, with a setting to keep either or both.
- **Battery Pause Mode** on Gen 1 (firmware 187 or later), Gen 2, Gen 3, HV Gen 3, All-in-One, Gateway and AC (firmware 200 or later), plus the pause timeslot on models that have it.
- **Per-slot charge and discharge target SOC** on 10-slot inverters, three-phase and the Gateway. Also charge and discharge rate on three-phase inverters, and Car Charge Boost on the EMS.
- **Pause When Inverter Stops Responding** (per inverter, off by default). Some dongles crash if they're sent more requests while they're struggling. With this set, GivTCP stops sending anything for a set time when the inverter stops answering, then reconnects. Stats/status shows `paused` meanwhile, and write commands sent over REST get an immediate "not sent" reply rather than piling up.
- **Power flow entities on every model**, now including three-phase inverters and Gateways with a single All-in-One, and worked out consistently: the flows into the house never add up to more than the load, and none is negative.
- **Battery charge and discharge MOS state** for each battery and HV stack, and a **Data Age** stat showing how old the inverter data is.
- **Settings Guide and Datapoints pages** in the web UI, describing every setting and every value GivTCP publishes.
- **Warning when the inverter's clock is out** by 5 minutes or more, as it makes the Today energy counters reset at the wrong time.
- **Faster network scan:** minutes rather than up to two hours on large networks.

## Major fixes

**Controls**
- **Gateway:** all controls failed (`'GatewayV1' object has no attribute ...`), and charge/discharge rates couldn't be set. Both work now.
- **Force Charge** did nothing on 10-slot inverters when the SOC was above slot 1's target.
- **Force Export** put discharge slot 1's times into charge slot 1 when it ended.
- **Force Charge and Force Export** didn't revert when some saved settings couldn't be read, and couldn't be cancelled from REST or MQTT.
- **Eco (Paused), Enable Discharge, Set Date and Time, Export (Paused)** and several three-phase and EMS controls failed or did nothing.
- **Battery charge/discharge rate** stopped just short of the maximum (e.g. 2976 W instead of 3000 W). On HV Gen 3, full rate now shows as the inverter's maximum (e.g. 6,000 W on a 3-module stack), so Predbat's rate settings read back correctly.
- **Sync Time** could set the inverter an hour out.
- A control sent at the same moment as a poll could be lost, along with other pending controls.

**Data**
- **Gateway energy totals** were 1000 times too small (see above).
- **Today energy stats** (Load, Self Consumption, Day/Night cost) could stay on yesterday's value after midnight.
- **Gateway** battery, inverter and Liberty power had the wrong sign, and Predbat saw a frozen inverter clock on the Gateway and EMS.
- **Gateway charge/discharge target SOCs** were always empty (shown as 0, which Home Assistant rejected).
- **HV batteries:** capacity, maximum rate, and the second (and later) battery stack's module data and temperature are now correct on HV Gen 3 and three-phase.
- **Battery pause mode** stopped updating for the rest of the session after one failed read. It's now read again with the next full refresh.
- A poll where some settings couldn't be read used to fail completely. Now the last good values are used for those settings, and the live data still updates.
- **Multi-inverter setups** could show an inverter as the wrong model.

**Reliability**
- **Recovery from an unresponsive inverter without a restart.** When the inverter stops answering, GivTCP now starts a fresh connection each time it retries, rather than reusing the old one, which could keep getting no answers until the add-on was restarted. It also no longer runs a full detect while nothing is answering.
- **Fewer reconnects, and far less log noise about them.** Many dongles close an idle connection after about 10 seconds, and GivTCP now only reconnects when it has something to send. A dropped connection is only logged when it delayed a data update.
- **Quicker recovery after a restart:** the inverter settings are retried within seconds rather than up to 4 minutes later.
- **Lighter polling on HV systems:** battery module cell data is read on full refreshes only, halving each poll on a two-stack system.
- Home Assistant discovery cleanup now works on every model, and no longer fails at startup with `dictionary changed size during iteration`.
- The EVC and main logs could keep writing to the previous day's file after midnight.
- Routine messages are no longer logged as critical, and old log files keep their `.log` extension so they can be attached to a GitHub issue directly.
