# Firmware notes required by the hardware

These are settings the firmware **must** follow because the board depends on them. Each note gives:
- the reason;
- the source (datasheet section or board fact);
- where on the board the setting lives.

The board itself is in `../RFVD_SENSOR_BOARD.kicad_pro`. The pin map is the U401 symbol in `MCU.kicad_sch`.

## 1. EXP_SYNC frequency (expansion shield buck sync)

**Net:** EXP_SYNC = U401 PB7 (TIM4_CH2), through R1220 to J1201.

**Rule:** do not run EXP_SYNC at 2.000 MHz. Use **2.400 MHz**, which is TIM4 kernel clock / 100 when that clock is 240 MHz, at 50 % duty. The board's whole purpose is measuring RF-induced voltage at the MRI frequencies. Every EXP_SYNC harmonic must therefore stay at least 500 kHz from each protected frequency: 63.86, 64.00, 123.2, 127.74 and 128.0 MHz (the Y401 Function field).

**Why 500 kHz.** A harmonic close to a protected frequency becomes a beat in the detector envelope. The envelope (VENV) low-pass on U501 has two unity-gain Sallen-Key stages:
- R502 2.26k / C501 510p / C503 470p: f0 143.8 kHz, Q about 0.52;
- R503, R504 1.33k / C502 1.2n / C504 470p: f0 159 kHz, Q about 0.8.

It attenuates a beat by 6.4 dB at 140 kHz, 18.4 dB at 240 kHz, 44.6 dB at 540 kHz and 63.6 dB at 940 kHz. These figures were recomputed from the schematic values and are unchanged at checkpoint 2a. The reference path (EREF, U502) has been a single 704 Hz pole (R506 22.6k / C506 10 nF, S-27) since checkpoint 2a, so it rejects a beat far more strongly.

| EXP_SYNC | Closest harmonic to a protected frequency | Verdict |
|---|---|---|
| 2.000 MHz (the old "~2 MHz") | **0 kHz** from 64.000 (n=32) and 128.000 MHz (n=64) | Not allowed |
| **2.400 MHz = 240 MHz / 100** | 540 kHz from 127.74 MHz (n=53); all others ≥ 800 kHz | **Use this** |
| 2.1818 MHz = 240 MHz / 110 | 587 kHz from 63.86 MHz (n=29) | Alternative if the shield buck needs about 2 MHz |
| 2.3077 MHz = 240 MHz / 104 | 615 kHz from 64.00 MHz (n=28) | Alternative |
| 2.6966 MHz = 240 MHz / 89 | 719 kHz from 64.00 MHz (n=24) | Alternative |
| 1.6667 MHz = 2 x fs | 133 kHz from 123.2 MHz (n=74) | Not allowed (beat inside the AFE passband) |
| 2.5 MHz = 3 x fs | 240 kHz from 127.74 MHz (n=51) | Not allowed |

(Computed 2026-10-03. Clearance = |n x f - protected| for the nearest harmonic n.)

**Notes**
- If the TIM4 kernel clock is not 240 MHz, choose the divider N so that clock / N matches a frequency from the table. Then re-run the check:

  ```
  min over p in {63.86, 64, 123.2, 127.74, 128} of |round(p/f) x f - p| >= 0.5 MHz
  ```
- Any frequency locked to fs (833.33 kHz) has a harmonic at 123.333 MHz, 133 kHz from 123.2 MHz. No fs-locked EXP_SYNC can meet the 500 kHz rule.
- BUCK_SYNC (the main LMR43620 buck) stays at fs = 833.33 kHz on purpose. That is a lead decision: its comb is locked to the ADC sample clock, so its ripple aliases to DC.
- The shield buck must accept the chosen frequency on its SYNC input. It must also run fixed-frequency, forced-PWM and locked to EXP_SYNC, with spread spectrum / dithering disabled; a dithered buck smears its harmonics across the protected bands. Both requirements belong in the RFVD-EXP shield spec.
- When the shield has no buck, EXP_SYNC is **static low** (timer off, pin output-low or analog).
- Sources:
  - critique finding EXP-04, verified, with the TIM4 clock-tree correction;
  - R1220 Function field;
  - the Y401 Function field for the protected frequencies.

## 2. MCU pins with no connection (checkpoints 2a and 2b)

| Pin | Was | Removed by |
|---|---|---|
| PA9 (68), PA10 (69) | (unused since the project) | — |
| PB3 (89) | SWO (J901.6, now NC) | S-18: use RTT or USB-CDC for debug output |
| PC13 (7) | VBUS_DET. R304/C302@pre-ECO003 deleted; R1109 stays as a 100k VBUS bleeder. **Plug detection is now firmware's job:** CHG_INT_N on WKUP1 (PA0), then the BQ25798 status register REG1B. | S-6 |
| PD3 (84) | Not connected: LID_INT and the OPT3004 lid sensor (U702@pre-ECO003) were removed at checkpoint 4b2. | S-24 |
| PD4 (85) | LCD_RD_N. The panel's RDX is tied to +3V3_UI; the bus is write-only. | S-11 |

**Rule:** configure every pin in the table as **analog** (GPIOx_MODER = 11). That is the STM32H7 reset state, so no init code may change it. Never leave them as floating digital inputs: analog mode has the lowest leakage and no input-buffer switching current.

**Source:** the kicad-cli netlist at checkpoint 2b (`unconnected-(U401-…)` nets).

## 3. SDMMC1 output speed (SD front end EMIF06, checkpoint 2b)

**Rule:** set SDMMC1 CLK, CMD and D0–D3 (PC8–PC12, PD2) to **medium** GPIO output speed (OSPEEDR = 01). **Never use very-high.**

**Why:** U601 (ST EMIF06-MSD02N16) puts its 36–54 Ω series resistors at the card end, so the MCU side of each line is now unterminated. The project's transmission-line model (`tl_model.py`, run for checkpoint 2b) gives these results:
- at the strongest drive, D0 rings to ±0.61 V at U601's input, past the ±0.4 V screen;
- at medium drive, every signal is clean;
- at medium, the clock's high-frequency current is still about 33 % above the old design. Shorter loops and the socket filter offset this, and a 33R at U401 pin 80 is an optional checkpoint-4 improvement.

## 4. Expansion rail and interrupts (checkpoint 2b)

- **EXP_3V3_EN** (TPS2553 enable, which also powers the TCA9517 B side): change it only while I2C1 is idle. Wait ≥ 5 ms after enabling, then run I2C bus recovery. (TI SCPS245E §5.6 note 1: EN may only change while the bus is idle; TCA9517 EN is now tied to VCCB, S-20.)
- **EXP_INT0_N / EXP_INT1_N** (PD9/PD10, EXTI9/10) have 10k pull-ups to +3V3_EXP (P1-26). Mask EXTI9/10 while +3V3_EXP is switching, and never enable the internal pull-ups while the rail is off: that would back-power the shield.
