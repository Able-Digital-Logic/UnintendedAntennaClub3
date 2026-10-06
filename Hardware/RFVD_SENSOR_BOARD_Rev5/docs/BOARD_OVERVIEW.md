# RFVD SENSOR-D: board overview

This page summarises the board as laid out in this handoff. The full device description, signal processing, calibration and validation are in `reference/RFVD_DEVICE_REPORT.docx`. The original layout rationale and the EMC analysis are in `reference/RFVD_PCB_LAYOUT_RATIONALE.docx` and `reference/RFVD_EMC_OPTIMIZATION_REPORT.docx`.

## What the board does

RFVD SENSOR-D is a battery-powered measurement and recording instrument:

- **RF front end.** The RF input (J1 `AIMD_IN`, U.FL, with ESD clamp D1 and a series input network) feeds an **ADL5511** (U2) envelope and RMS detector in the RF/AFE area. Rev A has no shield can; a GND ring for the AFE is planned (critique P1-17). J300 is a calibration input.
- **Analog chain.** The detector's envelope (`VENV`) passes through a two-stage unity-gain Sallen-Key low-pass (**OPA2320** U4: about 144 kHz and 159 kHz). The reference output (`EREF`) gets a single 704 Hz pole (R3 22.6k / C17 10 nF) buffered by U3 (checkpoint 2a, S-27). Each branch has a 33R / 2.2 nF C0G charge reservoir at its ADC pin.
- **Sampling.** An **AD7380** (U13) dual simultaneous-sampling ADC digitises them on its internal 2.5 V reference (checkpoint 2a, S-26). The **STM32H743** (U8) ADCs are referenced to a **REF5030** 3.0 V reference (U5).
- **Recording.** U8 timestamps and processes the data, spools it in an 8 MiB **APS6404L** PSRAM (U9) and records it to a microSD card (J3). The PSRAM QSPI lines have one 47R array (RN60) at the MCU side (S-17). The SD lines run through an ST **EMIF06-MSD02N16** (U901) at the socket: series resistors, pull-ups and ESD in one package, replacing 20 discrete parts (S-19).
- **User interface.** A 2.4" TFT (ST7789, 8080 parallel bus) on J4, a capacitive touch panel (FT5426, I2C) on J8, four buttons (RECORD, MARK, RESET, POWER); RECORD and MARK have a 1k series resistor at the MCU node (SC-11). BOOT0 is held low by R20; the BOOT button was removed (S-16), so recovery is via SWD under reset. The charge LED was removed in checkpoint 2a (S-7); the charge state is shown on the LCD.
- **Environment sensing.** TMP117 board temperature (U11) and SHT40 humidity/temperature (U701). The OPT3004 lid light sensor was removed at checkpoint 4b2; the display wakes on a button press or USB plug-in (firmware).
- **Power.**
  - A 2S Li-ion pack on J2 (PTC F1, reverse-polarity FET Q303, BQ29209 overvoltage protection and balancing U302) is charged from USB-C (J10, ESD U304/D301) by a **BQ25798** NVDC buck-boost charger (U301, L301) with a ship FET (Q301).
  - VSYS feeds an **LMR43620** synchronous buck (U6, L1) for `+3V3_D`, synchronised by MCU clock `BUCK_SYNC`.
  - An **LT3045** low-noise LDO (U7) makes `+5V_A` for the analog and RF sections, filtered into `+5V_RF` by FL1.
  - A TPS70933 always-on LDO (U303) supplies the RTC.
- **Expansion.** A 40-pin Samtec mezzanine J11 (bottom side) carries:
  - an eFuse-protected high-voltage rail (TPS259631, U402);
  - a switched 3.3 V rail (TPS2553, U401);
  - a buffered I2C bus (TCA9517A, U403);
  - SPI, timers, interrupts and an analog monitor. Every line has ESD protection (D401-D406).
  - **Shield-spec constraint:** under the shield (B-side window K8) every part is at most 0.6 mm tall, with one exception. **D203** (backlight current regulator NSI45020, SOD-123) sits at B (132.76, 121.09), rotated 90°. It stays because the CAT4104 that would have replaced it (S-15) has no legal site, and no copper-clear spot exists outside K8. The RFVD-EXP shield must keep its facing side clear over D203's courtyard.

## Physical

| Item | Value |
|---|---|
| Outline | **52.05 x 90.05 mm** (widened 2026-10-02 from 47.05 mm: +2.5 mm on each side for edge clearance; a 2.5 mm port notch at y 104.6-133.3 keeps J3 microSD and J10 USB-C flush with their own edge), rounded corners, mounting holes H1-H4 (unchanged positions, now 5.5 mm from the side edges) plus two bosses (H5, H6). Fits the 56 mm box interior: west gap 2.75 mm (5.25 mm at the ports), east 1.25 mm. See `PLACEMENT_AUDIT.md`. |
| Components | 341 footprints, 196 top and 145 bottom, all locked, at checkpoint 5 (B-side height windows K9 <= 0.55 mm and K8 <= 0.6 mm for the battery and shield) |
| Fixed by the mechanics | J1, J300 (top edge, U.FL); J10 (USB-C, left edge); J3 (microSD); J4 (TFT FPC); J8 (touch FPC); J2 (battery); J11 (mezzanine); J6 (SWD pads; SWO not connected since S-18); SW1-SW3, SW5 (bottom edge); H1-H6 |

## Stack-up (JLC06161H-3313, 6 layers, 1.6 mm, set by the team lead)

| Layer | Use | Dielectric to the next layer |
|---|---|---|
| F.Cu | components, short routes, escapes | 0.0994 mm (3313 prepreg) |
| In1.Cu | **solid GND**: reference for F.Cu | core |
| In2.Cu | **solid GND**: reference for In3 | 0.1088 mm (2116 prepreg) |
| In3.Cu | **buried signal layer**: long digital buses, power feeds | 0.55 mm (core) |
| In4.Cu | **solid GND**: reference for B.Cu | 0.0994 mm (3313 prepreg) |
| B.Cu | components, short routes | - |

In3 is the only inner signal layer. It sits 0.109 mm under its reference plane In2, so In2 cannot become a second signal layer without changing the stack-up.

## Net classes (from `RFVD_SENSOR_BOARD.kicad_pro` and the DRU)

| Class | Clearance | Track (opt) | Notes from the DRU |
|---|---|---|---|
| Default | 0.10 | 0.12 (min 0.10) | slow GPIO |
| HighSpeed_Digital | 0.10 | 0.15 | 0.20 mm to other non-GND copper outside IC courtyards |
| HighSpeed_Clock | 0.10 | 0.15 | 3W spacing 0.30 mm (`sp_clock_3w`); BUCK_SYNC >= 3 mm from the LSE crystal nets (`#SIGNOFF` rule) |
| Harness_IO | 0.10 | 0.25 (min 0.15) | off-board lines; >= 1.0 mm from precision analog |
| Analog_Precision / Ref_Kelvin | 0.15 | 0.20 / 0.30 | 0.5 mm to digital power and Default; 1.0 mm to HS and harness; 2 mm to buck SW; not on In3 |
| RF_Input / RF_50R | 0.15 | 0.20 / 0.15 | 0.5 mm to non-RF |
| Power_Digital / Power_Analog | 0.15 | 0.50 / 0.40 | neck-down to 0.2-0.3 mm inside IC courtyards |
| Power_Battery | 0.20 | 1.00 (min 0.5) | vias 0.6/0.3; charger-cap necks 0.2 mm (patch 5) |
| Power_Buck_SW | 0.20 | 0.80 | vias must be >= 0.5/0.3 (`fab_via_window`) |
| Ground | 0.15 | 0.40 | |

- **Vias:** 0.45/0.20 mm, plated over and filled (POFV), for signals and GND. Via-in-pad is allowed wherever the pad can hold the via; fine-pitch pins (U8 LQFP-100, RN arrays at 0.5 mm pitch) cannot.
- **Geometry:** octilinear (45-degree) routing only, with no right or acute angles (`v7_geom_*`).
- **Source stubs:** the MCU-side stubs of the PSRAM series array and of the LCD write strobe should stay <= 3 mm (`len_source_stubs`, warning). The LCD data/CS/DC stubs get 16 mm (`len_source_stubs_lcd`, checkpoint 3). The SD series resistance is inside U901 at the socket, so the SD MCU-side lines are unterminated: firmware keeps SDMMC1 at medium output speed (`FIRMWARE_NOTES.md` §3).

## EMC strategy (rule areas in the board)

- **AFE_PARTITION** covers the top half, y < 95.6 mm. HighSpeed, Harness and buck-SW tracks and vias are not allowed on F/B there. The exceptions are the bridges `BR1_SPI4_BRIDGE` (U8 to U13 SPI) and `BR2_ANALOG_CORNER`, the display lane `K16_DISP_LANE`, and the U8/U13 courtyards. Digital routes may pass **under** it on In3, between the In2 and In4 planes; vias stay outside.
- **RF corridor and shield.** `K3_RF_CORRIDOR`: only RF and ground copper on F/B. `K1*` voids are cut in In1 under the RF parts. FL1 is the feed-through filter into the RF/AFE area (no shield ring on Rev A yet).
- **Clock cells.**
  - `K10F_HSE_CELL` / `K10B_HSE_SHADOW`: only HSE nets plus +3V3_D/GND around the 12 MHz oscillator Y1.
  - `K17_LSE_GUARD`: only the PC14/PC15 crystal nets and GND under Y2.
- **Bottom-layer lanes K15-K20.** These reserve B.Cu channels for named nets: I2C (K15), the +3V3_D feed (K18), the display/clock lane (K16), VSYS (K19a-c), and the EREF/VENV analog lanes (K20a/b).
- **Keep-outs.** K4 (TFT loop), K7 (mounting holes), K11 (GND-only copper near the J11 and boss holes), K12/K13 (footprint and via bans), K5 (no pours under inductors L301/L1).
- **Return paths.** Every signal via changing reference planes gets a GND via within 1-2 mm (`retvia.py`). The outer layers carry GND fills stitched to In1/In2/In4.

## Placement philosophy

- **Modules.** Parts are grouped around their anchor IC (the Jev audit modules) so each module's nets stay local. Inter-module signals cross under other modules on In3.
- **Datasheet budgets.** Each part has a datasheet-backed placement budget: critical, high, medium or low sensitivity with a maximum distance to its anchor pin (`sensitivity_summary.md`). Critical parts sit at their pins, for example:
  - the BQ25798 PMID/SYS caps;
  - the ADC reference caps;
  - the LSE crystal and its load caps;
  - the LT3045 SET network.

  Low-sensitivity parts may move further out to make routing room.
- **U8 orientation.** U8 is rotated 180 deg. Of the long nets, only 5 leave from the side facing away from their destination. That is the best of the four orientations; the others give 15, 20 and 36.
- **Charger.** Laid out per TI SLUSDV2C section 8.4: PMID/SYS 0.1 uF on the IC layer, SW nodes through vias under the IC, BTST caps on B, REGN cap with 2 GND vias, BATP/TS away from SW.
