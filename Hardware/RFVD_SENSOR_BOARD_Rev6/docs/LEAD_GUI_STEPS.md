# Steps that need the KiCad GUI (for the lead)

> Designators in this dated record predate ECO-003 (2026-10-07). Look up the current ones in [`REFERENCE_MAP_ECO-003.md`](REFERENCE_MAP_ECO-003.md).

The scripts cannot make these changes. Rows 1-2 live in the board's setup block, which KiCad's Python API does not reach. Row 3 lives in the project file, and row 4 in a library footprint; Konnect has no tool for either, and those files are never hand-edited. So they are listed here for one quick GUI pass.

Work on the master project with no other tool running on it:
1. Open `RFVD_SENSOR_BOARD.kicad_pro` in KiCad 10.
2. Make the changes.
3. Save.
4. Tell Claude, who re-verifies with DRC and updates the outputs.

| # | Where | Change | Why (critique ID) |
|---|---|---|---|
| 1 | Board Setup > Board Stackup > Physical Stackup | **Dielectric 3** (the 2116 prepreg between In2 and In3): set **Loss Tg = 0.02** (it reads 0). The other dielectrics already have 0.02. | The stackup data feeds impedance/loss calculations and the fab notes (P1-13 / RULES-04). |
| 2 | Board Setup > Board Stackup > Board Finish (via protection) | Set **Filling = yes** and **Capping = yes** (IPC-4761 type VII). Covering and plugging stay as they are. | Every via is resin-filled and copper-capped (POFV, free on JLC 6-20 layers); the board file should say so (P1-13 / MFG-15). |
| 3 | Board Setup > Design Rules > Constraints | **Minimum text height = 1.0 mm** (reads 0.8) and **minimum text thickness = 0.15 mm** (reads 0.08). | JLC silkscreen minimums (P1-9 / MFG-14). All 7 visible silk texts are already 1.0 / 0.15 (checked 2026-10-04, incl. the 2b date and S/N label), so this only guards later edits and adds no DRC warnings. These limits live in the project file, which the scripts change only through Konnect, and Konnect has no tool for them. |
| 4 | Footprint Editor, library `RFVD_MVP_Footprints`, footprint `USB_C_Receptacle_HRO_TYPE-C-31-M-12` (J10) | On each of the **4 SH pads** (the plated shell-tab slots): Pad Properties > tick the **F.Paste** technical layer; Clearance overrides > **solder paste absolute margin = +0.15 mm**. Save the library. The board copy of J10 already has this (checkpoint 2b), so no board update is needed. DRC's one `lib_footprint_mismatch` warning on J10 then disappears. | Pin-in-paste: without paste on the shell tabs, reflow leaves the USB-C shell unsoldered (P1-12 / MFG-11). Konnect can edit pad size, drill and zone connection, but not pad layers or paste margins. |

When ordering at JLC, also choose:
- the **JLC06161H-3313** impedance stackup;
- **"Epoxy filled & capped"** vias.

## Optional placement clean-ups (found by the 2026-10-04 placement sign-off)

None of them is needed for a working board. A and B are recorded as justified keeps in `tools/placeaudit_keep.json`, and C clears cosmetic DRC warnings. Do them together with the hand routing if you have time. All footprints are locked: unlock the part (`L`), move it, re-lock it, then run DRC.

| # | Part | Now | Change | Gain |
|---|---|---|---|---|
| A | R417 (EXP_I2C_SCL 2.2 k pull-up, B.Cu) | (130.80, 129.04), 12 mm In3 stub from D402 | Delete the In3 stub (141.05, 134.68) → (139.95, 133.58) → (134.40, 133.58) → (130.75, 129.93), the via at (130.76, 128.53) and R417's +3V3_EXP B.Cu branch back to (135.73, 131.43). Then place R417 next to J11.25 / D402.2 on the bus end and connect it with two short tracks. | Frees an In3 corridor through the J11 field; same-net clustering. The spot at U403 is copper-blocked by the SCL / SDA F.Cu pair. |
| B | C318 / C313 (BQ25798 SYS caps, F.Cu) | C318 0.1 uF at 2.29 mm from U301.25, C313 10 uF at 1.88 mm | Use the 0.6 mm courtyard slack north of U301 so that C318 (0.1 uF) is the closest SYS cap, as TI Table 5-1 asks ("0.1 uF closest"). Keep the GND via in its pad. | Shorter high-frequency SYS loop (about 0.4 mm). |
| C | Whole board, **after** the 42 links are routed | Micro-jogs and stubs (DRC warnings: 6 `track_segment_length`, the LCD_RST 0.28 mm overshoot at (143.12, 89.50) and any unused hand-off via) | Run *Tools > Cleanup Tracks & Vias* with "merge co-linear segments" and "delete tracks unconnected at one end" ticked, then DRC. Do not run it before routing: it would delete the 42 hand-off vias. | Removes about 7 warnings plus the leftover vias. |
