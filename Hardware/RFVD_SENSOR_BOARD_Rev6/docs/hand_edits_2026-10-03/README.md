# Hand edits 2026-10-03 (applied in this order with `tools/place/pen.py`)

Each file is an explicit edit list: exact segments, vias and part poses. Nothing was searched or auto-routed.
Applying them in order to the handoff board as it was before this pass (backup
`backups/RFVD_SENSOR_BOARD_before_vsys_2026-10-03.kicad_pcb`, sha256 495e290b1a...) reproduces the current board
(m16; m11 = ed532a30f8...; m5 = f9f1d44f07... is in backups/RFVD_SENSOR_BOARD_before_drc14to3_2026-10-03.kicad_pcb):

    pen.py before.kicad_pcb m1.kicad_pcb e01.json   # EXP_TMR1 link at D404
    pen.py m1.kicad_pcb     m2.kicad_pcb e02.json   # VBAT_PACK / LCD_RST debris in the VSYS knot
    pen.py m2.kicad_pcb     m3.kicad_pcb e03.json   # LCD_RST to F, VBAT_PACK feed to In3, VBUS_DET hub, VSYS trunk
    pen.py m3.kicad_pcb     m4.kicad_pcb e05.json   # +3V3_D feed of the U8.100/R49/U401/U403 group (Y1.1 -> R49.1)
    pen.py m4.kicad_pcb     m5.kicad_pcb e07.json   # floating LCD_TE / LCD_D6 copper
    pen.py m5.kicad_pcb     m6.kicad_pcb e08.json   # VBUS_DET divider: R304 moved beside R303, 20 mm In3 run removed
    pen.py m6.kicad_pcb     m7.kicad_pcb e09.json   # R411 (EXP_VHP bleeder) beside C406, 6 mm In3 branch removed (DRC fix)
    pen.py m7.kicad_pcb     m8.kicad_pcb e10.json   # USB_DP/DM widened to 0.15 mm (4 DRC fixes)
    pen.py m8.kicad_pcb     m9.kicad_pcb e11.json   # R404 off the H3 boss (2 DRC fixes)
    pen.py m9.kicad_pcb     m10.kicad_pcb e12.json  # R417 off TP305's courtyard (DRC fix)
    pen.py m10.kicad_pcb    m11.kicad_pcb e13.json  # BUCK_SYNC 3W to VSYS at the buck input (3 DRC fixes)
    pen.py m11.kicad_pcb    m12.kicad_pcb e14.json  # +5V_A corner + BUCK_SYNC bend: 3 mm from the LSE (sign-off pass)
    pen.py m12.kicad_pcb    m13.kicad_pcb e15.json  # geometry: 22 track_angle warnings removed (duplicates, micro-jogs, T at pads)
    pen.py m13.kicad_pcb    m15.kicad_pcb e17.json  # DRC-flagged dead ends on connected signal nets (vias, stubs)
    pen.py m15.kicad_pcb    m16.kicad_pcb e18.json  # 14 mm dead +3V0_REF branch off R107 (antenna on the ADC reference), power stubs

(e04 and e06 were rejected by the checks and are not part of the board.) See `../LAYOUT_STATUS.md`, section
"Hand-layout pass 2026-10-03". The same lists are the transfer recipe for the project board through Konnect.
