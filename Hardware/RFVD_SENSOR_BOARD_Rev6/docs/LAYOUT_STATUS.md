# Layout status and what is left (handoff 2026-10-02; updated at checkpoint 3, 2026-10-04)

## 2026-10-07: ECO-002 (power modes) and ECO-003 (hierarchy, renumbering) landed

Designators below use the ECO-003 numbering (page × 100 + index). `REFERENCE_MAP_ECO-003.md` maps them to the old ones.

**PCB update 1** (re-link by designator) and **PCB update 2** (by path, 21:29) are both done. The board now carries the new designators and rating values: 348 footprints, none moved, all 136 copper items on auto-named nets carried to the new names, every pad net equal to the schematic.

- **DRC after update 2** (refilled copy): 361 violations (475 on the same board before the update, because the v13 rules already use the new names), 248 unconnected (unrouted, unchanged).
- **Left from the rename:** the longer designators add 18 silkscreen overlaps around U1301/U1302. The 4 short stubs (< 0.03 mm) on `Net-(U401-PC14/PC15)` at the via/pad centres now fall under `v7_geom_smooth_critical`. Both are warnings for the human router (routing is done by hand; Claude only places parts).
- **Old item, renamed:** `zz_side_guard_B` wants U301 (SHT40) on B.Cu; it has been on F.Cu at (156.4, 138.1) since before ECO-003 (the same failure showed as U701).
- **If update 2 is ever redone:** the Update PCB dialog remembers its boxes. Untick "Re-link footprints…" and "Delete footprints with no symbols" (H1-H4 have no symbols). A first try with both ticked duplicated 307 parts off-board; that board is kept in `_working/backups/f8_relink_broken_2026-10-07_2109/`.

### Placement pass for EMC and hand routing (2026-10-07, late)

Claude moves parts only; the team routes. Every move went through Konnect `set_component_placements` on the closed board, after a scratch copy passed DRC. Result: 0 new copper DRC errors (369 items, 361 at the start; the extra ones are silkscreen reference overlaps), ratsnest 3509 → 3482 mm.

- **U1301 TPS62913 buck re-laid to TI SLVSFP4B Fig. 10-1** (the board view is Fig. 10-1 turned 90° clockwise). Before: the switch pin faced away from L1301 (about 3.5 mm of SW copper past the VO pin), the 10 µF input caps sat on the far side of the IC, and the output-cap ground came back to PGND around L1301 (about 8 mm). Now:
  - U1301 (159.365, 98.68) rot 90. SW pin 2 faces L1301 pad 1 with a 0.71 mm gap; L1301 is rotated in place to rot 0 at (160.80, 102.44), still inside K5.
  - Input caps C1306 (100 nF) and C1305 (10 µF) are stacked on the VIN pin 6 / PGND pin 4 columns, north of the IC. C1304 (10 µF) sits on the In3 VSYS feed via, and C201 beside it.
  - Output caps C1301/C1302/C1303 are in a row east of the IC. Their GND pads are 1 mm from PGND, and VO pin 3 is 0.7 mm from C1301's +3V3_D pad.
  - FB/NR/S-CONF network on the west face: C1308 (NR/SS), R1302/R1301 (FB) on F.Cu; R1304 (S-CONF) and R1303 (EN/SYNC pull-down) on B.Cu under their escape vias. C1307 (47 pF) is at the EN/SYNC corner.
  - The user approved deleting 14 obsolete pre-ECO copper items first: 6 BUCK_SYNC, 5 VSYS and 2 BUCK_FB segments, and the GND via at (156.857, 95.959). Backup: `backups/before_stale_buck_copper_2026-10-07/`. Before/after picture: `03_hardware/_working/placement_2026-10-07/buck_before_after.png`.
  - `docs/sensitivity.json` now holds TPS62913 budgets for the 14 buck parts (it still had LMR43620 rules).
- **C1311** (LDO OUT 22 µF, B.Cu) moved to (159.75, 86.85) rot 180: 0.6 mm from OUT pin 1 and SENSE pin 3 (it was 3.4 mm away). Its GND pad covers an existing GND via.
- **FL1301** moved to (153.75, 88.25) rot 0, at the `+3V3_A` cut point. Its two runs drop from about 12 mm to 6 mm, and it stays 15.7 mm from L1301.
- **R1211** (EXP_I2C_SDA pull-up) moved to B (148.25, 136.25), saving 10.7 mm. **TP1104** (CHG_STAT) moved to B (141.5, 115.0).
- **Not moved, because they carry team-routed copper** (for the router to decide):
  - **C1113:** the BQ25798 SYS 0.1 µF is 4.07 mm from pin 25 (rule 3 mm) and farther away than the 10 µF C1114.
  - **AD7380 input RC:** C1004/C1005 are 1.70/1.90 mm from the AIN pins (rule 1.0 mm). R1006 is 4.3 mm away.
  - **RN601:** 3.69 mm from U401.58 (3 mm rule).
  - **C702:** 2.74 mm from U702.15 (2.5 mm rule).
- **U1302's north row (C1310/C1312)** is boxed in by its own GND vias, so no closer legal spot exists. It stays as is.
- **Backup** before this pass: `03_hardware/_working/backups/before_placement_2026-10-07_2245/`.

### Placement done (2026-10-07, Konnect + approved via edits)

- **Board positions:** every footprint is back at its pre-ECO position. The routing is intact apart from the stale copper listed below.
- **U1301 TPS62913 buck:** superseded by the late pass above (U1301 rot 90, TI layout).
- **U1302 TPS7A4701, RECORD LDO:** B.Cu at (159.1, 82.5), between FB1301 and the K19b VSYS lane. It is clear of the K18 +3V3_D feed channel.
  - North side: EN pin 13 with R1305/R1306, and NR pin 14 with C1312.
  - IN pins 15/16 at the north-east corner, with C1310 (100 nF) and C1309 (10 µF).
  - OUT pins 1/20 at the south-east corner, with C1311 (22 µF): moved closer in the late pass above.
  - Thermal-via field is GND.
- **FL1301 (NFM18):** superseded by the late pass above (now at the `+3V3_A` cut point, (153.75, 88.25)).
- **C1315 (A3V3_DAMP):** moved 3.6 mm north to (156.6, 79.2) to clear U1302's F.Cu thermal pad.
- **Deleted footprints:** C35, C37, C41 (ECO-002).

### Stale copper removed or renamed

- **Renamed:**
  - 9 F.Cu segments of the FB1301 → C1314/R1307/C1313/TP1303 node, to `/3.3 V supplies/+3V3_A_PRE`;
  - 6 segments of the C1307/TP1302 cluster, to `/3.3 V supplies/BUCK_SYNC`.
- **Deleted tracks:**
  - the `+3V3_A` diagonal from C1314 to the analog corner, since FL1301 now goes in series;
  - the BUCK_SYNC stub on U1301 pin 10;
  - the old VIN stubs on U1301's west pins.
- **Deleted vias (one undo step, kipy):**
  - the `+3V3_A` via in C1313's pad;
  - the BUCK_SYNC via in R1303's pad, which overlapped U1301 pin 10;
  - two old GND vias under U1301;
  - five GND stitching vias under new pads or too close to U1302's thermal vias.

### Routing to do (DRC: 0 shorts; remaining violations are the pre-ECO kinds)

| Node | Connect |
|---|---|
| U1301 pins (rot 90) | North: VIN 6 (159.115, 97.98), PG 5 (159.615, 97.805), PGND 4 (160.115, 97.98). South: EN/SYNC 1 (159.115, 99.555), SW 2 (159.615, 99.38), VO 3 (160.115, 99.555). West, x 158.44: PSNS 7 (y 97.93), NR/SS 8 (98.43), FB 9 (98.93), S-CONF 10 (99.43). |
| U1301 VIN/PGND | Pin 6 straight north to C1306.1, then C1305.1. Pin 4 straight north to C1306.2, then C1305.2. All F.Cu, no vias between the caps and the pins. Use 0.25 mm necks beside the PG via. VSYS feed: from the In3 VSYS via in C1304.1 (159.31, 93.14) diagonally to C1305.1. |
| BUCK_PG (pin 5) | PG sits between VIN and PGND, under the input caps. Escape through one via at (159.615, 97.44), touching the pin end and checked legal on scratch. Then In3 to U401 PD3. |
| U1301 GND | One solid F.Cu island joining PGND pin 4, C1306.2, C1305.2 and the C1301/C1302/C1303 GND pads, with GND vias in the cap GND pads. PSNS pin 7: GND via at (158.2, 97.25) (checked legal). |
| U1301 SW | Pin 2 straight south onto L1301 pad 1 (0.71 mm). F.Cu only (`via_none_on_buck_sw`). Keep other nets at least 0.5 mm from SW copper (`sp_buck_sw_to_signal`). |
| U1301 VO / +3V3_D | Pin 3 east to C1301.1 (0.7 mm). L1301 pad 2 straight north to C1301.1/C1302.1 (0.7 mm). From the COUT row to the +3V3_D In3 trunk at (160.81, 92.43) and FB1301. |
| BUCK_SYNC | Pin 1 diagonally to C1307.1 (158.06, 101.23). Via at (158.06, 102.0), in R1303.1 on B.Cu (checked legal: the earlier spot at R1303's old pad was 0.5 mm too close to SW). The In3 run goes to TP1302 (157.18, 93.30), where the existing In3 feed from the MCU ends. |
| FB / NR / S-CONF | Pin 8 straight west to C1308.1 (0.83 mm). Pin 9 west to R1302.2, then R1301.2 (FB node). R1301.1 (+3V3_D) gets a via-in-pad, then the In3 remote-sense run to COUT. Pin 10 diagonally to a via at (157.75, 99.94), in R1304.1 on B.Cu (checked legal). |
| U1302 | VSYS from the K19b lane to C1309/C1310 and pins 15/16. OUT pins 1/20 and SENSE pin 3 to C1311.1 (161.225, 86.85; 0.6 mm from pin 1), then 1.3 mm west on B.Cu to the +3V3_D via at FB1301 (159.39, 86.54), which sits between C1311's pads. LDO_EN from R1305/R1306 to U401 PC13. GND pads to plane vias. |
| FL1301 | Pad 1 `+3V3_A_PRE` (152.95, 88.25) from the TP1303 stub end (153.59, 85.72). Pad 3 `+3V3_A` (154.55, 88.25) round the south side to the trunk end (152.05, 91.40). GND pads (153.75, 87.85 / 88.65) to GND vias. |
| C1315 | Pad 1 (A3V3_DAMP) back to R1307 pad 2 |

## Checkpoint 5 (2026-10-04): DRC clean, every open link routable. Board sha256 `f9fb559366`

| Measure | m17 (session start) | Checkpoint 5 |
|---|---|---|
| Plain DRC errors (all-track-errors) | 3 | **0** |
| Warnings | 116 | **110**, each explained in the warning ledger below (42 are the deliberate hand-off vias) |
| Open links | 50 (28 blocked) | **42 (0 blocked: 12 direct, 30 with a mapped path)** |
| R17 return-via failures | 45 | 7 (all at the dense U401 west row; documented) |
| Neck chains | 46 | 0 |
| Ratsnest | 4018 mm | 3522 mm |
| Footprints locked | partial | all 341 |
| BOM | 105 lines / 318 parts | 100 / 309 |

Landed since checkpoint 4a, all gated:
- **4b1:** SEAM + BATT (F1401 Style 2 at (163.05, 126.80) r90 B; PACK_RAW B-only 1.0 mm, no via).
- **4b2:** BOM consolidation (SW3, R18, R44, R49, R206, R207, R214, U702@pre-ECO003 and C702@pre-ECO003 removed).
- **4b3:** J1101 −0.96 mm.
- **4b4:** U1201 cluster to F beside U301 (DRU side-guard patch d9).
- **5a:** last DRC fixes.
- **5b/5c:** escape vias for the blocked links; R1103 moved to (146.85, 112.20).
- **5 lock:** all footprints locked.

Accepted and documented:
- the AFE ring south wall is open over 5.6 mm;
- PROG passes 0.21 mm from the BTST2 via (read only at power-up);
- 7 R17 vias at the U401 west row have no legal GND site;
- the F1401 Style 2 footprint has no 3D model yet.

### Placement sign-off (2026-10-04, on `f9fb559366`, board unchanged)

- **`tools/placeaudit.py`: 0 MOVE, 0 OVER**, 7 fixed (mechanical); ratsnest 3522 mm.
- **`tools/dsgap.py`** (new): measures every datasheet budget in `docs/sensitivity.json` on the board itself. It uses the nearest pin of the IC on a shared net, so it follows pin swaps and multi-pin supplies.
  - The stored `gap_mm` values came from the old parts.json poses and had flagged the wrong parts (R506, C703, D1101, C1508, R1007).
  - Result: 269 budgets measured, 264 within budget, 5 over, all justified with measured reasons. The 73 rules of removed parts are not measured.
  - Per-IC table: `docs/PLACEMENT_DATASHEET_CHECK.md`.
  - placeaudit now takes OVER from this live check.
- **The 13 former MOVE candidates were kept for function**, each reason checked on the board (`tools/placeaudit_keep.json`):
  - divider tops at the rail end (R1505, R1506);
  - source termination at U401 (R804);
  - pull-ups at the MCU bus end, ≥ 5 mm from U302 (R302, R301);
  - load-end isolation (R601);
  - mechanical pogo pad (TP1102);
  - button ESD series R at the MCU (R808);
  - heat-spread backlight CCR (D803);
  - in-box RH/T sensor (U301);
  - slow gate resistor (R809);
  - C1103, inside its 5 mm budget, whose suggested spot is not copper-legal;
  - R1212 (below).
- **The 5 parts over their budget:**
  - C1113 / C1108 (BQ25798 SYS / PMID 0.1 uF, 2.29 / 1.69 mm against 1.5 mm EMC practice): at the two ends of U1101's west pin column, GND via in pad, as in TI Fig. 8-21. SW801 / SW802 exit between them.
  - C508 (REF5030 VIN, 0.1 mm over).
  - U1102 (USB ESD, 3.69 mm): at the edge of J1101's no-foreign-copper shell region.
  - R1212 (below).
- **Two minor deviations, low severity, with optional hand fixes in `docs/LEAD_GUI_STEPS.md` (A, B):**
  - R1212, the EXP_I2C_SCL pull-up, stayed at its pre-cp4 spot when U1201 moved, so its SCL tap is a 12 mm In3 stub. That is harmless at ≤ 400 kHz, but it uses an In3 corridor. The spot at U1201 is copper-blocked.
  - On SYS, the 10 uF C1114 (1.88 mm) is closer to pin 25 than the 0.1 uF C1113 (2.29 mm); TI Table 5-1 asks for the 0.1 uF closest.
- **Detours (routed copper > 1.6 x ratsnest):** EXP_TMR1 2.41, EXP_INT0_N_MCU 1.94, TP_RST 1.85, EXP_I2C_SDA 1.70 and SWCLK 1.64. All five are Harness_IO class: slow or static lines (a timer line, an interrupt, a reset, I2C, and the debug clock used only while programming). They are routed and DRC-clean; the extra length costs copper only.

### DRC warning ledger at checkpoint 5 (fresh run 2026-10-04 on `f9fb559366`)

Command: `kicad-cli pcb drc --all-track-errors --severity-all --refill-zones`. Result: **0 errors, 110 warnings, 42 unconnected, 0 track_angle**. Every warning is listed below by rule; item coordinates are in `outputs/RFVD_DRC_report.json`.

| Count | Type (rule) | Items | Why it is acceptable / what removes it |
|---|---|---|---|
| 42 | via_dangling | One escape via per open link | Deliberate hand-off vias (`ROUTING_FINISH_GUIDE.md` §0 starts each link from them). They disappear as the 42 links are routed; delete any left unused. |
| 45 | track_width (`v11_in3_power_digital_width`, min 0.4 / opt 0.6 mm, severity warning by design) | In3 power segments of 0.20-0.30 mm: +3V3_D 23 (41.5 mm in total, longest 7.9 mm, narrowest 0.20 mm), +3V3_UI 13 (27.6 mm, 0.30 mm), +5V_A 7 (7.0 mm, 0.25 mm), +3V3_EXP 2 (1.1 mm, 0.20 mm) | Necks where the dense MCU / display / AFE fields leave no room for 0.4 mm. Worst-case DC drop counts every narrow segment in series, In3 at 15.2 µm copper and ρ 1.72e-8 Ω·m: +3V3_D 160 mΩ (16 mV per 100 mA); +3V3_UI 104 mΩ (4 mV at its ≤ 38 mA logic load, 32 mV at U801's 303 mA limit); +5V_A 32 mΩ (4.8 mV at the LT3045's 150 mA limit, ILIM 1k); +3V3_EXP 4 mΩ (2.6 mV at U1501's 638 mA limit). Each is under 1.5 % of its rail. The error-level neck rules pass (0 neck chains). |
| 6 | track_segment_length (`v7_geom_smooth_critical`, min 0.1 mm) | EXP_MISO_MCU F (126.18, 91.22) 0.099999 mm (rounding); Net-(U401-PC15) B (140.80, 98.84) 0.05 mm; LCD_D4 In3 (144.30, 124.32) 0.05 mm; ADC_VENV F (139.67, 81.00) 0.097 mm and (138.36, 86.82) 0.079 mm; ADC_REFCAP F (134.80, 82.50) 0.035 mm | Sub-0.1 mm jogs where a track meets an off-grid pad centre: geometric only, electrically nil (≤ 0.1 mm of copper). KiCad's *Cleanup Tracks & Vias* (merge collinear segments) removes them: `LEAD_GUI_STEPS.md` C. |
| 5 | track_dangling | In3: LCD_D6 (135.70, 87.35) 0.85 mm, TP_SCL (130.60, 89.39) 0.40 mm, EXP_CS0_N_MCU (121.12, 87.68) 1.86 mm, EXP_SPI_SCK (128.09, 90.67) 0.55 mm, LCD_RST (141.62, 88.00) | The first four are hand-off stubs of open links (their nets are in the 42). On LCD_RST, a routed net, the In3 diagonal (141.62, 88.00) → (143.12, 89.50) runs about 0.28 mm past the T-junction where the J801 branch joins it at (142.89, 89.34). That is dead copper on a static reset line, far below any resonance that matters. *Cleanup Tracks & Vias* trims it (`LEAD_GUI_STEPS.md` C). |
| 3 | length_out_of_range (`len_source_stubs`, max 3 mm) | PSRAM_IO0_MCU U401.58 → RN601.1 4.67 mm, PSRAM_IO1_MCU U401.59 → RN601.3 3.71 mm, PSRAM_IO3_MCU U401.60 → RN601.2 5.02 mm | RN601 sits on B under U401's pin row (P1-21 single termination, cp2b; SI re-run passed). A 5 mm source stub is far below the critical length of a 1 ns edge (about 25 mm), so the series termination still works. |
| 1 | skew_out_of_range (`skew_venv_eref`, max 2.0 mm) | ADC_VENV vs ADC_EREF: −2.21 mm on a 14.57 mm target | 0.21 mm beyond a 2 mm warning band on a quasi-DC differential detector pair (envelope / reference). The mismatch is about 15 ps, irrelevant at the envelope bandwidth. |
| 4 | silk_over_copper | Library silk outlines of U702, U1401, U1001 and U1101 clipped by the neighbouring pads of D701.2, R1405.2, C1002.1 and C1108.1 | Cosmetic: JLC clips silkscreen at mask openings. |
| 1 | silk_overlap | U1101's silk polygon touches C1108's silk at (143.21, 114.40) | Cosmetic: C1108 sits courtyard to courtyard with U1101 on purpose (closest PMID cap, `PLACEMENT_DATASHEET_CHECK.md`). |
| 2 | silk_edge_clearance | J1101's silk outline segments at (119.19, 122.76) and (119.19, 132.16) against the west edge (118.00) | Cosmetic: the receptacle is flush with the edge by design (port notch), so its library outline crosses the edge and JLC trims it. |
| 1 | lib_footprint_mismatch | J1101 | The board copy carries the pin-in-paste shell pads (P1-12); `LEAD_GUI_STEPS.md` row 4 mirrors it into the library. |

ERC on the same master: **0 errors, 0 active warnings**, 1 excluded `pin_to_pin` (U401 VCAP1 / VCAP2 tied with C419 / C420 per ST AN4938; the reason is stored with the exclusion in the `.kicad_pro`). Parity: `tools/place/sync.py --dry-run` against a fresh netlist prints "no changes".

### Sourcing check (live, 2026-10-04)

`outputs/RFVD_JLCPCB_BOM.csv` has 100 lines and 309 placed parts, and every line has an MPN and an LCSC number. Each LCSC number was queried against the public JLC mirror (JLC assembly stock), and LCSC's product detail was queried where the mirror lacks a part. Need = 2 boards.

| Result | Lines |
|---|---|
| JLC assembly stock ≥ need + 5 spare | 93 |
| JLC assembly stock ≥ need, under 5 spare | C510 25MU105MA23216 (3 for 2), U701 TLV809EA46DBZR (3 for 2; LCSC holds 12 more) |
| JLC short or unlisted, but LCSC's warehouse holds them (JLC parts pre-order) | J802 84953-6 (JLC 1, LCSC 5,567, Mouser 3,142), U502/U501 OPA2320AIDGKR (JLC 1, need 4; LCSC 1,485), U1001 AD7380BCPZ-RL7 (LCSC 78), RN601/RN801-RN803 4D02WGJ0470TCE (LCSC 14,550) |
| **Only via Global Sourcing** | **L1301 XGL4020-472MEC: JLC 1 (enough for one board), LCSC 0, not listed at Mouser.** The lead decision of 2026-10-04 already sends L1301 through JLC Global Sourcing. Order it early, or buy it from Coilcraft. |

Every JLC listing's MPN matches the BOM MPN. Evidence: `04_parts/snapshots/jlc_stock_cp5_2026-10-04.json`, `04_parts/snapshots/mouser_cp5_short_2026-10-04.json`.

### Done-criteria evidence (re-measured 2026-10-04 on `f9fb559366`)

| # | Criterion | Measured |
|---|---|---|
| 1 | Medium-or-higher findings fixed or documented | `CRITIQUE_STATUS.md`: 40 P0/P1 rows, 0 Planned. The board facts behind the Done rows were re-measured: R17 7 of 88 fast-net vias (documented); 0 neck chains; mask expansion 0; JP401/JP402, U702@pre-ECO003 and SW3 absent; RN601 on B; U1201 on F; F1401 Style 2 at (163.05, 126.80); R1512 64.9k on both board and schematic |
| 2 | ERC, parity, datasheets, simplifications, BOM | ERC 0 errors, 0 active warnings, 1 documented exclusion; parity "no changes"; `DATASHEET_CHECKS.md` covers every IC; BOM 100 / 309 with MPN and LCSC; sourcing as in the table above (L1301 needs the Global Sourcing route) |
| 3 | Placement | placeaudit 0 MOVE / 0 OVER; dsgap 269 budgets, 0 unjustified; ratsnest 3522 mm (m17 4018); 341 / 341 footprints locked |
| 4 | DRC | 0 errors, 110 warnings (< 116), each in the ledger above; track_angle 0; sign-off PASS |
| 5 | Open links | 524 / 566 routed. `ROUTING_FINISH_GUIDE.md` §0 has 42 rows with both end coordinates (12 DIRECT, 30 ROUTE, 0 BLOCKED). It matches the live open-link list net for net, with all 42 end points verbatim. feasible.py ran at 18:58:35 on this board (last write 18:56:55) |
| 6 | Outputs and docs | `outputs/` regenerated 18:58-19:16 after the board's last write; the shipped DRC report equals a fresh run type for type. EXP_SYNC note: `FIRMWARE_NOTES.md` §1 (2.400 MHz, not 2.000). Release zip `RFVD_SENSOR_BOARD_release_2026-10-04_cp5-signoff.zip` |

## Checkpoint 4a (2026-10-04): regional hand-layout pass. Board sha256 `08570ddf0b`

Five region packages were each replayed alone on the checkpoint-3 master, then composed with the sourcing package. All gates pass: ERC 0, netlist unchanged except the sourcing fields, parity 0, no net worse. Backup: `backups/before_cp4a/`.

| Measure | Checkpoint 3 | Checkpoint 4a |
|---|---|---|
| DRC errors (all-track-errors) | 278 | **109** (west/J1101 68, MCU-core seam 26, battery 12, other 3) |
| Warnings | 134 | 116 |
| Open links | 44 | 43 |
| R17 return-via failures | 45 | 13 |
| Neck chains (`necks.py`) | 46 | 12 |

| Region | Main changes |
|---|---|
| A RF/AFE | 1.0 mm F.Cu GND ring under a mask-open strip, 19 fence vias, FL701 on the east wall, TP701/TP503 moved off the ring. VSYS_LDO at 0.5 mm. +5V_RF moved off B (K3). 12 edge vias. **South wall left open over 5.6 mm (x 137.7–143.3)**, where EREF/VENV leave between U702 and R506/R501/C501. Closing it means moving the datasheet-placed filter parts; at 64–128 MHz a 5.6 mm slot still attenuates about 46 dB, so it stays open (documented). |
| B1 MCU west | 68 of 73 errors fixed. RN802/R603 cluster re-escaped (via-in-pad), the U602-SCLK 3W violation fixed, VCAP and +3V3_D re-laid at 0.3 mm, 12 R1302 GND vias, 7 edge vias. |
| B2 MCU east | The PC14 via moved out of Y402's pad gap (sign-off LSE rule PASS), +5V_A and +3V3_D widened, C1201 GND via, 4 R17 vias, 7 edge vias. |
| C power band | VSYS necks to 0.5 mm. The VSYS island at U1502 routed (never through R1509.1). CHG_BAT/VBAT_PACK/PMID In3 at 0.8 mm. VBUS re-built (0.8 mm In3, 0.5 mm B). BQ25798 hot-loop "in all cases" subset: pin-27 stub 0.4 mm with 3 GND vias, VBUS via out of the loop, C1102 second via. 5 edge vias. |
| E south | EXP_SYNC/EXP_GATE on the pad axes at J1201 (EXP-04). EXP_VHP rebuilt on F at 0.5 mm. +3V3_EXP/+3V3_D/+3V3_UI necks widened. 5 R17 vias, the I2C_SDA T-junction removed, 5 edge vias. |

## Checkpoint 3 (2026-10-04): rules v11 and the stale sheet notes. Board sha256 `527e801c62`

**What landed.**
- **Rules v11** (`tools/dru_versions/d8.kicad_dru`):
  - side-aware courtyard exemptions (P0-5): 21 rules split into F/B/inner copies, plus side-guard assertions;
  - neck-length caps `v11_neck_len_*` (P0-5);
  - In3 power widths (P1-6), hole_to_hole as an error;
  - missing rule areas K6, K8, K21, the K11 shift, K19a/b, K19c removed (P1-16);
  - J1101 keep-out, pre-defined track/via sizes, skew_sdmmc 17 mm (D20), mask expansion 0 (P1-12);
  - EXP_SYNC and LCD CS/DC net classes (P1-15);
  - LCD source stubs 16 mm (WR stays 3 mm), SD lines out of the source-stub rule (the series R is in U601), skew_qspi pointed at the PSRAM RAM side, len_psram_ram_stubs removed (S-17).
- **Sheet notes and fields** (Konnect):
  - U1301 sync at 833 kHz;
  - R1301/R1302 = 23.2k/10k and L1301 Isat 3.0 A;
  - "charger is on the BQ25798 sheet";
  - U801 limit 234–303 mA;
  - the EXP eFuse values (R1513 1.50k / 64.9k / 47 nF);
  - ADC range note;
  - the RF interface row;
  - the +5V_RF caps;
  - FL701 (no can on Rev A);
  - C41/R1301 cite SNVSBY5B;
  - R1002 path order;
  - datasheet links for D801–D804 and F801.

**Measured on the master** (`--all-track-errors`):
- ERC 0, parity 0, unconnected 44, sign-off rules PASS.
- DRC **278 errors, 134 warnings**. That is intended: the stricter rules expose copper the old rules hid.

| Errors | Type | What it is | Fixed in |
|---|---|---|---|
| 115 | track_width | Power tracks narrower than their class on the wrong side or layer of an exemption (side-aware split) | Checkpoint 4 R706 |
| 61 | track_segment_length | Neck segments > 1.0 mm (`tools/necks.py`: 46 chains, 166.5 mm) | Checkpoint 4 R706 |
| 60 | clearance | High-speed / clock 3W and analog-to-harness spacing (e.g. U602-SCLK vs PSRAM_CS_N In3 0.21 mm; J1201.33 EXP_GATE vs EXP_SYNC 0.175 mm, critique EXP-04) | Checkpoint 4 R702–R5 |
| 42 | items_not_allowed | Foreign copper in keep-outs, mainly under J1101 (P1-7) | Checkpoint 4 R702 |

**Tool fix found here.** Without `--all-track-errors`, kicad-cli reports one error per track, and which one varies between runs: plain runs gave 33 clearance pairs ± 1 against 60 complete. Every DRC call in `tools/` now passes the flag. The checkpoint-2b numbers (0 errors, 82 warnings) were taken with sign-off (complete) and stand.

## Summary (checkpoint 2b, board sha256 `f539f0317c`)

| Item | Value |
|---|---|
| Board | **52.05 x 90.05 mm**, 6 layers, JLC06161H-3313 stackup (set by the lead in m17) |
| Parts | **350 footprints** (194 top / 156 bottom). Checkpoint 2b removed 39 and added 8 (2a: 381). |
| Routed | **538 of 582 connections (92.4 %)**; **44 open in 43 nets** (2a: 47; m17: 50). GND islands: **0**. All are drawn in `../outputs/RFVD_unrouted.png` |
| DRC errors (KiCad, project DRU, run in this folder) | **0.** The two `skew_sdmmc` errors are gone: the EMIF06 front end shortened the card-side SD lines to a 2.46 mm skew. **82 warnings** (2a: 85; m17: 97 counted the same way); every type is explained below. |
| DRC sign-off (`tools/drcsum.py`) | **0 errors**; all #SIGNOFF EMC rules pass |
| ERC | **0 errors, 0 warnings**; 1 documented exclusion (U401 VCAP1/VCAP2 tied, ST AN4938) |
| Ratsnest (placement audit) | **3617 mm** over 531 connections (2a: 3806; m17: 4018) |
| Return vias (R17, `retvia.py`) | 42 of 82 fast-net vias lack a GND via within 1.0 / 1.5 mm (2a: 71 of 103); fixed in checkpoint 4 |
| Copper | 3,029 mm of track (F 915 / In3 1,141 / B 973), 970 vias (876 of them 0.45/0.20), 7 zones, 43 rule areas |
| JLC BOM | **106 lines, 318 placed parts** (2a: 105 / 346) |

**Warnings at checkpoint 2b (82), by cause.**

| Count | Type | Cause | Goes away in |
|---|---|---|---|
| 36 + 7 | via_dangling, track_dangling | Escape vias and stubs of the 44 open links | Checkpoint 4 routing |
| 20 | length_out_of_range | Source stubs over 3 mm: 16 len_source_stubs, 3 len_psram_ram_stubs, 1 len_psram_clk_inward. The rules were written for the old resistor layout. | Checkpoint 3 (16 mm LCD rule, PSRAM/SD rule edits) and checkpoint 4 |
| 7 + 4 | track_segment_length, track_angle | Short and angled pieces of the open-link escapes | Checkpoint 4 |
| 5 + 1 | silk_over_copper, silk_overlap | Library silk outlines clipped by neighbouring pads. JLC clips silk at mask openings. | Accepted (cosmetic) |
| 1 | skew_out_of_range (warning) | skew_venv_eref, the VENV/EREF pair, inside the warning band | Checkpoint 4 |
| 1 | lib_footprint_mismatch | J1101 pin-in-paste on the board copy only | Lead GUI step 4 |

**Warning counts.** `drcsum.py` runs DRC on a copy under a long scratch path. There KiCad cannot open the project footprint library (path over 260 characters), which adds 19 false `lib_footprint_issues`. The counts above come from `kicad-cli` run in this folder (`outputs/RFVD_DRC_report.*`).

**Work plan.** The merged critique + placement plan is in [`WORKPLAN_2026-10-03.md`](WORKPLAN_2026-10-03.md); the lead's answers are recorded there.

The missing links are all drawn in `../outputs/RFVD_unrouted.png`. Their coordinates are in `../outputs/RFVD_unrouted.csv` (closest points of the two copper islands).

**Finishing the routing: read [`ROUTING_FINISH_GUIDE.md`](ROUTING_FINISH_GUIDE.md) (2026-10-03).** The team chose to finish the last 50 links interactively in KiCad (push-and-shove). The guide gives:
- every open link with both ends, class width, and whether a legal path exists today: 22 yes, 28 blocked (`tools/feasible.py`);
- the verified unlock moves (R19, R60 + EXP_INT0_N_MCU, C908, the RN803 escapes);
- the J801 via sites;
- the rule areas the router does not enforce;
- the order of work.

It supersedes the per-group tables under "Remaining connections" below, which are kept for history.

## Checkpoint 2b (2026-10-04): memory/SD, display bus, expansion, MCU service, silkscreen

**How it was built.** Four builder packages (G4a2 display, G4b memory/SD, G5a expansion, G5b MCU/service) plus the silkscreen/fab-note and J1101 pin-in-paste packages. Each was replayed alone on the 2a master, then all were composed. Composed gates: ERC 0, netlist = the union of the expected changes, parity 0, no net worse, DRC errors 2 → 0. Engineering review fixes applied before landing:
- R807 (G5b) collided with R804 (G4a2): pad gap 0.147 mm and a courtyard overlap. R807 was re-placed at B (137.55, 100.30) rot 270 and its track re-drawn flush.
- G4b's GND via at (130.93, 105.49) duplicated G4a2's at (131.05, 105.45), with overlapping drills. It was removed.
- R804 is 100R on the existing line instead of a new 47R line.

**Backup.** Checkpoint 2a's files are in `backups/before_cp2b/`.

| Area | Change | Why (critique ID) |
|---|---|---|
| SD front end | ST EMIF06-MSD02N16 (U601, B under J601) replaces R27–R38, D4–D10 and C1308 (20 parts): series R, pull-ups and ESD in one package; RDATA_VCC to +3V3_SD per ST Fig. 2/9. Card-side SD skew 2.46 mm, so both skew_sdmmc errors are cleared. A 0.3 mm +3V3_D feeder on B along the west edge replaces the supply the pull-ups had carried. | S-19 (D7) |
| PSRAM | RN601 (47R ×4) replaces R60–R63/R65–R67; R602 33R goes straight to U602.3; each line has 2 vias instead of 5; SI re-run passes | S-17 / P1-21 |
| Display bus | RN803 serves the U401 south-row pins (WR, D3, CS, D2); RN801 keeps D0/D701; R804 100R on D/C. Three stubs shortened (13.8 → 5.9 mm, 11.1 → 6.4 mm) | P1-20 |
| MCU / service | SW4 BOOT and R801@pre-ECO003 removed (BOOT0 by R401; recovery via SWD under reset). The test pad was not added because every legal spot puts a stub antenna on BOOT0. SWO deleted (61 copper items). LID_INT removed (OPT3004 polled). RECORD/MARK get 1k series resistors R807/R808. | S-16, S-18, S-24, SC-11 |
| Expansion | TCA9517 EN tied to VCCB (R416/C411@pre-ECO003 out); RN1201 330R array for INT1/IO0/IO1/DETECT; 10k pull-ups R1210/R1205 (JLC Basic) on EXP_INT0/1_N; all 14 TPD4E05U06 NC pins tied, 10 lines flow straight through on B; JP401/JP402 removed | S-20, S-22 (part), P1-26, P1-27, S-13 |
| Silkscreen / fab | B silk `${ISSUE_DATE}` (title-block date 2026-10-04) and a 6 × 4 mm S/N box beside the board ID. Fab note on User.Drawings (stackup, POFV, finish, minimums, RF_50R). The layer PDF now has a User.Drawings page. | P1-9, P1-13 |
| J1101 | F.Paste with +0.15 mm margin on the 4 shell slots (pin-in-paste); the library footprint is mirrored by lead GUI step 4 | P1-12 |

**Decisions in 2b.**
- S-15 (CAT4104) is not possible: there is no legal SOIC-8 site near J801. Under D1001's fallback the CCRs D801–D804 stay, D803 becomes a K8 shield-spec exception (`BOARD_OVERVIEW.md`), and a VSYS-based duty cap was added to the firmware contract §7.
- S-22 is partial. The CS/RST and 100k arrays would need vias at the ESD entry.
- S-21 stays optional.

**Firmware consequences:** `FIRMWARE_NOTES.md` §2–§4 (unused pins analog, SDMMC1 medium speed, EXP_3V3_EN / EXTI rules).

## Checkpoint 2a (2026-10-04): circuit changes, simplifications and part merges

**What it is.** Groups G1b (parts), G2 (analog/ADC), G3 (power) and G4a (display) from the work plan, plus the fix package G6 (below).

**How it was checked.**
- Every group was built on a scratch copy as a replayable package and gated (`tools/replay.py`): ERC, the netlist against the expected changes, schematic-to-board parity, no net worse (`metrics.py`), and DRC with no new error type.
- An independent engineering review then checked every change against the datasheets, the netlist and the board.
- That review found one blocker. The PACK_RAW rename had quietly moved the unfused battery net from Power_Battery to Default, so DRC passed only because the net had lost its width rules. Package G6 restores the class (Konnect `assign_net_to_class`) and adds the scoped rule `v10_pack_raw_kelvin`, which lets the 0.15 mm Kelvin sense track run on B inside the J1401 courtyard. With the class restored, DRC is the same.

**Backup.** The checkpoint-1 files are in `backups/before_cp2a/`. The change list below comes from the kicad-cli netlist diff of checkpoint 1 against checkpoint 2a.

| Area | Change | Why (critique ID) |
|---|---|---|
| ADC reference | AD7380 internal 2.5 V reference. Deleted R107, TP20 and 24.5 mm of +3V0_REF B.Cu branch; ADC_REFIO is now only U1001.11 + C1006 1 µF | S-26 (AD7380 Rev A Table 7 / Fig. 31) |
| EREF filter | U502's Sallen-Key is replaced by one pole: R506 22.6k + C506 10 nF (704 Hz). R5, R7, R9, C9, C10, C16 deleted; U3A is an unloaded follower | S-27 |
| ADC drive | R507/R505 47R 0.1% → 33R 1%, and C507/C505 1.5 nF 2% → 2.2 nF C0G (τ 72.6 ns). R1006 33R → 100R (AINB− overload ≤ 5 mA with the 2.5 V reference; 0.72 MHz RF low-pass with C1005) | S-3, S-26 |
| VSYS monitor | VSYS divider R21/R22/R23/C57 deleted (the BQ25798 ADC reports VSYS). EXP_ANA_MON moved PA4 → PC0 (R1222 1k / C1201 1 nF). R403 10k pulls PA4 high for the DFU bootloader | S-5, P1-22 |
| VBUS detect | R304/C302@pre-ECO003 deleted; R1109 100k stays as a VBUS bleeder; PC13 is no longer connected (firmware detects the plug via CHG_INT_N/WKUP1 + REG1B, `FIRMWARE_NOTES.md` §2) | S-6 |
| Buck | FB divider R1301/R1302 33.2k/14.3k → **23.2k/10k**: 3.320 V, RFBT‖RFBB 6.99 kΩ (LMR43620 SNVSBY5B Eq. 5 window 5–10 kΩ) | P1-23 / D24 |
| Expansion eFuse | R1512 73.2k → 64.9k: OVLO 9.89 V, above the PFM VSYS level (TPS259631 SLVSET8A Eq. 2). EXP_VHP_IN merged into VSYS (R405@pre-ECO003 0R / R406@pre-ECO003 DNP deleted) | P0-6, S-14, S-9 |
| Supply caps | C27 22 µF VSYS polymer deleted: the LT3045 needs ≥ 4.7 µF at IN, and C202 10 µF sits behind R201 1 Ω (LT3045 Rev B p.18). C68 47 µF on +3V3_UI deleted: no 190 mA inrush on +3V3_D | S-8, S-12 |
| Battery | PACK_RAW now carries the BQ29209 top-cell Kelvin sense: R1404 taps J1401.1 ahead of F1401/Q1401. TP1401 moved to B_VC1. R19/D3 charge LED, TP9 deleted | P1-5, S-7, S-10 |
| Display | 8080-II straps in copper on J801 (IM0 = 1, IM1/IM2 = 0; R200–R202@pre-ECO003 deleted). RDX tied to +3V3_UI: the bus is write-only, which frees LCD_RD_N, PD4 and RN803 element 2. CS/WR pull-ups R50/R203@pre-ECO003 and R204 deleted. R214 100k holds the touch controller in reset. R803 66.5k → 100k 0.1%: display-branch current limit 234/266/303 mA | S-11, SC-05, S-25 |
| Other deletions | DNP footprints C908 and C204@pre-ECO003; R105 (AD7380 SDI series 33R) | S-9, S-4 |
| Part merges | 13 caps 1 µF 25 V X7R: CL10B105KA8NNNC (LCSC out of stock 2026-10-04) → GRM188R71E105KA12D (C86020, same spec). Value strings normalised on 7 caps | S-23 |
| Placement | R1007 to B at the AD7380 SDOA pin; C1002 moved, which clears the C1002/C510 courtyard error | EXTADC-03, P1-25 |
| Rules | PACK_RAW back to Power_Battery + `v10_pack_raw_kelvin` (package G6) | 2a review M1 |

**Minor review items and where they went.**

| Item | Where it went |
|---|---|
| Return GND via at C1201 | Checkpoint 4 return vias |
| The open U1502/C1506/R1509 VSYS island | Checkpoint 4 routing: land the trunk at the C1506/U1502.4 via, never through R1509.1 |
| Stale sheet notes | Notes package after 2b |
| C202 16 V → 25 V (CL31B106KAHNNNE, C14860) | Sourcing package |
| PC13/PD4 | Analog mode (`FIRMWARE_NOTES.md` §2) |
| EREF_BUF meeting R507.1 at 45° | Accepted. The junction is on the pad. Any merge off the pad would create a 90° or 45° joint, which breaks the Analog_Precision 134° rule. |

## Checkpoint 1 (2026-10-04): critique + placement batch 1

Built on scratch copies of m17 and gated before landing:
- `metrics.py`: no net worse, 852 pads with copper.
- DRC: no new violation type.
- Sign-off: PASS.
- ERC: 0 errors.
- Netlist: identical (305 nets).
- Schematic-to-board parity: 0 pad-net and 0 DNP mismatches.

Backup of m17: `backups/before_cp1_2026-10-04/`.

| Area | Change | Why |
|---|---|---|
| Schematic (Konnect) | Deleted 4 zero-length wire stubs on the MCU sheet (PE11-PE14). Cleared the custom `DNP` field on 21 symbols. C1101 set `dnp` / not in BOM; R1106 not in BOM. ERC exclusion for U401 VCAP pin_to_pin | The custom DNP field shadowed KiCad's own DNP flag. It dropped the fitted FB1301 damper C1315/R1307 from the JLC BOM (critique P0-1). |
| RF | C703 to U702 FLT1; U701 rotated next to U702 so ENBL runs on F with no vias. GND vias in pad at FL701 and R704 | ADL5511 layout; U701 kept: ADL5511 Rev E p.8 forbids tying ENBL to VPOS when the supply ramps slower than 20 ms (LT3045 here takes about 55 ms) |
| Analog | R506 / C9 / TP503 compacted: the Sallen-Key input node on one straight track | OPA2320 Fig. 49 |
| Expansion | C1508 (dV/dT) at U1502 pin 2, with GND straight into U1502; pin-1 GND via restored | TPS259631 layout (SLVSET8A 11.1) |
| Charger / USB | D1101 (VBUS TVS) moved to B at J1101's first VBUS via; R1111 on the CHG_CE track | TVS at the connector pin before the branch (TPD1E10B06 7.4.1) |
| Buck | C1301 loop compacted; +3V3_D feed widened to 0.8 mm; VSYS zig-zag and BUCK_SYNC straightened | LMR43620 9.5.1 |
| Battery | 22.9 mm dead antenna stub on the BQ29209 CB_EN node deleted. Q1403 to F, out of the J1401 plug zone. F1401 rotated (PACK+ In3 31.9 -> 27.9 mm). Q1401 / R1403 / C1403 / TP1402 regrouped | EMC (open stub on a 470k node); mechanical clearance |
| MCU | GND vias in pad at Y401.2, C406.2 and C413.2 | AN2867 crystal ground loop |
| Fab | Overlapping EXP_FAULT_N drills removed (two 0.20 mm holes 0.167 mm apart) and re-joined | A drill defect that DRC rated only as a warning |
| Silkscreen | "RF IN" (hidden under the U.FL) replaced by "AIMD" and "CAL" beside each jack. "BAT 2S" moved to B beside J1401. Off-board ID texts replaced by "RFVD SENSOR-D REV A" plus a JLC order-number spot on B. J901 zone parameters taken from the library | Critique RF-03 / P1-9 |

## Hand-layout pass 2026-10-03 (no auto-routers; every track and move decided by hand)

User rule for this pass: "DO NOT rely on tools or auto routers, use your knowledge and tools be precise", and move parts a few mm where that opens a track. Every edit is an explicit coordinate list executed by `tools/place/pen.py`. Each was accepted only if `place/metrics.py` showed no net worse and the KiCad DRC showed no new error. Scratch boards m1-m5; the handoff board is m5.

| Step | What was done | Why |
|---|---|---|
| EXP_TMR1 | B.Cu link at the ESD array D1205 (138.65, 128.0-129.3); the GND stub there was shortened and its via removed. | 0.8 mm open link at J1201. |
| **VSYS trunk** | The charger SYS side (C1115, U1101.25, R21) and the buck/LDO side (U1301, U201, F801, C27-C201, C1116/C1117) were two islands. A 0.6 mm B.Cu track now runs from the 0.8 mm diagonal end at (150.6, 104.0) west along y 104.0, then 45 degrees into the C1115 via (145.5, 104.95). To clear the corridor: | Main power path; it was open. |
| | - LCD_RST moved from B.Cu to F.Cu between U1402's two pin columns (x 150.07); its two vias were removed. | |
| | - The U1402 (RTC LDO) VBAT_PACK feed moved from B.Cu to In3 (0.2 mm, inside the U1402/C1409 courtyards; microamps). | |
| | - The VBUS_DET hub via moved 0.57 mm north to (147.30, 103.25); its dead In3 branch was removed. | |
| | - The +3V3_D feed of the U401.100 / R49 / U1501 / U1201 group was re-laid: Y401.1 down F x 147.83, via (147.05, 102.60) south of C302@pre-ECO003, B.Cu into R49.1. It is 0.3 mm wide, the old jog was 0.2-0.3. This link is the only feed of that group, which includes the TPS2553 expansion rail switch. | |
| Debris | Removed copper that connected nothing: VBAT_PACK zig-zags and a 0.8 mm via at (150.6, 102.4); the LCD_RST dead branch (B and In3); a floating BUCK_SYNC via (147.1, 102.9); a floating LCD_TE B.Cu stub (150.18, 96.5-100.2); a floating LCD_D6 In3 piece (151.8-154.5, 98). | They counted as open items and blocked corridors. |
| Tools | `pen.py`: exact snapping of joints (sub-micron misses read as T-junctions to `track_angle`) and `--check`, a 4 s pairwise rule check of the new copper. `zoom.py`: `--grid` coordinate grid and `--free W,CLR` legal-corridor shading. | Precise hand routing. |

Result after m5: KiCad unconnected items 57 -> 50, VSYS islands 4 -> 3, DRC errors 14 (unchanged; warnings 212 -> 202), no net worse.

Second part (m6-m11, placement and DRC; the copper-aware `query.py free --copper` found the legal poses):

| Step | What was done | Effect |
|---|---|---|
| R304 (VBUS_DET divider bottom) | Moved from under U401 (137.07, 100.83) to beside R1109 at (146.75, 114.48) B rot -90. Short B link R304.2 to R1109.1; GND via at (147.40, 114.15). The 20 mm In3 run R1109 -> R304 across the U401-J801 band (x 136.9-147.4, y 100-114) was removed. | VBUS_DET 55 -> about 35 mm of copper; In3 space freed in the band. |
| R1510 (EXP_VHP bleeder) | Moved beside C1507 at (144.77, 122.67) B rot 270. Its EXP_VHP pad lands on C1507's EXP_VHP via (same-net via-in-pad). GND via at (144.85, 124.75). Its 6 mm In3 branch and two vias were removed. | DRC clearance error R1510 / EXP_VHP_IN fixed; In3 (140.7-144.3, 117-121.3) and B next to R19 freed. |
| USB_DP / USB_DM | The 4 segments at 0.12-0.14 mm widened to 0.15 mm. The 14.2 mm DM run moved 0.011 mm east (0.1 mm from the EXP_TMR_IN_MCU vias); the DM stub/via at U401.70 moved 0.007 mm off the PA10 pad. | 4 `v7_usb_fs_width` errors fixed. |
| R1504 (+3V3_EXP bleeder) | Moved (-0.15, -0.40) mm with its GND via-in-pad. The only offset that keeps >= 1.9 mm from the H3 boss and clears H1201's courtyard. | 2 `mech_h1_h4_boss_courtyard_B` errors fixed. |
| R1212 | Moved 0.04 mm in x. | TP1101/R1212 courtyard overlap fixed. |
| BUCK_SYNC at the LMR43620 input | Via slid 0.07 mm along its own line to (156.23, 93.57); the C1307 stub moved 0.06 mm west (x 157.82). | 3 `sp_clock_3w` errors (BUCK_SYNC vs VSYS 0.27 mm) fixed; now >= 0.30 mm. |

| Geometry (m13) | 22 `track_angle` warnings removed by hand:
- duplicate overlapping CHG_INT_N segments plus a dead stub and via at U401.22;
- micro-jogs (< 0.05 mm) at the R1303 BUCK_SYNC via and in ADC_REFIO;
- a near-vertical PSRAM_IO1 segment made exactly vertical;
- the USB_DM T-branch at J1101 run straight through its via;
- UI_EN diagonal joined exactly;
- ILIM_HIZ re-laid pad to pad (R1102.1 - R1101.2) with the U1101.17 via branch ending in R1102.1's pad;
- PC0's two branches started at one point in C57.1's pad. | `track_angle` 28 -> 6 (left: the USB_DM T at the U1102 ESD tap and an I2C_SDA T at (150, 137); both need a junction moved onto a pad). |
| Dead copper (m15, m16) | Removed only what the DRC flags as dangling on nets that are complete:
- dead vias on BUCK_SYNC, BUCK_SYNC_MCU, PC14, SWCLK, SWDIO, SWO;
- EXP_INT0_N_MCU's dead stub at U401.56;
- a 4 mm dead LCD_RST In3 stub;
- stubs on PSRAM_IO3, EXP_3V3_EN, Net-(Q801-D), +3V3_EXP, GND;
- **a 14 mm dead branch of +3V0_REF** hanging off R107.1 (two vias, B and F runs, a 0.025 mm-step staircase, ending under U401) — an antenna on the ADC reference;
- a 1.5 mm dead +3V0_REF stub with its via at D1001. | Warnings 176 -> 153; all nets keep their pads (+3V0_REF: 1 island, 9 pads). |
| BUCK_SYNC to the LSE crystal (m12) | The +5V_A In3 corner moved 0.7 mm east: y 94.27 to x 143.67, then 45 degrees to (144.67, 95.27). The BUCK_SYNC In3 bend then moved to x 143.45 -> (144.50, 96.33): 3.04 mm from the PC14 via-in-pad at U401.8 (rule 3.0), 0.67 mm from +5V_A (3W rule 0.3). | Sign-off `v7_emc05_buck_sync_lse_3mm` passes (was 2.80 mm). |

Not fixed, with reasons:
- **C1002/C510 courtyard overlap** (U1001 REGCAP and U503 NR caps, both "high" sensitivity at their pins): no copper-legal pose within 0.5 mm for either part.
- **skew_sdmmc** (2): resolves only when SD_D1 is routed. Its series resistor R35 sits outside U401's west pin row; R34 (SD_D0) sits under the pins, east of the row. So SD_D1 would have to cross the whole U401 SW-corner fan-out to reach J601.8. Moving R35 under U401.66 next to R34 and following SD_D0's In3 path (x 129.16) was the proposed fix, but it is **not possible** (checked 2026-10-03 with `query.py free --copper`): no copper-legal R35 spot exists next to R34. The only legal B spots are its current one and spots 4–5 mm away. Re-fan the SD escapes around R35 instead (routing guide, WP3).

### Band re-layout study (2026-10-03, user-approved: lift detoured nets, move U1502 to J1201, re-pack the SD ESD field)
Measured on a scratch copy with 11 detoured transit nets lifted: SWO, SWCLK, EXP_TMR*, EXP_INT0_N_MCU, EXP_FAULT_N, EXP_VHP_EN, EXP_I2C_SDA, CHG_STAT, CHG_LED_A. That is 570 mm and 50 vias. Tool: `lanes`-style vertical free-run scan, 0.15 mm track / 0.2 mm spacing.
- **West corridor exists**:
  - In3 x 119-126.5, from y 103.5 down to y 116-121;
  - B partly free x 118-127.
  - F under J601 is NOT a through-route: J601's footprint keep-outs (F only) cover a strip y 106.8-107.5 at x 121-128.6 and x 128.3-129.9 at y 107.5-116.2.
  - This corridor suits USB D+, the expansion lines from U401's west pins and the lifted debug/timer lines.
- **Centre of the band (x 128-152, y 104-123) has no vertical lane longer than about 6-9 mm** on any layer, even after the lift. The blockers are fixed parts:
  - J601's contacts with the ESD/series-resistor field D4-D10 / R31-R38 and their vias (x 133-137, y 104-118);
  - the charger power stage (L1101, U1101, PMID/VBUS trunks, K5_L301_BODY);
  - U1502 with its thermal-via field K13 (x 138.6-141, y 117.4-122.2).
- **U1502 cannot move**:
  - no courtyard-legal pose on F anywhere in the lower half;
  - F under J801 is K4_TFT_LOOP (display flex fold, no parts), and B around J1201 is the expansion-shield bay;
  - its only B spot is (164, 128), 24 mm away;
  - it cannot shift east either, because C1507's courtyard touches it.
- **SD ESD re-pack** could open one lane at x 135.5-137.2 (y 105.5-117.5) by moving the ESD GND vias and SD signal vias into or west of J601's contact pads (same-net via-in-pad is allowed). But north of it the U401.90-92 fan-out vias (EXP_DETECT_N / EXP_RST_N / PSRAM_CS_N) and south of it U1502's west pins (x >= 136.35) still block a 4-line display-control lane to J801.10-13.
- **USB D+ escape at U401.71** is ringed by the SWDIO (128.17, 100.42), SD_D0 (129.06, 99.48), SD_D2 (128.38, 102.85), UI_FAULT_N, UI_EN and GND escape vias at about 0.45 mm spacing. It needs a re-fan-out of U401 pins 69-75 and the SD_D0/D2 escapes together.
- **Conclusion:** the display bus (12 lines), the buttons and USB D+ need either a board-level re-placement (J601 + its ESD field, or the charger block, away from U401's south-west fan-out) or an interactive push-and-shove session that re-fans U401's south-west corner. Single-net hand routes cannot open them.
- **J601 re-placement checked, not possible (2026-10-03).** A whole-board search for a courtyard-legal J601 pose returned none:
  - J601 is the microSD socket, with a 17.7 × 15.7 mm courtyard; the search covered F, all 4 rotations, on a 1 mm grid.
  - The port notch fits only J601 + J1101; moving J601 down overlaps J801's courtyard, and below the notch is H3's boss keep-out.
  - The team then chose the interactive hand-off: see `ROUTING_FINISH_GUIDE.md`.
  - Note on the second bullet above: the later m6–m16 edits (R304/R1510 moved, dead copper removed) opened a direct In3 corridor for USB D+ (U401.71 escape → U1101.6). The J1101 → U401.71 main path also exists now (feasibility check, 2026-10-03).

### Display bus (decided)
The display uses the 8-bit 8080 bus: D0-D7 plus CS/DC/WR, through the most congested band (U401 -> J801). **Rejected (lead decision D13, critique P1-31): the 8080 bus stays.** For the record, 4-wire SPI on this panel would use J801.9 SDA (GND today), J801.11 SCL, J801.12 D/CX and J801.10 CSX with IM = 0/1/1. It would also need an MCU re-pin (SPI1 on PB3/PD7, which loses SWO), a rev-2 or later panel, and about 81 ms per full frame at 15 MHz. The earlier note in this guide (SCL on WR, SDA on D0) named the wrong pins. Checkpoint 2a made the bus write-only (RDX tied to +3V3_UI, so LCD_RD_N is gone) and put the IM straps in copper (R200-R202@pre-ECO003 deleted).

### Blockers found while hand-routing (what each remaining power/control link needs)
- **VBAT_RTC** (C401/U401.6 to C1410/U1402.5, 7 mm): the straight path crosses the HSE cell. K10F bans it on F, K10B on B. On In3, VSYS (144.1-145.4, 100.2-101.5), TP_SDA (x 149.53) and EXP_VHP_EN (y 99.72) close it. North of the cell, B.Cu holds the +5V_A / LCD_RST / CHG_INT_N vias at y 94.5-95.3. Fix: re-route the TP_SDA F hop and the EXP_VHP_EN segment around U1402, then run VBAT_RTC on In3 at y about 100.3.
- **CHG_INT_N** (U1101.21): the B.Cu lane K16 (x 143.05-144.9) is empty and reserved for it. Entering at the top needs a B-only start at C405.1, because any via there is within 1 mm of +3V0_REF (C417/C418 on F). The real blocker is the U1101 end. Pin 21 is boxed by C1113.2 (GND) and C1401.1 (CHG_BAT), only 0.44 mm apart. The way north from the via at (144.40, 109.25) crosses VSYS on B (y 104.95-106.08), I2C_SCL on In3 (x - y = 39.24) and I2C_SDA / SDRV on F (y 105.74 / 106.01). Fix: move the I2C_SCL In3 diagonal about 0.6 mm south-west, then In3 from the U1101 via to a via at about (143.35, 104.9) and up the lane.
- **REGN to R19** (charge LED): R19.1 is boxed by R19.2, R1510.2, the I2C_SCL via/track and the VBUS/BTST1 pair. R19's rule allows it anywhere in series with D3 (max 40 mm). The fix is to move R19 next to R1108 / REGN and re-run CHG_LED_A, which today detours 57 mm with 6 vias, beside CHG_STAT (In3 x 155.5) to D3. The band y 117.6-124.5 between them is the J801 fan-out (LCD_LED_K1/K3/A, LCD_RST, VBUS), so this is a planned move, not a nudge. **Verified 2026-10-03** on a scratch copy:
  - R19 goes to (149.00, 113.90), rot 0, B. That pose is copper-legal, and its REGN pad lands on REGN copper, so REGN closes.
  - Remove the old CHG_LED_A copper (38 items, 57 mm).
  - R19.2 → D3.2 then has a legal B > In3 > F path (2 vias) down the east side.
- **USB_DP to U401.71**: the MCU side only reaches a via under U401 (131.12, 99.06). Below it, the U401 south-row fan-out vias (SD_CLK_MCU/SD_D3_MCU/LCD_D2_MCU/LCD_D3_MCU at y 104-105) and the SD bus on In3 close every path. The F column beside USB_DM (x 127.1) is held by EXP_TMR_IN_MCU (x 126.7) and +3V3_UI / VBUS vias (x 127.6-127.75). Fix: re-route EXP_TMR_IN_MCU, then run D+ beside D- as a pair.
- **RN801 (LCD_D0-D3)**: its connector-side pads are boxed on F by EXP_INT0_N_MCU (west at x 123.80, 0.19 mm; north at y 94.32) and by the LCD_D0_MCU / PSRAM_IO1_MCU vias (south). EXP_INT0_N_MCU detours 64 mm (34 mm direct) down the west edge. Fix: re-route EXP_INT0_N_MCU first, then exit RN801.5-8 west to vias and run south on B.Cu through the free west area (x 118-127, y 104-120).

## Why the last 9% is hard (read this first)

- **One inner signal layer.** In1, In2 and In4 are solid GND, and In2 is In3's 0.109 mm reference. So every long route shares In3, and crossing another In3 route needs two vias to F/B.
- **The U401 periphery is saturated.**
  - About 60 small parts sit inside U401's pin-escape bands: series resistors, resistor arrays, decouplers and dividers, many of them on B, directly under the pin rows.
  - Their far pads are boxed in. There is no legal spot to move them to within about 1.6 mm without breaking a neighbour.
  - Resistor arrays at 0.5 mm pitch cannot take via-in-pad.
- **The corridor from U401 to J801/J1201** (y 104-122) runs through the charger (U1101/L1101), the eFuse (U1502) and the SD socket (J601). About 45 long nets must pass there.
- **U401's orientation is already optimal.** At 180 deg, only 5 long nets leave from the side facing away from their destination; the other orientations give 15, 20 and 36.
- **The automatic tools stalled.**
  - The tools used: the in-house A* router with rip-up, KiCadRoutingTools, and placement search.
  - The yield fell to a few connections per hour, so the rest is better done interactively (push-and-shove).

## Remaining connections and recommended approach

### LCD bus to J801 (18)
| Net | From | To | Gap mm |
|---|---|---|---|
| LCD_D0..D3 | J801.22-25 | RN801.8-5 | 30.6-33.8 |
| LCD_D4..D7 | J801.26-29 | RN802.8-5 | 34.3-36.1 |
| LCD_D2_MCU | U401.81 | RN801.3 | 9.4 |
| LCD_DC / CS_N / RD_N / WR_N | J801.11 / J801.10 / J801.13 / J801.12 side | RN803.5 / .6 / .7 / .8 | 18.4-20.1 |
| LCD_TE | J801.40 | R206.2 | 31.6 |
| LCD_RST | J801.30 / R806 | R405.2 | 24.0 |
| LCD_BL | U401.63 | R811.1 | 24.9 |
| LCD_LED_K4 | J801.37 | D804.2 | 20.2 |
| LCD_BL_SW | D801/D802/Q803 | D803/D804 | 14.8 |

**RN801 (top side, west of U401, D0-D3)**
- Its connector-side pads (5-8) can only exit west, where R60/R63 (PSRAM series resistors) and R35 sit. Move R60/R63 about 1-1.5 mm west or north (medium sensitivity, 5 mm budget) and exit RN801.5-8 west to vias.
- Then route on In3 down the west side under J601 (J601's keep-outs are top-layer only) to J801.22-25.
- LCD_D2_MCU comes from the south pin row (U401.81) and is about 9 mm long by construction. Either accept it, or move RN801 to U401's south-west corner and accept `len_source_stubs` warnings.

**RN802 (bottom side, under U401's north pins 37-40, D4-D7)**
- The far pads need a short stub (0.5-1 mm) south under the U401 body to a via each. Inside the U401 courtyard the analog-partition ban does not apply.
- Then run In3 south under U401 to J801.26-29.
- Make room by moving C908 (TP_INT shunt), R1003 (ADC CS series) or R1005 (pull-up, low sensitivity) by about 1 mm.

**RN803 (bottom side, under U401's south half)**
- The CS_N and RD_N far pads already have escape vias; DC and WR_N are blocked by +3V3_D / I2C_SCL copper next to RN803.
- Re-route that +3V3_D or I2C_SCL segment by about 0.5 mm, then run In3 south to J801.10-13.

**Backlight group (right of J801)**
- LCD_TE, LCD_RST, LCD_BL, LCD_LED_K4 and LCD_BL_SW are short-to-medium runs.
- Keep LCD_TE and LCD_RST in the B.Cu display lane `K16_DISP_LANE` (allowed owners) where it helps.

### Expansion to J1201 (16; EXP_SPI_MISO and EXP_FAULT_N routed since)
| Group | Nets | Gap mm |
|---|---|---|
| MCU side to series resistor at J1201 | EXP_CS0_N_MCU (U401.51→R1208), CS1_N (U401.55→R1214), MISO (U401.53→R1206), INT1_N (U401.57→R428), RST_N (U401.91→R1218), DETECT_N (U401.90→R432), IO0 (U401.98→R429), IO1 (U401.97→R430) | 20-47 |
| Connector side from resistors near U401 | EXP_SPI_SCK (R1201→J1201.5/D1201), SPI_MOSI (R1203→J1201.7/D1201), GATE (R1219→J1201.33/D1203), SYNC (R1220→J1201.35/D1203), ANA_MON (R1222→J1201.34/D1204) | 31-42 |
| Monitors | EXP_3V3_SNS (U401.18 group→R1506), EXP_VHP_SNS (U401.17 group→R1505) | 43 |
| Short / local | EXP_I2C_SDA (D1202.4→J1201.27, 0.8), EXP_FAULT_N (U1502.6→R1501/U1501/U401.87, 6.0); EXP_TMR1 routed 2026-10-03 | <=6 |

- **Bus routing.** Route the long ones as a bus on In3 from U401's west and south pins, passing west of the charger (x about 128-136, under J601/U602) and south to the J1201 area. That corridor is lighter than the one under U1101.
- **Short links.** EXP_I2C_SDA and EXP_TMR1 are 0.8 mm links at the ESD arrays D1202/D1205 (bottom side). Each needs one short B.Cu track; move a GND stitching via if it blocks.
- **Optional.** The series resistors R1201/R1203/R1219-R1222 sit under U401's pins (medium sensitivity, 4-10 mm budgets). Moving them 2-3 mm outward frees their far pads.

### Power and charger (10; CHG_BAT / VBAT_PACK closed by moving R1402 under Q1402)
| Net | From | To | Gap mm |
|---|---|---|---|
| VSYS (x2; main trunk closed 2026-10-03) | U1101 SYS group | R405@pre-ECO003 (EXP_VHP source select A) - TP9 (test pad) | 10.1 / 10.9 |
| VBAT_PACK | main group (Q1402/Q1401/U1402...) | R1402.2 | 27.8 |
| CHG_BAT | U1101.22/23 / C1401 / C1402 / Q1402 | R1402.1 | 25.3 |
| REGN | U1101.5 group | R19.1 (charge LED) | 4.7 |
| CHG_INT_N | U1101.21 | C405/R1107/U401.22 | 15.1 |
| QON_N | U1101.12 | SW1101.2 | 31.8 |
| USB_DP (x2), USB_DM | U1101.6/.7 (BC1.2 D+/D-) | J1101/U1102 and U401.71 | 18-20 |
| VBAT_RTC | C401/U401.6 | C1410/U1402.5 | 6.3 |

- **VSYS** (0.5 mm Power_Battery track) needs a channel near R1401/R1103/U1402. Re-route SDRV, I2C_SDA and +3V3_D there by about 0.5 mm, or use the planned B.Cu lane `K19a_VSYS_BAND` (y about 106) to reach F801 and U1301.
- **R1402** joins CHG_BAT and VBAT_PACK and sits about 25 mm from the charger. Moving it next to Q1402/U1101 removes two long power runs. Check its function in the Power_USB sheet first.
- **USB D+/D-** to U1101 are only for BC1.2 detection. Route them as a pair with stubs as short as possible. Width 0.15 mm (`v7_usb_fs_width`).

### Other (9)
| Net | From | To | Gap mm |
|---|---|---|---|
| NRST | U401.14 / C404 / R18 | J901.3 (SWD) / SW3.1 | 43.4 |
| BOOT0 | U401.94 / R401 | SW4.1 | 37.6 |
| MARK_N | U401.3 / C808 / R49 | SW802.1 | 36.4 |
| RECORD_N | U401.2 / C807 / R44 | SW801.1 | 35.6 |
| LID_INT | U401.84 / C906 / R701@pre-ECO003 | U702@pre-ECO003.5 | 35.9 |
| TP_INT | J802.5 / R815 | R408.2 | 28.9 |
| TP_SCL | J802.3 / R813 | U401.46 | 34.0 |
| PSRAM_IO2 | R602.2 (at U401) | R65.1 (at U602) | 18.5 (QSPI data: keep the skew to its IO0/1/3 siblings <= +-10 mm) |
| SD_D1 | R35.2 | J601.8 / D9 / R37 | 14.0 (then check `skew_sdmmc`) |

- The button, SWD and lid lines are slow signals and Harness_IO class. They can share In3 with the J1201 bus.

### GND (0 islands; joined 2026-10-02 night)
U401.49, U401.19, D1206.8, D1202.3/.8, D1201.3, D1201.8. Add one GND via each, in the pad where it fits, otherwise a 0.3 mm stub to a 0.45/0.20 via. `tools/gndvip.py` in the repo `tools/layout` does this automatically.

## DRC errors (outputs/RFVD_DRC_report.rpt) and how to fix them

| # | Rule / type | Reports | Where | Fix |
|---|---|---|---|---|
| 1 | `fab_pth_hole_clearance` | 12 (1 issue) | SWDIO via (120.50, 132.62), 0.293 mm from the J1101 shield PTH (rule 0.30) | Move the via 0.05 mm away from J1101. |
| 2 | `v9_w_power_neckdown_chg_caps` | 7 | REGN tracks 0.15 mm inside C3xx courtyards (around 143.9-148.5, 108-118) | Widen to 0.20 where it fits, or make `v9_regn_light` (0.15 min) win inside C3xx (append after the neck rule). |
| 3 | `starved_thermal` | 6 | J1101 shell pins (4) and J1201 shield pin: 1 spoke instead of 2 | Add a short GND track from each pad into the fill, or make those pads solid-connect. |
| 4 | `fab_via_window` | 8 (4 vias) | BTST1/BTST2/SW801/SW802 vias at U1101 are 0.45/0.20; the rule wants >= 0.50/0.30 | Resizing breaks `v3_sp_chg_sw_in_u301` (tested: +13 errors). Either add a scoped via exception for U1101 (like `v3_allow_chg_boot_vias`) or re-place the 4 vias with more room. |
| 5 | `v7_usb_fs_width` | 4 | USB_DP/DM segments at 0.14 mm next to U401 (127-129, 99-108) and U1101 (145.6, 113.6) | Nudge the neighbours and widen to 0.15, or allow a 0.14 neck at the IC pins. |
| 6 | `sp_clock_3w` | 3 | BUCK_SYNC vs VSYS around (156-159, 93-95): 0.27 mm instead of 0.30 | Move the BUCK_SYNC via or track 0.05 mm. |
| 7 | `sp_analog_to_harness` | 2 | TP_RST_MCU via and track at (143.3, 89.1) vs C511 pad 1 (reference filter): 0.83 mm instead of 1.0 | Move the TP_RST_MCU via about 0.2 mm away from C511. |
| 8 | clearance | 2 | R1510 pad vs EXP_VHP_IN (0.198 / 0.2); +3V3_D vs R49.2 (0.145 / 0.15) | 0.01 mm nudges. |
| 9 | `mech_h1_h4_boss_courtyard_B` | 2 | R1504 courtyard 1.845 mm from H3 (rule 1.9) | Move R1504 0.06 mm away from H3. |
| 10 | courtyards_overlap | 2 | TP1101/R1212; C1002/C510 | Nudge TP1101 and C510 (both low sensitivity). |
| 11 | `skew_sdmmc` | 2 | SD bus skew 15.3 mm (SD_D1 is still unrouted) | Route SD_D1, then length-match CLK/CMD/D0-D3 (max skew 10 mm). |
| S | `v7_emc05_buck_sync_lse_3mm` (sign-off) | 2 | BUCK_SYNC In3 segment near (143-150, 95-96) passes within 2.8 mm of the PC14/PC15 vias | Shift that segment about 0.3 mm away from Y402. |

**Warnings worth a look.**
- `len_source_stubs` (12): some MCU-to-series-resistor stubs are longer than 3 mm (RN801 serves two pin rows).
- `track_angle` (10 right-angle or acute, 20 on smooth-critical nets).
- `track_segment_length` (53 short segments on critical nets).
- Clean-up items: `via_dangling` (51) and `track_dangling` (24) are escape vias and stubs waiting for their missing connection. They are used when you route the rest; delete whatever remains unused at the end.
- One each: `v3_afe_partition_aggressors`, `len_psram_clk_inward`, `skew_venv_eref`.
- Silkscreen: 20 left after the designators were hidden (outline / label overlaps).

## Decisions and deviations made in this layout pass

1. **In3 under the analog partition.** Digital nets may run on In3 under `AFE_PARTITION`, between the In2 and In4 GND planes, but no vias are placed inside it. This matches the project DRU: `v3_afe_partition_aggressors` covers F/B and does not flag In3; verified with KiCad DRC.
2. **Soft module locality.** Tracks may cross another module's surface (F/B) or put a via inside it at a cost. Some inter-module routes do this; the strict version left about 40 routes impossible.
3. **NRST corner re-placed.** R18 moved to (136.1, 95.7) rot 90 and R409 to (138.4, 94.5). C404/C57 kept. NRST now leaves U401.14 under the body to C404.
4. **USB widened in place** to 0.15 mm on 30 segments. 4 segments remain at 0.14 (DRC item 5).
5. **Design rules.** `.kicad_pro` `min_hole_clearance` is 0.2 here (project: 0.25). DRU patches 1-5 are applied; see `CHANGES_FROM_PROJECT.md`.
6. **KiCadRoutingTools.** Its output was used only where every new item passed the full rule check (widths, vias, angles, rule areas, clearances): 17 net changes. Its first, unfiltered result (282 DRC errors) was rejected.
7. **Clean-up.** Removed one GND via inside J601's keep-out and one GND stub in a keep-out (DRC-driven).

## Track clean-up / "signal highways" attempt (2026-10-02 night)

**Goal.** One dominant direction per layer: In3 vertical; B horizontal; F vertical in the analog half and horizontal in the digital half. Also no zig-zags, and vias moved out of the way.

**Tools.**
- `mr.py`: direction costs (`MR_DIRPREF`, `MR_DIR_PERP`, `MR_DIR_DIAG`) and a bundling reward for running beside parallel tracks (`MR_BUNDLE`).
- `geomstat.py`: geometry measurement.
- `place/highway2.py`: chain straightening and via relocation, topology-safe.
- `place/slate.py`: lifts a whole layer and re-lays it.
- `place/revert_nets.py`: lossless fallback.

**Baseline.** The share of length on the preferred axis is 24-33% per layer, about 40% of the length is 45-degree diagonals, and there are 135 zig-zag chains.

**Result: not adopted.**
- Straightening chains and relocating vias in place: 18 chains and 9 vias improved, 135 to 130 zig-zag chains, but 8 more angle warnings.
- Lifting all 115 In3 chains and re-laying them: lossless after negotiation and a 3-net revert, but almost the same picture.
- Why: every chain ends at a fixed via or pin escape, and those positions follow from the dense placement around U401, J801 and J1201. Real highways need the end points to move, which means re-doing the U401/J801/J1201 escapes and moving the series resistors. That is the same work as finishing the last 57 connections.
- **Recommendation:** define the lanes while routing the remaining connections. Use In3 north-south lanes from U401's south and west sides to J801/J1201, and B east-west lanes for the button and SWD lines along the bottom edge. Clean up neighbouring routes interactively as you go.

## Remaining DRC errors after the 2026-10-03 clean-up (14 with the project DRU, 21 with the sign-off rules)

| Errors | Problem | Fix |
|---|---|---|
| 2 (+8 sign-off) | **BUCK_SYNC spacing.** 3W to VSYS near the LMR43620 input caps (156-159, 93-95), plus 3 mm to the LSE net PC14 (#SIGNOFF `v7_emc05`, at 144-150, 96.3). | Re-route BUCK_SYNC by hand, keeping 3W to VSYS, 3 mm to PC14/PC15, <= 40 mm and 5 mm from RF/edge. It is EMC-critical, so it was left for a deliberate manual route. |
| 4 | **USB widths.** USB_DP/DM segments at 0.12-0.14 mm; the rule asks 0.15. | Boxed in, so widening in place fails. Re-route those 4 segments, or accept them: at 12 Mb/s full speed the impedance shift is harmless. |
| 2 | **Courtyard overlaps** TP1101/R1212 and C1002/C510. | Nudge R1212 0.05 mm right and C1002 0.3 mm left. The automatic nudge collided with copper, so do it in the GUI with push-and-shove. |
| 2 | **R1504 vs the H3 boss** (`mech_h1_h4_boss_courtyard_B`, 1.9 mm from the hole wall). | Move R1504 about 0.2 mm up, away from H3. |
| 1-2 | **R1510 pad vs the EXP_VHP_IN track** (micro-clearance). | Re-route the short EXP_VHP_IN stub. |
| 2 | **skew_sdmmc.** | Resolves when SD_D1 (still open) is routed with matched length. |

Fixed in this pass:
- 6 starved thermals (solid shield pads);
- 13 SWDIO hole-clearance errors (via re-routed);
- TP_RST next to analog C511 and +3V3_D at R49;
- 8 + 7 rule conflicts on the charger bootstrap vias and REGN (DRU patch v10, see `CHANGES_FROM_PROJECT.md`).

## Board widening and placement audit (2026-10-02 night)

See `PLACEMENT_AUDIT.md`. In short:
- **Widening.** +2.5 mm on each side; the port notch keeps J601/J1101 flush. Every part keeps its absolute position.
- **Edge gaps.** Parts within 2 mm of the real edge: 47 -> 27, all edge-bound by design or in the port section.
- **Moves.** R1402 went under Q1402, closing 2 power connections. TP1301 sits on +3V3_D. Q1403 went to the bottom side next to U1401: a 55 mm drain detour along the bottom edge became a 4 mm route plus a 20 mm VBUS gate route, which frees the bottom-edge corridor for the button lines.
- **Fenced in.** D803/D804, R1505/R1506, R18, C302@pre-ECO003, R304, TP9, R806 and R1007 were flagged but have no legal or routable spot; the reasons are in the audit document.
- **Gate.** Every change passed metrics (no net worse) and sign-off DRC (no new errors).

## How every step was verified

Each change was accepted only if all three checks passed:
- KiCad's unconnected count did not rise and no net lost connectivity (`tools/place/metrics.py`).
- New copper passed the exact pairwise rule model (`tools/mr.py`: DRU class clearances, HS/clock/analog/RF spacing, rule-area bans, neck-downs).
- The KiCad DRC with the project rules did not get worse (`tools/drcsum.py`).
