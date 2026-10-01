# Draft requests for dewet22/givenergy-modbus

Found while porting GivTCP to givenergy-modbus 2.12.0 (GivTCP `modbusv2` branch). Each section below is written to be posted as its own issue. The first three block features GivTCP users rely on today; the rest are smaller.

Thanks again for the migration guide and the offer of help in britkat1980/giv_tcp#556. The port has gone smoothly apart from these points.

---

## 1. Allow battery pause mode / pause slot writes (HR 318–320), firmware-gated where needed

**Problem**

`one_shot_command()` rejects HR 318 (battery pause mode) and HR 319/320 (pause slot start/end) for every model. `WRITE_SAFE_SINGLE_PHASE` excludes them as "firmware-gated", but `write_safe_registers()` never adds them back: its docstring notes that `arm_fw` is accepted but no write capability is firmware-gated yet. `WRITE_SAFE_AC_CONFIG` doesn't include them either, even though `has_ac_config_block` describes 318–320 as part of that block on AC and All-in-One.

So `set_battery_pause_mode()`, `set_pause_slot()`, `set_pause_slot_start()` and `set_pause_slot_end()` can't be used on any model:

```
InvalidPduState: HR(318) is not permitted for HYBRID_GEN1 inverter
```

The registers pass `WriteHoldingRegisterRequest.ensure_valid_state()`, since they're in `WRITE_SAFE_REGISTERS`. Only the per-model gate blocks them.

**Evidence that these writes work**

- On **Gen 1 hybrids with ARM firmware 187** (D0.187-A0.187, the firmware that added real-time control), GivTCP on the old async fork wrote pause mode successfully. Logs from two Gen 1 hybrids in britkat1980/giv_tcp#441:
  `Setting Battery Pause Mode to PauseDischarge was a success` / `... to Disabled was a success`. That user drives it from Predbat daily.
- The GivTCP maintainer's own Gen 1 hybrid (DTC 2003) is also on ARM firmware 187 and now fails with the error above.
- The manifest already describes pause mode/slot as present on AC and All-in-One.

**Request**

1. Add 318–320 to the write-safe set for `AC` and `ALL_IN_ONE`, where the manifest already says they exist.
2. Implement the firmware gate `write_safe_registers(model, arm_fw)` already allows for, so 318 (and 319/320 if confirmed) is allowed on single-phase hybrids at or above the first firmware that supports pause. 187 is confirmed on Gen 1; we don't know the exact first version for Gen 1, 2 or 3. GivTCP users can supply captures or test builds.
3. Reading the state needs the same gate. `load_config()` only reads HR(300-359) for `has_ac_config_block` models (hybrids time out on the whole block, per #162). A narrow read such as HR(318, 3) for pause-capable hybrids would let consumers show the current pause mode.

**GivTCP workaround:** `GivTCP/modbus_patches.py` adds HR 318-320 to the write-safe set for `ALL_IN_ONE`, `GATEWAY`, `HYBRID_GEN2`, `HYBRID_GEN3`, `HYBRID_HV_GEN3`, and `HYBRID_GEN1` from ARM firmware 187, and HR 318 only for `AC` (it has pause mode but no pause slot). Three-phase and EMS have no pause functions. It reads HR(318, 3) after `load_config()` on the models without the AC config block. The Gateway model has no pause fields, so GivTCP decodes them from its register cache. Remove it once the library supports this.

Impact: Predbat uses pause mode to hold the battery (for example "freeze" and "hold for car"). Without these writes it can't do that on any GivEnergy inverter through GivTCP v2.

---

## 2. Per-slot charge/discharge target SOC writes for 10-slot inverters

**Problem**

On models with `has_extended_slots`, the library reads `charge_target_soc_1..10` (HR 242, 245, … stride 3) and `discharge_target_soc_1..10` (HR 272, 275, …). There's no command helper to write them, and the registers aren't in any write-safe set. `set_charge_target_soc()` (thanks for #243) covers only the single HR 116 target.

GivTCP exposes per-slot targets as Home Assistant controls, and users automate them (Predbat, Octopus tariffs). On v2 these writes can only fail.

**Request**

- Helpers such as `set_charge_slot_target_soc(idx, soc)` / `set_discharge_slot_target_soc(idx, soc)`, resolving registers from the slot map the way `set_charge_slot_start(idx, …)` does.
- Add those registers to the write-safe set for `has_extended_slots` models.

---

## 3. Charge/discharge rate writes on three-phase, HV Gen 3 and Gateway

**Problem**

- `ThreePhaseInverter` reads `battery_charge_limit_ac` at **HR 1110** and `battery_discharge_limit_ac` at **HR 1108** (the manifest notes three-phase remaps the AC-config controls there). Neither is in `WRITE_SAFE_THREE_PHASE` and there's no command helper, so a consumer can't set the charge/discharge rate on three-phase or HV Gen 3. The old async fork wrote these as `TPH_BATTERY_CHARGE_LIMIT_AC = 1110` / `TPH_BATTERY_DISCHARGE_LIMIT_AC = 1108`.
- `set_battery_charge_limit_ac()` / `set_battery_discharge_limit_ac()` write HR 313/314, which are only write-safe with the AC-config block, so only on `AC` and `ALL_IN_ONE`.
- On a **Gateway**, none of 313/314/1108/1110 are write-safe, and HR(300-359) isn't read. givenergy-modbus#373 settled the routing: the Gateway controls the AIOs behind it, and a capture showed GivTCP setting the AC charge/discharge limit (HR 313/314) on the Gateway at device 0x11. The library's own Gateway capture (`gateway_gaaa0014`) includes the whole HR(300-359) block, and a Gateway on firmware A0.014 answers live reads of it (HR 313/314 = 50/100). HR 111/112 read 0 on a Gateway, so the AC pair is its rate control.

**Possible inconsistency to check**

`ThreePhaseInverter.set_battery_soc_reserve()` correctly writes the three-phase shadow HR 1109. But on the same class, `set_battery_charge_limit()` writes HR 111, `set_battery_discharge_limit()` writes HR 112 and `set_battery_power_reserve()` writes HR 114, all single-phase registers. `WRITE_SAFE_THREE_PHASE` includes 1078, which the old fork used as `TPH_BATTERY_DISCHARGE_MIN_POWER_RESERVE`. Could you confirm whether those three helpers should route to three-phase registers on `ThreePhaseInverter`?

**Request**

- Three-phase helpers (or model-aware routing) for the AC charge/discharge limits at 1110/1108, added to `WRITE_SAFE_THREE_PHASE`.
- Add `Model.GATEWAY` to `has_ac_config_block`, so `load_config()` reads HR(300-359) and HR 313/314 are write-safe.

**GivTCP workaround:** `GivTCP/modbus_patches.py` adds HR 313/314 to the write-safe set on `GATEWAY`, and reads HR(313, 8) after `load_config()` there (which also covers the pause registers from item 1).

---

## 4. EMS model: identity and energy totals

**Problem**

The v2 `Ems` model exposes the EMS page registers (slots, targets, meter and inverter summaries) but none of the identity or energy fields the old fork provided. Accessing any of these on `plant.ems` raises `AttributeError`:

`serial_number`, `model`, `firmware_version`, `system_time`, `status`, `p_inverter_active`, `grid_port_max_power_output`, `enable_plant_control` (possibly now `plant_enabled`), and the energy counters `e_grid_in_day`, `e_grid_in_total`, `e_grid_out_day`, `e_grid_out_total`, `e_generation_day`, `e_generation_total`, `e_pv_generation_total`, `e_inverter_in_total`, `e_inverter_out_today`, `e_ac_charge_today`. Only `e_active_generation_total` is present.

Related GivTCP report: britkat1980/giv_tcp#538. The EMS "generation today" should come from the generation meter's `e_pv1_day`, not the inverter output.

**Request**

- Identity (serial, model, firmware, system time) for EMS from the HR(0-59) block every device answers.
- The EMS energy counters, if they're in registers the library can read. An EMS owner has offered GivTCP remote access for testing (britkat1980/giv_tcp#499).

---

## 5. Consistent device identity and model across device types

**Problem**

- `GatewayV1`/`GatewayV2` and `Ems` have no `serial_number`, `model` or `arm_firmware_version`. GivTCP now reads identity from `plant.inverter` **before** setting capabilities (the HR 13–17 serial and HR 0 DTC), which works but relies on an unguaranteed detail.
- `SinglePhaseInverter.model`, decoded from the raw DTC, disagrees with `detect()` for some families. DTC **0x8102** decodes as `Model.ALL_IN_ONE`, while `detect()` resolves the same unit as `HYBRID_HV_GEN3`. GivTCP users saw Gen 3 HV inverters labelled "All-in-One" (britkat1980/giv_tcp#565).

**Request**

- A common identity accessor, for example `Plant.identity` → serial, DTC, model and ARM/DSP firmware, valid for any device type and available after a single HR(0,60) read.
- `model` on the device classes should match the model `detect()` resolves, or be documented as a coarse DTC-family decode.

---

## 6. Capability naming: `is_three_phase` vs "uses the 1000-range registers"

`HYBRID_HV_GEN3` and `ALL_IN_ONE_HYBRID` report `is_three_phase = True` because they use the HR/IR 1000-range layout, and `select_inverter()` returns `ThreePhaseInverter` for them. Consumers naturally read `is_three_phase` as "electrically three-phase". GivTCP used it to choose three-phase UI and processing for single-phase HV Gen 3 units.

**Update (2.13.0):** `HYBRID_HV_GEN3` is no longer in `is_three_phase` (hass#295), which resolves this for HV Gen 3. `ALL_IN_ONE_HYBRID` is still the one model where the flag means the register layout rather than the phase count.

**Request:** consider a separate capability for the register layout (for example `uses_extended_register_map`), keeping `is_three_phase` for electrical phase count. At minimum, document the current meaning in the property docstring.

---

## 7. Total battery count across battery architectures

`Plant.number_batteries` counts only LV battery addresses. HV stacks (`bcu_stacks` module counts), HV BMUs and AIO modules aren't included, so HV and three-phase systems report 0. You flagged this as a migration trap in giv_tcp#556. GivTCP now computes `max(lv, sum(bcu modules), aio modules, hv bmus)` itself.

**Request:** a property that gives the total installed battery modules across architectures, for example `Plant.number_battery_modules`.

---

## 8. Public signal for batteries awaiting cold-start corroboration

After a fresh connect, the first battery frame is held pending a corroborating read ("serving unknown meanwhile"), so `Battery.is_valid()` is `False` on the first poll. That's sensible, but consumers can't tell this state apart from a missing or failed battery without reading the private `Plant._splice_pending_baseline`. GivTCP now counts consecutive empty polls instead.

**Request:** a public accessor, for example `Plant.battery_pending(address) -> bool` or a pending set, so consumers can show "waiting for confirmation" rather than an error.

---

## 9. `one_shot_command()` default timeout/retries

`one_shot_command()` defaults to `timeout=1.5, retries=0`, tighter than `refresh()`'s `2.0 / 1`, which that docstring explains is tuned for a contended bus (#132). Writes were failing with a bare timeout on busy dongles, especially straight after a full `load_config()`. GivTCP now passes `timeout=3.0, retries=2`, relying on the library skipping a resend whose response already arrived.

**Request:** consider matching the read defaults, or documenting that register writes are safe to retry and recommending a budget for contended buses.

---

## 10. EMS car charge boost write (HR 2073)

**Problem**

The v2 `Ems` model reads `car_charge_boost` at **HR 2073**, but there's no command helper to write it, and 2073 isn't in the EMS write-safe set (the EMS block allowlist stops at 2071). The old async fork wrote it with `set_car_charge_boost(val)`, valid 0–22000 W. GivTCP exposes Car Charge Boost as a Home Assistant control, so on v2 it can only fail.

**Request**

- A helper such as `Ems.set_car_charge_boost(watts)`, bounded 0–22000.
- Add HR 2073 to the EMS write-safe set.

---

## 11. Gateway write commands

**Problem**

`GatewayV1`/`GatewayV2` model only the IR 1600+ block and have no command methods, so calling a setter on `plant.gateway` raises `AttributeError` (for example `'GatewayV1' object has no attribute 'set_enable_discharge'`). GivTCP now sends Gateway writes through `plant.inverter`, which `select_inverter()` returns as a `SinglePhaseInverter` for `Model.GATEWAY`. Those writes are allowed only because `write_safe_registers(Model.GATEWAY)` falls through to `WRITE_SAFE_SINGLE_PHASE`: no Gateway-specific set exists. That matches what the old async fork did, where Gateway writes were plain single-phase HR writes, but it relies on a fallback rather than a supported path.

**Request**

- Confirm whether the single-phase write set is correct for the Gateway (mode, discharge enable, charge/discharge slots, targets, reserve), or define a Gateway write-safe set.
- Either compose the command mixin onto `GatewayV1`/`GatewayV2`, or document `plant.inverter` as the write path for Gateways.
- Rate control is covered in item 3, and identity in item 5.
