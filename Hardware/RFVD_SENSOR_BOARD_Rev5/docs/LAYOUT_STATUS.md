# Layout status and what is left (handoff 2026-10-02; updated at checkpoint 3, 2026-10-04)

## Checkpoint 5 (2026-10-04): DRC clean, every open link routable. Board sha256 `f9fb559366`

| Measure | m17 (session start) | Checkpoint 5 |
|---|---|---|
| Plain DRC errors (all-track-errors) | 3 | **0** |
| Warnings | 116 | **110**, each explained in the warning ledger below (42 are the deliberate hand-off vias) |
| Open links | 50 (28 blocked) | **42 (0 blocked: 12 direct, 30 with a mapped path)** |
| R17 return-via failures | 45 | 7 (all at the dense U8 west row; documented) |
| Neck chains | 46 | 0 |
| Ratsnest | 4018 mm | 3522 mm |
| Footprints locked | partial | all 341 |
| BOM | 105 lines / 318 parts | 100 / 309 |

Landed since checkpoint 4a, all gated:
- **4b1:** SEAM + BATT (F1 Style 2 at (163.05, 126.80) r90 B; PACK_RAW B-only 1.0 mm, no via).
- **4b2:** BOM consolidation (SW3, R18, R44, R49, R206, R207, R214, U702 and C702 removed).
- **4b3:** J10 −0.96 mm.
- **4b4:** U403 cluster to F beside U701 (DRU side-guard patch d9).
- **5a:** last DRC fixes.
- **5b/5c:** escape vias for the blocked links; R305 moved to (146.85, 112.20).
- **5 lock:** all footprints locked.

Accepted and documented:
- the AFE ring south wall is open over 5.6 mm;
- PROG passes 0.21 mm from the BTST2 via (read only at power-up);
- 7 R17 vias at the U8 west row have no legal GND site;
- the F1 Style 2 footprint has no 3D model yet.

### Placement sign-off (2026-10-04, on `f9fb559366`, board unchanged)

- **`tools/placeaudit.py`: 0 MOVE, 0 OVER**, 7 fixed (mechanical); ratsnest 3522 mm.
- **`tools/dsgap.py`** (new): measures every datasheet budget in `docs/sensitivity.json` on the board itself. It uses the nearest pin of the IC on a shared net, so it follows pin swaps and multi-pin supplies.
  - The stored `gap_mm` values came from the old parts.json poses and had flagged the wrong parts (R3, C4, D301, C405, R103).
  - Result: 269 budgets measured, 264 within budget, 5 over, all justified with measured reasons. The 73 rules of removed parts are not measured.
  - Per-IC table: `docs/PLACEMENT_DATASHEET_CHECK.md`.
  - placeaudit now takes OVER from this live check.
- **The 13 former MOVE candidates were kept for function**, each reason checked on the board (`tools/placeaudit_keep.json`):
  - divider tops at the rail end (R412, R414);
  - source termination at U8 (R213);
  - pull-ups at the MCU bus end, ≥ 5 mm from U11 (R53, R54);
  - load-end isolation (R907);
  - mechanical pogo pad (TP306);
  - button ESD series R at the MCU (R47);
  - heat-spread backlight CCR (D203);
  - in-box RH/T sensor (U701);
  - slow gate resistor (R210);
  - C301, inside its 5 mm budget, whose suggested spot is not copper-legal;
  - R417 (below).
- **The 5 parts over their budget:**
  - C318 / C309 (BQ25798 SYS / PMID 0.1 uF, 2.29 / 1.69 mm against 1.5 mm EMC practice): at the two ends of U301's west pin column, GND via in pad, as in TI Fig. 8-21. SW1 / SW2 exit between them.
  - C902 (REF5030 VIN, 0.1 mm over).
  - U304 (USB ESD, 3.69 mm): at the edge of J10's no-foreign-copper shell region.
  - R417 (below).
- **Two minor deviations, low severity, with optional hand fixes in `docs/LEAD_GUI_STEPS.md` (A, B):**
  - R417, the EXP_I2C_SCL pull-up, stayed at its pre-cp4 spot when U403 moved, so its SCL tap is a 12 mm In3 stub. That is harmless at ≤ 400 kHz, but it uses an In3 corridor. The spot at U403 is copper-blocked.
  - On SYS, the 10 uF C313 (1.88 mm) is closer to pin 25 than the 0.1 uF C318 (2.29 mm); TI Table 5-1 asks for the 0.1 uF closest.
- **Detours (routed copper > 1.6 x ratsnest):** EXP_TMR1 2.41, EXP_INT0_N_MCU 1.94, TP_RST 1.85, EXP_I2C_SDA 1.70 and SWCLK 1.64. All five are Harness_IO class: slow or static lines (a timer line, an interrupt, a reset, I2C, and the debug clock used only while programming). They are routed and DRC-clean; the extra length costs copper only.

### DRC warning ledger at checkpoint 5 (fresh run 2026-10-04 on `f9fb559366`)

Command: `kicad-cli pcb drc --all-track-errors --severity-all --refill-zones`. Result: **0 errors, 110 warnings, 42 unconnected, 0 track_angle**. Every warning is listed below by rule; item coordinates are in `outputs/RFVD_DRC_report.json`.

| Count | Type (rule) | Items | Why it is acceptable / what removes it |
|---|---|---|---|
| 42 | via_dangling | One escape via per open link | Deliberate hand-off vias (`ROUTING_FINISH_GUIDE.md` §0 starts each link from them). They disappear as the 42 links are routed; delete any left unused. |
| 45 | track_width (`v11_in3_power_digital_width`, min 0.4 / opt 0.6 mm, severity warning by design) | In3 power segments of 0.20-0.30 mm: +3V3_D 23 (41.5 mm in total, longest 7.9 mm, narrowest 0.20 mm), +3V3_UI 13 (27.6 mm, 0.30 mm), +5V_A 7 (7.0 mm, 0.25 mm), +3V3_EXP 2 (1.1 mm, 0.20 mm) | Necks where the dense MCU / display / AFE fields leave no room for 0.4 mm. Worst-case DC drop counts every narrow segment in series, In3 at 15.2 µm copper and ρ 1.72e-8 Ω·m: +3V3_D 160 mΩ (16 mV per 100 mA); +3V3_UI 104 mΩ (4 mV at its ≤ 38 mA logic load, 32 mV at U10's 303 mA limit); +5V_A 32 mΩ (4.8 mV at the LT3045's 150 mA limit, ILIM 1k); +3V3_EXP 4 mΩ (2.6 mV at U401's 638 mA limit). Each is under 1.5 % of its rail. The error-level neck rules pass (0 neck chains). |
| 6 | track_segment_length (`v7_geom_smooth_critical`, min 0.1 mm) | EXP_MISO_MCU F (126.18, 91.22) 0.099999 mm (rounding); Net-(U8-PC15) B (140.80, 98.84) 0.05 mm; LCD_D4 In3 (144.30, 124.32) 0.05 mm; ADC_VENV F (139.67, 81.00) 0.097 mm and (138.36, 86.82) 0.079 mm; ADC_REFCAP F (134.80, 82.50) 0.035 mm | Sub-0.1 mm jogs where a track meets an off-grid pad centre: geometric only, electrically nil (≤ 0.1 mm of copper). KiCad's *Cleanup Tracks & Vias* (merge collinear segments) removes them: `LEAD_GUI_STEPS.md` C. |
| 5 | track_dangling | In3: LCD_D6 (135.70, 87.35) 0.85 mm, TP_SCL (130.60, 89.39) 0.40 mm, EXP_CS0_N_MCU (121.12, 87.68) 1.86 mm, EXP_SPI_SCK (128.09, 90.67) 0.55 mm, LCD_RST (141.62, 88.00) | The first four are hand-off stubs of open links (their nets are in the 42). On LCD_RST, a routed net, the In3 diagonal (141.62, 88.00) → (143.12, 89.50) runs about 0.28 mm past the T-junction where the J4 branch joins it at (142.89, 89.34). That is dead copper on a static reset line, far below any resonance that matters. *Cleanup Tracks & Vias* trims it (`LEAD_GUI_STEPS.md` C). |
| 3 | length_out_of_range (`len_source_stubs`, max 3 mm) | PSRAM_IO0_MCU U8.58 → RN60.1 4.67 mm, PSRAM_IO1_MCU U8.59 → RN60.3 3.71 mm, PSRAM_IO3_MCU U8.60 → RN60.2 5.02 mm | RN60 sits on B under U8's pin row (P1-21 single termination, cp2b; SI re-run passed). A 5 mm source stub is far below the critical length of a 1 ns edge (about 25 mm), so the series termination still works. |
| 1 | skew_out_of_range (`skew_venv_eref`, max 2.0 mm) | ADC_VENV vs ADC_EREF: −2.21 mm on a 14.57 mm target | 0.21 mm beyond a 2 mm warning band on a quasi-DC differential detector pair (envelope / reference). The mismatch is about 15 ps, irrelevant at the envelope bandwidth. |
| 4 | silk_over_copper | Library silk outlines of U2, U302, U13 and U301 clipped by the neighbouring pads of D1.2, R316.2, C106.1 and C309.1 | Cosmetic: JLC clips silkscreen at mask openings. |
| 1 | silk_overlap | U301's silk polygon touches C309's silk at (143.21, 114.40) | Cosmetic: C309 sits courtyard to courtyard with U301 on purpose (closest PMID cap, `PLACEMENT_DATASHEET_CHECK.md`). |
| 2 | silk_edge_clearance | J10's silk outline segments at (119.19, 122.76) and (119.19, 132.16) against the west edge (118.00) | Cosmetic: the receptacle is flush with the edge by design (port notch), so its library outline crosses the edge and JLC trims it. |
| 1 | lib_footprint_mismatch | J10 | The board copy carries the pin-in-paste shell pads (P1-12); `LEAD_GUI_STEPS.md` row 4 mirrors it into the library. |

ERC on the same master: **0 errors, 0 active warnings**, 1 excluded `pin_to_pin` (U8 VCAP1 / VCAP2 tied with C49 / C52 per ST AN4938; the reason is stored with the exclusion in the `.kicad_pro`). Parity: `tools/place/sync.py --dry-run` against a fresh netlist prints "no changes".

### Sourcing check (live, 2026-10-04)

`outputs/RFVD_JLCPCB_BOM.csv` has 100 lines and 309 placed parts, and every line has an MPN and an LCSC number. Each LCSC number was queried against the public JLC mirror (JLC assembly stock), and LCSC's product detail was queried where the mirror lacks a part. Need = 2 boards.

| Result | Lines |
|---|---|
| JLC assembly stock ≥ need + 5 spare | 93 |
| JLC assembly stock ≥ need, under 5 spare | C24 25MU105MA23216 (3 for 2), U1 TLV809EA46DBZR (3 for 2; LCSC holds 12 more) |
| JLC short or unlisted, but LCSC's warehouse holds them (JLC parts pre-order) | J8 84953-6 (JLC 1, LCSC 5,567, Mouser 3,142), U3/U4 OPA2320AIDGKR (JLC 1, need 4; LCSC 1,485), U13 AD7380BCPZ-RL7 (LCSC 78), RN60/RN201-RN203 4D02WGJ0470TCE (LCSC 14,550) |
| **Only via Global Sourcing** | **L1 XGL4020-472MEC: JLC 1 (enough for one board), LCSC 0, not listed at Mouser.** The lead decision of 2026-10-04 already sends L1 through JLC Global Sourcing. Order it early, or buy it from Coilcraft. |

Every JLC listing's MPN matches the BOM MPN. Evidence: `04_parts/snapshots/jlc_stock_cp5_2026-10-04.json`, `04_parts/snapshots/mouser_cp5_short_2026-10-04.json`.

### Done-criteria evidence (re-measured 2026-10-04 on `f9fb559366`)

| # | Criterion | Measured |
|---|---|---|
| 1 | Medium-or-higher findings fixed or documented | `CRITIQUE_STATUS.md`: 40 P0/P1 rows, 0 Planned. The board facts behind the Done rows were re-measured: R17 7 of 88 fast-net vias (documented); 0 neck chains; mask expansion 0; JP401/JP402, U702 and SW3 absent; RN60 on B; U403 on F; F1 Style 2 at (163.05, 126.80); R409 64.9k on both board and schematic |
| 2 | ERC, parity, datasheets, simplifications, BOM | ERC 0 errors, 0 active warnings, 1 documented exclusion; parity "no changes"; `DATASHEET_CHECKS.md` covers every IC; BOM 100 / 309 with MPN and LCSC; sourcing as in the table above (L1 needs the Global Sourcing route) |
| 3 | Placement | placeaudit 0 MOVE / 0 OVER; dsgap 269 budgets, 0 unjustified; ratsnest 3522 mm (m17 4018); 341 / 341 footprints locked |
| 4 | DRC | 0 errors, 110 warnings (< 116), each in the ledger above; track_angle 0; sign-off PASS |
| 5 | Open links | 524 / 566 routed. `ROUTING_FINISH_GUIDE.md` §0 has 42 rows with both end coordinates (12 DIRECT, 30 ROUTE, 0 BLOCKED). It matches the live open-link list net for net, with all 42 end points verbatim. feasible.py ran at 18:58:35 on this board (last write 18:56:55) |
| 6 | Outputs and docs | `outputs/` regenerated 18:58-19:16 after the board's last write; the shipped DRC report equals a fresh run type for type. EXP_SYNC note: `FIRMWARE_NOTES.md` §1 (2.400 MHz, not 2.000). Release zip `RFVD_SENSOR_BOARD_release_2026-10-04_cp5-signoff.zip` |

## Checkpoint 4a (2026-10-04): regional hand-layout pass. Board sha256 `08570ddf0b`

Five region packages were each replayed alone on the checkpoint-3 master, then composed with the sourcing package. All gates pass: ERC 0, netlist unchanged except the sourcing fields, parity 0, no net worse. Backup: `backups/before_cp4a/`.

| Measure | Checkpoint 3 | Checkpoint 4a |
|---|---|---|
| DRC errors (all-track-errors) | 278 | **109** (west/J10 68, MCU-core seam 26, battery 12, other 3) |
| Warnings | 134 | 116 |
| Open links | 44 | 43 |
| R17 return-via failures | 45 | 13 |
| Neck chains (`necks.py`) | 46 | 12 |

| Region | Main changes |
|---|---|
| A RF/AFE | 1.0 mm F.Cu GND ring under a mask-open strip, 19 fence vias, FL1 on the east wall, TP1/TP2 moved off the ring. VSYS_LDO at 0.5 mm. +5V_RF moved off B (K3). 12 edge vias. **South wall left open over 5.6 mm (x 137.7–143.3)**, where EREF/VENV leave between U2 and R3/R4/C11. Closing it means moving the datasheet-placed filter parts; at 64–128 MHz a 5.6 mm slot still attenuates about 46 dB, so it stays open (documented). |
| B1 MCU west | 68 of 73 errors fixed. RN202/R39 cluster re-escaped (via-in-pad), the U9-SCLK 3W violation fixed, VCAP and +3V3_D re-laid at 0.3 mm, 12 R17 GND vias, 7 edge vias. |
| B2 MCU east | The PC14 via moved out of Y2's pad gap (sign-off LSE rule PASS), +5V_A and +3V3_D widened, C412 GND via, 4 R17 vias, 7 edge vias. |
| C power band | VSYS necks to 0.5 mm. The VSYS island at U402 routed (never through R408.1). CHG_BAT/VBAT_PACK/PMID In3 at 0.8 mm. VBUS re-built (0.8 mm In3, 0.5 mm B). BQ25798 hot-loop "in all cases" subset: pin-27 stub 0.4 mm with 3 GND vias, VBUS via out of the loop, C312 second via. 5 edge vias. |
| E south | EXP_SYNC/EXP_GATE on the pad axes at J11 (EXP-04). EXP_VHP rebuilt on F at 0.5 mm. +3V3_EXP/+3V3_D/+3V3_UI necks widened. 5 R17 vias, the I2C_SDA T-junction removed, 5 edge vias. |

## Checkpoint 3 (2026-10-04): rules v11 and the stale sheet notes. Board sha256 `527e801c62`

**What landed.**
- **Rules v11** (`tools/dru_versions/d8.kicad_dru`):
  - side-aware courtyard exemptions (P0-5): 21 rules split into F/B/inner copies, plus side-guard assertions;
  - neck-length caps `v11_neck_len_*` (P0-5);
  - In3 power widths (P1-6), hole_to_hole as an error;
  - missing rule areas K6, K8, K21, the K11 shift, K19a/b, K19c removed (P1-16);
  - J10 keep-out, pre-defined track/via sizes, skew_sdmmc 17 mm (D20), mask expansion 0 (P1-12);
  - EXP_SYNC and LCD CS/DC net classes (P1-15);
  - LCD source stubs 16 mm (WR stays 3 mm), SD lines out of the source-stub rule (the series R is in U901), skew_qspi pointed at the PSRAM RAM side, len_psram_ram_stubs removed (S-17).
- **Sheet notes and fields** (Konnect):
  - U6 sync at 833 kHz;
  - R16/R17 = 23.2k/10k and L1 Isat 3.0 A;
  - "charger is on the BQ25798 sheet";
  - U10 limit 234–303 mA;
  - the EXP eFuse values (R410 1.50k / 64.9k / 47 nF);
  - ADC range note;
  - the RF interface row;
  - the +5V_RF caps;
  - FL1 (no can on Rev A);
  - C41/R16 cite SNVSBY5B;
  - R101 path order;
  - datasheet links for D201–D204 and F201.

**Measured on the master** (`--all-track-errors`):
- ERC 0, parity 0, unconnected 44, sign-off rules PASS.
- DRC **278 errors, 134 warnings**. That is intended: the stricter rules expose copper the old rules hid.

| Errors | Type | What it is | Fixed in |
|---|---|---|---|
| 115 | track_width | Power tracks narrower than their class on the wrong side or layer of an exemption (side-aware split) | Checkpoint 4 R1 |
| 61 | track_segment_length | Neck segments > 1.0 mm (`tools/necks.py`: 46 chains, 166.5 mm) | Checkpoint 4 R1 |
| 60 | clearance | High-speed / clock 3W and analog-to-harness spacing (e.g. U9-SCLK vs PSRAM_CS_N In3 0.21 mm; J11.33 EXP_GATE vs EXP_SYNC 0.175 mm, critique EXP-04) | Checkpoint 4 R2–R5 |
| 42 | items_not_allowed | Foreign copper in keep-outs, mainly under J10 (P1-7) | Checkpoint 4 R2 |

**Tool fix found here.** Without `--all-track-errors`, kicad-cli reports one error per track, and which one varies between runs: plain runs gave 33 clearance pairs ± 1 against 60 complete. Every DRC call in `tools/` now passes the flag. The checkpoint-2b numbers (0 errors, 82 warnings) were taken with sign-off (complete) and stand.

## Summary (checkpoint 2b, board sha256 `f539f0317c`)

| Item | Value |
|---|---|
| Board | **52.05 x 90.05 mm**, 6 layers, JLC06161H-3313 stackup (set by the lead in m17) |
| Parts | **350 footprints** (194 top / 156 bottom). Checkpoint 2b removed 39 and added 8 (2a: 381). |
| Routed | **538 of 582 connections (92.4 %)**; **44 open in 43 nets** (2a: 47; m17: 50). GND islands: **0**. All are drawn in `../outputs/RFVD_unrouted.png` |
| DRC errors (KiCad, project DRU, run in this folder) | **0.** The two `skew_sdmmc` errors are gone: the EMIF06 front end shortened the card-side SD lines to a 2.46 mm skew. **82 warnings** (2a: 85; m17: 97 counted the same way); every type is explained below. |
| DRC sign-off (`tools/drcsum.py`) | **0 errors**; all #SIGNOFF EMC rules pass |
| ERC | **0 errors, 0 warnings**; 1 documented exclusion (U8 VCAP1/VCAP2 tied, ST AN4938) |
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
| 1 | lib_footprint_mismatch | J10 pin-in-paste on the board copy only | Lead GUI step 4 |

**Warning counts.** `drcsum.py` runs DRC on a copy under a long scratch path. There KiCad cannot open the project footprint library (path over 260 characters), which adds 19 false `lib_footprint_issues`. The counts above come from `kicad-cli` run in this folder (`outputs/RFVD_DRC_report.*`).

**Work plan.** The merged critique + placement plan is in [`WORKPLAN_2026-10-03.md`](WORKPLAN_2026-10-03.md); the lead's answers are recorded there.

The missing links are all drawn in `../outputs/RFVD_unrouted.png`. Their coordinates are in `../outputs/RFVD_unrouted.csv` (closest points of the two copper islands).

**Finishing the routing: read [`ROUTING_FINISH_GUIDE.md`](ROUTING_FINISH_GUIDE.md) (2026-10-03).** The team chose to finish the last 50 links interactively in KiCad (push-and-shove). The guide gives:
- every open link with both ends, class width, and whether a legal path exists today: 22 yes, 28 blocked (`tools/feasible.py`);
- the verified unlock moves (R19, R60 + EXP_INT0_N_MCU, C908, the RN203 escapes);
- the J4 via sites;
- the rule areas the router does not enforce;
- the order of work.

It supersedes the per-group tables under "Remaining connections" below, which are kept for history.

## Checkpoint 2b (2026-10-04): memory/SD, display bus, expansion, MCU service, silkscreen

**How it was built.** Four builder packages (G4a2 display, G4b memory/SD, G5a expansion, G5b MCU/service) plus the silkscreen/fab-note and J10 pin-in-paste packages. Each was replayed alone on the 2a master, then all were composed. Composed gates: ERC 0, netlist = the union of the expected changes, parity 0, no net worse, DRC errors 2 → 0. Engineering review fixes applied before landing:
- R46 (G5b) collided with R213 (G4a2): pad gap 0.147 mm and a courtyard overlap. R46 was re-placed at B (137.55, 100.30) rot 270 and its track re-drawn flush.
- G4b's GND via at (130.93, 105.49) duplicated G4a2's at (131.05, 105.45), with overlapping drills. It was removed.
- R213 is 100R on the existing line instead of a new 47R line.

**Backup.** Checkpoint 2a's files are in `backups/before_cp2b/`.

| Area | Change | Why (critique ID) |
|---|---|---|
| SD front end | ST EMIF06-MSD02N16 (U901, B under J3) replaces R27–R38, D4–D10 and C911 (20 parts): series R, pull-ups and ESD in one package; RDATA_VCC to +3V3_SD per ST Fig. 2/9. Card-side SD skew 2.46 mm, so both skew_sdmmc errors are cleared. A 0.3 mm +3V3_D feeder on B along the west edge replaces the supply the pull-ups had carried. | S-19 (D7) |
| PSRAM | RN60 (47R ×4) replaces R60–R63/R65–R67; R64 33R goes straight to U9.3; each line has 2 vias instead of 5; SI re-run passes | S-17 / P1-21 |
| Display bus | RN203 serves the U8 south-row pins (WR, D3, CS, D2); RN201 keeps D0/D1; R213 100R on D/C. Three stubs shortened (13.8 → 5.9 mm, 11.1 → 6.4 mm) | P1-20 |
| MCU / service | SW4 BOOT and R801 removed (BOOT0 by R20; recovery via SWD under reset). The test pad was not added because every legal spot puts a stub antenna on BOOT0. SWO deleted (61 copper items). LID_INT removed (OPT3004 polled). RECORD/MARK get 1k series resistors R46/R47. | S-16, S-18, S-24, SC-11 |
| Expansion | TCA9517 EN tied to VCCB (R416/C411 out); RN401 330R array for INT1/IO0/IO1/DETECT; 10k pull-ups R441/R442 (JLC Basic) on EXP_INT0/1_N; all 14 TPD4E05U06 NC pins tied, 10 lines flow straight through on B; JP401/JP402 removed | S-20, S-22 (part), P1-26, P1-27, S-13 |
| Silkscreen / fab | B silk `${ISSUE_DATE}` (title-block date 2026-10-04) and a 6 × 4 mm S/N box beside the board ID. Fab note on User.Drawings (stackup, POFV, finish, minimums, RF_50R). The layer PDF now has a User.Drawings page. | P1-9, P1-13 |
| J10 | F.Paste with +0.15 mm margin on the 4 shell slots (pin-in-paste); the library footprint is mirrored by lead GUI step 4 | P1-12 |

**Decisions in 2b.**
- S-15 (CAT4104) is not possible: there is no legal SOIC-8 site near J4. Under D12's fallback the CCRs D201–D204 stay, D203 becomes a K8 shield-spec exception (`BOARD_OVERVIEW.md`), and a VSYS-based duty cap was added to the firmware contract §7.
- S-22 is partial. The CS/RST and 100k arrays would need vias at the ESD entry.
- S-21 stays optional.

**Firmware consequences:** `FIRMWARE_NOTES.md` §2–§4 (unused pins analog, SDMMC1 medium speed, EXP_3V3_EN / EXTI rules).

## Checkpoint 2a (2026-10-04): circuit changes, simplifications and part merges

**What it is.** Groups G1b (parts), G2 (analog/ADC), G3 (power) and G4a (display) from the work plan, plus the fix package G6 (below).

**How it was checked.**
- Every group was built on a scratch copy as a replayable package and gated (`tools/replay.py`): ERC, the netlist against the expected changes, schematic-to-board parity, no net worse (`metrics.py`), and DRC with no new error type.
- An independent engineering review then checked every change against the datasheets, the netlist and the board.
- That review found one blocker. The PACK_RAW rename had quietly moved the unfused battery net from Power_Battery to Default, so DRC passed only because the net had lost its width rules. Package G6 restores the class (Konnect `assign_net_to_class`) and adds the scoped rule `v10_pack_raw_kelvin`, which lets the 0.15 mm Kelvin sense track run on B inside the J2 courtyard. With the class restored, DRC is the same.

**Backup.** The checkpoint-1 files are in `backups/before_cp2a/`. The change list below comes from the kicad-cli netlist diff of checkpoint 1 against checkpoint 2a.

| Area | Change | Why (critique ID) |
|---|---|---|
| ADC reference | AD7380 internal 2.5 V reference. Deleted R107, TP20 and 24.5 mm of +3V0_REF B.Cu branch; ADC_REFIO is now only U13.11 + C103 1 µF | S-26 (AD7380 Rev A Table 7 / Fig. 31) |
| EREF filter | U3's Sallen-Key is replaced by one pole: R3 22.6k + C17 10 nF (704 Hz). R5, R7, R9, C9, C10, C16 deleted; U3A is an unloaded follower | S-27 |
| ADC drive | R11/R12 47R 0.1% → 33R 1%, and C21/C22 1.5 nF 2% → 2.2 nF C0G (τ 72.6 ns). R100 33R → 100R (AINB− overload ≤ 5 mA with the 2.5 V reference; 0.72 MHz RF low-pass with C102) | S-3, S-26 |
| VSYS monitor | VSYS divider R21/R22/R23/C57 deleted (the BQ25798 ADC reports VSYS). EXP_ANA_MON moved PA4 → PC0 (R435 1k / C412 1 nF). R601 10k pulls PA4 high for the DFU bootloader | S-5, P1-22 |
| VBUS detect | R304/C302 deleted; R303 100k stays as a VBUS bleeder; PC13 is no longer connected (firmware detects the plug via CHG_INT_N/WKUP1 + REG1B, `FIRMWARE_NOTES.md` §2) | S-6 |
| Buck | FB divider R16/R17 33.2k/14.3k → **23.2k/10k**: 3.320 V, RFBT‖RFBB 6.99 kΩ (LMR43620 SNVSBY5B Eq. 5 window 5–10 kΩ) | P1-23 / D24 |
| Expansion eFuse | R409 73.2k → 64.9k: OVLO 9.89 V, above the PFM VSYS level (TPS259631 SLVSET8A Eq. 2). EXP_VHP_IN merged into VSYS (R405 0R / R406 DNP deleted) | P0-6, S-14, S-9 |
| Supply caps | C27 22 µF VSYS polymer deleted: the LT3045 needs ≥ 4.7 µF at IN, and C31 10 µF sits behind R902 1 Ω (LT3045 Rev B p.18). C68 47 µF on +3V3_UI deleted: no 190 mA inrush on +3V3_D | S-8, S-12 |
| Battery | PACK_RAW now carries the BQ29209 top-cell Kelvin sense: R315 taps J2.1 ahead of F1/Q303. TP308 moved to B_VC1. R19/D3 charge LED, TP9 deleted | P1-5, S-7, S-10 |
| Display | 8080-II straps in copper on J4 (IM0 = 1, IM1/IM2 = 0; R200–R202 deleted). RDX tied to +3V3_UI: the bus is write-only, which frees LCD_RD_N, PD4 and RN203 element 2. CS/WR pull-ups R50/R203 and R204 deleted. R214 100k holds the touch controller in reset. R43 66.5k → 100k 0.1%: display-branch current limit 234/266/303 mA | S-11, SC-05, S-25 |
| Other deletions | DNP footprints C908 and C204; R105 (AD7380 SDI series 33R) | S-9, S-4 |
| Part merges | 13 caps 1 µF 25 V X7R: CL10B105KA8NNNC (LCSC out of stock 2026-10-04) → GRM188R71E105KA12D (C86020, same spec). Value strings normalised on 7 caps | S-23 |
| Placement | R103 to B at the AD7380 SDOA pin; C106 moved, which clears the C106/C24 courtyard error | EXTADC-03, P1-25 |
| Rules | PACK_RAW back to Power_Battery + `v10_pack_raw_kelvin` (package G6) | 2a review M1 |

**Minor review items and where they went.**

| Item | Where it went |
|---|---|
| Return GND via at C412 | Checkpoint 4 return vias |
| The open U402/C404/R408 VSYS island | Checkpoint 4 routing: land the trunk at the C404/U402.4 via, never through R408.1 |
| Stale sheet notes | Notes package after 2b |
| C31 16 V → 25 V (CL31B106KAHNNNE, C14860) | Sourcing package |
| PC13/PD4 | Analog mode (`FIRMWARE_NOTES.md` §2) |
| EREF_BUF meeting R11.1 at 45° | Accepted. The junction is on the pad. Any merge off the pad would create a 90° or 45° joint, which breaks the Analog_Precision 134° rule. |

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
| Schematic (Konnect) | Deleted 4 zero-length wire stubs on the MCU sheet (PE11-PE14). Cleared the custom `DNP` field on 21 symbols. C321 set `dnp` / not in BOM; R310 not in BOM. ERC exclusion for U8 VCAP pin_to_pin | The custom DNP field shadowed KiCad's own DNP flag. It dropped the fitted FB1 damper C100/R109 from the JLC BOM (critique P0-1). |
| RF | C4 to U2 FLT1; U1 rotated next to U2 so ENBL runs on F with no vias. GND vias in pad at FL1 and R301 | ADL5511 layout; U1 kept: ADL5511 Rev E p.8 forbids tying ENBL to VPOS when the supply ramps slower than 20 ms (LT3045 here takes about 55 ms) |
| Analog | R3 / C9 / TP2 compacted: the Sallen-Key input node on one straight track | OPA2320 Fig. 49 |
| Expansion | C405 (dV/dT) at U402 pin 2, with GND straight into U402; pin-1 GND via restored | TPS259631 layout (SLVSET8A 11.1) |
| Charger / USB | D301 (VBUS TVS) moved to B at J10's first VBUS via; R323 on the CHG_CE track | TVS at the connector pin before the branch (TPD1E10B06 7.4.1) |
| Buck | C39 loop compacted; +3V3_D feed widened to 0.8 mm; VSYS zig-zag and BUCK_SYNC straightened | LMR43620 9.5.1 |
| Battery | 22.9 mm dead antenna stub on the BQ29209 CB_EN node deleted. Q302 to F, out of the J2 plug zone. F1 rotated (PACK+ In3 31.9 -> 27.9 mm). Q303 / R322 / C904 / TP303 regrouped | EMC (open stub on a 470k node); mechanical clearance |
| MCU | GND vias in pad at Y1.2, C909.2 and C910.2 | AN2867 crystal ground loop |
| Fab | Overlapping EXP_FAULT_N drills removed (two 0.20 mm holes 0.167 mm apart) and re-joined | A drill defect that DRC rated only as a warning |
| Silkscreen | "RF IN" (hidden under the U.FL) replaced by "AIMD" and "CAL" beside each jack. "BAT 2S" moved to B beside J2. Off-board ID texts replaced by "RFVD SENSOR-D REV A" plus a JLC order-number spot on B. J6 zone parameters taken from the library | Critique RF-03 / P1-9 |

## Hand-layout pass 2026-10-03 (no auto-routers; every track and move decided by hand)

User rule for this pass: "DO NOT rely on tools or auto routers, use your knowledge and tools be precise", and move parts a few mm where that opens a track. Every edit is an explicit coordinate list executed by `tools/place/pen.py`. Each was accepted only if `place/metrics.py` showed no net worse and the KiCad DRC showed no new error. Scratch boards m1-m5; the handoff board is m5.

| Step | What was done | Why |
|---|---|---|
| EXP_TMR1 | B.Cu link at the ESD array D404 (138.65, 128.0-129.3); the GND stub there was shortened and its via removed. | 0.8 mm open link at J11. |
| **VSYS trunk** | The charger SYS side (C314, U301.25, R21) and the buck/LDO side (U6, U7, F201, C27-C33, C315/C316) were two islands. A 0.6 mm B.Cu track now runs from the 0.8 mm diagonal end at (150.6, 104.0) west along y 104.0, then 45 degrees into the C314 via (145.5, 104.95). To clear the corridor: | Main power path; it was open. |
| | - LCD_RST moved from B.Cu to F.Cu between U303's two pin columns (x 150.07); its two vias were removed. | |
| | - The U303 (RTC LDO) VBAT_PACK feed moved from B.Cu to In3 (0.2 mm, inside the U303/C326 courtyards; microamps). | |
| | - The VBUS_DET hub via moved 0.57 mm north to (147.30, 103.25); its dead In3 branch was removed. | |
| | - The +3V3_D feed of the U8.100 / R49 / U401 / U403 group was re-laid: Y1.1 down F x 147.83, via (147.05, 102.60) south of C302, B.Cu into R49.1. It is 0.3 mm wide, the old jog was 0.2-0.3. This link is the only feed of that group, which includes the TPS2553 expansion rail switch. | |
| Debris | Removed copper that connected nothing: VBAT_PACK zig-zags and a 0.8 mm via at (150.6, 102.4); the LCD_RST dead branch (B and In3); a floating BUCK_SYNC via (147.1, 102.9); a floating LCD_TE B.Cu stub (150.18, 96.5-100.2); a floating LCD_D6 In3 piece (151.8-154.5, 98). | They counted as open items and blocked corridors. |
| Tools | `pen.py`: exact snapping of joints (sub-micron misses read as T-junctions to `track_angle`) and `--check`, a 4 s pairwise rule check of the new copper. `zoom.py`: `--grid` coordinate grid and `--free W,CLR` legal-corridor shading. | Precise hand routing. |

Result after m5: KiCad unconnected items 57 -> 50, VSYS islands 4 -> 3, DRC errors 14 (unchanged; warnings 212 -> 202), no net worse.

Second part (m6-m11, placement and DRC; the copper-aware `query.py free --copper` found the legal poses):

| Step | What was done | Effect |
|---|---|---|
| R304 (VBUS_DET divider bottom) | Moved from under U8 (137.07, 100.83) to beside R303 at (146.75, 114.48) B rot -90. Short B link R304.2 to R303.1; GND via at (147.40, 114.15). The 20 mm In3 run R303 -> R304 across the U8-J4 band (x 136.9-147.4, y 100-114) was removed. | VBUS_DET 55 -> about 35 mm of copper; In3 space freed in the band. |
| R411 (EXP_VHP bleeder) | Moved beside C406 at (144.77, 122.67) B rot 270. Its EXP_VHP pad lands on C406's EXP_VHP via (same-net via-in-pad). GND via at (144.85, 124.75). Its 6 mm In3 branch and two vias were removed. | DRC clearance error R411 / EXP_VHP_IN fixed; In3 (140.7-144.3, 117-121.3) and B next to R19 freed. |
| USB_DP / USB_DM | The 4 segments at 0.12-0.14 mm widened to 0.15 mm. The 14.2 mm DM run moved 0.011 mm east (0.1 mm from the EXP_TMR_IN_MCU vias); the DM stub/via at U8.70 moved 0.007 mm off the PA10 pad. | 4 `v7_usb_fs_width` errors fixed. |
| R404 (+3V3_EXP bleeder) | Moved (-0.15, -0.40) mm with its GND via-in-pad. The only offset that keeps >= 1.9 mm from the H3 boss and clears H5's courtyard. | 2 `mech_h1_h4_boss_courtyard_B` errors fixed. |
| R417 | Moved 0.04 mm in x. | TP305/R417 courtyard overlap fixed. |
| BUCK_SYNC at the LMR43620 input | Via slid 0.07 mm along its own line to (156.23, 93.57); the C900 stub moved 0.06 mm west (x 157.82). | 3 `sp_clock_3w` errors (BUCK_SYNC vs VSYS 0.27 mm) fixed; now >= 0.30 mm. |

| Geometry (m13) | 22 `track_angle` warnings removed by hand:
- duplicate overlapping CHG_INT_N segments plus a dead stub and via at U8.22;
- micro-jogs (< 0.05 mm) at the R900 BUCK_SYNC via and in ADC_REFIO;
- a near-vertical PSRAM_IO1 segment made exactly vertical;
- the USB_DM T-branch at J10 run straight through its via;
- UI_EN diagonal joined exactly;
- ILIM_HIZ re-laid pad to pad (R307.1 - R306.2) with the U301.17 via branch ending in R307.1's pad;
- PC0's two branches started at one point in C57.1's pad. | `track_angle` 28 -> 6 (left: the USB_DM T at the U304 ESD tap and an I2C_SDA T at (150, 137); both need a junction moved onto a pad). |
| Dead copper (m15, m16) | Removed only what the DRC flags as dangling on nets that are complete:
- dead vias on BUCK_SYNC, BUCK_SYNC_MCU, PC14, SWCLK, SWDIO, SWO;
- EXP_INT0_N_MCU's dead stub at U8.56;
- a 4 mm dead LCD_RST In3 stub;
- stubs on PSRAM_IO3, EXP_3V3_EN, Net-(Q202-D), +3V3_EXP, GND;
- **a 14 mm dead branch of +3V0_REF** hanging off R107.1 (two vias, B and F runs, a 0.025 mm-step staircase, ending under U8) — an antenna on the ADC reference;
- a 1.5 mm dead +3V0_REF stub with its via at D12. | Warnings 176 -> 153; all nets keep their pads (+3V0_REF: 1 island, 9 pads). |
| BUCK_SYNC to the LSE crystal (m12) | The +5V_A In3 corner moved 0.7 mm east: y 94.27 to x 143.67, then 45 degrees to (144.67, 95.27). The BUCK_SYNC In3 bend then moved to x 143.45 -> (144.50, 96.33): 3.04 mm from the PC14 via-in-pad at U8.8 (rule 3.0), 0.67 mm from +5V_A (3W rule 0.3). | Sign-off `v7_emc05_buck_sync_lse_3mm` passes (was 2.80 mm). |

Not fixed, with reasons:
- **C106/C24 courtyard overlap** (U13 REGCAP and U5 NR caps, both "high" sensitivity at their pins): no copper-legal pose within 0.5 mm for either part.
- **skew_sdmmc** (2): resolves only when SD_D1 is routed. Its series resistor R35 sits outside U8's west pin row; R34 (SD_D0) sits under the pins, east of the row. So SD_D1 would have to cross the whole U8 SW-corner fan-out to reach J3.8. Moving R35 under U8.66 next to R34 and following SD_D0's In3 path (x 129.16) was the proposed fix, but it is **not possible** (checked 2026-10-03 with `query.py free --copper`): no copper-legal R35 spot exists next to R34. The only legal B spots are its current one and spots 4–5 mm away. Re-fan the SD escapes around R35 instead (routing guide, WP3).

### Band re-layout study (2026-10-03, user-approved: lift detoured nets, move U402 to J11, re-pack the SD ESD field)
Measured on a scratch copy with 11 detoured transit nets lifted: SWO, SWCLK, EXP_TMR*, EXP_INT0_N_MCU, EXP_FAULT_N, EXP_VHP_EN, EXP_I2C_SDA, CHG_STAT, CHG_LED_A. That is 570 mm and 50 vias. Tool: `lanes`-style vertical free-run scan, 0.15 mm track / 0.2 mm spacing.
- **West corridor exists**:
  - In3 x 119-126.5, from y 103.5 down to y 116-121;
  - B partly free x 118-127.
  - F under J3 is NOT a through-route: J3's footprint keep-outs (F only) cover a strip y 106.8-107.5 at x 121-128.6 and x 128.3-129.9 at y 107.5-116.2.
  - This corridor suits USB D+, the expansion lines from U8's west pins and the lifted debug/timer lines.
- **Centre of the band (x 128-152, y 104-123) has no vertical lane longer than about 6-9 mm** on any layer, even after the lift. The blockers are fixed parts:
  - J3's contacts with the ESD/series-resistor field D4-D10 / R31-R38 and their vias (x 133-137, y 104-118);
  - the charger power stage (L301, U301, PMID/VBUS trunks, K5_L301_BODY);
  - U402 with its thermal-via field K13 (x 138.6-141, y 117.4-122.2).
- **U402 cannot move**:
  - no courtyard-legal pose on F anywhere in the lower half;
  - F under J4 is K4_TFT_LOOP (display flex fold, no parts), and B around J11 is the expansion-shield bay;
  - its only B spot is (164, 128), 24 mm away;
  - it cannot shift east either, because C406's courtyard touches it.
- **SD ESD re-pack** could open one lane at x 135.5-137.2 (y 105.5-117.5) by moving the ESD GND vias and SD signal vias into or west of J3's contact pads (same-net via-in-pad is allowed). But north of it the U8.90-92 fan-out vias (EXP_DETECT_N / EXP_RST_N / PSRAM_CS_N) and south of it U402's west pins (x >= 136.35) still block a 4-line display-control lane to J4.10-13.
- **USB D+ escape at U8.71** is ringed by the SWDIO (128.17, 100.42), SD_D0 (129.06, 99.48), SD_D2 (128.38, 102.85), UI_FAULT_N, UI_EN and GND escape vias at about 0.45 mm spacing. It needs a re-fan-out of U8 pins 69-75 and the SD_D0/D2 escapes together.
- **Conclusion:** the display bus (12 lines), the buttons and USB D+ need either a board-level re-placement (J3 + its ESD field, or the charger block, away from U8's south-west fan-out) or an interactive push-and-shove session that re-fans U8's south-west corner. Single-net hand routes cannot open them.
- **J3 re-placement checked, not possible (2026-10-03).** A whole-board search for a courtyard-legal J3 pose returned none:
  - J3 is the microSD socket, with a 17.7 × 15.7 mm courtyard; the search covered F, all 4 rotations, on a 1 mm grid.
  - The port notch fits only J3 + J10; moving J3 down overlaps J4's courtyard, and below the notch is H3's boss keep-out.
  - The team then chose the interactive hand-off: see `ROUTING_FINISH_GUIDE.md`.
  - Note on the second bullet above: the later m6–m16 edits (R304/R411 moved, dead copper removed) opened a direct In3 corridor for USB D+ (U8.71 escape → U301.6). The J10 → U8.71 main path also exists now (feasibility check, 2026-10-03).

### Display bus (decided)
The display uses the 8-bit 8080 bus: D0-D7 plus CS/DC/WR, through the most congested band (U8 -> J4). **Rejected (lead decision D13, critique P1-31): the 8080 bus stays.** For the record, 4-wire SPI on this panel would use J4.9 SDA (GND today), J4.11 SCL, J4.12 D/CX and J4.10 CSX with IM = 0/1/1. It would also need an MCU re-pin (SPI1 on PB3/PD7, which loses SWO), a rev-2 or later panel, and about 81 ms per full frame at 15 MHz. The earlier note in this guide (SCL on WR, SDA on D0) named the wrong pins. Checkpoint 2a made the bus write-only (RDX tied to +3V3_UI, so LCD_RD_N is gone) and put the IM straps in copper (R200-R202 deleted).

### Blockers found while hand-routing (what each remaining power/control link needs)
- **VBAT_RTC** (C603/U8.6 to C327/U303.5, 7 mm): the straight path crosses the HSE cell. K10F bans it on F, K10B on B. On In3, VSYS (144.1-145.4, 100.2-101.5), TP_SDA (x 149.53) and EXP_VHP_EN (y 99.72) close it. North of the cell, B.Cu holds the +5V_A / LCD_RST / CHG_INT_N vias at y 94.5-95.3. Fix: re-route the TP_SDA F hop and the EXP_VHP_EN segment around U303, then run VBAT_RTC on In3 at y about 100.3.
- **CHG_INT_N** (U301.21): the B.Cu lane K16 (x 143.05-144.9) is empty and reserved for it. Entering at the top needs a B-only start at C907.1, because any via there is within 1 mm of +3V0_REF (C56/C59 on F). The real blocker is the U301 end. Pin 21 is boxed by C318.2 (GND) and C319.1 (CHG_BAT), only 0.44 mm apart. The way north from the via at (144.40, 109.25) crosses VSYS on B (y 104.95-106.08), I2C_SCL on In3 (x - y = 39.24) and I2C_SDA / SDRV on F (y 105.74 / 106.01). Fix: move the I2C_SCL In3 diagonal about 0.6 mm south-west, then In3 from the U301 via to a via at about (143.35, 104.9) and up the lane.
- **REGN to R19** (charge LED): R19.1 is boxed by R19.2, R411.2, the I2C_SCL via/track and the VBUS/BTST1 pair. R19's rule allows it anywhere in series with D3 (max 40 mm). The fix is to move R19 next to R312 / REGN and re-run CHG_LED_A, which today detours 57 mm with 6 vias, beside CHG_STAT (In3 x 155.5) to D3. The band y 117.6-124.5 between them is the J4 fan-out (LCD_LED_K1/K3/A, LCD_RST, VBUS), so this is a planned move, not a nudge. **Verified 2026-10-03** on a scratch copy:
  - R19 goes to (149.00, 113.90), rot 0, B. That pose is copper-legal, and its REGN pad lands on REGN copper, so REGN closes.
  - Remove the old CHG_LED_A copper (38 items, 57 mm).
  - R19.2 → D3.2 then has a legal B > In3 > F path (2 vias) down the east side.
- **USB_DP to U8.71**: the MCU side only reaches a via under U8 (131.12, 99.06). Below it, the U8 south-row fan-out vias (SD_CLK_MCU/SD_D3_MCU/LCD_D2_MCU/LCD_D3_MCU at y 104-105) and the SD bus on In3 close every path. The F column beside USB_DM (x 127.1) is held by EXP_TMR_IN_MCU (x 126.7) and +3V3_UI / VBUS vias (x 127.6-127.75). Fix: re-route EXP_TMR_IN_MCU, then run D+ beside D- as a pair.
- **RN201 (LCD_D0-D3)**: its connector-side pads are boxed on F by EXP_INT0_N_MCU (west at x 123.80, 0.19 mm; north at y 94.32) and by the LCD_D0_MCU / PSRAM_IO1_MCU vias (south). EXP_INT0_N_MCU detours 64 mm (34 mm direct) down the west edge. Fix: re-route EXP_INT0_N_MCU first, then exit RN201.5-8 west to vias and run south on B.Cu through the free west area (x 118-127, y 104-120).

## Why the last 9% is hard (read this first)

- **One inner signal layer.** In1, In2 and In4 are solid GND, and In2 is In3's 0.109 mm reference. So every long route shares In3, and crossing another In3 route needs two vias to F/B.
- **The U8 periphery is saturated.**
  - About 60 small parts sit inside U8's pin-escape bands: series resistors, resistor arrays, decouplers and dividers, many of them on B, directly under the pin rows.
  - Their far pads are boxed in. There is no legal spot to move them to within about 1.6 mm without breaking a neighbour.
  - Resistor arrays at 0.5 mm pitch cannot take via-in-pad.
- **The corridor from U8 to J4/J11** (y 104-122) runs through the charger (U301/L301), the eFuse (U402) and the SD socket (J3). About 45 long nets must pass there.
- **U8's orientation is already optimal.** At 180 deg, only 5 long nets leave from the side facing away from their destination; the other orientations give 15, 20 and 36.
- **The automatic tools stalled.**
  - The tools used: the in-house A* router with rip-up, KiCadRoutingTools, and placement search.
  - The yield fell to a few connections per hour, so the rest is better done interactively (push-and-shove).

## Remaining connections and recommended approach

### LCD bus to J4 (18)
| Net | From | To | Gap mm |
|---|---|---|---|
| LCD_D0..D3 | J4.22-25 | RN201.8-5 | 30.6-33.8 |
| LCD_D4..D7 | J4.26-29 | RN202.8-5 | 34.3-36.1 |
| LCD_D2_MCU | U8.81 | RN201.3 | 9.4 |
| LCD_DC / CS_N / RD_N / WR_N | J4.11 / J4.10 / J4.13 / J4.12 side | RN203.5 / .6 / .7 / .8 | 18.4-20.1 |
| LCD_TE | J4.40 | R206.2 | 31.6 |
| LCD_RST | J4.30 / R51 | R904.2 | 24.0 |
| LCD_BL | U8.63 | R211.1 | 24.9 |
| LCD_LED_K4 | J4.37 | D204.2 | 20.2 |
| LCD_BL_SW | D201/D202/Q203 | D203/D204 | 14.8 |

**RN201 (top side, west of U8, D0-D3)**
- Its connector-side pads (5-8) can only exit west, where R60/R63 (PSRAM series resistors) and R35 sit. Move R60/R63 about 1-1.5 mm west or north (medium sensitivity, 5 mm budget) and exit RN201.5-8 west to vias.
- Then route on In3 down the west side under J3 (J3's keep-outs are top-layer only) to J4.22-25.
- LCD_D2_MCU comes from the south pin row (U8.81) and is about 9 mm long by construction. Either accept it, or move RN201 to U8's south-west corner and accept `len_source_stubs` warnings.

**RN202 (bottom side, under U8's north pins 37-40, D4-D7)**
- The far pads need a short stub (0.5-1 mm) south under the U8 body to a via each. Inside the U8 courtyard the analog-partition ban does not apply.
- Then run In3 south under U8 to J4.26-29.
- Make room by moving C908 (TP_INT shunt), R106 (ADC CS series) or R108 (pull-up, low sensitivity) by about 1 mm.

**RN203 (bottom side, under U8's south half)**
- The CS_N and RD_N far pads already have escape vias; DC and WR_N are blocked by +3V3_D / I2C_SCL copper next to RN203.
- Re-route that +3V3_D or I2C_SCL segment by about 0.5 mm, then run In3 south to J4.10-13.

**Backlight group (right of J4)**
- LCD_TE, LCD_RST, LCD_BL, LCD_LED_K4 and LCD_BL_SW are short-to-medium runs.
- Keep LCD_TE and LCD_RST in the B.Cu display lane `K16_DISP_LANE` (allowed owners) where it helps.

### Expansion to J11 (16; EXP_SPI_MISO and EXP_FAULT_N routed since)
| Group | Nets | Gap mm |
|---|---|---|
| MCU side to series resistor at J11 | EXP_CS0_N_MCU (U8.51→R425), CS1_N (U8.55→R427), MISO (U8.53→R423), INT1_N (U8.57→R428), RST_N (U8.91→R431), DETECT_N (U8.90→R432), IO0 (U8.98→R429), IO1 (U8.97→R430) | 20-47 |
| Connector side from resistors near U8 | EXP_SPI_SCK (R419→J11.5/D401), SPI_MOSI (R421→J11.7/D401), GATE (R433→J11.33/D403), SYNC (R434→J11.35/D403), ANA_MON (R435→J11.34/D406) | 31-42 |
| Monitors | EXP_3V3_SNS (U8.18 group→R414), EXP_VHP_SNS (U8.17 group→R412) | 43 |
| Short / local | EXP_I2C_SDA (D402.4→J11.27, 0.8), EXP_FAULT_N (U402.6→R403/U401/U8.87, 6.0); EXP_TMR1 routed 2026-10-03 | <=6 |

- **Bus routing.** Route the long ones as a bus on In3 from U8's west and south pins, passing west of the charger (x about 128-136, under J3/U9) and south to the J11 area. That corridor is lighter than the one under U301.
- **Short links.** EXP_I2C_SDA and EXP_TMR1 are 0.8 mm links at the ESD arrays D402/D404 (bottom side). Each needs one short B.Cu track; move a GND stitching via if it blocks.
- **Optional.** The series resistors R419/R421/R433-R435 sit under U8's pins (medium sensitivity, 4-10 mm budgets). Moving them 2-3 mm outward frees their far pads.

### Power and charger (10; CHG_BAT / VBAT_PACK closed by moving R314 under Q301)
| Net | From | To | Gap mm |
|---|---|---|---|
| VSYS (x2; main trunk closed 2026-10-03) | U301 SYS group | R405 (EXP_VHP source select A) - TP9 (test pad) | 10.1 / 10.9 |
| VBAT_PACK | main group (Q301/Q303/U303...) | R314.2 | 27.8 |
| CHG_BAT | U301.22/23 / C319 / C320 / Q301 | R314.1 | 25.3 |
| REGN | U301.5 group | R19.1 (charge LED) | 4.7 |
| CHG_INT_N | U301.21 | C907/R311/U8.22 | 15.1 |
| QON_N | U301.12 | SW5.2 | 31.8 |
| USB_DP (x2), USB_DM | U301.6/.7 (BC1.2 D+/D-) | J10/U304 and U8.71 | 18-20 |
| VBAT_RTC | C603/U8.6 | C327/U303.5 | 6.3 |

- **VSYS** (0.5 mm Power_Battery track) needs a channel near R313/R305/U303. Re-route SDRV, I2C_SDA and +3V3_D there by about 0.5 mm, or use the planned B.Cu lane `K19a_VSYS_BAND` (y about 106) to reach F201 and U6.
- **R314** joins CHG_BAT and VBAT_PACK and sits about 25 mm from the charger. Moving it next to Q301/U301 removes two long power runs. Check its function in the Power_USB sheet first.
- **USB D+/D-** to U301 are only for BC1.2 detection. Route them as a pair with stubs as short as possible. Width 0.15 mm (`v7_usb_fs_width`).

### Other (9)
| Net | From | To | Gap mm |
|---|---|---|---|
| NRST | U8.14 / C46 / R18 | J6.3 (SWD) / SW3.1 | 43.4 |
| BOOT0 | U8.94 / R20 | SW4.1 | 37.6 |
| MARK_N | U8.3 / C70 / R49 | SW2.1 | 36.4 |
| RECORD_N | U8.2 / C67 / R44 | SW1.1 | 35.6 |
| LID_INT | U8.84 / C906 / R701 | U702.5 | 35.9 |
| TP_INT | J8.5 / R208 | R906.2 | 28.9 |
| TP_SCL | J8.3 / R45 | U8.46 | 34.0 |
| PSRAM_IO2 | R64.2 (at U8) | R65.1 (at U9) | 18.5 (QSPI data: keep the skew to its IO0/1/3 siblings <= +-10 mm) |
| SD_D1 | R35.2 | J3.8 / D9 / R37 | 14.0 (then check `skew_sdmmc`) |

- The button, SWD and lid lines are slow signals and Harness_IO class. They can share In3 with the J11 bus.

### GND (0 islands; joined 2026-10-02 night)
U8.49, U8.19, D405.8, D402.3/.8, D401.3, D401.8. Add one GND via each, in the pad where it fits, otherwise a 0.3 mm stub to a 0.45/0.20 via. `tools/gndvip.py` in the repo `tools/layout` does this automatically.

## DRC errors (outputs/RFVD_DRC_report.rpt) and how to fix them

| # | Rule / type | Reports | Where | Fix |
|---|---|---|---|---|
| 1 | `fab_pth_hole_clearance` | 12 (1 issue) | SWDIO via (120.50, 132.62), 0.293 mm from the J10 shield PTH (rule 0.30) | Move the via 0.05 mm away from J10. |
| 2 | `v9_w_power_neckdown_chg_caps` | 7 | REGN tracks 0.15 mm inside C3xx courtyards (around 143.9-148.5, 108-118) | Widen to 0.20 where it fits, or make `v9_regn_light` (0.15 min) win inside C3xx (append after the neck rule). |
| 3 | `starved_thermal` | 6 | J10 shell pins (4) and J11 shield pin: 1 spoke instead of 2 | Add a short GND track from each pad into the fill, or make those pads solid-connect. |
| 4 | `fab_via_window` | 8 (4 vias) | BTST1/BTST2/SW1/SW2 vias at U301 are 0.45/0.20; the rule wants >= 0.50/0.30 | Resizing breaks `v3_sp_chg_sw_in_u301` (tested: +13 errors). Either add a scoped via exception for U301 (like `v3_allow_chg_boot_vias`) or re-place the 4 vias with more room. |
| 5 | `v7_usb_fs_width` | 4 | USB_DP/DM segments at 0.14 mm next to U8 (127-129, 99-108) and U301 (145.6, 113.6) | Nudge the neighbours and widen to 0.15, or allow a 0.14 neck at the IC pins. |
| 6 | `sp_clock_3w` | 3 | BUCK_SYNC vs VSYS around (156-159, 93-95): 0.27 mm instead of 0.30 | Move the BUCK_SYNC via or track 0.05 mm. |
| 7 | `sp_analog_to_harness` | 2 | TP_RST_MCU via and track at (143.3, 89.1) vs C25 pad 1 (reference filter): 0.83 mm instead of 1.0 | Move the TP_RST_MCU via about 0.2 mm away from C25. |
| 8 | clearance | 2 | R411 pad vs EXP_VHP_IN (0.198 / 0.2); +3V3_D vs R49.2 (0.145 / 0.15) | 0.01 mm nudges. |
| 9 | `mech_h1_h4_boss_courtyard_B` | 2 | R404 courtyard 1.845 mm from H3 (rule 1.9) | Move R404 0.06 mm away from H3. |
| 10 | courtyards_overlap | 2 | TP305/R417; C106/C24 | Nudge TP305 and C24 (both low sensitivity). |
| 11 | `skew_sdmmc` | 2 | SD bus skew 15.3 mm (SD_D1 is still unrouted) | Route SD_D1, then length-match CLK/CMD/D0-D3 (max skew 10 mm). |
| S | `v7_emc05_buck_sync_lse_3mm` (sign-off) | 2 | BUCK_SYNC In3 segment near (143-150, 95-96) passes within 2.8 mm of the PC14/PC15 vias | Shift that segment about 0.3 mm away from Y2. |

**Warnings worth a look.**
- `len_source_stubs` (12): some MCU-to-series-resistor stubs are longer than 3 mm (RN201 serves two pin rows).
- `track_angle` (10 right-angle or acute, 20 on smooth-critical nets).
- `track_segment_length` (53 short segments on critical nets).
- Clean-up items: `via_dangling` (51) and `track_dangling` (24) are escape vias and stubs waiting for their missing connection. They are used when you route the rest; delete whatever remains unused at the end.
- One each: `v3_afe_partition_aggressors`, `len_psram_clk_inward`, `skew_venv_eref`.
- Silkscreen: 20 left after the designators were hidden (outline / label overlaps).

## Decisions and deviations made in this layout pass

1. **In3 under the analog partition.** Digital nets may run on In3 under `AFE_PARTITION`, between the In2 and In4 GND planes, but no vias are placed inside it. This matches the project DRU: `v3_afe_partition_aggressors` covers F/B and does not flag In3; verified with KiCad DRC.
2. **Soft module locality.** Tracks may cross another module's surface (F/B) or put a via inside it at a cost. Some inter-module routes do this; the strict version left about 40 routes impossible.
3. **NRST corner re-placed.** R18 moved to (136.1, 95.7) rot 90 and R24 to (138.4, 94.5). C46/C57 kept. NRST now leaves U8.14 under the body to C46.
4. **USB widened in place** to 0.15 mm on 30 segments. 4 segments remain at 0.14 (DRC item 5).
5. **Design rules.** `.kicad_pro` `min_hole_clearance` is 0.2 here (project: 0.25). DRU patches 1-5 are applied; see `CHANGES_FROM_PROJECT.md`.
6. **KiCadRoutingTools.** Its output was used only where every new item passed the full rule check (widths, vias, angles, rule areas, clearances): 17 net changes. Its first, unfiltered result (282 DRC errors) was rejected.
7. **Clean-up.** Removed one GND via inside J3's keep-out and one GND stub in a keep-out (DRC-driven).

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
- Why: every chain ends at a fixed via or pin escape, and those positions follow from the dense placement around U8, J4 and J11. Real highways need the end points to move, which means re-doing the U8/J4/J11 escapes and moving the series resistors. That is the same work as finishing the last 57 connections.
- **Recommendation:** define the lanes while routing the remaining connections. Use In3 north-south lanes from U8's south and west sides to J4/J11, and B east-west lanes for the button and SWD lines along the bottom edge. Clean up neighbouring routes interactively as you go.

## Remaining DRC errors after the 2026-10-03 clean-up (14 with the project DRU, 21 with the sign-off rules)

| Errors | Problem | Fix |
|---|---|---|
| 2 (+8 sign-off) | **BUCK_SYNC spacing.** 3W to VSYS near the LMR43620 input caps (156-159, 93-95), plus 3 mm to the LSE net PC14 (#SIGNOFF `v7_emc05`, at 144-150, 96.3). | Re-route BUCK_SYNC by hand, keeping 3W to VSYS, 3 mm to PC14/PC15, <= 40 mm and 5 mm from RF/edge. It is EMC-critical, so it was left for a deliberate manual route. |
| 4 | **USB widths.** USB_DP/DM segments at 0.12-0.14 mm; the rule asks 0.15. | Boxed in, so widening in place fails. Re-route those 4 segments, or accept them: at 12 Mb/s full speed the impedance shift is harmless. |
| 2 | **Courtyard overlaps** TP305/R417 and C106/C24. | Nudge R417 0.05 mm right and C106 0.3 mm left. The automatic nudge collided with copper, so do it in the GUI with push-and-shove. |
| 2 | **R404 vs the H3 boss** (`mech_h1_h4_boss_courtyard_B`, 1.9 mm from the hole wall). | Move R404 about 0.2 mm up, away from H3. |
| 1-2 | **R411 pad vs the EXP_VHP_IN track** (micro-clearance). | Re-route the short EXP_VHP_IN stub. |
| 2 | **skew_sdmmc.** | Resolves when SD_D1 (still open) is routed with matched length. |

Fixed in this pass:
- 6 starved thermals (solid shield pads);
- 13 SWDIO hole-clearance errors (via re-routed);
- TP_RST next to analog C25 and +3V3_D at R49;
- 8 + 7 rule conflicts on the charger bootstrap vias and REGN (DRU patch v10, see `CHANGES_FROM_PROJECT.md`).

## Board widening and placement audit (2026-10-02 night)

See `PLACEMENT_AUDIT.md`. In short:
- **Widening.** +2.5 mm on each side; the port notch keeps J3/J10 flush. Every part keeps its absolute position.
- **Edge gaps.** Parts within 2 mm of the real edge: 47 -> 27, all edge-bound by design or in the port section.
- **Moves.** R314 went under Q301, closing 2 power connections. TP11 sits on +3V3_D. Q302 went to the bottom side next to U302: a 55 mm drain detour along the bottom edge became a 4 mm route plus a 20 mm VBUS gate route, which frees the bottom-edge corridor for the button lines.
- **Fenced in.** D203/D204, R412/R414, R18, C302, R304, TP9, R51 and R103 were flagged but have no legal or routable spot; the reasons are in the audit document.
- **Gate.** Every change passed metrics (no net worse) and sign-off DRC (no new errors).

## How every step was verified

Each change was accepted only if all three checks passed:
- KiCad's unconnected count did not rise and no net lost connectivity (`tools/place/metrics.py`).
- New copper passed the exact pairwise rule model (`tools/mr.py`: DRU class clearances, HS/clock/analog/RF spacing, rule-area bans, neck-downs).
- The KiCad DRC with the project rules did not get worse (`tools/drcsum.py`).
