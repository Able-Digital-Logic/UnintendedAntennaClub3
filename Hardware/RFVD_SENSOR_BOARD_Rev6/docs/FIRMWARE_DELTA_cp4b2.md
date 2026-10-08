# Firmware delta for the bom2 package (BOM consolidation, 2026-10-04)

> Designators in this dated record predate ECO-003 (2026-10-07). Look up the current ones in [`REFERENCE_MAP_ECO-003.md`](REFERENCE_MAP_ECO-003.md).

Package: `rw/bom2/pkg`, replayed on base_m5 (board sha b298c85857).
Hardware removed: SW3, R18, R44, R49, R206, R207, R214, U702 and C702.
Every pin and net below was read from the kicad-cli netlist of the replayed project.

## 1. Buttons: internal pull-ups on PE3 and PE4 (FEAT-5: R44 and R49 removed)

| Signal | MCU pin | What stays on the board |
|---|---|---|
| RECORD_N_MCU | U8.2, PE3 | R46 1k series, C67 100 nF |
| MARK_N_MCU | U8.3, PE4 | R47 1k series, C70 100 nF |

**Init**
- Configure PE3 and PE4 as inputs with the internal pull-up (GPIOE PUPDR = 01). DS12110 gives RPU = 30 / 40 / 50 kOhm (min / typ / max).
- Keep EXTI3 = RECORD_N and EXTI4 = MARK_N.

**Arming**
- Ignore both inputs for at least 30 ms after the pull-ups are enabled, or arm only after a released (high) level has been read.
- Release time with 40k × 100 nF: τ = 4 ms. The pin reaches VIH (0.7 VDD) in 4.8 ms typical and 6.6 ms worst case (50k, 110 nF).

**Debounce**
- Keep the software debounce of at least 10 ms.

**Sector-0 DFU stub**
- The stub samples the RECORD+MARK chord at reset, so it must enable the same pull-ups and wait the same 30 ms before it reads the chord.
- Before this change, the external 10k pull-ups held the pins high without any firmware.

**Levels**
- Pressed: 3.3 V × 1k / 41k = 0.08 V typical (0.11 V with a 30k pull-up), against VIL = 0.3 VDD ≈ 1.0 V.
- Static switch current: about 80 µA. That is above the B3U minimum applicable load of 10 µA (A162-E1-07). The C67/C70 discharge through the 1k still gives the 3.3 mA wetting pulse.

## 2. NRST and reset (FEAT-4: SW3 removed; FEAT-5: R18 removed)

**What NRST is now**
- NRST (U8.14) has only U8's internal permanent pull-up (DS12110: RPU 30-50 kOhm), C46 100 nF at the pin, and Tag-Connect J6 pad 3.
- J6.3 stays on NRST, as the verifier's FEAT-4 correction requires: it is the debugger connect-under-reset path.
- There is no reset button any more.

**Ways to reset**
- SWD SYSRESETREQ: hot-plug or normal attach.
- Probe NRST through J6.3.
- IWDG: enable it in release builds.
- Unplug the pack.
- Hold SW5 (QON) for 10 s. This BQ25798 system reset (SLUSDV2C §7.3.12.3) works only after firmware has written SFET_PRESENT = 1 once since the pack was connected. That write is FIRMWARE_CONTRACT §5 step 1.

**Rules**
- Never repurpose PA13 or PA14 (SWDIO, SWCLK).
- In debug builds, set DBGMCU DBGSLEEP, DBGSTOP and DBGSTBY.
- Leave the NRST pin mode at its default (bidirectional reset). IWDG and software resets drive it low through the internal pulse generator; C46 only slows the edge.

**Brick recovery (unchanged)**
- Strap R20 pad 1 (BOOT0) to +3V3_D and reset through SWD or J6.3. The other route is the DFU stub chord.

## 3. Display wake: buttons and VBUS, no lid sensor (DIS-1: U702 OPT3004 and C702 removed)

**Removed**
- Remove the OPT3004 driver and the 250 ms FH-flag poll.
- I2C1 address 0x45 becomes **reserved** (keep it reserved on EXP_I2C as well).
- I2C1 now carries 0x44 SHT40, 0x48 TMP117 and 0x6B BQ25798, plus the TCA9517 A side. Its pull-ups are now R53 and R54 at 2.2k (PAS-01). Run I2C1 at 100 kHz as before.

**Wake rule** (the verifier's corrected version)
- While `!acquiring` and the display is off, any of these wakes the display:
  - a RECORD_N press (EXTI3, PE3);
  - a MARK_N press (EXTI4, PE4);
  - a VBUS attach (CHG_INT_N, U8.22 PA0, on WKUP1).
- The wake press is consumed: it starts no run and inserts no marker.
- While `acquiring`, RECORD and MARK keep their run behaviour and the display stays off.
- No wake at run end. The box is opaque and closed, and lighting the CCR backlight there would drain VSYS.
- Add an idle auto-off timeout. Every backlight-on path still applies the §7 duty cap.

## 4. LCD_TE unused (FEAT-6: R206 and R207 removed)

**Pins**
- U8.23 (PA1) and J4.40 (panel TE output) are not connected; both carry no-connect flags in the schematic.
- Set PA1 to analog mode (lowest leakage). PA1 has no pull-down any more.

**Display driver**
- Drop tearing-effect sync: do not wait on TE, and leave TEON (0x35) off.
- Pace frame writes on a timer.
- Use ST7789 partial windows (CASET/RASET) for numeric and status fields.
- Do full-frame redraws only outside RECORD (the display is off during acquisition anyway).
- Optional: set the frame rate with FRCTRL2.

**Expected tearing**
- A full frame takes 240 × 320 × 2 B × 66 ns = 10.1 ms, which is shorter than one 16.7 ms panel refresh. At most an occasional single tear line on a full redraw.

**Side effect**
- The PA1-versus-TE contention of the legacy image (FIRMWARE_CONTRACT §0) is gone.

## 5. TP_RST state (FEAT-7: R214 100k pull-down removed)

- TP_RST (J8.6, FT5426 /RESET) is driven only by U8.25 (PA3, TP_RST_MCU), through R905 330R. C910 100 pF stays at the pin.
- PA3 must be **output-low**:
  - at least 100 µs before UI_EN (U8.33, PC5) rises (NHD Trtp ≥ 100 µs);
  - whenever the UI is off.
- §7 power-on step 2 becomes: "Drive TP_RST (PA3) and RESX low ≥ 100 µs before raising UI_EN".
- §7 power-off step 5 ("all FMC and reset pins output-low") already covers the off state.
- While U8 is in reset, PA3 floats. R41 (100k on UI_EN) then holds UI_EN low, so U10 keeps +3V3_UI off and the touch controller is unpowered. No hardware pull-down is needed.
- Release order is unchanged: release TP_RST, then RESX, then wait 120 ms. The first touch I2C access comes at least 200 ms later.

## 6. EXP_VHP_SNS scale constant (PAS-04: R413 33.2k → 20k)

**Scale**

| | Divider | Scale |
|---|---|---|
| Old | R412 100k / R413 33.2k | 4.012 |
| New | R412 100k / R413 20k | **6.000** |

```
EXP_VHP [V] = V(PC2_C) × 6.000   (old constant 4.012)
```

- Pin: U8.17 PC2_C, ADC3_INP0.
- VREF+ = +3V0_REF (REF5030, 3.000 V), so at 16 bits: `EXP_VHP = code / 65536 × 3.000 × 6.000`.
- Ratio tolerance with 1 % parts: ±1.67 % (was ±1.50 %).

**Pin voltages**
- 9 V → 1.50 V.
- 10.28 V OVLO worst case → 1.71 V.
- The ADC saturates only above 18 V (was 12 V).

**Rails-off check (§8)**
- The threshold is unchanged: EXP_VHP < 0.3 V. At the pin that is now < 50 mV, about 1,092 LSB.

**Settling**
- Source impedance: 100k ∥ 20k = 16.7k. With C407 100 nF, τ = 1.67 ms (was 2.5 ms).
- 5τ = 8.3 ms. Any existing wait of ≥ 12.5 ms still covers it.

**Contract**
- FIRMWARE_CONTRACT has no EXP_VHP_SNS scale today; the 4.012 lived only in the R413 Function text.
- Add to §8: "EXP_VHP = EXP_VHP_SNS × 6.000 (R412 100k / R413 20k); rails-off = EXP_VHP < 0.3 V (pin < 50 mV)".

## 7. FIRMWARE_CONTRACT edits to make when this package lands

| Section | Edit |
|---|---|
| §4 | PC2_C (ADC3_INP0) = EXP_VHP_SNS, scale 6.000 |
| §7 | Power-on step 2 as in §5 above; TE is not used (§4 above) |
| §8 | Add the EXP_VHP scale and rails-off line from §6 above |
| §9 Buttons | Add "internal pull-ups PE3/PE4 (PUPDR = 01), arm ≥ 30 ms after enabling, also in the DFU stub" |
| §9 Reset | Add the reset and recovery list from §2 above |
| §9 | Replace the "Lid light sensor" line with the wake rule from §3 above |
| §10 | Change "0x45 OPT3004" to "0x45 reserved" |
