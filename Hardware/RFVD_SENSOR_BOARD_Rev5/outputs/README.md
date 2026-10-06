# Outputs (regenerated 2026-10-02 night from this folder's project with `tools/make_outputs.py`)

| File | What it is | How it was made |
|---|---|---|
| `RFVD_BOM_grouped.csv` | BOM grouped by value + footprint + MPN + DNP: 140 lines, 371 references, 4 DNP. Includes manufacturer, MPN, LCSC, function, distributor, cost and sourcing status. | `kicad-cli sch export bom` |
| `RFVD_BOM_per_reference.csv` | One line per reference. | `kicad-cli sch export bom` |
| `RFVD_JLCPCB_BOM.csv` | JLCPCB assembly BOM (Comment, Designator, Footprint, LCSC Part #). 136 lines; DNP excluded; every line has an LCSC/JLC number. | from the grouped BOM |
| `RFVD_JLCPCB_CPL.csv` | JLCPCB pick-and-place (Designator, Mid X, Mid Y, Layer, Rotation), 405 placements (Q302 is now Bottom). **Check rotations in JLC's preview**: library-orientation offsets differ per package. | `kicad-cli pcb export pos` |
| `RFVD_positions_all.csv` | KiCad position file (mm, both sides). | `kicad-cli pcb export pos` |
| `RFVD_schematic.pdf` | Full schematic (root + 11 sheets). | `kicad-cli sch export pdf` |
| `RFVD_board_layers.pdf` | One page per layer: F/In1/In2/In3/In4/B copper, silkscreen and fab, with the outline. | `kicad-cli pcb export pdf --mode-multipage` |
| `RFVD_DRC_report.rpt` / `.json` | KiCad DRC with the project rules (zones refilled), regenerated 2026-10-03 for board m16: 3 errors, 153 warnings, 50 unconnected. | `kicad-cli pcb drc --severity-all` |
| `RFVD_placement_audit_*` | Placement audit (`tools/placeaudit.py`): every ratsnest connection with its length (`_connections.csv`), every part with its demand, best spot, free spot and class (`_parts.csv`), the summary (`_summary.md`) and the map (`_map.png`). |
| `RFVD_unrouted.csv` / `.png` | Every missing connection (50, 2026-10-03): net, group, gap and closest-point coordinates of the two copper islands, plus a map. Input to `tools/feasible.py` and `tools/zoom.py --open` (see `docs/ROUTING_FINISH_GUIDE.md`). | `tools/unrouted_map.py` |

**Regenerate everything:** `tools/make_outputs.py` (add `--bom` after schematic edits).

**Not included on purpose: Gerbers and drill files.** Generate them only once routing is complete and DRC is clean. Use the JLC plug-in, or `kicad-cli pcb export gerbers` / `drill`.
