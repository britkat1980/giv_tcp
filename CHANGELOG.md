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
