# Placement audit and board widening (2026-10-02 night)

> Designators in this dated record predate ECO-003 (2026-10-07). Look up the current ones in [`REFERENCE_MAP_ECO-003.md`](REFERENCE_MAP_ECO-003.md).

**Requests:**
- "look for cases of components being unnecessarily far away from where they should".
- "combine components whose nets are the same so you can connect stuff close together; stuff that cannot be close together at least in the same area; make your tools check the distance between nets that need to be connected and flag it".
- "make the board a little bit bigger on the sides".

Tool: `tools/placeaudit.py BOARD --png`. It builds the ratsnest as a minimum spanning tree per net. For each part it computes the demand, the best spot and the nearest legal free spot, applies the datasheet budget check, and reads the KEEP reasons from `tools/placeaudit_keep.json`. Re-run it after any placement change. Current tables: `outputs/RFVD_placement_audit_*`.

## 1. Board widened: 47.05 → 52.05 mm

- **Outline.** The left and right edges each move out 2.5 mm. On the left, a **port notch** keeps the old edge from y 104.6 to 133.3, so J3 (microSD) and J10 (USB-C) stay flush. Their 5.25 mm access gap in the box is kept, because the card protrudes 4.5 mm. The notch's inside corners have r 0.5 mm, the milling bit radius.
- **Nothing else moved.** Every part, mounting hole and track kept its absolute position, so the mounting bosses don't change.
- **Planes and areas extended.** The GND planes and pours (F, In1, In2, In4, B) and the board-wide rule areas (K9 battery window, AFE partition) reach the new edges.
- **Box fit.** The board still fits the 56 mm box interior: west gap 2.75 mm (5.25 mm at the ports), east gap 1.25 mm.
- **Edge clearance.** Footprints within 2 mm of the real edge went from **47 to 27**. All remaining ones are edge-bound by design (J3, J10, J1/J300 RF inputs, J6 SWD pogo pads, SW1-SW5, pogo GND pads, holes H1-H4), or sit in the port section:

| Part | Edge gap | Where |
|---|---|---|
| U403 | 0.47 mm | Port section |
| C409 | 0.96 mm | Port section |
| C68 | 0.35 mm | At the notch corner |
| C63 | 1.9 mm | Port section |

- **Rejected alternative.** Moving J3/J10 out with their ESD parts and stretching their tracks was tried. 31 nets run under their new positions (531 DRC errors), so that option was rejected. You chose the notch.
- **Checks.** DRC and connectivity are identical before and after (`tools/place/stretch.py --notch-left`).

## 2. Parts moved closer to their partners

| Part | Was | Now | Effect |
|---|---|---|---|
| **R314** (DNP 0R bypass of the ship FET Q301) | (120.5, 120.4) B, 38 mm from Q301 | (158.4, 108.4) B, directly under Q301 | Its pads land on Q301's existing CHG_BAT / VBAT_PACK vias. Two open power connections closed (25 and 28 mm) with no new copper. It sits in the K9 battery height window (<= 0.55 mm): **if this build option is ever fitted, use a 0805 0R no taller than 0.55 mm** (for example Panasonic ERJ-6GEY0R00V, 0.45 mm). |
| **TP11** (+3V3_D test pad) | (150.6, 121.8) B | (147.8, 127.2) B | Sits on existing +3V3_D copper; its 7 mm stub is gone. |
| **Q302** (2N7002 that enables BQ29209 cell balancing while VBUS is present) | (129.6, 131.6) F, by the USB-C | (163.4, 122.1) **B** (flipped), next to U302 | Its drain route to U302 was a 55 mm detour along the bottom edge. It is now 3.8 mm, plus a 20 mm VBUS gate route. Total copper roughly halves, and the bottom-edge corridor is free for the button lines (RECORD_N, MARK_N, QON_N, BOOT0, NRST). |

## 3. Flagged but not movable (space or rules), kept with reasons

| Part(s) | Why it stays |
|---|---|
| **D203 / D204** (backlight 20 mA regulators, 15-20 mm from D201/D202 and J4.36/37) | No legal spot near D201/D202. The B side there is filled by four round pogo test pads, the battery connector J2 and the eFuse via field. The F side is J8 and the charger. Their 2 open connections stay for routing. (The board's 2 courtyard-overlap errors are TP305/R417 and C106/C24, not these.) |
| **R412 / R414** (expansion rail read-back divider tops, 43 mm high-impedance runs to U8) | The MCU-side spots are fenced by the BR2 analog corner, the K16 display lane and the K17 LSE guard; no pose routes. Recommended: route EXP_VHP_SNS / EXP_3V3_SNS on In3, which is shielded between GND planes. |
| R18, C302, R304 (MCU right side) | Every candidate pose fails routing inside the same guard areas. They stay routed where they are. |
| TP9 (VSYS test pad) | Test pads are banned in the K9 window on B, and no VSYS copper is reachable outside it. |
| R51 | No legal pose near J4.30. |
| R402, R417 | No legal pose clear of the notch corner (R402) or of TP305 (R417, existing courtyard overlap). Both stay at their original pose with their original copper. |
| R103 (U13 SDOA damping) | The spot at U13.13 is the AFE GND return-via field. Moving it would cost more analog quality than its 0.8 mm gain. |
| C68 | No room above it; 0.35 mm from the notch corner. |
| JP402, D3, U11, RN201-203, TP901/902 | Placed by function (`placeaudit_keep.json`): F-side jumper access, charge LED at the UI edge, temperature sensor at the AFE, source terminations at U8, display-frame pads. |

## 4. Long links that are inherent (fixed connectors), to route as bundles

These were checked and are long because both ends are fixed:
- the LCD bus between U8 / RN201-203 and J4 (display FPC);
- the expansion bus between U8 and J11 (resistors sit at J11 by their 5 mm datasheet rule);
- the buttons, NRST, BOOT0 and SWD at the UI edge;
- the touch controller J8.

The new 2.5 mm strips along both side edges (outside the notch) are free on every layer. They are natural lanes for the bottom-edge signals and the expansion bus.

## 5. Over the datasheet distance budget (accepted, reasons)

| Part | Gap / max | Reason it stays |
|---|---|---|
| C318 (critical) | 2.29 / 1.5 mm | L301 occupies the pin-25 side. |
| C309 (critical) | 1.69 / 1.5 mm | Same reason. |
| R3 | 3.75 / 2.0 mm | Moving it lengthens the unfiltered EREF_RAW node instead. |
| R103 | 3.80 / 3.0 mm | Section 3. |
| C405, C4, C902, D301 | Over by at most 0.5 mm | Small deviations, accepted. |

## 6. Routing detours worth cleaning when you route

These are complete nets whose copper is 1.6-2.5x their ratsnest length:

| Net | Ratsnest | Routed |
|---|---|---|
| SWO | 37 mm | 76 mm |
| VBUS_DET | 24 mm | 60 mm |
| +3V0_REF | 31 mm | 64 mm |
| EXP_INT0_N_MCU | 34 mm | 64 mm |
| CHG_LED_A | 28 mm | 57 mm |
| SWCLK | 38 mm | 67 mm |
| TP_RST | 30 mm | 56 mm |
| CHG_STAT | 26 mm | 50 mm |
| Net-(J2-Pin_1) | 18 mm | 32 mm |
| EXP_I2C_SCL | 22 mm | 35 mm |
