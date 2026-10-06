# Changes from the project folder

**Base.** `03_hardware/RFVD_SENSOR_BOARD_GITHUB` as of 2026-10-02 16:00. That folder was not modified.

| File | Project hash (sha256, first 10) | This folder |
|---|---|---|
| RFVD_SENSOR_BOARD.kicad_pcb | 2ccd301640 | checkpoint 5 board: placement final and locked, DRC 0 errors, 42 open links (sha256 `f9fb559366`) |
| RFVD_SENSOR_BOARD.kicad_dru | 9227e92320 | project DRU + patches 1-5 + v10 + v11 side-aware split + d9 (sha256 `350283974c`) |
| RFVD_SENSOR_BOARD.kicad_pro | 9be714c884 | net classes and patterns (cp2a, cp3), ERC exclusion (cp1), pre-defined sizes (cp3), `min_hole_clearance` 0.25 -> 0.20 (sha256 `4426de7021`) |
| *.kicad_sch, libraries, models | - | **changed** from checkpoint 1 on: circuit changes, removed and added parts, sheet notes (cp1-cp4b2), the EMIF06 symbol and footprint (cp2b). `Trigger.kicad_sch` is not referenced by the root sheet and was left out |

## 2026-10-03/04: m17 and checkpoint 1

- **m17** (lead, sha256 `f536efcf8e`): the physical stackup was set to JLC06161H-3313 (6 layers), and 103 sliver segments were merged or removed (2631 -> 2528 segments). No part moved.
- **Checkpoint 1** (sha256 `5c22d06d54`): the first batch of the critique and placement revision. See `LAYOUT_STATUS.md`, section "Checkpoint 1".
  - Schematic: wire stubs, DNP flags/fields, and the VCAP ERC exclusion in the `.kicad_pro`.
  - Board: 14 part moves or rotations, 1 flip (Q302 to F), and 8 new GND vias in pads. One antenna stub and one duplicate via were removed. Silkscreen texts were moved onto the board.
  - Backup: `backups/before_cp1_2026-10-04/`.
- **Checkpoint 2a** (sha256 `c4383fe7ab`): the critique's circuit changes for groups G1b, G2, G3 and G4a, plus the PACK_RAW net-class fix (package G6). See `LAYOUT_STATUS.md`, section "Checkpoint 2a".
  - Schematic (Konnect), 10 sheets changed: 30 parts removed, 2 added (R214, R601), 32 values or part numbers changed.
    - Nets gone: 15, including VBUS_DET, CHG_LED_A, LCD_RD_N, the IM straps and EXP_VHP_IN.
    - Net renamed: `Net-(J2-Pin_1)` → `PACK_RAW`.
  - Project file: PACK_RAW assigned to Power_Battery. The dead pattern `Net-(J2-Pin_1)` is left in place because Konnect cannot remove a pattern; it matches nothing.
  - Rules: `v10_pack_raw_kelvin` appended to the DRU (B.Cu, inside the J2 courtyard, min 0.12 mm) for the BQ29209 Kelvin sense track.
  - Board: synced from the schematic with `tools/place/sync.py` (removed parts deleted, new ones placed). The copper of the removed circuits was deleted with `pen.py`; R103 and C106 were moved.
  - Backup: `backups/before_cp2a/`.
- **Checkpoint 2b** (sha256 `f539f0317c`): groups G4a2, G4b, G5a and G5b, plus the silkscreen/fab-note and J10 pin-in-paste packages. See `LAYOUT_STATUS.md`, section "Checkpoint 2b".
  - Schematic (Konnect), 6 sheets changed: 39 parts removed, 8 added (R213, R441, R442, R46, R47, RN401, RN60, U901). 24 nets gone (incl. SWO, LID_INT, the PSRAM RAM-side resistor nets), 13 new (incl. RECORD_N_MCU, MARK_N_MCU).
  - Libraries: the EMIF06-MSD02N16 symbol (RFVD_MVP_Symbols) and footprint `ST_EMIF06-MSD02N16_uQFN-16_3.5x1.2mm_P0.4mm` (RFVD_MVP_Footprints), created with Konnect.
  - Board: synced; copper of the removed parts deleted; new escapes, return vias, the B silk date / S/N box, the User.Drawings fab note, the title-block date and the J10 shell paste (board copy) added with `pen.py`.
  - Backup: `backups/before_cp2b/`.
- **Checkpoint 3** (sha256 `527e801c62`): rules v11 (DRU patch + `dru_sideaware.py` split; Konnect: EXP_SYNC / LCD CS / DC classes, hole_to_hole severity, pre-defined sizes), the K-area rule-area edits and mask expansion 0 (`pen.py`), and the stale-note package (Konnect: 7 notes, 15 field edits). See `LAYOUT_STATUS.md`, section "Checkpoint 3". Backup: `backups/before_cp3/`. The DRU is saved as `tools/dru_versions/d8.kicad_dru`.

- **Checkpoint 4a** (sha256 `08570ddf0b`): five regional hand-layout packages (A RF/AFE, B1/B2 MCU core, C power band, E south J11/J2) and the sourcing package (47 parts to in-stock JLC Basic / FOJAN types, C31 to 25 V). See `LAYOUT_STATUS.md`, section "Checkpoint 4a".
- **Checkpoints 4b1-4b4** (last sha256 `022e8a3830`):
  - F1 on its Style 2 land at J2, with a B-only PACK_RAW run (4b1);
  - the BOM consolidation (4b2): schematic through Konnect; SW3, R18, R44, R49, R206, R207, R214, U702 and C702 removed; the firmware rules are in `05_firmware/FIRMWARE_CONTRACT.md` §11;
  - J10 moved 0.96 mm (4b3);
  - the U403 cluster moved to F with DRU patch d9 (4b4).
  - Backups: `backups/before_cp4b*`.
- **Checkpoint 5** (sha256 `f9fb559366`): the last DRC fixes (5a), the escape vias for every blocked link and R305 moved (5b/5c), then every footprint locked. DRC 0 errors, 110 warnings, 42 open links, 0 blocked. Backups: `backups/before_cp5*`.
- **Placement sign-off** (2026-10-04, board unchanged): `tools/dsgap.py` and the keep reasons; `docs/PLACEMENT_DATASHEET_CHECK.md`.

## Board changes (`changes_vs_project.json`, `changes_part_moves.csv`)

| Change | Count |
|---|---|
| Board outline | **47.05 -> 52.05 mm wide** (+2.5 mm each side, port notch at the USB-C / microSD; see `PLACEMENT_AUDIT.md`). The 5 board-wide GND zones (F, In1, In2, In4, B) and rule areas K9 / AFE_PARTITION were extended to the new edges. |
| Footprints moved | 119, median move 0.47 mm |
| Footprints flipped | 2: C305 to B.Cu at (143.804, 114.323) rot 270; Q302 to B.Cu at (163.4, 122.1) rot 270 (next to U302 BQ29209, 2026-10-02 night) |
| Tracks removed / added | 52 / 2,327 |
| Vias removed / added | 346 / 750 |
| Copper zones | 1 added: `CHG_CHG_BAT` (F.Cu CHG_BAT pour at the BQ25798 BAT pins); the 5 GND zones have new outlines (wider board) |

**Largest moves.**
- R303: 14.6 mm, low sensitivity.
- C314: 8.5 mm, medium.
- R18: 5.7 mm, low.
- C302: 5.0 mm, low.
- C311: 4.8 mm, high. This one and C310 (3.7 mm, high) are charger BTST caps moved to B.Cu per the BQ25798 datasheet.
- D203: 4.7 mm.
- R417: 4.6 mm.
- R416: 4.5 mm.

Every move kept each part inside its datasheet placement budget (`sensitivity_summary.md`). The exceptions already flagged there are C309 and C318 at 1.69 and 2.29 mm against 1.5 mm; both are critical BQ25798 caps.

**2026-10-02 night pass (after the first handoff).** These were driven by the placement audit (`PLACEMENT_AUDIT.md`):
- the board was widened;
- R314 (DNP Q301 bypass) moved under Q301;
- TP11 moved onto +3V3_D copper;
- Q302 moved and flipped next to U302;
- the routing gained the GND islands, EXP_I2C_SDA, EXP_SPI_MISO, EXP_FAULT_N, CHG_BAT and VBAT_PACK;
- two dangling In3 GND stubs and two misplaced GND vias were removed (one in J3's keep-out, one starving a J10 shield thermal).

The board before this pass is `backups/RFVD_SENSOR_BOARD_before_widening_2026-10-02.kicad_pcb`.

**DRC clean-up pass (2026-10-03, after the widening).** Sign-off DRC went from 53 to 21 errors and the KiCad unconnected count from 58 to 57. Changes:
- The J10/J11 shield pads connect solidly to the outer GND pours: 6 starved thermals gone, and a better shield bond.
- The SWDIO via that sat 0.25 mm from a J10 shield-leg hole was re-routed (13 hole-clearance errors). The router model `tools/mr.py` now keeps every net 0.30 mm from plated holes (`fab_pth_hole_clearance`), so this cannot recur.
- TP_RST_MCU (next to analog C25) and a +3V3_D stub at R49 were re-routed locally.
- LCD_RST is routed.
- DRU patch v10 (below).

The board before this pass is `backups/RFVD_SENSOR_BOARD_before_drcfix_2026-10-03.kicad_pcb` (+ `.kicad_dru`).

**Silkscreen.** All reference designators are hidden on F/B silkscreen (`tools/hide_silk_refs.py`); the fab layers keep them. The board before this step is `backups/RFVD_SENSOR_BOARD_before_silkrefs.kicad_pcb`.

## Design-rule changes (`dru_changes_vs_project.diff`)

1. **Patch 1.**
   - Same-net GND via-in-pad is allowed in the U.FL ground pads of J1 and J300.
   - GND stitching vias are allowed inside the K16/K18/K19 lanes. They are the lane net's return path; foreign signals stay banned.
2. **Patch 2:** `layout_pofv_via_in_pad_6l`. Every via is resin-filled and capped (JLC 6-layer POFV), so a same-net via-in-pad is allowed in any SMD pad. Copper and hole spacing to neighbouring pins is still checked.
3. **Patch 3:** Default class minimum width 0.12 -> 0.10 mm (opt stays 0.12). This is the JLC 6-layer floor; slow GPIO only.
4. **Patch 4:** `v9_regn_light` / `v9_regn_clearance`. BQ25798 REGN (< 50 mA) may run at 0.15 mm (opt 0.3) with 0.15 clearance, so it can leave pin 5 at 0.4 mm pitch.
5. **Patch 5:** `v9_w_power_neckdown_chg_caps`. Power tracks may neck down to 0.2 mm inside the charger caps' (C3xx) courtyards.

6. **Patch v10 (2026-10-03, DRC clean-up).** Two rules are appended; each was A/B-checked with a sentinel run.
   - `v10_chg_bootstrap_vias` lets the four BQ25798 bootstrap-path vias (BTST1/BTST2 and the SW1/SW2 drops to C310/C311 on B) use 0.45/0.20 POFV vias. They carry only bootstrap-capacitor charge; the switch current runs on F from U301 pins 26/28 into L301. Their class (Power_Battery) would otherwise ask for 0.6/0.3.
   - `v10_regn_light_in_chg_caps` keeps REGN at its patch-4 0.15 mm minimum inside the C3xx courtyards, where patch 5's 0.2 mm neck-down rule was overriding it.
   - Result: 11 DRC errors fewer, no new ones.

**Available but not applied.**
- `tools/dru_patch6.py` gives Power-class pours on In3 an exemption from `planes_gnd_only`. Apply it only if you add an In3 power pour (for example a +3V3_D feed).
- All versions are in `tools/dru_versions/d0..d7.kicad_dru`. `d0` is the project DRU; `d7` (d5 + v10) is the one in this folder. The patch scripts were retired in the 2026-10-02 tool clean-up, and `dru_patch6`'s text is in `d6`.

## Bringing it back into the project

**Option A (simplest).**
1. Close KiCad.
2. Back up the three files in `RFVD_SENSOR_BOARD_GITHUB`.
3. Copy `RFVD_SENSOR_BOARD.kicad_pcb`, `.kicad_pro` and `.kicad_dru` from this folder over them.
4. **Also copy every `*.kicad_sch`, the `libraries/` folder, `fp-lib-table` and `sym-lib-table`.** The schematics and libraries changed from checkpoint 1 on, so the board alone would not match its schematic. Then re-run ERC, DRC (`--all-track-errors`) and the parity check.

**Option B (incremental, through Konnect).** This is the path prepared earlier. **Since the 2026-10-02 widening, option A is required.** `transfer_plan.py` does not carry the Edge.Cuts outline or the changed zone and rule-area outlines.
1. `tools/transfer_plan.py PROJECT FINAL plan.json` lists moves, flips, tracks, vias and zones.
2. `tools/transfer_exec.py plan.json BOARD closed calls.json` builds the Konnect calls. The closed phase is flip_component plus set_component_placements; the live phase is delete_trace, route_trace and add_via, with vias added after the tracks.
3. `tools/kipy_vias.py plan.json` removes project vias over KiCad IPC. Do a dry run first, then `--apply` as one undo step.
4. Verify via nets after saving: KiCad re-nets an IPC-created via from the copper it touches.
