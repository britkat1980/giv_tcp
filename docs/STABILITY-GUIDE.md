# Finding stable settings for your inverter

Some inverters, or their dongles, stop answering GivTCP from time to time: data stops updating for a few minutes, the log fills with timeouts, or GivTCP only recovers after a restart. Three-phase inverters with HV battery stacks seem to be the most affected, but it happens on other models too. Some inverters will even crash now and then and stop functioning completely.

There is no single set of settings that works for every system. This guide describes how to find settings that work for yours, one change at a time. The [table at the end](#settings-that-work) collects combinations that people have found to work. If you find a stable set, please add yours.

None of the settings below fixes the inverter or dongle itself. They reduce how much GivTCP asks of it, and help GivTCP recover when it stops answering.

## 1. Check the basics first

- **One local app at a time.** Every app that polls the inverter over the local network (GivTCP, another Home Assistant integration, a second GivTCP instance, a script) adds to the dongle's load. Use one. The portal goes through the cloud, so it doesn't count, but the dongle's own uploads to the cloud do add to its load, even when the cloud is blocked. On most inverters there is no way to stop cloud uploads, so this will always be active in the background.
- **A fixed IP address.** Give the dongle a DHCP reservation in your router, so it keeps the same address.
- **The connection.** On Wi-Fi, check the dongle's signal. Ethernet is usually more reliable.
- **Restart the dongle/inverter once.** If the problems started recently, power-cycle before changing anything else.

## 2. Measure before you change anything

Without a baseline you can't tell whether a change helped. Interruptions often come only a few times a day, so measure for at least 24 hours, preferably 48, before and after each change.

Set the **Log Level** to Debug on the config page while you measure. Some of the lines below are only logged at debug level. Set it back afterwards, as debug logs grow quickly.

The log is in `/config/GivTCP/logs/log_inv_1.log` (one per inverter), and you can also read it with **Logs** in the web UI. These lines tell you what happened:

| Log line | Level | Meaning |
|---|---|---|
| `Error num N in watch loop read: RefreshFailed: all N register reads failed` | debug | The inverter didn't answer anything in that poll. This is the main thing to count |
| `N register reads failed, using partial data` | debug | Some reads in a poll weren't answered. A few a day is normal |
| `Inverter not responding (2 failures in a row), sending it nothing for Ns` | warning | Pause When Inverter Stops Responding started a pause |
| `Recovery pause over, reconnecting to the inverter` | info | The pause ended. Check whether the next poll worked |
| `Unable to read all the inverter settings after connecting` | warning | The first read after GivTCP started failed (see Wait After Connecting) |
| `Inverter closed the Modbus connection` | debug | The dongle closed an idle connection. After most polls, this means the dongle has a short idle timeout |
| `Registers HR ... could not be read 3 times in a row` | info | Your firmware doesn't have an optional setting. Harmless, and not a stability problem |

You can also watch the **Time Since Last Update** and **Data Age** entities in Home Assistant: long gaps are interruptions.

To count the main events in a log file:

```
grep -c "RefreshFailed: all" log_inv_1.log
grep -c "Inverter not responding" log_inv_1.log
grep -c "Recovery pause over" log_inv_1.log
```

Write down the numbers per day, and whether GivTCP had to be restarted.

## 3. Change one setting at a time

Change one setting, measure again for 24-48 hours, and compare. If you change several at once, you won't know which one helped, and that's what the table at the end needs.

The settings are on the config page: the timers are in the **Self Run** section, and the others are per inverter, on the **Inverter Config** page. Restart GivTCP after saving, as the config page asks, for a change to take effect.

A suggested order, from the least to the most specific:

### 3.1 Read less often

- **Self Run Loop Timer** (default 30 s): how often GivTCP reads the inverter's live data. Try 60 s or more.
- **Self Run Loop Timer (Full)** (default 120 s): how often GivTCP also reads all the settings, which is much more work for the inverter. Make it a multiple of the loop timer. Try 4 or 5 times the loop timer first, and much longer (eg. 30-60 minutes) if your settings rarely change outside GivTCP. If your inverter reports to cloud, it will send its data to all connected devices. Reporting to cloud happens every 5 minutes. The result is, that setting a timeline for full reads beyond 300s doesn't mean that your data is not updated. Updates just follow the inverters internal schedule.

A full refresh is many more requests than a normal poll, so the full timer often matters more than the loop timer. The trade-off: changes made outside GivTCP (in the GivEnergy app, for example) show up later.

### 3.2 Skip Reads Fresher Than

In the Self Run section (default 0, off). The dongle passes on its answers to other requests, such as the cloud's, to GivTCP too. With this set, GivTCP skips reads it got such an answer for within this many seconds. Try a value a bit below the loop timer (eg. 45 s with a 60 s timer).

### 3.3 Pause When Inverter Stops Responding

Per inverter (default 0, off). When the inverter doesn't answer 2 polls in a row, GivTCP closes the connection and sends it nothing for this many seconds, then reconnects with a new connection. Without it, GivTCP keeps retrying every few seconds, which can keep a struggling dongle from recovering.

Start with 300-600 s. If the first poll after `Recovery pause over` usually fails and another pause starts, try a longer pause. If it usually works, you can try a shorter one. Write commands sent during a pause are answered at once with "not sent", and Stats/status shows `paused`.

### 3.4 Wait After Connecting

Per inverter (default 0, off). Some dongles don't answer requests sent straight after a connection opens, so the first poll after a restart or after a pause fails. Use this if you see `Unable to read all the inverter settings after connecting` after most restarts, or a failed poll straight after most `Recovery pause over` lines. Try 5-10 s.

Keep it below the dongle's idle timeout: many dongles close a connection after about 10 seconds without traffic. If you see `Inverter closed the Modbus connection` after most polls, your dongle is one of these: keep this well below 10 s, or leave it off.

### 3.5 Lite mode

Per inverter (default off), only for HV battery stacks: three-phase and HV Gen 3. Every read of a battery stack or battery module is passed on by the inverter to the battery. In lite mode GivTCP reads each battery module only until it has data, and each stack only on full refreshes. SOC, battery power, current and voltage are still read every poll. Module and stack values usually keep updating anyway, because the dongle reads them itself for the cloud and passes the answers on to GivTCP. Lite mode for Hybrid 3 phase Gen 3 and HV Gen 3 use this to reduced the load on the inverter even further and only query data this must be refreshed in intervals shorter than 5 minutes. For the rest it relies on the dongle automatic refreshes. 

### 3.6 Use latest dongle firmware

Use the latest version of the dongle firmware. You can uodate the firmware with the GivInstaller app. Be careful when updating the firmware of the inverter and the battery stack. Givenergy has gone out of commission. If it is broken, it is broken. Unless your installer still got some spare parts. That said, newwer versions could indroduce new bugs. For instance the latest version for the Hybrid 3ph 11kW is tuck in "force charge" mode when PV panels are connected. So the PV panels charge the battery, but will refuse to deliver power to the grid or the house when be battery is full.

### 3.7 Security warning

If you don't use GivEnergy cloud, block your inverter access to the Internet on your router. All communication is cleartext and not authenticated. Taking over control of your inverter is not trivial, but not that hard either.

## 4. When you've found settings that work

Add a row to the table below, through a pull request or by posting it in an issue. Include what you can: a row with only some columns filled in is still useful. Leave out serial numbers and IP addresses.

## Settings that work

Timers are in seconds. Results are "before → after", in interruptions per day, from a log of at least 24 hours on each side. "Restarts" means GivTCP had to be restarted, by hand or by an automation.

| Inverter (model, DTC) | Inverter firmware | Inverter software | Battery | Stack firmware | PV | Dongle, connection | Cloud | Loop timer | Full timer | Skip Reads Fresher Than | Pause When Not Responding | Wait After Connecting | Lite mode | GivTCP version | Result | Who / issue |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3-phase hybrid Gen3 11kW | ZAAA090909 | ZA1.0 | HV, 6 modules | BABA0009 | 2 strings 11kWp & AC-Coupled 1.8kWp | Ethernet | Blocked | 60 | 3600 | 45 | 600 | 10 | On | 3.6.14 | Before: 5-6 interruptions per day that needed restarts, with inverter hard crashes every week. After: 1-2 pauses per day that recover automatically, no restarts | @lancer73 |
| HV Gen 3 | | | HV, 10 modules | | | Ethernet | Active | 90 | 360 | 0 | 600 | 0 | On | 3.6.15 | Before: Daily crash. After" Runs stable with 1-2 pauses per day. | @RogueCarbon |
| | | | | | | | | | | | | | | |

### What the columns mean

- **Inverter:** the model as GivTCP shows it at startup (eg. `Hybrid_gen1(2003)`), so with the device type code in brackets.
- **Inverter firmware/software/Stack firmware:** from the inverter's firmware entities in Home Assistant, or the GivEnergy portal.
- **Battery:** LV or HV, number of batteries or modules (and stacks), capacity if you know it.
- **PV:** strings and kWp, or "AC-coupled".
- **Dongle, connection:** Wi-Fi or Ethernet, and the dongle type or firmware if you know it.
- **Cloud:** whether the dongle can reach the GivEnergy cloud (Connected / Blocked).
- **Result:** before and after, and anything that's still not right.
