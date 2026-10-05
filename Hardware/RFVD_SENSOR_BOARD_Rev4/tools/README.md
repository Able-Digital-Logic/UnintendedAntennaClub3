# RFVD layout tools (single toolset, cleaned 2026-10-02)

This folder is the **only** copy of the layout tools. One tool per job: when a job needs more, the existing tool
gets the option (no `_v2` copies). 64 obsolete or duplicate scripts went to the Windows Recycle Bin on
2026-10-02 (recoverable): DRU patch scripts 1-6, the KiCadRoutingTools wrapper, early pass pipelines, debug and
one-off scripts. The DRU history stays in `dru_versions/`.

**Check before use:** `selftest.py BOARD.kicad_pcb [--drc]` runs every active tool on a scratch copy and prints
PASS/FAIL. It covers compile, query, metrics, placeaudit, dsgap, the stretch dry run and prerip scope. Run it after any tool
edit.

## Rules for every tool
- **KiCad's Python.** `"C:/Program Files/KiCad/10.0/bin/python.exe"`. Under Git-Bash, set `MSYS_NO_PATHCONV=1` and `PYTHONIOENCODING=utf-8`.
- **Scratch copies only.** Every tool reads one board and writes another. `mr.PROTECTED` refuses writes into the project folder. Never run a tool on a board KiCad has open.
- **Sidecar files.** Copy `.kicad_pro` / `.kicad_dru` next to any work copy, or KiCad falls back to default net classes. The tools copy them for their own outputs.
- **One board per process.** Multi-board tools (placefit, merge, query diff) use child processes, because KiCad's Python breaks after a few loads.
- **Removed items stay referenced.** Keep removed items alive (`thisown = 0` + a graveyard list).
- **Acceptance gate for any board change.** `place/metrics.py OLD NEW` must show no worse net, then `drcsum.py NEW OUT OLD/drc.json` must show no new errors.

## Inspect (read-only)
| Tool | Job |
|---|---|
| `query.py part / net / near / diff / zones / edge / free` | Inspection, with one subcommand per question. Part data plus its datasheet rule; a net's copper; the nearest copper of a net to a point; the copper diff of two boards; rule areas; parts near the real (notched) edge; legal free spots for a part (courtyards, keep-outs, B-side height windows; with `--copper` also the class clearance of every pad to other-net copper, i.e. spots a hand move can use as-is). |
| `placeaudit.py BOARD [--png]` | **Connection-length placement audit.** It builds the ratsnest (MST per net) and flags long connections with the end that is cheapest to move. For each part it reports its connection demand, best spot and nearest legal free spot. Parts are classed FIXED / KEEP (`placeaudit_keep.json`, with reasons) / OVER budget / MOVE. It also lists routing detours. Output: CSV, summary and map. |
| `dsgap.py BOARD [--out docs/PLACEMENT_DATASHEET_CHECK.md]` | **Datasheet placement check on the board** (2026-10-04). For every part with a rule in `docs/sensitivity.json`, it measures the pad-edge gap to the nearest pin of its IC on a shared net. That follows pin swaps and multi-pin supplies; the stored `gap_mm` values came from old poses. It writes the per-IC table (layout rules with section and page, each part's gap, budget and verdict) and exits 1 if a part is over budget without a reason in `placeaudit_keep.json`. placeaudit's OVER class uses it. `--selftest`. |
| `place/metrics.py A B...` | The acceptance check: unconnected count, pads carrying copper, per-net island regressions. |
| `place/netisl.py`, `unconn.py`, `place/openregion.py`, `place/diagpairs.py` | Copper islands per net; missing connections; where they sit; whether an open connection is boxed in or blocked. |
| `place/u8box.py`, `place/icband.py` | Open IC pins and what blocks their escape; parts in an IC's escape bands. |
| `geomstat.py`, `trackq.py` | Track direction and geometry statistics; track economy (detours, bends). |
| `render.py`, `zoom.py [--layer L] [--net N,..] [--grid] [--free W,CLR] [--open CSV]`, `layer_images.py`, `unrouted_map.py` | Renders: the whole board; a close-up window (one layer with `--layer`, with that layer's pads); one image per copper layer; the map of missing connections. `--grid` adds a labelled mm grid for reading hand-route coordinates. `--free W,CLR` shades where a W mm track keeps CLR mm from all other copper on that layer (visual aid only). `--open outputs/RFVD_unrouted.csv` draws the missing links with net names (only the `--net` ones if given). |
| `feasible.py BOARD UNROUTED.csv OUT.json [--band] [--only N,..]` | **Routability check per missing link, geometry only, nothing routed** (2026-10-03). It builds free space per signal layer with the pairwise DRU clearances (mr.py model, courtyard exemptions included) and legal via space. Result per link: `DIRECT layer`, a route with its layer sequence and via count, or `BLOCKED`, plus the "reach" of each end (< 2 mm = boxed in). `--band` allows detours across the full width but not through the analog half. Each link is checked alone. Used for `docs/ROUTING_FINISH_GUIDE.md`. |
| `cutcap.py BOARD W CLR h:Y:X0:X1 \| v:X:Y0:Y1 ...` | Cut capacity: how many W mm tracks at CLR spacing cross a straight cut on F / In3 / B. It applies the lane / partition rules for a generic signal net and lists the free intervals (2026-10-03). |
| `drcsum.py BOARD OUTDIR [BASE.json]`, `drc_signoff.py` | Sign-off DRC with all rules, summarised per rule against a base report. |

## Placement
| Tool | Job |
|---|---|
| `place/prerip.py IN OUT REF,...` | Removes the tracks of parts about to move, then prunes the dangling remains back to the next junction (true geometric connectivity). `--prune-nets NET,...` only prunes. `--rip-at NET@x,y,r` removes a net's copper at one spot, to clear a local DRC problem before `ripfix` re-routes it. Caveat: a pad that a chain passes through gets cut; for parts that end up not moving, restore with `revert_nets.py`. |
| `place/placefit.py` | Routability-scored placement. Every legal pose in a window is checked against courtyards, keep-outs, copper and the B-side height windows (`--height-ok` exempts low parts). Each pose is scored by routing its connections with `mr.py`. It never commits a pose that does not route; the part keeps its original pose instead. |
| `place/unbox.py` | Automated placefit for boxed-in connection ends. It keeps only changes that improve the metrics. |
| `place/applyposes.py IN OUT POSES.json...` | Sets poses from placefit results or `{REF: {x, y, rot, side}}` move lists, flipping parts if the side changes. It refuses courtyard overlaps. |
| `place/stretch.py IN OUT [--left L --right R] [--notch-left Y0,Y1] [--carry REF,...] [--nudge REF:dx,dy]` | Widens the board. It moves the outline, extends planes, pours and board-wide rule areas, and can carry edge-bound groups with stretched connections. `--notch-left` keeps the old edge at the ports. `--nudge` moves a part by a small vector with stretched contacts, without ripping anything. Check the result with DRC: the inserts can hit neighbouring copper. |

## Routing and clean-up
| Tool | Job |
|---|---|
| `place/pen.py IN OUT EDITS.json` | **Hand-layout executor** (2026-10-03, no auto-routing). It applies an explicit edit list: part moves, `track` point lists (octilinear only), vias, and deletions of exact segments, vias or a net's copper in a box. Joints within 0.01 mm of existing same-net copper are snapped exactly. After writing, `pen.py --check OUT EDITS.json` runs automatically: every new track and via is measured against the mr.py rule model (class / DRU clearances, rule-area bans, holes, edge), and each shortfall is printed with measured vs required mm. |
| `mr.py` | Router and rule model, imported by everything. It encodes the DRU clearances and widths, the class spacings, the rule-area bans, octilinear A* and via-in-pad first. It loads `an/nets.json`. Since 2026-10-03 it also models `fab_pth_hole_clearance`: other nets stay 0.30 mm from plated pad holes. |
| `place/ripfix.py` | Priority rip-up and reroute. A fix is kept only if KiCad's unconnected count drops and no pad loses copper. |
| `place/intermod.py`, `place/modroute.py`, `place/fanout.py` | Inter-module routing; module-local routing; escapes for fine-pitch parts. |
| `place/merge.py BASE X Y OUT` | Merges copper from a parallel branch net by net, with the full rule check. It does not move parts; use applyposes first. |
| `place/revert_nets.py`, `place/corridor_rip.py` | Lossless revert of nets to a base; clearing a corridor for a priority bus. |
| `place/highway.py`, `place/highway2.py`, `place/slate.py`, `reroute.py` | Track clean-up experiments ("signal highways"); rerouting wasteful chains. |
| `place/widen.py`, `place/drcfix.py`, `place/straddle.py`, `place/chg_copper.py`, `place/pour_in3.py`, `pourlink.py` | Widen tracks in place; mechanical DRC fixes; a shared via-in-pad; the BQ25798 copper; the In3 power pour; joining power islands. |
| `thin.py`, `restitch.py`, `retvia.py`, `run_post.sh` | GND stitching field before and after routing; return vias for fast nets; the post-route pipeline. |
| `hide_silk_refs.py` | Hides the silkscreen reference designators (they stay on the fab layers). |
| `transfer_plan.py`, `transfer_exec.py`, `kipy_vias.py` | Transfer into the real project board through Konnect and the approved kicad-python scope. |

## Schematic-to-board sync, outputs and releases (2026-10-04)
| Tool | Job |
|---|---|
| `place/sync.py BOARD NETLIST.xml OUT [--place P.json] [--delete REFS] [--swap REFS] [--dry-run]` | **Update PCB from Schematic without the GUI.** Matches footprints to symbols by path, then reference. Adds new parts (pose from `--place`, library footprint, symbol path, fields, attributes, pad nets; silkscreen reference hidden). Syncs value, fields, DNP/BOM attributes and pad nets of existing parts. Swaps footprints in `--swap`; deletes board parts in `--delete`. Lists copper left on nets that no longer exist. Never touches copper. Board net spelling: `/` from a pin name becomes `{slash}` inside generated `Net-(...)` / `unconnected-(...)` names. |
| `make_outputs.py [PROJECT]` | Regenerates DRC report, positions, CPL, layer PDF, placement audit, renders, schematic PDF and BOMs. The JLC BOM comes from KiCad's own DNP flag, one designator per entry, and the CPL is cut to it. Fails if a fitted part has no LCSC number. **Run it in the project folder**: copies under the long session scratch path exceed Windows MAX_PATH, and KiCad then reports 19 false `lib_footprint_issues`. |
| `release_zip.py [PROJECT] --tag T [--signoff SO.json]` | Clean GitHub release zip for each checkpoint, with a generated README holding the measured status. |
| `place/pen.py` (new ops) | `movetext` / `deltext` / `addtext` for board texts; `fpattr` (exclude_pos / exclude_bom / dnp); `fpzone_from_lib`; `delseg` also cuts a span out of a merged collinear segment and skips slivers a merge already absorbed. |
| `place/pen.py` arcs (2026-10-04) | `track` takes an optional `"r"`: every interior corner of the octilinear point list is rounded by a tangent arc of that radius. The point list stays the octilinear construction line; only its two ends snap. An explicit `arc` op takes `start` / `mid` / `end`. `--check` measures the arcs as well as the straight runs. The DRU's track_angle rules skip arcs, so filleted corners pass. Use arcs on reflection- and noise-sensitive lines (track-geometry standard). Tested on a scratch board: R 0.500 mm, 45/45/90 degree sweeps, every joint exact. |
| `sch_notes.py PROJ [--grep RX] [--json OUT]` | Read-only list of the free text notes (text / text_box) of every sheet: uuid, position, size, justify. It is the input for Konnect note-fix packages (`batch_delete` by uuid, then `add_schematic_text` at the same place). `--selftest` included. |
| `place/pen.py` silk / fab ops (2026-10-04) | `addrect` (unfilled rectangle on any layer, e.g. the B.Silkscreen S/N box); `titleblock` (date / rev / title / company / comment1..9; the date feeds `${ISSUE_DATE}`); `addtext` takes `"justify": "left"\|"right"` for multi-line notes; `padpaste` adds the side's paste layer and a local paste margin to a footprint's plated through-hole pads (pin-in-paste, P1-12). |
| `necks.py BOARD [--max 1.0] [--csv OUT]` | P0-5 chain check (2026-10-04): joins consecutive power segments narrower than the class minimum (Power_Battery 0.5, Power_Digital 0.3, Power_Analog 0.25 mm) and lists chains over `--max`. The DRU `v11_neck_len_*` rules cap single segments at 1.0 mm. The same exclusions apply: REGN, the PACK_RAW Kelvin track in J2, VBAT_RTC, the U303 VBAT_PACK feed. Exit 1 if any chain is over. `--selftest`. |
| `make_panel.py BOARD OUT_DIR [--cols 1 --min-size 72] [--cpl --bom --drc --render] [--suggest]` | Customer panel for JLC Standard PCBA (2026-10-04, P1-10 / D27). JLC panelises only rectangles and round boards, so we supply the panel. It keeps the real outline (R3 corners, W notch); routed 2 mm gaps; rails on the 90 mm edges; mouse-bite tabs checked against courtyards (≥ 3 mm), copper (≥ 1 mm) and fill; fiducials on F and B; 2.0 mm tooling holes. Writes the panel CPL/BOM (REF_n, cross-checked against KiCad's own position export) and classifies panel DRC as inherited / shared-net / NEW. **D27: use the 1-up 72 × 90 mm frame (`--cols 1 --min-size 72`)**: JLC counts the 2-piece PCBA minimum per panel, and the plan is 2 populated boards. Reads the board only. |
| `make_fab_outputs.py` | Gerbers (6 copper, job file with the 3313 stackup), separate PTH/NPTH drill with map and report, a fab-notes PDF and a checker report (fab spec S01-S0x, incl. S04: copper between the Y2 pads). No IPC-D-356 for multi-board panels (shared net names would join the copies). |

## Typical move workflow (what was used on 2026-10-02)
1. Audit: `placeaudit.py BOARD --png`. Take the MOVE parts, and check the KEEP and FIXED reasons.
2. Prerip: `place/prerip.py BOARD R.kicad_pcb REF,...`.
3. Place: `place/placefit.py R.kicad_pcb OUT.kicad_pcb --part REF:window:rots --conn REF.PAD-NET|-VIA ...`.
4. Gate: `place/metrics.py BOARD OUT.kicad_pcb`, then `drcsum.py OUT.kicad_pcb drc_out BOARD_drc/drc.json`. Keep the result only if nothing got worse.

**DRC completeness (2026-10-04).** Every kicad-cli DRC call in these tools passes `--all-track-errors`. Without it KiCad reports only one error per track, and which one varies between runs: on checkpoint 3 the plain runs gave 33 clearance pairs ± 1, the complete set 60. Gate comparisons (`replay.py`) and the outputs DRC report are therefore complete and reproducible.
