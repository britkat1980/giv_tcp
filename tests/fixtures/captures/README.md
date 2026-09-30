# Wire captures

Real, serial-redacted GivEnergy wire captures, used by the test harness to serve each device model from a
`givenergy_modbus.testing.MockPlant`. They come from the
[givenergy-modbus](https://github.com/dewet22/givenergy-modbus) project (`tests/fixtures/captures/`),
Copyright (c) 2021 Dewet Diener, used under the Apache License 2.0. They are unchanged apart from the file name.

| File | Upstream file | Device |
|---|---|---|
| `hybrid_gen1.capture` | `hybrid_2_bat_a/hybrid_gen1_arm449_0x11_poll_10min.log` | Hybrid Gen 1, ARM 449, 2 LV batteries |
| `hybrid_gen2.capture` | `hybrid_gen2_1_bat_a/hybrid_gen2_arm920_60s.log` | Hybrid Gen 2, ARM 920, 1 LV battery |
| `ac.capture` | `ems_2_inv_3_bat_a/ac_arm282_2x_givbat52_30min.log` | AC, ARM 282, 2x Giv-Bat 5.2 |
| `all_in_one.capture` | `aio_a/aio_arm612_5min.log` | All-in-One, ARM 612 |
| `ems.capture` | `ems_2_inv_3_bat_a/ems_arm1036_60s.log` | EMS, ARM 1036 |
| `gateway.capture` | `gateway_2aio_a/gateway_gaaa0014_10min_night.log` | Gateway GA0014 with 2 AIOs |
| `hybrid_3ph.capture` | `three_phase_hv_a/giv3hy11_da011_detect_10min.log` | Three-phase hybrid, HV battery |
| `hybrid_hv_gen3.capture` | `hybrid_hv_gen3_a/givhy80g3hv_hass295_120s.log` | Hybrid HV Gen 3 (8 kW). The capture has no identity block (HR 0-59), so the harness adds one (see `harness/devices.py`) |

To add a device, capture it with `givenergy-cli capture` (which redacts serials), save it here as `<name>.capture` and an
entry to `DEVICES` in `tests/harness/devices.py`, then run the tests with `--update-golden`.
