# RFVD SENSOR-D board: layout handoff (2026-10-02)

This folder holds a complete KiCad 10 project of the RFVD sensor board. Placement is final and locked, and 92.6% of the board is routed (42 links left, each with a mapped path). You can open it and keep routing.

**To finish the routing, start with [`docs/ROUTING_FINISH_GUIDE.md`](docs/ROUTING_FINISH_GUIDE.md).**

**Checkpoint 5 (2026-10-04), board sha256 `f9fb559366`: final state of this pass, ready for hand routing.**
- **DRC: 0 errors**, 110 warnings, sign-off PASS.
- **42 open links, 0 blocked.** `docs/ROUTING_FINISH_GUIDE.md` §0 lists each link with a suggested path and its hand-off via.
- Placement is final and every footprint is locked.
- Ratsnest 3522 mm (m17: 4018). BOM: 100 lines / 309 parts.
- Since checkpoint 4a:
  - J10 moved 0.96 mm to match the HRO drawing;
  - F1 on its Bourns Style 2 land at J2, with PACK+ as a 1 mm B-only run;
  - the U403 buffer moved out from under J10;
  - the BOM consolidation (firmware rules in FIRMWARE_CONTRACT §11);
  - the remaining DRC fixes;
  - pad escapes for every blocked link.

**Checkpoint 4a (2026-10-04), board sha256 `08570ddf0b`.**
- Five region hand-layout packages: A RF/AFE, B1/B2 MCU core, C power band, E south J11/J2. The sourcing package moved 47 parts to in-stock JLC Basic or FOJAN types and C31 to 25 V.
- **DRC 278 → 109 errors**, 116 warnings, 43 open links (was 44), missing return vias 45 → 13, neck chains 46 → 12. Sign-off PASS. ERC 0.
- What was added:
  - an AFE GND ring: a 1.0 mm band under a mask-open strip, 19 fence vias, FL1 on the east wall;
  - the 32 kHz crystal-gap via moved out of the gap;
  - the EXP_SYNC fix at J11;
  - the VSYS island at U402 routed;
  - battery trunks at 0.8 mm on In3;
  - BQ25798 hot-loop GND vias;
  - 31 edge-stitching vias.
- Next: the routing waves for the remaining errors and links (west/J10, MCU-core seam, battery, then the LCD and expansion buses).

**Checkpoint 3 (2026-10-04), board sha256 `527e801c62`.**
- The stricter rules v11 landed: side-aware exemptions, neck caps, In3 power widths, missing keep-outs, pre-defined sizes, mask 0.
- Every stale sheet note and Function field was corrected.
- DRC now shows **278 errors**, on purpose. They are the copper the old rules hid (power widths and necks, 3W spacing, foreign copper under J10), and they are checkpoint 4's routing work list (`docs/LAYOUT_STATUS.md`, Checkpoint 3).
- ERC 0, 44 open links, sign-off rules PASS.

**Checkpoint 2b (2026-10-04), board sha256 `f539f0317c`. DRC: 0 errors.**
- **SD:** an ST EMIF06 SD front end replaces 20 parts and clears both SD skew errors.
- **PSRAM:** one series array.
- **Display bus:** resistors regrouped by pin side.
- **MCU/service:** SWO, the BOOT button and the lid interrupt are removed; the buttons get series resistors.
- **Expansion:** pull-ups added, ESD flow-through, the MR-kill jumpers are gone.
- **Back silkscreen:** an issue date and a serial-number box. A fab note sits on User.Drawings.
- **J10:** pin-in-paste on its shell.

Totals: 538/582 routed (44 open), 82 warnings (each explained in `docs/LAYOUT_STATUS.md`), sign-off PASS. JLC BOM: 106 lines / 318 parts. The manufacturing spec and the panel tool are in `docs/MANUFACTURING_EMC_SPEC.md` and `tools/make_panel.py`; the panel is a 72 × 90 mm 1-up frame, so exactly 2 boards are assembled.

**Checkpoint 2a (2026-10-04), board sha256 `c4383fe7ab`.** The circuit changes from the critique landed:
- the AD7380 runs on its internal reference;
- the EREF filter is a single pole;
- 33R / 2.2 nF ADC reservoirs;
- buck FB divider 23.2k/10k;
- eFuse OVLO 64.9k;
- display straps in copper and a write-only bus;
- the VSYS and VBUS dividers, the charge LED and two polymer caps are gone;
- the 1 µF line merged.

30 parts removed, 2 added. DRC: 2 errors (both `skew_sdmmc`, until SD_D1 is routed), 85 warnings; sign-off PASS. ERC is clean. 47 open links (was 50). The JLC BOM is 105 lines / 346 parts (was 111 / 369). An independent review checked every change against its datasheet. Details: `docs/LAYOUT_STATUS.md` (Checkpoint 2a); firmware consequences: `docs/FIRMWARE_NOTES.md`.

**Checkpoint 1 (2026-10-04), board sha256 `5c22d06d54`.** The first batch from the full design critique and the placement revision landed:
- placement and EMC fixes in the RF, analog, expansion, charger/USB, buck and battery areas;
- a 22.9 mm antenna stub deleted;
- overlapping drills fixed;
- silkscreen labels and the board ID moved onto the board;
- schematic DNP flags fixed, so the BOM now includes the FB1 damper.

DRC warnings went from 97 to 87 (counted in this folder), ERC is clean, and no connection got worse. Details: `docs/LAYOUT_STATUS.md` (Checkpoint 1); the plan for the rest: `docs/WORKPLAN_2026-10-03.md`.

**Update 2026-10-03 (hand-layout pass, no auto-routers):**
- Every edit was an explicit coordinate list (`docs/hand_edits_2026-10-03/`).
- **DRC errors 14 → 3; warnings 212 → 153.** The VSYS trunk is closed.
- R304, R411, R404 and R417 were re-placed. The BUCK_SYNC spacing now passes the 3W and the 3 mm LSE sign-off rules.
- The rest of the board is handed over for interactive push-and-shove routing, with a measured, step-by-step guide.
- J3 has no legal alternative pose (checked), so the band is solved by re-fanning escapes, not by moving the big parts.

**Update 2026-10-02 night:**
- The board was **widened to 52.05 x 90.05 mm**: +2.5 mm per side, with a notch that keeps the USB-C and microSD flush.
- A connection-length **placement audit** was added: `docs/PLACEMENT_AUDIT.md` and `outputs/RFVD_placement_audit_*`.
- R314 and Q302 moved next to their partners, and 5 more connections plus all GND islands were routed.
- A DRC clean-up took the errors from 50 to 14:
  - shield pads now connect solidly to the GND pours;
  - an SWDIO via too close to a J10 hole was re-routed, and the router now models that rule;
  - 3 clearance problems were re-routed locally;
  - two scoped rule exceptions were added (DRU patch v10).
- The tools were cleaned into one self-tested folder: `tools/README.md`.
- The board before this pass is in `backups/RFVD_SENSOR_BOARD_before_widening_2026-10-02.kicad_pcb`.

The project folder `03_hardware/RFVD_SENSOR_BOARD_GITHUB` was **not** modified. Everything here was built from it on scratch copies; the base board hash was `2ccd301640`.

Open **`RFVD_SENSOR_BOARD.kicad_pro`** in KiCad 10. The libraries and 3D models are included and use project-relative paths.

## Status at a glance (checkpoint 5, board sha256 `f9fb559366`)

| Item | State |
|---|---|
| Outline | **52.05 x 90.05 mm** (widened 2026-10-02 from 47.05 mm; port notch at y 104.6-133.3 keeps J3/J10 flush). Fits the 56 mm box: west gap 2.75 mm (5.25 at the ports), east 1.25 mm. |
| Placement | **Final and locked**: 341 footprints (196 top / 145 bottom), all locked. Placed against each IC's datasheet layout guide (`docs/sensitivity.json`, with section and page). The 2026-10-04 sign-off on the board: **placeaudit 0 MOVE / 0 OVER**; `tools/dsgap.py` measured 269 datasheet budgets, 264 within budget and 5 justified with measured reasons (`docs/PLACEMENT_DATASHEET_CHECK.md`, `tools/placeaudit_keep.json`). |
| Routing | **524 of 566 connections (92.6%)**; the total was 633 before the BOM consolidation removed parts. **42 open links, 0 blocked**: 12 direct, 30 with a mapped legal path. Every link is in `docs/ROUTING_FINISH_GUIDE.md` §0 with exact coordinates. No GND islands. |
| Copper | 3,038 mm of track (F 994 / In3 1,047 / B 997 mm), 1,028 vias (941 of them 0.45/0.20 POFV), 7 copper zones, 45 rule areas. |
| DRC (`outputs/RFVD_DRC_report.*`) | **0 errors**, 110 warnings (each class explained in `docs/LAYOUT_STATUS.md`, Checkpoint 5; 42 of them are the deliberate hand-off vias), sign-off PASS. Always run DRC with `--all-track-errors` from the CLI. |
| Silkscreen | No reference designator is visible on F/B silkscreen; they stay on the fab layers. |
| BOM | Regenerated by `tools/make_outputs.py` from KiCad's own DNP flags: **100 lines / 309 placed parts**, every one with MPN and LCSC number. The CPL has exactly those designators, rotation-corrected for JLC. Live stock check 2026-10-04 (`docs/LAYOUT_STATUS.md`): 95 lines are in JLC stock for 2 boards and 4 come from LCSC via a parts pre-order. **L1 (XGL4020-472MEC) needs the Global Sourcing route: JLC holds 1.** |
| Fab outputs | **Not generated on purpose** until the last 42 links are routed. Then run `tools/make_fab_outputs.py` and `tools/make_panel.py` (D27: 1-up 72 x 90 mm frame). |

## What is left to route (`outputs/RFVD_unrouted.csv`, `outputs/RFVD_unrouted.png`)

| Group | Open | Nets |
|---|---|---|
| Expansion to J11 | 15 | EXP_3V3_SNS, EXP_ANA_MON, EXP_CS0_N_MCU, EXP_CS1_N_MCU, EXP_DETECT_N_MCU, EXP_GATE, EXP_INT1_N_MCU, EXP_IO0_MCU, EXP_IO1_MCU, EXP_MISO_MCU, EXP_RST_N_MCU, EXP_SPI_MOSI, EXP_SPI_SCK, EXP_SYNC, EXP_VHP_SNS |
| LCD bus to J4 | 14 | LCD_BL, LCD_BL_SW, LCD_CS_N, LCD_D0-LCD_D7, LCD_DC, LCD_LED_K4, LCD_WR_N |
| Power / charger | 6 | CHG_INT_N, QON_N, USB_DM, USB_DP (2 islands), VBAT_RTC |
| Other | 7 | MARK_N, NRST, PSRAM_IO2_RAM, RECORD_N, SD_D1_MCU, TP_INT, TP_SCL |
| GND | 0 | All GND islands are joined. |

Each link, with both ends, the suggested path and its hand-off via, is in **`docs/ROUTING_FINISH_GUIDE.md` §0**. The history and root causes are in `docs/LAYOUT_STATUS.md`.

## What to do next

1. **Do the GUI-only setup steps** in `docs/LEAD_GUI_STEPS.md` (stackup loss, via filling, silk minimums, J10 shell paste). The two optional placement clean-ups (A, B) are listed there too.
2. **Route the 42 open links** with KiCad's interactive router in push-and-shove mode, following `docs/ROUTING_FINISH_GUIDE.md` §0:
   - set the pre-defined sizes first (0.45/0.20 vias, 0.15 mm tracks);
   - start each link from its hand-off via;
   - octilinear tracks, fillets on clocks and strobes.
   Footprints are locked, so push-and-shove moves only tracks.
3. **Add a GND return via** at every layer change of a fast net (R17: within 1.0 mm for clocks, 1.5 mm for digital).
4. **Re-run DRC** with the project rule file (`RFVD_SENSOR_BOARD.kicad_dru`) and `--all-track-errors`; the goal is 0 errors and no new warning class.
5. **Regenerate the outputs**: `tools/make_outputs.py` (run it in this folder), then the fab outputs and the panel (`tools/make_fab_outputs.py`, `tools/make_panel.py --cols 1 --min-size 72`). Check the CPL rotations in JLCPCB's preview before ordering.
6. **Copy the result back** into `RFVD_SENSOR_BOARD_GITHUB`: replace the board, rule file and project file there, or follow the Konnect transfer plan in `docs/CHANGES_FROM_PROJECT.md`.

## Folder map

| Path | Contents |
|---|---|
| `RFVD_SENSOR_BOARD.kicad_pro/.kicad_pcb/.kicad_dru` | Project, routed board (this handoff) and design rules. |
| `*.kicad_sch` | Schematic: root plus 11 sheets, unchanged from the project. |
| `libraries/`, `models/`, `fp-lib-table`, `sym-lib-table` | Custom symbols, footprints and 3D models (project-relative). |
| `outputs/` | BOMs, JLCPCB BOM/CPL, position file, schematic PDF, multi-page layer PDF, DRC report, unrouted list and map. See `outputs/README.md`. |
| `renders/` | 3D renders (top/bottom) and one image per copper layer with footprint outlines (`layer_1_F_Cu.png` ... `layer_6_B_Cu.png`). |
| `docs/` | Board overview, layout status, changes from the project, tools guide, placement sensitivity study, and the original reports (`docs/reference/`). |
| `tools/` | The single, self-tested layout toolset: router, placement audit, placement, widening, merge, DRC and output helpers. Index: `tools/README.md`; check it with `tools/selftest.py`; regenerate every output with `tools/make_outputs.py`. |

## Documents

- `docs/BOARD_OVERVIEW.md`: what the board does, blocks and key parts, stack-up, net classes, EMC strategy, placement philosophy.
- `docs/ROUTING_FINISH_GUIDE.md`: **how to finish the last 50 links interactively**. It covers every link with today's feasibility, the verified unlock moves, the J4 via sites, the rule areas the router does not enforce, router set-up and order of work. Maps are in `docs/routing_guide/`.
- `docs/LAYOUT_STATUS.md`: routing status per group, root causes, recommended fixes, the DRC error list, and decisions and deviations.
- `docs/CHANGES_FROM_PROJECT.md`: everything that differs from `RFVD_SENSOR_BOARD_GITHUB`, and how to bring it back.
- `docs/PLACEMENT_DATASHEET_CHECK.md`: every part against its IC's datasheet layout rule, measured on the board (generated by `tools/dsgap.py`), with the reason for each part kept over its budget.
- `docs/LEAD_GUI_STEPS.md`: the steps only the KiCad GUI can do, and the optional placement clean-ups.
- `docs/PLACEMENT_AUDIT.md`: the placement audit (what was flagged, moved and kept, with reasons) and the board widening.
- `tools/README.md`: the layout tools and how to re-run them (`docs/TOOLS.md` points there).
- `docs/sensitivity_summary.md` / `docs/sensitivity.json`: per-part datasheet placement budgets.
- `docs/reference/`: the project's device report, PCB layout rationale and EMC report (.docx), plus sheet images.
