# RFVD SENSOR-D Rev A: manufacturing and EMC specification (JLCPCB)

**Status 2026-10-04, fix-plan item P1-10.** This replaces `scratchpad/v6/fab/MANUFACTURING_EMC_SPEC.md` (2026-09-30, with the 6-layer note of 2026-10-01) and `v6/fab/fab_spec.md`.

**Where the numbers come from.** Every board number below was read from one of these:
- the board file `rw/base_cp2a/RFVD_SENSOR_BOARD.kicad_pcb` (sha256 `c4383fe7aba5...`, the checkpoint-2a candidate);
- its `.kicad_pro` and `.kicad_dru`;
- the tool reports named in the Source column.

Other work streams are still editing the board, so re-run both tools on the final board before ordering (section 10). Nothing was uploaded, and no order or quote was started.

**Files (all in `%LOCALAPPDATA%/Temp/rw/fab/`)**
- `make_panel.py`: builds the panel, its checks, the panel CPL/BOM, the panel DRC classification and the renders.
- `make_fab_outputs.py`: builds the Gerber, drill and fab-notes package and runs the checker. It is the Python port of `make_fab_outputs.sh`.
- `fab_notes.txt`: the fab-notes block (section 9).
- This spec.
- Test runs are in `work/` (section 10).

---

## 1. Panel decision

### 1.1 Recommendation
**Build our own panel and order it as "Panel by Customer".** Upload our panel Gerbers and a "Complete File" panel CPL/BOM.

"Panel by JLCPCB" is not available for this outline:
- JLC panels only rectangles and round boards, and uses V-cut.
- This board has four R3 corners and a 2.5 x 29.7 mm notch on the W edge, where J3 (microSD) and J10 (USB-C) sit.

JLC's other fallback is to add rails itself to an under-size single board. JLC then chooses the tab positions, and parts on this board sit 0.00 to 0.68 mm from the edges (J10, J3, Q302, J1, J300). So we place the tabs ourselves.

### 1.2 Evidence (JLC help pages read 2026-10-04; the help articles show "last updated Sep 09, 2026")

| Question | Page | JLC's words | Meaning here |
|---|---|---|---|
| Which outlines does "Panel by JLCPCB" take? | jlcpcb.com/help/article/instructions-for-ordering (section 14) | "Generally, if you choose JLCPCB to panel the PCB for you when you place your order, basically, we will panel your order with V-cut, but we panel those PCB with rectangle and round shape only." | Our outline is neither a rectangle nor round, so (b) is closed. |
| Complex outlines | jlcpcb.com/help/article/how-do-i-order-a-panel | "Please ensure that the board outline is simple. For complex board outlines, you will need to panelize them yourself." | We panelize. |
| Rails for Panel by JLCPCB | same page | "By default, we will add a 5mm board edge, as shown in the image below." | No price is published; v-cut only costs extra "If either side of the single PCB is within 15mm". |
| CPL with Panel by JLCPCB | jlcpcb.com/help/article/common-bom-and-cpl-matching-issues-and-explanations | "Your BOM and CPL files are for a single PCB." / "If you select panelization when placing the order, you must choose this option so the system can automatically replicate the data and calculate the total component quantity based on panel count and placement quantity." | This "Single Piece" route would have avoided a hand-made CPL, but it needs Panel by JLCPCB. |
| CPL with our own panel | same page | "If your files already contain complete panelized data, select this option." / "The system will calculate the total component quantity by multiplying the placement quantity only." | "Complete File": one CPL row per placement on the panel. |
| Designator rules | same page | "Each reference designator appears only once" / "The minimum coordinate spacing between different reference designators is greater than 0.2 mm" | Panel CPL uses `REF_1` / `REF_2`. The smallest spacing is 0.233 mm (C312_1 on top, R303_1 on the bottom). |
| BOM and CPL must agree | jlcpcb.com/help/article/advice-for-bom-and-cpl-files-preparation | "Please verify that all reference designators (e.g., R1, C2, U3) listed in the BOM file exactly match those listed in the CPL file." / "Each BOM line should contain no more than 200 reference designators." / "Please include both top-layer and bottom-layer placement data in a single CPL file." | Panel BOM and CPL both have 692 designators. The largest BOM line has 100. One CPL file covers both sides. |
| JLC fallback for a small single board | jlcpcb.com/help/article/Terms-and-Conditions-of-JLCPCB-Assembly-Service | "Tooling holes, Edge rails and Fiducials are required for PCB assembly orders." / "for board dimension smaller than 70mmx 70mm or missed edge rail on standard PCBA service, JLCPCB will select a suitable production method for edge rail, for instance, mouse bite method." | JLC would choose the tabs. Rejected, because parts sit at the edges. |
| Same fallback, other page | jlcpcb.com/help/article/how-to-design-multi-color-silkscreen-using-easyeda | "The edge rails are added with v-cut for regular shape PCB, but with mouse bite for irregular shape board." | Confirms the fallback uses mouse bites at JLC-chosen spots. |
| Standard PCBA limits | jlcpcb.com/capabilities/pcb-assembly-capabilities | Standard PCBA: PCB panel size "70x70mm - 250x250mm"; delivery format "Single PCB, Panel with mouse bites, Panel with V-cut"; edge rails "Necessary"; fiducials "Necessary"; minimum package "0201" (Economic "0402"); order volume "2 - 80000 pcs" | D1 and D300 are SOD962-2 (0201 class), so the order must be Standard PCBA. The panel is 120 x 90 mm. |
| Panel method for Standard PCBA | jlcpcb.com/help/article/pcb-assembly-faqs | "Mouse-bites and V-cut are available, for Economic assembly, please panelize your boards with mouse-bites. for Standard assembly, you can panelize with mouse-bites or V-cut." | Mouse bites. |
| Rails, tooling holes, fiducials | jlcpcb.com/help/article/specifications-for-adding-process-edges-and-positioning-holes | "For boards that use JLCPCB's SMT assembly service, we recommend 5 mm process edges, 2 mm tooling holes, and 1 mm fiducials placed 3.85 mm from the panel edge" | 5.0 mm rails, 2.0 mm tooling holes, fiducial centres 3.85 mm from the outer rail edge. |
| Fiducial details | jlcpcb.com/help/article/how-to-add-edge-rails-fiducials-for-pcb-assembly-order | "The minimum width of edge rails should be at least 5 mm." / "The recommended diameter of a fiducial marker is 1 mm." / mask opening "twice the diameter" / "Three to four fiducial markers should be placed along the board edges." / "Fiducial markers must maintain a minimum clearance of 3.35 mm from the board edge." | 1.0 mm copper with a 2.0 mm opening. 3.85 - 0.5 = 3.35 mm from copper to the edge. 3 per side. |
| Tooling-hole size conflict | jlcpcb.com/help/article/how-to-add-tooling-holes-for-pcb-assembly-order | "Tooling holes should be 1.152mm(45.4mil) round non-plated holes with 0.148mm solder mask expansion." / "For Economic PCBA type, tooling holes are a must." | This page covers board tooling holes, chiefly for Economic PCBA. We follow the SMT process-edge page (2.0 mm). T&C section 5: "If you choose 'Tooling Holes Added by Customer' ... but there are no tooling holes and edge rails/fiducial or incompatibility in your file, to avoid delays, we will help to add or modify them by default." |
| Mouse bites | jlcpcb.com/blog/pcb-design-efficiency-mouse-bites (updated Apr 08, 2026) | "sets of 5 to 8 holes, each with a diameter of 0.60 mm" / "Mouse bite spacing (hole edge to hole edge): 0.35–0.4 mm, with a minimum of 0.3 mm" / "Panelization spacing between boards is typically 1.6 mm or 2 mm, with a minimum of 1.2 mm" / "Mouse bites should be placed along the centerline of the board frame or extending one-third into the board" / "At least 2 symmetrically placed sets are required for boards up to 30 mm wide; add one set every 50–60 mm for larger panels" | 5 holes of 0.60 mm at 0.95 mm pitch (0.35 mm web), 0.20 mm (one third) inside the board, 2 mm gaps. Each 90 mm board edge has 2 sets. |
| Board spacing and copper | jlcpcb.com/capabilities/pcb-capabilities | "The spacing between boards should be ≥ 2 mm, as narrow spacing results in difficulties for routing and V-cut" / mouse-bite panel: "Copper clearance from non-mouse-bite board edges: ≧0.2 mm; Minimum tooling edge width: 3 mm" | Gaps are 2.0 mm. The board keeps copper 0.5 mm from its edges (`min_copper_edge_clearance`), which is 0.30 mm from the bite holes. |
| Parts near tabs | jlcpcb.com/blog/pcb-panelization-tools-techniques | "maintain at least 3–5 mm away from perforation lines" | The hard limit is 3.0 mm. Parts under 5 mm are listed (section 3.2). |

The fetch tool returned these quotes verbatim on request; re-read the pages on the order day.

### 1.3 D27: a 2 x 1 panel or a 1-up frame (lead decision)

Both were built and verified with the same tool and the same tab positions.

| | 2 x 1 (default, as requested) | 1-up frame, `--cols 1 --min-size 72` |
|---|---|---|
| Panel | 120.0 x 90.0 mm (120.05 x 90.05 incl. line), 5.0 mm rails | 72.0 x 90.0 mm (72.05 x 90.05 incl. line), 8.0 mm rails. A 70 mm frame would sit exactly on JLC's minimum; 72 mm keeps a margin |
| Boards from the 5-panel PCB minimum | 10 | 5 |
| Assembled boards at the Standard PCBA minimum of 2 ("2 - 80000 pcs", counted per panel under "Complete File") | **4** (2 panels x 2), unless JLC accepts a CPL that fills only one position per panel (not confirmed) | **2** |
| CPL/BOM | 692 rows, designators `REF_1` / `REF_2` | the single-board files, unchanged (346 rows) |
| Holes per m2 (JLC charges extra above 150,000) | 196,481 | 164,043 |
| Verified | `work/panel`: DRC 0 new, CPL cross-check 0 mismatches; `work/fab_panel` 0 FAIL | `work/panel_1up72`: DRC identical to the board (0 new); `work/fab_1up72` 0 FAIL |

The build plan in the ledger (2026-09-29) is "1 final unit and 1 redundancy unit populated, the rest bare, 3-5 boards maximum". **That fits the 72 mm 1-up frame.** The 2 x 1 panel doubles the assembled parts (4 boards) and gives 10 bare boards. Before upload, check on JLC's order form whether the PCBA quantity counts panels.

---

## 2. Board facts

| Item | Value | Source |
|---|---|---|
| Outline | 52.00 x 90.00 mm on the Edge.Cuts centre line (x 115.5036-167.5036, y 52.7434-142.7434); 52.05 x 90.05 mm including the 0.05 mm line | Edge.Cuts shapes (pcbnew); `board_outline_line_width 0.05` in `.kicad_pro` |
| Corners | 4 x R3.000 | Edge.Cuts arcs |
| W notch | x 115.5036 to 118.0036 (2.5 mm deep). At the edge it spans y 104.1-133.8; its straight floor runs y 105.1-132.8. Two R0.5 outer and two R0.5 inner corners | Edge.Cuts |
| Copper layers | 6: F.Cu, In1 (power type), In2 (power), In3 (signal), In4 (power), B.Cu. One GND zone each on In1, In2 and In4 | `(layers ...)`; zones |
| Stackup | F 0.035 / FR4 3313 0.0994 (er 4.1) / In1 0.0152 / core 0.55 (er 4.6) / In2 0.0152 / 2116 0.1088 (er 4.16) / In3 0.0152 / core 0.55 / In4 0.0152 / 3313 0.0994 / B 0.035; mask 0.01 per side; total 1.5584 mm. This matches JLC06161H-3313 | `(stackup ...)`, `(general (thickness 1.5584))`; Gerber job file dielectrics |
| Loss tangent | 0.02 on four dielectrics, **0 on "dielectric 3" (2116)** | `(loss_tangent ...)` (P1-13 open, cosmetic) |
| Finish | `(copper_finish "ENIG")`; job file Finish = ENIG | board setup; `.gbrjob` |
| Via protection flags | `(capping no)` `(filling no)` | board setup (P1-13 open; the order form carries the requirement) |
| Vias | 1012, all through: 918 x 0.45/0.20, 12 x 0.50/0.30, 75 x 0.60/0.30, 7 x 0.80/0.40 (pad/drill mm). Largest drill 0.40 mm | pcbnew; drill file PTH hits: 0.2 = 918, 0.3 = 95, 0.4 = 7 |
| Plated pad holes | U402 8 x 0.30; J10 2 x 0.6x1.2 and 2 x 0.6x1.7 slots; J11 2 x 1.00; H5/H6 2 x 3.80 | pcbnew; PTH file |
| NPTH | J10 2 x 0.65, J6 3 x 0.991, J11 2 x 1.45, H1-H4 4 x 2.70 | pcbnew; NPTH file |
| Holes per m2 | single board: 1039 holes on 52 x 90 mm = 221,672 /m2 (JLC: "For orders with over 150,000 drill holes per square meter, an extra cost will be applied.") | `make_fab_outputs.py` check |
| Track and space | narrowest track 0.10 mm (470 segments); `min_clearance 0.1`, `min_track_width 0.1`; JLC multilayer 1 oz: "0.09 / 0.09 mm" | pcbnew; `.kicad_pro` rules |
| Smallest via | 0.45/0.20 (`min_via_diameter 0.45`, `min_through_hole_diameter 0.2`); JLC 6-layer: "0.15 mm hole size / 0.25 mm via diameter" | `.kicad_pro`; JLC capabilities page |
| Copper to edge | 0.5 mm (`min_copper_edge_clearance 0.5`); measured fill-to-edge at every tab 0.500 mm | `.kicad_pro`; panel report |
| Solder mask | `pad_to_mask_clearance 0.05`, min web 0; **26 webs under 0.10 mm as plotted** (RN201-RN203 4 each, U3 4, U4 4, U403 6) | board setup; `maskweb` check (P1-12 open) |
| Silkscreen | texts 1.0 mm / 0.15 mm (AIMD, CAL, RFVD SENSOR-D REV A, JLCJLCJLCJLC, BAT 2S); **lines: 958 at 0.12 mm and 2 at 0.10 mm**; setup minimum text 0.8 / 0.08 | pcbnew (P1-9 lines open) |
| Order-number marker | "JLCJLCJLCJLC" on B.Silkscreen at (131.75, 56.80) | pcbnew |
| Placements | 346 per board: top 177, bottom 169 | footprint attributes; JLC CPL from `tools/make_outputs.py` (cp2a outputs: 346 rows, 105 BOM lines) |
| Do not populate | C321, C911, R310, R314 (B) and R903 (F). kicad-cli 10.0.6 plots paste on DNP pads (10 flashes seen), so the tools strip it on their copy | pcbnew; paste Gerber test |
| Smallest parts / pitch | D1, D300 SOD962-2 (0201 class); U301 VQFN-29, 0.4 mm pitch | pcbnew |
| Bottom-terminated / EP parts (X-ray list) | U2 LFCSP-16, U13 TQFN-16, U301 VQFN-29, U302 VSON-8, U402 PowerPAD SO-8, U6 VQFN-HR-9, U7 MSOP-12-EP, U702 USON-6, U11 WSON-6, U701 DFN-4 | footprint names |
| J10 shell legs | 4 PTH slots, `zone_connect 2` (solid), **no F.Paste** | pcbnew (pin-in-paste, P1-12 open) |
| EMC bond pads | TP901 (162.30, 109.39), TP902 (122.96, 71.68), TP903 (159.74, 77.09): 3 x 3 mm GND, mask open, no paste | pcbnew |
| CAL_IN (RF_50R class) | 8.08 mm on F.Cu, 0.15 and 0.16 mm wide | tracks + `.kicad_pro` netclass patterns |
| Parts near the edges | J10 courtyard 0.00 mm (on the notch floor), J3 0.30, U403 0.47, Q302 0.58, J1/J300 0.68, TP16 0.72, R402 0.77, R322 0.78, SW1-SW5 1.10 mm | courtyard-to-outline scan |
| Overhang | **None.** No courtyard or pad leaves the outline. 3D models (STEP B-rep vertices, KiCad transform) all stay inside; the nearest are J10 at 0.50 mm and J3 at 0.85 mm. Only J3's F.Fab card outline reaches past the edge (to x 113.41); that is the inserted card, not the socket | `make_panel.py` check; model scan |

**Correction to the brief:** J2, J11 and J4 do not overhang or sit near the outline on this board. Their courtyards are 6.45 mm (J2, E edge), 7.95 mm (J11, S edge) and 13.4 mm (J4) from the edges. The earlier "overhang" figures came from all STEP points, including axis-placement and control points; the B-rep vertices stay inside.

---

## 3. Panel (`make_panel.py`)

### 3.1 Geometry (2 x 1)

| Item | Value |
|---|---|
| Size | 120.000 x 90.000 mm on the centre line; the Gerber job reports 120.05 x 90.05. Both sides meet JLC's 70 mm minimum |
| Boards | Copy 1 at its own coordinates. Copy 2 is rotated 180 deg and moved +54.000 mm. The centre gap therefore pairs E edge with E edge, every board has the same tabs, and a panel loaded 180 deg wrong still puts every part on matching pads |
| Gaps | 2.0 mm, routed |
| Rails | 5.0 mm on the two 90 mm sides (x 108.5036-113.5036 and 223.5036-228.5036). No top or bottom bar: the conveyor needs only the two rails, and the S edge has no usable tab spot (SW1-SW5 sit 1.10 mm from it, J6 0.40 mm, and the H3/H4 mounting holes fill the corners), so a bottom bar could not be attached |
| Outline | Real board primitives (R3 arcs and the notch) cut only at tab spans. 64 Edge.Cuts items, no open endpoints. KiCad builds 1 outline with 3 closed slots, 10,161 mm2 |
| Tabs | 6 tabs, 5.0 mm wide. Rail L: board y 64.50 and 78.50 (copy 1 W edge). Centre: y 90.74 and 104.74 (E edges of both copies). Rail R: panel y 116.99 and 130.99 (copy 2 W edge = board y 78.50 and 64.50) |
| Mouse bites | 8 rows of 5 x 0.60 mm NPTH at 0.95 mm pitch (0.35 mm web, 0.30 mm end webs), centres 0.10 mm outside the edge (0.20 mm inside the board), 40 holes. Board edges only; the rail side keeps the tab |
| Tooling holes | 4 x 2.0 mm NPTH at (111.004, 57.743), (111.004, 137.743), (226.004, 57.743), (226.004, 132.743). The bottom-right one is offset 5 mm |
| Fiducials | Fiducial_1mm_Mask2mm on F **and** B at (112.354, 72.743), (112.354, 122.743), (224.654, 82.743): 3.85 mm from the outer rail edge, an asymmetric set |
| Holes | 2122 on 120 x 90 mm = 196,481 /m2 (over JLC's 150,000 threshold, as is the single board) |

### 3.2 Tab clearances (distance from the perforation line; hard limits: courtyard >= 3.0 mm, copper >= 1.0 mm, fill to bite hole >= 0.2 mm)

| Tab (board-local) | Nearest component courtyard | Nearest MLCC | Copper | Fill to bite hole |
|---|---|---|---|---|
| W 64.50 | 6.38 U11 | 9.06 C71 | 3.27 (GND via) | 0.30 |
| W 78.50 | 6.32 C65 | 6.32 C65 | 3.79 (GND via) | 0.30 |
| E 90.74 | 4.33 R17 (C37 4.46) | 4.46 C37 | 3.43 (In3 TP_RST) | 0.30 |
| E 104.74 | 4.43 C39 (L1 4.68) | 4.43 C39 | 3.43 (In3 TP_RST) | 0.30 |

- Every tab sits on a straight edge with at least 6.26 mm to the edge's end.
- No connector is within 5 mm of a tab. J8 was 4.25 mm from an E tab at 105.74, so the E pair moved to 90.74/104.74.
- No tab is on the notch, the bottom edge, or E-edge y 111.5-139.7.
- C39 (22 uF 0805, its long axis perpendicular to the edge) and C37 are 4.4-4.5 mm from the centre tabs. That passes the 3 mm limit but lies inside JLC's 3-5 mm band, so **cut the tabs, never snap them**.
- To re-pick tabs on a changed board, `make_panel.py BOARD OUT --suggest` lists every legal centre per edge.

### 3.3 Verification (test run `work/panel`, input sha256 unchanged before and after)

- **DRC** (kicad-cli 10.0.6 with the project rules, refilled board vs panel): **0 new errors and 0 new warnings from the panel features.**
  - Every board warning appears exactly twice: 38 lib_footprint_issues, 80 via_dangling, 16 track_dangling, 16 track_segment_length, 8 track_angle, 14 silk_overlap, 10 silk_over_copper.
  - The board's own 2 skew_sdmmc errors and 12 length warnings remain.
  - Unconnected: 390 = 2 x 47 (the board's own) + 296 (one edge per net, because the copies share net names). This exact count proves no copy gained or lost a connection.
  - The net-length and skew results differ only because a shared net's length sums both copies.
- **Panel DRU copy.** The panel's DRU copy adds one rule: hole_to_hole >= 0.3 mm between mouse-bite holes, per JLC's mouse-bite spacing. The board rule `fab_pad_hole_to_hole` is 0.45 mm.
- **References.** References stay unchanged in the panel file. Renaming them made the DRU's reference-keyed rules (H1-H4, U301, U2 ...) report 400 false errors.
- **CPL cross-check.** The panel CPL (692 rows) matches the panel's own kicad-cli position file in position, side and rotation: 0 mismatches. Each copy-2 rotation is copy 1 + 180 deg on both sides, so the JLC rotation corrections from `tools/jlc_rotations.csv` carry over unchanged.
- **Negative test.** Tabs at W 100 and 120 and E 124 were rejected:
  - R48 at 2.82 mm;
  - the notch is not a straight edge, and J10 sits at 2.50 mm;
  - Q302 at 0.58 mm, with its pad at 0.83 mm;
  - a fiducial was 0.18 mm from a tab;
  - the outline left open was reported. Exit 3.
- **Renders** (looked at):
  - `work/panel/RFVD_SENSOR_BOARD_panel_3D_top.png` and `_3D_bottom.png`;
  - `RFVD_SENSOR_BOARD_panel_2D.png` (outline, NPTH, fiducials, courtyards F red / B blue, tab keep-outs orange).
  - Nothing crosses a gap.
  - J10/J3 face the rail across a 4.5 mm channel (2.5 mm notch + 2.0 mm gap).

---

## 4. JLC order form: PCB

| Field | Set to | Source / reason |
|---|---|---|
| Layers | 6 | board |
| Dimensions | the size in the Gerber job (2 x 1: 120.05 x 90.05; 1-up: 72.05 x 90.05) | `.gbrjob` |
| Delivery format | Panel by Customer; 2 x 1 (or 1 x 1) | section 1 |
| Different designs | 1 | one design, copied |
| PCB qty | 5 (panels) | D27, section 1.3 |
| Thickness | 1.6 mm | JLC06161H-3313; board file 1.5584 mm |
| Specify stackup | Yes, JLC06161H-3313 | board stackup = 3313/0.55/2116/0.55/3313 |
| Impedance control | **lead decision.** The old spec (2026-09-30) chose "No requirement"; CAL_IN is now 8.08 mm long | section 2 |
| Solder mask / silkscreen | Green / white | green holds a 0.10 mm dam ("Min. Soldermask Bridge 0.10 mm" for 1 oz green) |
| Surface finish | ENIG | board setup and job file |
| Outer / inner copper | 1 oz / 0.5 oz | stackup copper 0.035 / 0.0152 mm |
| Via covering | Epoxy Filled & Capped | JLC capabilities: "This process is the default for 6-layer and above multilayer boards."; via-covering page: "For our 6-layer and above multi-layer boards, resin filling is now available for free" |
| Min via hole / diameter | 0.2 / 0.45 mm | 918 vias at 0.45/0.20 |
| Outline tolerance | +/-0.2 mm | JLC "Routed: ±0.2 mm (regular precision)" |
| Mark on PCB | "Order Number (Specify Position)" uses the board's JLCJLCJLCJLC text; or "Remove Mark" | lead decision; the option wording comes from search results, not a verbatim page |
| Confirm production file | Yes | check the via-fill map, stackup, mask and tabs before production |
| Electrical test | Flying probe, fully tested | |

## 5. JLC order form: PCBA

| Field | Set to | Source / reason |
|---|---|---|
| PCBA type | Standard | 0201 parts (D1, D300); JLC: Economic minimum package "0402" |
| Assembly side | Both | top 177, bottom 169 per board |
| PCBA qty | per D27 (counted in panels) | section 1.3 |
| Edge rails / fiducials | Added by customer | panel rails |
| Tooling holes | Added by customer | 4 x 2.0 mm |
| BOM/CPL mode | "Complete File, just proceed with my own files" | section 1.2 |
| Files | `*_JLC_BOM.csv` and `*_JLC_CPL.csv` from `make_panel.py` (2 x 1), or the single-board files from `tools/make_outputs.py` (1-up) | |
| Confirm parts placement | Yes | P1-11: engineers fix rotation and polarity "based on the silkscreen markings" (PCBA FAQ part 2) |

## 6. Order remarks (paste-ready; fill the bracketed parts)

**PCB remark**
> Stackup JLC06161H-3313 exactly (6 layers; In1, In2, In4 solid GND planes; In3 signal), no substitution. ENIG. Epoxy-fill and cap (IPC-4761 type VII) ALL vias: per board 918 x 0.20 mm, 87 x 0.30 mm, 7 x 0.40 mm drill, and the 8 x 0.30 mm thermal holes in the U402 pad. Do not fill holes of 0.6 mm and larger (J10 slots, J11 1.0 mm, H5/H6 3.8 mm). Customer panel [2 x 1, 120 x 90 mm | 1 x 1, 72 x 90 mm] with mouse bites: no V-cut, do not add, move or remove tabs, rails, fiducials or tooling holes. The 3 x 3 mm pads TP901, TP902, TP903 are intentionally mask-open GND: no mask, no paste. [Order number at the JLCJLCJLCJLC text | Remove mark]. Please send the CAM files with the stackup and via-fill map for approval.

**PCBA remark**
> Standard PCBA, both sides. Reflow TOP first, BOTTOM last. Use our paste layers 1:1 (paste is already removed from the do-not-fit pads). Do not place: C321, C911, R310, R314, R903 [on every board]. J10: [pin-in-paste on its 4 shell legs, once the footprint carries the paste | hand-solder the 4 shell legs]. X-ray U2, U13, U301, U302, U402, U6, U7, U702, U11, U701: exposed-pad voids 25 % or less, no bridges. Check pin 1 and polarity of every U, Q, D, J, Y1 and C63 in the placement preview on both sides. Keep the rails; ESD packaging.

---

## 7. EMC requirements that depend on fabrication

- **Stackup.** In1, In2 and In4 are solid GND, and F/B sit 0.0994 mm (3313) above In1/In4. Ordering "Specify stackup = JLC06161H-3313" fixes those distances. A different prepreg moves the return path and the RF_50R width (CAL_IN 0.15 mm).
- **Via-in-pad and POFV.**
  - Return and decoupling vias sit in pads (board: 918 x 0.20/0.45).
  - Filling and capping keeps solder out of them, so the short paths survive assembly.
  - JLC fills 6+ layer boards by default and limits fill to holes of 0.5 mm or less; our largest via drill is 0.40 mm.
- **ENIG.** ENIG is flat for 0.4 mm-pitch U301, the 0201-class D1/D300 and the exposed pads.
- **Mask.** Mask expansion 0 (1:1) gives a real dam between the RN201-RN203 LCD bus arrays and the U3/U4 precision op-amp pins (P1-12).
- **Bond pads.** TP901-TP903 stay mask-open GND copper, with no paste.
- **Depaneling.** Cut the tabs. The decoupling MLCCs C37 and C39 are 4.4-4.5 mm from the centre tabs.
- **Edge rules.** The board keeps copper 0.5 mm from the edges. The DRC with the 10 `#SIGNOFF` rules switched on (including BUCK_SYNC >= 5 mm from the edge) adds no errors beyond the routing ones (`work/fab_board/reports/drc_signoff.json`).

## 8. Open items before ordering

| # | Item | Evidence | Owner / plan |
|---|---|---|---|
| O1 | Routing not finished: 47 unconnected and 2 `skew_sdmmc` errors (SD_CLK, SD_D1) | refilled DRC | layout (checkpoint 4) |
| O2 | The saved zone fill in base_cp2a is stale: 139 errors as saved vs 49 after refill | `drc_saved` vs `drc_refilled` | refill and save before release. Both tools refill on their copies |
| O3 | Mask expansion 0.05 mm: 26 webs under 0.10 mm as plotted | `maskweb` check | P1-12 |
| O4 | J10 shell legs have no paste (pin-in-paste missing) | pcbnew | P1-12, or order hand soldering |
| O5 | `(filling no) (capping no)`; dielectric 3 loss tangent 0 | board setup | P1-13 (the order form still carries POFV) |
| O6 | 958 silk lines at 0.12 mm and 2 at 0.10 mm; JLC minimum is 0.15 mm | pcbnew | P1-9 |
| O7 | **New:** a via (0.45/0.20, Net-(U8-PC14), x 142.048-142.498, y 98.591-99.041) on Y2 pad 2. It overlaps the pad by 0.15 mm and fills 0.30 mm of the 0.60 mm gap under the crystal, 0.30 mm from pad 1 (PC15). The ported S04 check now covers vias and pads | `make_fab_outputs.py` S04 | layout: move it fully into pad 2 or out of the gap |
| O8 | Holes per m2 over 150,000 on every variant (JLC extra cost) | checks | accept or quote |
| O9 | D27: 2 x 1 or 1-up; is PCBA quantity counted per panel? | section 1.3 | lead |
| O10 | Tooling-hole size: 2.0 mm (SMT process-edge page) vs 1.152 mm (tooling-hole page) | section 1.2 | JLC adapts by its T&C; optional remark |
| O11 | Impedance control yes or no; order-number mark | sections 4 and 6 | lead |
| O12 | CPL rotations: 33 rows corrected from the community table. U2, U301, U7, U13, U302, U6, U702, U11, U402, U701, J2, J3, J4, J11, Y1 have no table entry | cp2a `RFVD_JLCPCB_CPL_rotation_check.csv` | P1-11; check in the placement preview |

**Status at checkpoint 5 (2026-10-04, board `f9fb559366`, checked on the board):**
- **O1** open: 42 links for hand routing, 0 blocked (`docs/ROUTING_FINISH_GUIDE.md` §0). The `skew_sdmmc` errors are gone, and DRC is 0 errors.
- **O2:** `tools/make_outputs.py` runs DRC with `--refill-zones`. Refill and save once more after the hand routing.
- **O3** fixed at checkpoint 3 (mask expansion 0).
- **O4:** the board side was done at checkpoint 2b; the library footprint is `docs/LEAD_GUI_STEPS.md` row 4.
- **O5:** `docs/LEAD_GUI_STEPS.md` rows 1-2 (GUI-only setup fields).
- **O6** still open, cosmetic: 859 silk lines at 0.12 mm and 2 at 0.10 mm (library footprint outlines); every visible text is 1.0 / 0.15 mm. JLC prints them thin or drops them. They were not widened, because that would add silk-over-copper warnings.
- **O7** fixed at checkpoint 4a: no via lies within 0.9 mm of Y2.
- **O8-O12** unchanged (ordering decisions; D27 = the 1-up 72 x 90 mm frame).

## 9. Fab notes
The block is `fab_notes.txt`. `make_fab_outputs.py` puts it on User.Comments in a copy and writes `reports/<name>_fab_notes.pdf` for the record. JLC reads the order remarks, not this drawing.

## 10. Output recipe and test runs

```
PY="C:/Program Files/KiCad/10.0/bin/python.exe"
# 1. single-board BOM/CPL (rotation corrections) with the handoff tool, on a copy:      tools/make_outputs.py <copy>
# 2. panel + panel CPL/BOM + DRC classification + renders:
"$PY" make_panel.py <board.kicad_pcb> <OUT_PANEL> --cpl <copy>/outputs/RFVD_JLCPCB_CPL.csv --bom <copy>/outputs/RFVD_JLCPCB_BOM.csv --drc --render
#    1-up frame for D27:  ... --cols 1 --min-size 72 --name RFVD_SENSOR_BOARD_frame72
#    re-pick tabs:        "$PY" make_panel.py <board> <OUT> --suggest
# 3. Gerbers, drill, fab notes, checks, from the panel (or the board):
"$PY" make_fab_outputs.py <OUT_PANEL>/RFVD_SENSOR_BOARD_panel.kicad_pcb <NEW_OUT> --cpl <OUT_PANEL>/..._JLC_CPL.csv --bom <OUT_PANEL>/..._JLC_BOM.csv
```

**What `make_fab_outputs.py` does**
- Gerber X2 (13 layers, Protel extensions, mask subtracted from silk, 6-digit precision) plus the job file.
- Excellon PTH and NPTH files (absolute, mm, decimal, oval holes "alternate", following JLC's KiCad guide).
- Drill map PDF and drill report in `reports/`.
- An upload zip.
- IPC-D-356 only for a single board: on a multi-board panel the shared net names would join the copies.
- DNP paste stripped on the copy.
- DRC as saved, refilled with schematic parity, and with the sign-off rules (board).
- The checker.

**Test results** (all on copies; the source hash is unchanged):
- `work/fab_panel` (2 x 1 panel): **0 FAIL, 8 WARN, 22 PASS.**
  - The 8 warnings: O3 (twice: expansion and webs), O4, O5 (twice: via flags and loss tangent), O6, O7 and O8.
  - Files: `jlc/RFVD_SENSOR_BOARD_panel_JLC_gerbers.zip`; `jlc/gerbers/` holding 13 `.g*` Gerbers (`-F_Cu.gtl`, `-In1_Cu.g1` ... `-In4_Cu.g4`, `-B_Cu.gbl`, `-F/B_Paste.gtp/gbp`, `-F/B_Silkscreen.gto/gbo`, `-F/B_Mask.gts/gbs`, `-Edge_Cuts.gm1`), `-PTH.drl`, `-NPTH.drl` and `-job.gbrjob`; `jlc/*_JLC_BOM.csv`, `jlc/*_JLC_CPL.csv`; `reports/` with the drill maps, `drill_report.txt`, `*_fab_notes.pdf`, `drc_saved.json` and `check_fab_outputs.txt/.json`.
  - Drill hits: PTH 0.2 = 1836, 0.3 = 190, 0.4 = 14, 0.6 = 8, 1.0 = 4, 3.8 = 4 (exactly 2 x the board). NPTH 0.60 = 40 (bites), 2.00 = 4 (tooling).
- `work/fab_board` (single board): **2 FAIL (O1), 10 WARN, 19 PASS.** The two extra warnings are O2 and the 52 x 90 mm size, which is below 70 mm without a panel.
  - The job file shows 6 layers, ENIG and the 3313 dielectrics.
  - BOM = CPL = 346 placed footprints.
- `work/fab_1up72` (72 mm frame): **0 FAIL, 8 WARN, 22 PASS** (the same warnings). The job file size is 72.05 x 90.05; the single-board CPL/BOM are reused unchanged and match the frame's footprints 346/346.

## 11. Stale facts corrected from the old spec and script

| Old (v6, 2026-09-30/10-01) | Now (from this board) |
|---|---|
| Board 47.0 x 90.0 mm, rounded rectangle | 52.00 x 90.00 mm (52.05 x 90.05 incl. line) with a 2.5 x 29.7 mm W notch |
| Panel 70.0 x 104.0 mm, 1 x 1 frame, 9.5 mm W/E rails, 5.0 mm N/S bars | 2 x 1, 120 x 90 mm, 5 mm W/E rails, no bars; D27 alternative 1-up 72 x 90 mm |
| 9 tabs: W 17.55/27.60/39.10, E 22.80/33.30/48.75, N 37.70, S 17.05/34.45 mm | 6 tabs: W board y 64.5/78.5, E 90.74/104.74. The S edge has no usable spot |
| Bites 6 x 0.60 mm at 0.85 mm pitch (0.25 mm web, below JLC's 0.3 mm minimum) | 5 x 0.60 mm at 0.95 mm pitch (0.35 mm web), one third inside the board |
| `make_panel.py` deleted Edge.Cuts and redrew a bbox rounded rectangle with the mean arc radius (the notch was lost); exit 3 on vias at the S tabs | the real outline primitives are kept, cut only at tabs; checks for courtyard, copper, fill, outline and DRC |
| Stackup table and fab notes: JLC04161H-3313, core 1.265 mm, 4 layers, "1.564 mm as built" | JLC06161H-3313, 6 layers, 1.5584 mm stackup sum |
| POFV counts "569 / 6" (old spec); the critique's "938 x 0.20, 86 x 0.30, 7 x 0.40" | 918 x 0.20, 87 x 0.30, 7 x 0.40 = 1012 vias, plus 8 x 0.30 U402 pad holes |
| Hole-density area 47 x 90 | 52 x 90 (board) or the panel area |
| DNP: R406 R314 R310 C321 R903 C204 C908 C911; "R321 IS placed" | DNP: C321, C911, R310, R314, R903. R406, C204 and C908 are gone; R321 is fitted (5.23k) |
| 187 F / 184 B placements | 177 F / 169 B = 346 |
| Mask: expansion 0.025 mm plus local 0 on 6 parts | global 0 (critique MFG-05 / P1-12); the board is still 0.05 |
| Silk: "994 thin items"; texts 0.8 mm | 960 thin lines; texts now 1.0/0.15 |
| C27 and C68 polymer caps, swap and cost tables, UP-01 ring SH900 | C27, C68 and SH900 are not on the board (C63 is the only polymer cap). The cost tables are dropped as stale |
| TP902 (122.5, 72.0), TP903 (152.0, 75.0) | TP902 (122.96, 71.68), TP903 (159.74, 77.09), TP901 (162.30, 109.39) |
| IPC-D-356 always in the zip | omitted for a multi-board panel (shared net names) |
| "kicad-cli has no option to drop DNP paste" | still true on 10.0.6: 10 DNP paste flashes without the strip |
| Critique: J10, J2, J11, J4 overhang | not on this board (section 2) |

Not ported from the .sh, on purpose:
- the swap, consignment and LCSC tables (sourcing work moved to `04_parts`);
- the per-LCSC CPL rotation fit (P1-11: `tools/make_outputs.py` + `jlc_rotations.csv`);
- the ENIG-area estimate and the UP-01/UP-04/FAB-14 layout warnings (those features are not on this board).

## 12. Sources
JLC pages as in section 1.2, plus:
- jlcpcb.com/help/article/pcb-via-covering: "Plugged and epoxy-filled vias holes should not be larger than 0.5 mm as larger holes may be incompletely filled."
- jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra: "For orders with over 150,000 drill holes per square meter, an extra cost will be applied."
- jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-8: "Use Protel filename extensions", "Subtract soldermask from silkscreen", "Use alternate drill mode for 'Oval Holes Drill Mode'", "Absolute for 'Drill Origin'", "Decimal format for 'Zeros Format'".
- jlcpcb.com/help/article/pcb-assembly-faqs-part-2: "our engineers will review and fix the rotation and polarity of the components based on the silkscreen markings before assembly."

Board, project, DRC and tool numbers come from the files and reports named in each table.
