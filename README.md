# GivTCP

GivTCP connects to GivEnergy devices over the local network and makes their data and controls available to Home Assistant, MQTT, REST and InfluxDB. It supports:

- Hybrid inverters (Gen 1, Gen 2, Gen 3 and Gen 4)
- HV Gen 3 hybrid inverters, with one or more HV battery stacks
- AC-coupled inverters
- Three-phase hybrid and AC-coupled inverters
- All-in-One
- Gateway (single All-in-One or parallel)
- EMS
- EV Charger (EVC)

GivTCP talks Modbus to each device through its own WiFi/Ethernet dongle, over your LAN or the dongle's built-in access point. It can find devices on the network itself, for a (near) zero-config setup. It uses the [givenergy-modbus](https://github.com/dewet22/givenergy-modbus) library, and adds a few controls the library doesn't support yet.

GivTCP usually runs as a Home Assistant add-on, but can also run as a standalone Docker container.

<a href="https://www.buymeacoffee.com/givtcp" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>

## Quick set-up

### Install GivTCP

#### Home Assistant add-on
- Add https://github.com/britkat1980/ha-addons to the add-on store repositories in Home Assistant.
- Refresh the add-on store, click GivTCP and click Install.

The add-on uses Home Assistant's Mosquitto broker add-on if it's installed, and connects to it automatically. Otherwise, install an MQTT broker and enter its details on the config page.

#### Docker
- Download [docker-compose.yml](https://github.com/britkat1980/giv_tcp/blob/main/docker-compose.yml) into a folder of its own, set your timezone (`TZ`) in it, and run `docker compose up -d` there. GivTCP keeps its settings, captures and logs in a `config` folder next to the file.
- It uses host networking, so GivTCP can scan your network for inverters (Linux). On Docker Desktop (Windows/macOS), or to use a bridge network, follow the comments in the file to map the ports instead, and add your inverters by their IP address on the config page, as GivTCP can't scan your network from there.
- Without Home Assistant, MQTT is off until you enter a broker on the config page. To use GivTCP's own broker, enter `127.0.0.1`. With an MQTT username and password set on the config page, GivTCP's broker only accepts those (so anything else that uses it, such as Home Assistant's MQTT integration, needs them too). Without them it accepts anyone on your network.

### Start GivTCP

- Start the add-on or container.
- On first start GivTCP scans your network for GivEnergy inverters and EV chargers, then detects each inverter's model, batteries and meters. It saves what it finds, so later starts are quicker. It detects again by itself if an inverter stops matching what was saved.

### Configure GivTCP

- Open the config page:
  - **Home Assistant:** from the GivTCP entry in the sidebar (or "Open Web UI" on the add-on page). To open it at http://IPADDRESS:8099/config.html from other devices too, turn on **LAN Access** in the Web section: without it, port 8099 only accepts Home Assistant, so a Home Assistant login is needed.
  - **Docker:** http://IPADDRESS:8099/config.html
- Step through the sections. The inverters found by the scan and your MQTT details should already be filled in.
  - **Inverter Config:** add or remove inverters. There's no limit on the number, and inverters found by the last scan can be added in one click.
  - **Self Run:** turn on **Self Run**, and **Home Assistant Auto Discovery** if you use Home Assistant.
  - **MQTT:** only needed if you use an MQTT broker other than the Home Assistant add-on.
- Click **Save and Restart**. With Docker, restart the container yourself (`docker compose restart`).

<img src="docs/images/config-1.png" width="400">
<img src="docs/images/config-2.png" width="400">
<img src="docs/images/config-3.png" width="400">

GivTCP should now be publishing data to your MQTT broker, and Home Assistant should pick it up automatically.

### Check Home Assistant (optional)

Once GivTCP has restarted:
- Go to Settings → Devices & services → MQTT.
- Check the GivTCP devices have been created.

You should now have lots of data and controls in Home Assistant to build into your smart home. See the [Settings Guide](docs/SETTINGS-GUIDE.md) for more on the controls, and [Datapoints](docs/DATAPOINTS.md) for every value GivTCP publishes.

### Parallel All-in-One

With parallel All-in-Ones, the Gateway and each All-in-One (three inverters for a dual All-in-One) should be listed on the Inverter Config page. Add any that are missing, and give them all static IP addresses. Control the system through the Gateway only, and treat each All-in-One's data as information.

## Web UI

The web UI (the config page, opened as above) has a menu with:

- **Config:** the settings, described in the [Settings Guide](docs/SETTINGS-GUIDE.md).
- **Readme:** this page.
- **Settings Guide** and **Datapoints:** what each setting does, and every value GivTCP publishes.
- **Share Device:** helps GivTCP support more devices. It captures a few minutes of your inverter's Modbus data (with serial numbers and IP addresses removed), which you can download and attach to a pre-filled GitHub issue, to be added to the library of real devices GivTCP is tested against.
- **Dashboard:** the web dashboard, if it's turned on (see below).
- **Logs:** a log viewer for each inverter's main, write and REST logs, the startup log and the EV charger log. Tick one log to see it on its own, or several to merge them into one timeline. You can pick an earlier day, filter by level or text, follow new lines as they're written and download a log, for example to attach to a GitHub issue. The logs are kept for 7 days in `/config/GivTCP/logs`.

## Home Assistant

GivTCP is designed to run all the time. Once the settings have been checked, turn on Self Run. You can change how often it reads the inverter on the config page (Self Run Loop Timer, and the Full timer for the settings and energy totals), but it's not recommended to go below 30 seconds.

GivTCP creates a device in Home Assistant for each inverter, battery and meter. You can find them under the MQTT integration.

<img src="docs/images/config-4.png" width="400">

Timeslots can be shown as drop-downs, as time pickers (Home Assistant 2026.5 or later) or both: see "Timeslot entities in Home Assistant" on the Misc page. If you switch, update any automations that set them: a drop-down takes the time as `HH:MM:SS` and a time picker as `HH:MM`. Entities a model doesn't support are removed from Home Assistant automatically. Home Assistant keeps entities you've disabled, though, so delete those yourself in Settings → Entities.

## Other ways to use GivTCP

GivTCP's data and controls are also available over MQTT and REST, for other systems and your own scripts.

### MQTT

With MQTT turned on, GivTCP publishes all the inverter's data to your MQTT broker, under `GivEnergy/<serial_number>/` by default, or under the topic set on the MQTT page.

<img src="docs/images/config-5.png" width="400">

With **Print Raw** on (the Misc page; always on in the add-on), the inverter's raw register values are also published under `<topic>/<serial_number>/raw/`, one topic per register, for example `raw/invertor/battery_soc`.

You can also control the inverter over MQTT by publishing to:

- `GivEnergy/control/<serial_number>/` by default (note the lower-case "control")
- `<topic>/control/<serial_number>/` if you've set a topic

### REST

GivTCP has a REST API for data and control. Each inverter's API is at http://IPADDRESS:8099/REST1/, /REST2/ and so on (in the add-on, with LAN Access on), numbered by its slot on the Inverter Config page. Call `REST1/api` to list the calls available.

To protect the controls, set a **REST API Key** in the Web section (16 to 128 letters, digits, `-` or `_`). Every call except the read-only data (`/readData`, `/getCache`, `/runAll`, `/getEVCCache`, `/api`, `/captureStatus`) then needs it, as an `X-API-Key: <key>` or `Authorization: Bearer <key>` header. GivTCP's own pages add it themselves. Only set one if everything that sends commands to GivTCP's REST API (for example a `rest_command` in Home Assistant, or Predbat if you use its REST mode) can send it. Requests from another website's page in your browser are always refused.

Each inverter's API also has its own port, which is what you use with Docker in host mode: slots 1–5 use ports 6345–6349 (as in earlier versions, so existing Predbat and Home Assistant setups keep working), and slot 6 onwards use port 6356 onwards.

## Web Dashboard

You can turn on the built-in web dashboard to see your inverters' data at a glance. Turn it on in the Dashboard section of the config page. It runs on port 3000 by default.

For more details see the [ReadMe in its own repository](https://github.com/DanielGallo/GivEnergy-Smart-Home-Display/).

<img src="https://github.com/DanielGallo/GivEnergy-Smart-Home-Display/blob/master/graphics/ReadMe-Landscape.png" width="400">

The dashboard can show a single inverter, or several in a single-phase or three-phase system. If you have any issues or feedback about it, please post them [here](https://github.com/DanielGallo/GivEnergy-Smart-Home-Display/issues).

## GivEnergy EV Charger (GivEVC)

GivTCP can monitor and control the GivEnergy EV charger over local Modbus: live stats, plus simple controls. The charger's cloud control doesn't use Modbus, so changes made through GivTCP may not show in the GivEnergy app or portal. In particular, the charging modes are only imitated by GivTCP.

Note: charger firmware up to v1.12 only offers Modbus over WiFi. If your charger is connected by Ethernet, connect it by WiFi instead to get data in GivTCP. Or ask GivEnergy to update the firmware to v1.13, then enable local control in the GivEnergy portal: expand the "My EV Charger" card → Settings → Other → "Enable Local Control".

### Configuration

Set the charger's IP address and the timer on the config page's EVC section, and turn on EVC Enable.

### Controls

Most controls are self-explanatory, but some need explaining:

#### Plug and Go

When on, the vehicle starts charging as soon as it's plugged in. When off, charging starts when triggered by an RFID card or by Charge Control.

#### Charge Control

Starts and stops charging when Plug and Go is on.

#### Charging Mode

Imitates the cloud's charging modes:

- **Grid:** charges at the Charge Limit, whatever energy is available (typically drawing from the grid).
- **Solar:** adjusts the Charge Limit to the solar left over after the house load. The EVSE spec needs at least 1.4 kW (6 A) of excess.
- **Hybrid:** a constant 6 A from the grid, topped up with any excess solar.

#### Max Session Energy

Caps the energy delivered to the vehicle in one charging session. 0 kWh turns it off.

#### Import Cap

Watches the grid current from the first GivTCP inverter. If it comes within 5% of the Import Cap, the charging current is reduced to stay 10% below it. 0 A turns it off.

## Upgrading from 3.5

3.6 uses the new [givenergy-modbus](https://github.com/dewet22/givenergy-modbus) library, so some things change on upgrade:

- **HV Gen 3 hybrids** are read as single-phase inverters, which is what they are, so their Home Assistant entities change to the single-phase set.
- **AC and All-in-One:** the PV string voltage, current and power entities are removed, as these models can't measure individual strings. PV Power (the total) remains.
- **Battery BMS Current** is now **Battery Pack Current**, and only shown where the inverter and battery firmware report it.
- **"Only report battery data and controls"** now takes effect: 3.5 ignored it.
- Data cached by 3.5 can't be read by the new library. It's set aside automatically and GivTCP starts afresh.

The full list of changes is in the [change log](https://github.com/britkat1980/giv_tcp/blob/main/CHANGELOG.md).

## Advanced

Some tips for troubleshooting your inverter or GivTCP.

### Finding devices

GivTCP scans your network for inverters and EV chargers when it starts, the host's own /24 first. A large network such as a /16 takes a few minutes, and networks larger than a /16 are limited to the /16 around the host.

To skip the scan, turn off **Auto Scan** (Self Run section of the config page) and make sure each inverter's IP address is set on the Inverter Config page. Give your inverters static IP addresses, so they're found at the same address each time.

### Timeouts and an unresponsive inverter

If you see many timeouts in the log, or large jumps in the Time Since Last Update or Data Age entities, the inverter or its dongle may be overloaded. Three-phase inverters with several batteries are the most affected. GivTCP recovers from dropped connections by itself, but you can reduce the load on the inverter:

- **Read less often:** set a longer Self Run Loop Timer, e.g. 60 seconds or more, with the Full timer a multiple of it (e.g. 90 and 270).
- **Pause When Inverter Stops Responding** (each inverter, on the Inverter Config page): if the inverter stops answering, GivTCP sends it nothing at all for this many seconds, then reconnects, giving it time to recover. Stats/status shows `paused` meanwhile. Some dongles crash if they're sent more requests while they're struggling, and this has prevented that. Write commands sent over REST during the pause get an immediate "not sent" reply, and other commands (such as the end of a force charge) are sent once it's over.
- **Lite mode** (each inverter, on the Inverter Config page; for HV battery stacks, so three-phase and HV Gen 3): the inverter passes every read of a battery stack or battery module on to the battery, which adds to its load. In lite mode GivTCP reads each battery module only until it has data, and each battery stack only on full refreshes. The inverter's own battery figures (SOC, battery power, current and voltage) are still read every poll, and SOC kWh is worked out from them, so the live data and the controls are unaffected. You'll usually still see the battery modules' cell voltages and temperatures update: the dongle reads them itself to send to the GivEnergy cloud, and passes every answer it gets on to GivTCP too. On one system they still updated every 5 to 10 minutes, with the dongle's connection to the cloud blocked. Without that, the module values stay as GivTCP read them when it started, and the stack values (stack voltage, current, power, cycles and energy) update with each full refresh.
- **Wait After Connecting** (each inverter, on the Inverter Config page, off by default): some dongles don't answer requests sent straight after a connection opens. GivTCP sends its first requests within milliseconds of connecting, and they all time out, so the first poll after a restart or after a recovery pause fails (in the log: "Unable to read all the inverter settings after connecting" at startup, or a failed poll straight after "Recovery pause over"), while a minute later the same reads work. With this set, GivTCP waits this many seconds after every new connection before sending anything. A failed poll right after a pause counts towards the next pause, so this matters most with Pause When Inverter Stops Responding. Many dongles close a connection after about 10 seconds without traffic, and then reconnect for every poll. On those, keep this well below 10 seconds or leave it off: if the wait is longer than the dongle's idle time, it closes the connection before GivTCP sends anything, and no data comes in at all. If your log shows "Inverter closed the Modbus connection" at debug level after most polls, your dongle is one of these. Dongles that keep the connection open between polls are only affected when GivTCP connects, so a longer wait (eg. 15 seconds) costs a few seconds after a restart or a pause.
- **Skip Reads Fresher Than** (Self Run section): skips reads the dongle has just answered for another app polling it, such as the GivEnergy app.

### Battery settings

Two settings on the Inverter Config page, for each inverter:

- **Only report battery data and controls:** for an inverter behind a Gateway or EMS, which reports the plant's power and energy itself. GivTCP leaves out this inverter's power and energy data, and still publishes its battery data, controls, timeslots and status, and its own details such as its clock and firmware.
- **No battery fitted:** for a hybrid running without a battery, so GivTCP stops checking it for one. When detect finds no battery on a hybrid, GivTCP checks again from time to time in case the battery didn't answer, backing off to hourly. Without this setting, it stops by itself after 5 detects in a row find none, until GivTCP restarts. AC-coupled inverters and All-in-Ones always have a battery, so GivTCP doesn't save a detect that finds none for them, and keeps trying.

## Development

See the [development guide](DEVELOPMENT.md) for testing, coverage, frame pacing, and extending the test harness.
