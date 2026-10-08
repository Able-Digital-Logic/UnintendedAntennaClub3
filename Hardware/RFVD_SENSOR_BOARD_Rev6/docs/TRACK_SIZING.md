# Track sizing and pad-entry rules (2026-10-06, rules v12)

**Why this changed.** While hand routing, some pads could not be reached because the EMC spacing rules (0.2-2.0 mm) also applied between a track and the pad it was entering. Power nets also started at one large width per class, whatever current they carried. v12 sizes every power net from its real current and lets every pad be entered at the router's width. Track-to-track EMC spacing is unchanged.

## How the widths are chosen

- **Router width (opt):** the IPC-2221 external-layer width for a 10 °C rise on the 1 oz (35 µm) outer copper.
- **Minimum (min):** the 20 °C width, for short necks. Never below 0.15 mm on power nets.
- **In3:** the copper is only 15.2 µm, so the same current needs a wider track. Widths there use the same curve at In3's thickness.
- **Currents** come from the project documents:
  - IINDPM ≤ 2 A and ICHG ≤ 1 A (`05_firmware/FIRMWARE_CONTRACT.md`);
  - F1401 hold 1.5 A;
  - U1501 638 mA, U1502 0.613 A, U801 303 mA (load ≤ 38 mA);
  - the LT3045 ILIM of 150 mA.

| Nets | Design current | Outer: router / min (mm) | In3: router / min (mm) | Before (outer router / min) |
|---|---|---|---|---|
| VBUS, PMID | 2 A while charging | 0.8 / 0.5 | 1.2 / 1.2 | 1.0 / 0.5 (In3 1.0 / 0.8) |
| CHG_BAT, VBAT_PACK, PACK_FUSED, PACK_RAW, VSYS | ≤ 1.5 A | 0.6 / 0.4 | 1.0 / 0.8 (unchanged) | 1.0 / 0.5 |
| +3V3_D | ≤ 1.2 A | 0.5 / 0.3 (unchanged) | 0.6 / 0.4 warning (unchanged) | 0.5 / 0.3 |
| U1301 SW (buck switch node) | ≤ 1.5 A | 0.6 / 0.4, necked to 0.2 inside U1301 / C35 | (keep it off In3) | 0.8 / 0.5 |
| U1101 SW801 / SW802 | 2-3 A | 0.8 / 0.5 (unchanged) | (keep it off In3) | 0.8 / 0.5 |
| +3V3_EXP, EXP_VHP | ≤ 0.65 A | 0.3 / 0.2 | 0.4 / 0.2 | 0.5 / 0.3 and 1.0 / 0.5 |
| +3V3_SD, +5V_A, +3V3_A, VSYS_LDO, VCAP | ≤ 0.3 A | 0.3 / 0.2 | 0.3 / 0.2 | 0.4-1.0 / 0.25-0.5 |
| +3V3_UI, +5V_RF, VBAT_RTC, ADC_VLOGIC, U1001 REGCAP, A3V3_DAMP | ≤ 50 mA | 0.25 / 0.15 | 0.25 / 0.15 | 0.4-0.5 / 0.25-0.3 |
| Signals (Default, HighSpeed, Harness, Analog, RF) | mA | unchanged: 0.12-0.2 | unchanged | unchanged |

**Inside IC courtyards** (`U*`, J1201, the charger caps) power tracks neck to **0.2 mm**, the width of U1101's pads. That used to be 0.3 mm, which could not enter U1101's 0.2 mm pads at 0.45 mm pitch.

## Clearances

- **EMC spacing rules now apply between tracks and vias only:**
  - the 3W rule for clocks;
  - high-speed to signal;
  - analog to digital, digital power, harness and high-speed;
  - +3V3_D to +3V3_A.

  A pad keeps its net class clearance (0.1-0.15 mm), so a track can enter it and fan out. These rules still hold along every run, as before.
- **Unchanged and still applied to pads:**
  - the buck SW-node rules;
  - analog to SW (2 mm);
  - every RF rule;
  - the U.FL centre-pin rule;
  - the 0.15 mm pad-to-pad floor.
- **Net classes:** Power_Battery and Power_Buck_SW clearance 0.2 → **0.15 mm**. IPC-2221 needs 0.05-0.1 mm for these voltages (≤ 10 V). Inside U1101, the SW801/SW802 spacing is 0.2 → 0.15 mm (0.25 mm pad gap).

## Vias (net class defaults, JLC no-surcharge 0.45/0.20 POFV)

- **All signal classes, Ground, Power_Digital and Power_Analog:** 0.45/0.20, which carries about 1 A per via.
  - Before: 0.5/0.3 (signals), 0.6/0.3 (Ground and the other two).
  - The +3V3_D trunk (1.2 A) changes layer through **two** vias.
- **Power_Battery and Power_Buck_SW:** 0.6/0.30, about 1.6 A per via.
  - Power_Battery was 0.8/0.4.
  - VBUS / PMID (2 A) change layer through **two** vias.

## Evidence (board `c4cafbab76`, the 2026-10-05 23:48 save)

**Pad-entry test.** Every connected pad (787) was tried 9 ways under KiCad's own DRC: a probe track in each of the 8 octilinear directions and a via in the pad. The table counts how many pads had no clean way in, or only one.

| Rules | Pads with no clean way in | Pads with only one way in |
|---|---|---|
| Old rules, router width | 16 | 58 |
| **v12, router width** | **0** | **36** |
| Placement alone (0.1 mm everywhere) | 0 | 15 |

**DRC on the same board, old rules → v12** (both files proved to load with a sentinel rule):
- Errors: 27 → 32 (27 + 10 new − 5 cleared).
  - **10 new:** the VBUS / PMID tracks on In3, which are 0.8 mm and need 1.2 mm for 2 A. Widen them or move them to F / B.
  - **Cleared:** 4 ADC_VLOGIC width errors and 1 pad clearance error.
- Warnings: 83 → 63 on identical scratch copies. Track-width warnings go from 23 to 3: the old In3 rule flagged low-current nets narrower than 0.4 mm. In the project folder the v12 total is 49, because the scratch path adds 19 false library warnings and the real folder reports 5 library mismatches instead.

**Files.**
- Rules: `tools/dru_versions/d10_v12_sizing.kicad_dru`.
- Backups: `backups/before_sizing_2026-10-06/`.
- Net classes and the 1.2 mm predefined width were changed through Konnect.
