# Shared device captures

Captures users have shared from GivTCP's **Share Device** page, attached to GitHub issues titled "Device capture: ...".
givenergy-modbus redacts them as they're made (serial numbers keep their prefix and date with the unit digits zeroed,
and IP addresses are removed). They're stored here as received, renamed to `.capture`. None is in the harness's
`DEVICES` yet: to use one, add it there (see `../README.md`).

| File | Issue | Device | Firmware | Devices found | Notes |
|---|---|---|---|---|---|
| `hybrid_gen1_arm187_issue624.capture` | #624 | Hybrid Gen 1 (DTC 2003) | ARM/DSP 187 | 2 LV batteries (BMS 3022) | Every full refresh, the IR 0-59 reply has registers 28-59 replaced by the IR 180 block. The library rejects it and re-reads |
| `all_in_one_8003_arm620_issue627.capture` | #627 | All-in-One (DTC 8003) | ARM/DSP 620 | 4 battery modules, 1 BCU stack | |
| `all_in_one_8001_arm620_issue631.capture` | #631 | All-in-One (DTC 8001) | ARM/DSP 620 | 4 battery modules, 1 BCU stack | |
| `ems_arm1036_issue632.capture` | #632 | EMS (DTC 5001) | ARM 1036 | 2 meters | Captured on 3.6.3, which doesn't poll IR 0-59: the IR 0-59 replies in it are the cloud's polls, relayed by the dongle (#635) |
| `ac_3001_arm282_issue638.capture` | #638 | AC (DTC 3001) behind an EMS | ARM 282, DSP 291 | 1 LV battery (BMS 4009) | Also reads LV battery addresses 0x30-0x37 once (detect) |
| `ems_arm1036_issue638.capture` | #638 | EMS (DTC 5001) with 2 AC inverters | ARM 1036 | 2 meters | Same plant as the AC above. As #632, its IR 0-59 replies are the cloud's polls |
| `hybrid_3ph_4006_issue667.capture` | #667 | Three-phase hybrid (DTC 4006) | ARM 0 (as reported) | 3 BCU stacks of 6 HV modules, 1 meter | The first three-phase capture with several stacks |
| `hybrid_gen1_2001_arm451_issue666.capture` | #666 | Hybrid Gen 1 (DTC 2001) | ARM 451, DSP 450 | 1 LV battery (BMS 3022) | The original Gen 1 firmware, which doesn't answer HR 313-314 or HR 318 (#655) |
