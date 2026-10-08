# Layout tools

> Designators in this dated record predate ECO-003 (2026-10-07). Look up the current ones in [`REFERENCE_MAP_ECO-003.md`](REFERENCE_MAP_ECO-003.md).

The tool index, the rules for running the tools and the move workflow are in **[`../tools/README.md`](../tools/README.md)**. That folder is the only copy of the tools.

## Housekeeping (2026-10-02)

The toolset was cleaned up on request ("one tool per job, check before use"):

- **Single folder.** The scratch copies were removed: 188 debug, patch and backup scripts went to the Recycle Bin. `tools/` now holds 48 tools.
- **Dependency-checked removal.** 64 handoff scripts nothing used any more went to the Recycle Bin (recoverable): the DRU patch scripts 1-6, the KiCadRoutingTools wrapper, early pass pipelines, and one-off debug and fix scripts. The removal was dependency-checked: every remaining tool's imports and script calls resolve. The DRU history is still in `tools/dru_versions/`.
- **Duplicates merged:**

| Merged tool | Replaces |
|---|---|
| `query.py` | The inspection helpers |
| `placeaudit.py` | `farparts.py` |
| `zoom.py --layer` | `place/layer_render.py` |
| `place/applyposes.py` | `setpos.py`, `applymoves.py`, `flip.py` |
| `zoom.py` (close-up view) | `place/render.py` |

- **Missing data restored.** `tools/an/nets.json` and `net_class.json` were never copied with the first handoff. `mr.py` could not import without them, so every routing tool was broken in the handoff copy. The new `selftest.py` caught this; it now passes on all tools.

## External router (historical)

KiCadRoutingTools v0.22.1 was tried on a locked copy. It ignores class widths, lanes, the AFE partition and octilinear geometry, so its output was only ever imported through `place/merge.py`'s rule check. Its wrapper was retired in the clean-up.
