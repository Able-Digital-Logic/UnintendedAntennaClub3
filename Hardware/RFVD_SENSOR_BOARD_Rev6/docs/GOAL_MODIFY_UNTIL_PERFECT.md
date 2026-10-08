GOAL: RFVD SENSOR-D "modify until perfect" (set 2026-10-03; internal file, never put in a release zip)

> Designators in this dated record predate ECO-003 (2026-10-07). Look up the current ones in [`REFERENCE_MAP_ECO-003.md`](REFERENCE_MAP_ECO-003.md).

Keep working until every item in DONE WHEN (section 7) is true and has been verified from the source files. Iterate find -> fix -> verify -> repeat. Do not stop at a plan.

## 1. Mission

- Critique the whole design: everything done, changed or modified, plus anything earlier that is weird or iffy.
- Fix it until the board is perfect, or at least in a state the lead can hand-finish easily.
- Make sure everything works and that the schematics have no mistakes.
- Simplify the schematic wherever possible ("if 1 IC replaces 10 components that is a big win"), but never at EMC's expense.
- Make every component's placement follow its datasheet's recommended layout, comply with EMC, and minimise track expenditure.
- "This is the foundation, now we improve it."
- EMC and noise reduction is a hard requirement. It outranks cost and convenience.

## 2. Master board and inputs

- **Master:** `03_hardware/RFVD_SENSOR_BOARD_LAYOUT_HANDOFF_2026-10-02/RFVD_SENSOR_BOARD.kicad_pcb`.
  - m17, sha256 starting `f536efcf8e`. This is the lead's save with the corrected stackup and merged tracks.
  - Check this hash before every write. If it changed, re-read and diff first (another session or the lead may have edited it).
- **m17 baseline:**
  - 583/633 connections routed, 50 unrouted;
  - plain DRC 3 errors (C106/C24 courtyard overlap, 2x skew_sdmmc), 116 warnings;
  - sign-off DRC PASS;
  - 2528 segments, 1031 vias;
  - footprint locks 192/409.
- **Stackup (lead-fixed, do not change):** JLC06161H-3313, 6 layers.
  - In1, In2 and In4 are solid GND. In3 is the buried signal layer, referenced to In2 0.109 mm above it.
  - All vias are POFV (resin-filled and capped), so via-in-pad is allowed everywhere.
- **Schematic:** root + 11 sheets, identical in the handoff folder and in `RFVD_SENSOR_BOARD_GITHUB`. The Trigger sheet is unreferenced.
- **Inputs to process first:**
  - critique workflow `wf_4fba49dd-dc3`: 19 lenses, verified findings, P0/P1/P2 fix plan, lead decisions;
  - placement-revision workflow `wf_5310b9f1-82d`: 11 modules, MOVE items, adversarial challenge per module, track-expenditure analysis, merged plan.
  - Both ran on m16 (`31e0108f2f`). Re-check every item against m17 before applying it.
- **Evidence pack:** session scratch `critique/` (BRIEF.md, pack/: components, nets, board, parity, ERC, DRC, renders, BOM/CPL).

## 3. Work phases (in order; loop until done)

### A. Merge the plans

- Read both workflow results. Merge them into ONE ordered execution plan:
  - schematic fixes;
  - simplifications;
  - placement batches by module;
  - rule changes;
  - routing;
  - docs and firmware notes.
- Drop anything refuted or infeasible on m17.
- Show the merged plan to the lead.
- Ask (AskUserQuestion) only for genuine lead decisions: mechanical changes, part swaps that change the BOM, architecture. Check feasibility BEFORE offering any option.

### B. Schematic correctness and simplification

For every IC, check the following against the manufacturer datasheet (quote section, page or figure):
- pin functions;
- decoupling values and placement;
- strap/setting resistors;
- pull-ups;
- ESD;
- reference and bias networks;
- enable and sequencing;
- the power-tree current budget.

Schematic hygiene:
- Fix the real ERC issues: the 4 zero-length wire stubs and the 19 footprint_link warnings. Investigate the "RFVD_MVP_Footprints not in configuration" warning.
- Keep the U8 VCAP pin_to_pin only if it is documented as benign.

Simplify where one part replaces many (arrays, integrated parts) and EMC is equal or better. Every new part must be in stock at LCSC/JLC with an MPN and an LCSC number.

After any schematic change:
- ERC;
- kicad-cli netlist diff;
- schematic-to-board parity, 0 mismatches;
- update the board from the schematic through Konnect.

### C. Placement revision (per module)

Modules: RF, analog, ext-ADC, MCU, buck, charger, battery, SD, display, expansion, misc.

**Datasheet layout first.** Follow each IC's own layout guide, for example BQ25798 per TI SLUSDV2C section 8.4. Keep the switching loop, bootstrap, crystal, RF and reference parts tight.

**Sensitivity scoring.**
- Critical parts stay close to their IC.
- Free parts may move out to open routing room: pull-ups, setting resistors, bulk caps (which can connect through vias).

**Module locality.**
- Each module is an IC plus its passives, with only a few signals leaving it.
- No foreign tracks under any module.
- Rotate parts so GND pads don't create pour islands; the aim is a continuous, smooth GND pour.

**Back-side passives.** No different-net back-side part stacked under an IC, FPC or SD pin unless its pad has its own via-in-pad escape.

**Via-in-pad first, tracks second.** Align pads so that tracks run flush, pad side to pad side.

**Respect the mechanical envelope:**
- K4_TFT_LOOP: no F parts in the display FPC fold loop.
- K8_SHIELD_BAY: B parts no taller than 0.6 mm.
- K9_BATT_WINDOW: B parts no taller than 0.55 mm over y 59-116.
- K14_CTP_FOLD: F parts no taller than 1.2 mm.
- K11 (GND-only), K12 and K13 (footprint bans).
- Mounting holes H3/H5/H6; port notch at y 104.6-133.3.

**Gates for every move:**
- `tools/placeaudit.py`: same-net clustering, connection length;
- `query.py free --copper`;
- `feasible.py`;
- `metrics.py`: no net loses connectivity;
- total ratsnest/track length must not get worse.

**Known items:**
- R19 -> (149.00, 113.90) rot 0, B. This closes REGN; CHG_LED_A then re-routes east (B > In3 > F).
- R60 -> (121.30, 95.10) rot 180, F, plus lifting EXP_INT0_N_MCU's F run. This opens RN201.5-8.
- C908 (DNP): removal opens RN202.8.
- The RN201/RN203 regroup; the RN203 escapes must be re-laid as one group.
- R53/R54 I2C pull-up relocation.
- C106/C24 courtyard overlap.
- C902 flip (rip up the +5V_A stub first).
- U403 block to F.Cu.
- The V1/V2 charger extras (V1 delete + C319; V2 move + C305).
- The U701 keep-out zone stranded at (141.35-142.85, 116.89-118.39): re-centre it on U701 if it is still there.
- Blockers:
  - VBAT_RTC around the HSE cell (K10F/K10B);
  - CHG_INT_N at U301 pin 21;
  - USB_DP to U8.71 (U8 SW corner);
  - J4 via sites D2/D4;
  - the saturated lower-middle band (y 104-122). It needs planned re-organisation, not single squeezes.
- Re-lock all footprints once placement is final.

### D. Rules

- Decide and apply: ground and digital-power clearance 0.10 (class-aware audit: blocked pairs 46 -> 26).
- Keep the JLC no-surcharge minimums:
  - 0.10-0.12 mm digital track;
  - 0.45/0.20 signal vias;
  - power vias 0.6/0.3 and 0.8/0.4;
  - `jlc_smd_pad_to_pad_floor` 0.15.
- Add pre-defined track and via sizes to the project (0.45/0.20 included), so interactive routing uses the right sizes.
- Edit .kicad_dru only under the scoped exception: sentinel A/B DRC proves the file parses, atomic write, hash check, Board Setup closed.

### E. Routing (hand-layout rules; NO auto-routers)

- Every copper edit is an explicit coordinate list run through `tools/place/pen.py`, checked with `--check`.
- Geometry: octilinear only (0/45/90-degree segments), 45-degree bends, no right-angle corners, no zig-zags or polyline clutter. Arcs or smooth bends on noise- and reflection-sensitive lines.
- Minimum track length per connection.
- Return/stitching vias at every layer change, and abundant stitching where needed.
- Close the 50 unrouted links where a legal path exists (plan/guide: `docs/ROUTING_FINISH_GUIDE.md`).
- Fix the 2x skew_sdmmc errors (needs SD_D1 routed).
- Every remaining link must have a verified legal path (`feasible.py`) and a guide entry with exact coordinates.

### F. Firmware and docs notes

- EXP_SYNC: move the firmware clock off 2.000 MHz, whose harmonics land near 64/128 MHz.
- Record the BUCK_SYNC = ADC fs (833.33 kS/s) relationship.
- Write down every lead decision.

## 4. Verification for every batch (no batch lands without all of these)

1. Hash-check the master.
2. Apply on a scratch copy, with the .kicad_pro and .kicad_dru copied next to it.
3. ERC (schematic batches).
4. Netlist diff and parity: 0 mismatches.
5. `metrics.py`: no net worse, pads-with-copper never drops.
6. `drcsum.py`, plain + sign-off: no new errors, sign-off still PASS; report the warnings delta.
7. `placeaudit.py`.
8. Geometry audit: no new track_angle or 90-degree corners.
9. Render the changed area and look at it.
10. Back up the master to `backups/`.
11. Transfer to the master via Konnect (closed-file mode).
12. Re-verify the master: hash, DRC and metrics identical to the scratch result.
13. Update `LAYOUT_STATUS.md` and `CHANGES_FROM_PROJECT.md`.
14. Regenerate the outputs (`tools/make_outputs.py`).
15. Make the CHECKPOINT RELEASE ZIP (section 5).
16. Give the lead a short report with the numbers.

## 5. Release zip at EVERY checkpoint (checkpoint = a verified batch landed on the master)

**Include:**
- KiCad project: .kicad_pro, .kicad_pcb, .kicad_dru, root + the 11 referenced sheets (not Trigger), sym-lib-table, fp-lib-table, libraries/ (symbols, footprints, 3dmodels);
- fresh outputs: schematic PDF, layer PDF, BOM, JLC BOM + CPL, DRC report, 3D renders;
- README with honest status numbers (routed X/633, DRC errors/warnings, sign-off), BOARD_OVERVIEW.md, and a KiCad .gitignore.

**Exclude:** tools/, backups/, scratch, .kicad_prl, the old renders history, internal logs and goal files, lock files and caches.

**Before the first zip:** confirm that `models/` (2.7 MB) is unreferenced. Only `${KIPRJMOD}/libraries/3dmodels` and the stock `${KICAD10_3DMODEL_DIR}` are used.

**Name:** `RFVD_SENSOR_BOARD_release_<date>_<checkpoint>.zip`, saved next to the handoff folder.

## 6. Hard constraints (always)

**KiCad edits**
- All KiCad changes go through Konnect MCP. Never text-edit .kicad_sch, .kicad_pcb, .kicad_pro, .kicad_sym, .kicad_mod or the lib tables.
- kipy (kicad-python) is allowed only for rule areas, deleting vias and moving vias: dry run first, one undo step, saved and verified.
- Never edit a board while KiCad has it open. Never drive the KiCad GUI with computer use.
- Work on scratch copies. Master writes happen only after verification.

**Tools**
- Tools live ONLY in the handoff `tools/` folder, self-tested (`tools/selftest.py`).
- Run them with KiCad's Python: `MSYS_NO_PATHCONV=1`, `PYTHONIOENCODING=utf-8`, one subprocess per board.
- No auto-routers (Freerouting, KRT, ripfix, placefit routing) for the layout goal.

**Evidence**
- Answer nets, classes, sizes and values only from the schematic, the kicad-cli netlist and the board, quoting the numbers. Never infer them.
- Datasheets come from the manufacturer or a distributor.
- Web queries carry no project or person names.

**Files and accounts**
- Never hard-delete; use the Recycle Bin.
- Don't commit or push without asking. Nothing goes to the cloud without approval.
- Never quote secrets. Never ask for auth codes or tokens.

**Working mode**
- Bypass mode: don't ask permission for routine engineering steps.
- Run independent work in parallel (workflows are allowed).
- Give progress updates.
- Update the requirements-ledger memory whenever the lead adds an instruction.

## 7. DONE WHEN (all must hold, each verified on the master)

1. **Critique closed.** Every critique finding of medium severity or higher is either fixed and verified, or recorded in `docs/` with an evidence-based reason or a lead decision. Low findings are fixed or listed.
2. **Schematic clean.**
   - ERC: 0 errors, and every remaining warning is documented as benign.
   - Schematic-to-board parity: 0 mismatches.
   - Every IC is checked against its datasheet, with references written down.
   - Accepted simplifications are applied.
   - BOM: every part has an MPN and an LCSC number and is in stock.
3. **Placement final.**
   - Every module follows its datasheet layout guide.
   - placeaudit passes.
   - No foreign tracks under modules, or each exception is documented.
   - The mechanical keep-outs are respected.
   - Total connection length is no worse than m17.
   - All footprints are re-locked.
4. **DRC clean.**
   - Plain DRC: 0 errors.
   - Sign-off DRC: PASS.
   - Warnings are reduced from 116, and each remaining one is explained.
   - track_angle: 0.
5. **Routing.**
   - Either 633/633 connections are routed (KiCad unconnected 0),
   - or every remaining link is shown by `feasible.py` to have a legal path, with exact coordinates in `ROUTING_FINISH_GUIDE.md`, and 0 links are blocked.
6. **Deliverables.**
   - Outputs are regenerated from the final master.
   - docs (README, LAYOUT_STATUS, BOARD_OVERVIEW, CHANGES_FROM_PROJECT, ROUTING_FINISH_GUIDE) match the final numbers.
   - The firmware notes (EXP_SYNC offset) are written.
   - A final release zip has been produced.
