# RFVD SENSOR-D placement sensitivity (datasheet-backed)

Read-only study. Positions from `goal/place/parts.json`; pad geometry from the Jev board export. `gap` = pad-edge gap from the part pad on the anchor net to the anchor pin (the jev_audit metric). `max` = largest acceptable gap. Numbers no datasheet prints are marked *EMC practice* in `sensitivity.json` (with the rulebook rule or reason).

**Scored: 374 parts** (332 Jev audit items + FL1, F1, F201, Q201-Q303, JP401/402, U304, SW1-5, 25 test points).

| class | all | lower half (y >= 98) | meaning |
|---|---|---|---|
| critical | 21 | 6 | at the pin, same layer, datasheet-mandated loop/node |
| high | 99 | 46 | 1.5-3 mm, short direct trace |
| medium | 114 | 55 | 3-10 mm, vias acceptable |
| low | 140 | 107 | placement-insensitive, 8-60 mm |

## Per IC: datasheet rule, critical parts, high parts

Format: part (gap now / max, mm). The routing note and citation for each part are in `sensitivity.json`.

**U301 BQ25798 charger.** SLUSDV2C 8.4.1 p.139: PMID/SYS 0.1 uF on the IC layer, on top of the IC, short traces (one 10 uF in parallel); SW1/SW2 may drop through vias under the IC; BTST caps may use vias on both sides; REGN cap close + 2 GND vias; VBUS 0.1 uF close, VBUS 10 uF may be farther; BAT caps close; BATP/TS away from SW.  
- critical: C309 (1.69/1.50 OVER), C318 (2.29/1.50 OVER)
- high: C305 (1.13/2.00), C306 (1.77/3.00), C310 (1.81/3.00), C311 (1.87/3.00), C312 (1.88/2.00), C313 (1.88/3.00), C319 (0.94/3.00), C905 (0.71/3.00), L301 (1.21/3.00)

**U8 STM32H743.** AN4938 2.2 p.12, 7.4 p.32, 9.3 p.38-39; DS12110 6.1.6 p.97 + Table 24 p.101: 100 nF per VDD pin (same side, or underside below the pins), 4.7 uF per package, VDDA and VREF+ 100 nF + 1 uF, VCAP 2.2 uF <100 mOhm. LSE crystal and load caps as close as possible (AN4938 4.2.2 p.23, AN2867 5.1 p.26-27). SDMMC/QSPI routing limits: AN4938 9.4.1 p.40, 9.4.3 p.41-43. APS6404L 16.4 p.25: 1 uF is the primary U9 decoupler.  
- critical: C21 (0.42/1.50), C22 (0.42/1.50), C601 (0.93/2.00), C602 (0.71/2.00), Y2 (0.00/3.00)
- high: C46 (0.49/2.00), C48 (1.50/2.50), C49 (0.72/2.50), C50 (0.46/2.50), C52 (0.53/2.50), C53 (0.80/2.50), C54 (0.44/2.50), C55 (0.44/2.50), C56 (0.46/2.50), C58 (0.44/2.50), C64 (0.49/2.00), C65 (0.55/2.00), C93 (0.59/1.50), C412 (0.00/2.00), C906 (0.07/2.00), C907 (0.00/2.00), R26 (0.55/1.50), R33 (1.39/3.00), R39 (1.45/3.00), R104 (0.90/3.00), Y1 (2.56/6.00)
- U9 itself: QSPI allows <120 mm and +/-10 mm matching (AN4938 9.4.3 p.41-42); rulebook R42 proposes a <=30 mm bus. U9 can move away from U8 if that frees fan-out; C64/C65 and R61/R63/R65/R67 travel with it.

**U402 TPS259631 eFuse.** SLVSET8A 11.1 p.36: IN bypass closest to IN/GND; RILM, CdVdT, EN/UVLO and OVLO networks close to their pins, shortest GND return, away from switching nets.  
- high: C404 (0.00/2.00), R408 (0.36/3.00), R409 (0.36/3.00), R410 (0.00/2.00)
- U402 itself: eFuse: on the VSYS to J11 EXP_VHP path with a thermal-via field; RILM/OVLO/dVdT/IN-cap travel with it.

**U302 BQ29209 / U303 TPS70933.** SLUSA52C 11.1 p.15: VC1/VC2 input filters and the VDD RC as close to the IC as possible. TPS709 SBVS186H 10.1 p.16: CIN/COUT close, COUT GND to the device GND pin.  
- high: C322 (0.94/2.00), C323 (1.42/2.00), C324 (1.59/2.00), C327 (0.73/2.00)
- U302 itself: Cell monitor: placement free; its VC/VDD RC filters must sit at its pins (SLUSA52C 11.1 p.15), so long BATT_MID/VBAT_PACK runs to it are acceptable.
- U303 itself: uA always-on LDO: anywhere on the VBAT_PACK to U8 VBAT path; C326/C327 travel with it.

**U401 / U10 TPS2553D, U403 TCA9517A.** SLVSDL7 12.1 p.26 and 10.2.1.2.4 p.20: >=0.1 uF IN bypass close, RILIM trace as short as possible. TCA9517A SCPS245E 10.1 p.16: no special layout, 100 nF close to VCCA/VCCB.  
- high: C66 (1.36/2.00), C401 (0.42/2.00), R43 (0.00/2.00), R401 (0.43/2.00)
- U401 itself: Load switch for +3V3_EXP: anywhere between +3V3_D and J11 pins 3/4/37/38; C401/R401 travel with it.
- U10 itself: Load switch for +3V3_UI: anywhere on the +3V3_D to J4/J8 supply path; C66/R43 travel with it (SLVSDL7 12.1 p.26).
- U403 itself: I2C buffer (400 kHz): anywhere between the host I2C bus and J11 pins 25/27; no special layout (SCPS245E 10.1 p.16).

**Connectors J10 / J3 / J4 / J8 / J11 / J2 (ESD, series, shunts).** TPD4E05U06 7.4.1 p.16, TPD1E10B06 7.4.1 p.11, PESD5V0U1UL 7 p.6: TVS as close to the connector as possible, straight protected trace, nothing unprotected alongside, short GND return. Series R and RF shunts at connectors are EMC practice (rulebook R33/R35/R36/R44).  
- high: C207 (0.00/2.00), D4 (0.00/3.00), D5 (0.00/3.00), D6 (0.00/3.00), D7 (0.00/3.00), D8 (0.00/3.00), D9 (0.00/3.00), D10 (0.12/3.00), D301 (3.05/3.00), D401 (0.86/3.00), D402 (1.05/3.00), D403 (0.78/3.00), D404 (0.78/3.00), D405 (1.05/3.00), D406 (0.78/3.00), U304 (3.10/3.00 OVER)

**U6 LMR43620 buck.** SNVSBY5B 9.2.2.5 p.31, 9.5.1 p.39-40, Fig. 9-23 p.41: small-case 100 nF at VIN/GND (EVM 0.38 mm) plus >=4.7 uF CIN; CVCC and CBOOT close with short wide traces; FB divider at FB (VOUT sense may be long, away from SW); minimal SW area.  
- critical: C32 (0.44/1.00), C35 (0.44/1.50), C37 (0.68/1.50)
- high: C30 (1.98/3.00), C33 (1.62/2.00), C41 (2.43/3.00), C900 (1.53/2.00), L1 (2.09/3.00), R16 (0.44/3.00), R17 (2.57/3.00)

**U7 LT3045.** LT3045 Rev B p.12-19: COUT >=10 uF (ESR <20 mOhm, ESL <2 nH) with OUTS Kelvin; SET bypassed and guarded (OUT-tied ring on both sides), RSET/CSET GND to COUT GND; ILIM Kelvin to the GND pin; CIN >=4.7 uF at IN; keep switching current away.  
- critical: C34 (1.18/1.50), C36 (0.68/1.50), R14 (0.57/1.50)
- high: C29 (0.72/2.00), C31 (0.74/3.00)

**U2 ADL5511 + RF input (U1).** ADL5511 Rev E p.19 + Table 5 p.24: 100 pF + 0.1 uF 0402 as close as possible to VPOS. Table 3 p.8: FLT2/FLT3/FLT4 VPOS-referenced, VENV load <=10 pF, EP to GND. TLV809E 11.1 p.24: 0.1 uF at VDD.  
- critical: C2 (1.24/1.50), C3 (0.64/1.00), FL1 (-/-), R1 (0.70/1.50), R2 (0.34/1.50)
- high: C1 (0.58/2.00), C4 (2.00/2.00), C6 (0.65/2.00), C8 (1.12/2.00), C901 (2.46/2.50), D1 (0.48/1.50), D300 (0.69/1.50), R302 (1.88/2.00), R903 (0.80/1.50)
- U1 itself: Supervisor: anywhere on +5V_RF inside the shield; ENBL to U2 pin 4 is a DC line; C1 travels with it.

**U13 AD7380.** AD7380 Rev A Table 7 p.9, p.16-17: 1 uF REFIO (mandatory), 0.1 uF REFCAP, 1 uF REGCAP, separate 1 uF VCC and VLOGIC, RC filter on the inputs, 100 ohm close to SDOA.  
- critical: C101 (0.44/1.00), C102 (0.44/1.00), C103 (0.54/1.50)
- high: C104 (0.47/1.50), C105 (0.80/2.00), C106 (0.80/1.50), C107 (1.03/2.00), R100 (1.25/2.00), R101 (1.23/2.00), R103 (3.80/3.00 OVER)
- U13 itself: Design intent: straddle the U3/U4 to U8 boundary with inputs facing the op-amps and SPI facing U8 (rulebook R23).

**U3/U4 OPA2320 Sallen-Key.** OPAx320 SBOS513F 9 and 10.1 p.28, Fig. 49: 0.1 uF at the supply pins with minimum inductance; filter parts close to the device and to each other; inputs away from supply lines (EMI 7.3.6 p.18).  
- high: C10 (1.47/2.00), C12 (1.48/2.00), C13 (0.44/1.50), C15 (0.43/1.50), C17 (0.82/2.00), C19 (0.83/2.00), R3 (3.75/2.00 OVER), R4 (0.62/2.00), R5 (0.65/2.00), R6 (0.68/2.00), R9 (0.92/2.00), R10 (0.92/2.00)

**U5 REF5030.** REF50 SBOS410O 9.3 p.29, 9.4.1.1 p.29-30: VIN bypass as close as possible, 1 uF on NR, 1-50 uF output (ESR 1-1.5 ohm, optional series R) plus an HF cap at VOUT.  
- high: C23 (0.42/2.00), C24 (0.09/1.50), C26 (0.32/2.00), C902 (2.10/2.00 OVER)
- U5 itself: Keep >=10 mm from L1/SW copper (rulebook R73, proposed); currently 16.6 mm.

**Sensors U11 / U701 / U702.** TMP117 SNOSD82D 10.1 p.36: 0.1 uF close; pull-ups are heat sources, keep them away. SHT4x Fig. 1 p.3: 100 nF. OPT3004 11.1 p.34: bypass close; the opposite side is optically best.  
- medium: C71 (0.43/3.00), C701 (0.41/3.00), C702 (0.44/3.00)
- U11 itself: Thermal: away from U6/L1/U8/U7 heat and with its pull-ups >=5 mm away (SNOSD82D 10.1 p.36).
- U701 itself: Uncoated vent window; no copper under the sensor (SHT4x 5.3 p.16).
- U702 itself: Optical window face-up; nearby parts >=2x their height away or on the other side (SBOS929A 11.1 p.34).

## Parts currently beyond their max

| part | class | anchor | gap | max |
|---|---|---|---|---|
| C309 | critical | U301.29 | 1.69 | 1.50 |
| C318 | critical | U301.25 | 2.29 | 1.50 |
| C902 | high | U5.2 | 2.10 | 2.00 |
| R103 | high | U13.13 | 3.80 | 3.00 |
| R3 | high | R5.1 | 3.75 | 2.00 |
| U304 | high | J10.A6 | 3.10 | 3.00 |
| C405 | medium | U402.2 | 4.47 | 4.00 |

## 20 most useful LOW parts to relocate

Ranked by local crowding (pads + vias within 3 mm) x footprint size x slack. Moving these opens fan-out room around U8 (B side), J11, J4 and U402.

| # | part | value | where (x, y, side) | anchor | gap now | max | why low |
|---|---|---|---|---|---|---|---|
| 1 | R22 | 20.0k 0.1% | 135.88, 101.8, B | R23.1 | 3.05 | 15.00 | divider_resistor (VSYS 100k/20k) |
| 2 | R207 | 100k 1% | 141.37, 90.11, B | U8.23 | 0.28 | 10.00 | pull_down_resistor (TE) |
| 3 | R311 | 10k | 139.56, 91.82, B | U301.21 | 18.05 | 30.00 | pull_up_resistor (INT) |
| 4 | R433 | 33R | 139.1, 90.35, B | U8.29 | 0.13 | 15.00 | series_termination_resistor (EXP_GATE 1 kHz) |
| 5 | R24 | 100k 0.1% | 140.25, 94.62, B | U8.16 | 0.00 | 12.00 | divider_resistor (+5V_A monitor 100k/100k) |
| 6 | R440 | 100k | 144.14, 137.14, B | J11.35 | 2.58 | 15.00 | pull resistor (100 k default level) |
| 7 | D203 | NSI45020A | 135.85, 117.59, B | J4.36 | 12.13 | 25.00 | constant_current_regulator (backlight 20 mA) |
| 8 | R304 | 100k | 140.97, 100.82, B | U8.7 | 1.03 | 15.00 | divider_resistor (VBUS_DET bottom) |
| 9 | R438 | 100k | 142.14, 138.14, B | J11.31 | 3.63 | 15.00 | pull resistor (100 k default level) |
| 10 | JP402 | SJ open | 155.3, 101.64, F | U402.3 | 24.93 | 40.00 | solder_jumper (MR kill) |
| 11 | R203 | 10k 1% | 137.25, 122.01, B | J4.12 | 0.13 | 15.00 | pull_up_resistor (8080 strobe default) |
| 12 | R25 | 100k 0.1% | 139.3, 96.12, B | U8.16 | 2.69 | 12.00 | divider_resistor (+5V_A monitor 100k/100k) |
| 13 | R204 | 10k 1% | 139.75, 122.86, B | J4.13 | 1.09 | 15.00 | pull_up_resistor (8080 strobe default) |
| 14 | R439 | 100k | 144.11, 126.14, B | J11.32 | 2.58 | 15.00 | pull resistor (100 k default level) |
| 15 | R53 | 4.7k 1% | 138.6, 102.65, B | U11.1 | 42.98 | 60.00 | pull_up_resistor (I2C 4.7 k, heat source) |
| 16 | R403 | 10k | 135.51, 103.99, B | U8.87 | 0.48 | 15.00 | pull_up_resistor (EXP_FAULT_N) |
| 17 | C406 | 10uF | 144.62, 120.72, F | J11.19 | 7.35 | 15.00 | bulk_cap (EXP_VHP 10 uF at J11) |
| 18 | TP5 | VENV_BUF | 148.01, 77.98, F | net:VENV_BUF | 0.87 | 15.00 | test_point |
| 19 | R417 | 2.2k | 126.38, 127.63, B | U403.7 | 1.48 | 15.00 | pull_up_resistor (EXP I2C 2.2 k) |
| 20 | R437 | 100k | 140.6, 138.65, B | J11.15 | 3.66 | 15.00 | pull resistor (100 k default level) |

## All LOW parts (move freely within max; respect the DRU keep-outs)


**J10:** C302 (1.44/10.00) R303 (2.31/25.00) R304 (1.03/15.00) R320 (0.00/10.00) R321 (0.00/10.00) 

**J11:** C402 (13.30/15.00) R404 (11.88/20.00) R436 (3.63/15.00) R437 (3.66/15.00) R438 (3.63/15.00) R439 (2.58/15.00) R440 (2.58/15.00) 

**J2:** F1 (15.19/25.00) Q303 (13.05/25.00) R322 (0.67/10.00) 

**J3:** C63 (10.47/15.00) R27 (0.13/10.00) R28 (0.23/10.00) R29 (0.23/10.00) R36 (0.13/10.00) R37 (0.23/10.00) R38 (0.23/10.00) R907 (0.50/15.00) 

**J4:** D201 (4.73/25.00) D202 (5.87/25.00) D203 (12.13/25.00) D204 (17.19/25.00) F201 (4.04/15.00) FB201 (2.26/15.00) Q201 (12.54/20.00) Q202 (2.46/15.00) Q203 (12.13/20.00) R50 (4.56/15.00) R51 (6.77/15.00) R52 (0.72/10.00) R200 (0.00/15.00) R201 (0.01/15.00) R202 (0.13/15.00) R203 (0.13/15.00) R204 (1.09/15.00) R209 (0.00/10.00) R210 (0.08/10.00) R211 (0.00/10.00) 

**J8:** R42 (0.03/15.00) R45 (0.00/15.00) R208 (0.00/15.00) 

**TP:** TP1 (5.96/15.00) TP2 (0.82/15.00) TP4 (-/-) TP5 (0.87/15.00) TP8 (0.51/15.00) TP9 (8.60/15.00) TP10 (2.40/15.00) TP11 (6.26/15.00) TP12 (0.82/15.00) TP13 (-/-) TP16 (-/-) TP20 (2.16/15.00) TP301 (5.28/15.00) TP302 (1.54/15.00) TP303 (2.92/15.00) TP304 (0.00/15.00) TP307 (-/-) TP308 (3.53/15.00) TP900 (0.66/15.00) TP901 (-/-) TP902 (-/-) TP903 (-/-) 

**U10:** C68 (0.93/10.00) R41 (0.00/10.00) R48 (0.61/15.00) R205 (25.28/30.00) 

**U11:** R53 (42.98/60.00) R54 (44.21/60.00) 

**U13:** D12 (5.74/15.00) R102 (2.62/10.00) 

**U301:** C303 (3.25/10.00) C304 (7.00/20.00) C315 (17.14/25.00) C316 (18.70/25.00) C321 (0.00/10.00) D3 (24.77/40.00) Q301 (13.11/25.00) R19 (26.34/40.00) R305 (0.25/8.00) R306 (1.83/8.00) R307 (1.32/8.00) R308 (0.44/10.00) R309 (0.78/10.00) R310 (1.03/10.00) R311 (18.05/30.00) R312 (0.00/15.00) R314 (38.54/40.00) R323 (4.43/10.00) R324 (1.91/15.00) 

**U302:** Q302 (29.76/40.00) R317 (0.54/8.00) R319 (1.98/15.00) 

**U401:** JP401 (0.00/40.00) R402 (0.49/10.00) 

**U402:** C406 (7.35/15.00) JP402 (24.93/40.00) R405 (0.61/15.00) R406 (0.65/15.00) R407 (0.13/10.00) R411 (4.61/20.00) 

**U403:** C411 (0.69/10.00) R416 (0.65/10.00) R417 (1.48/15.00) R418 (1.46/15.00) 

**U6:** C44 (1.50/8.00) C100 (2.38/10.00) R109 (0.56/10.00) R900 (0.00/10.00) 

**U7:** C27 (2.94/10.00) R902 (2.81/10.00) 

**U702:** R701 (36.36/40.00) 

**U8:** C60 (1.74/15.00) R11 (8.70/15.00) R12 (5.96/15.00) R18 (0.00/10.00) R21 (1.02/15.00) R22 (3.05/15.00) R24 (0.00/12.00) R25 (2.69/12.00) R44 (2.67/10.00) R49 (2.14/10.00) R108 (0.72/15.00) R207 (0.28/10.00) R403 (0.48/15.00) R412 (43.33/50.00) R414 (41.53/50.00) R433 (0.13/15.00) R801 (0.00/15.00) 

**U9:** R40 (0.00/15.00) 

**UI:** SW1 (38.82/-) SW2 (38.21/-) SW3 (43.46/-) SW4 (37.53/-) SW5 (32.12/-) 


(format: part (gap now / max mm); max "-" = mechanical/GND, position set by enclosure or not anchored)

## Notes and deviations

- Anchors assigned or changed vs Jev (Jev had none, a rail-level anchor, or a different pin of the same part): C27, C35, C39, C42, C44, C45, C56, C59, C60, C65, C301, C304, C326, C903, C904, D12, FB1, FB201, R3, R4, R11, R12, R21, R101, R109, R303, Y1.
- Most "max" numbers are EMC practice because datasheets say "as close as possible" without a distance. Printed numbers: LMR43620 EVM CINHF ~0.38 mm (9.2.2.5 p.31), LT3045 "1 inch" (CIN omission condition, p.18), AN4938 SDMMC/QSPI <120 mm and +/-10 mm (p.40-43).
- R3/R4: the datasheet only limits VENV load to 10 pF (ADL5511 Table 3 p.8), so the long run may be on VENV/EREF_RAW; keep the R3/R5/C9 (R4/R6/C11) junction compact at U3/U4. R3 is 3.7 mm from that junction today. Rulebook R13 (2 mm at U2) is a proposal, not a datasheet rule.
- R11/R12 are scored low: rulebook R27 allows a long op-amp-to-R run; C21/C22 (critical) stay at the ADC pins.
- D4-D10 and U304 sit on B.Cu under F.Cu connectors. The TVS datasheets ask for "as close as possible" and give no layer rule. Rulebook R35 prefers the TVS before any via; under-pin B.Cu placement is acceptable if each TVS pad lands on the first via (no stub).
- FB1 and FL1 have no pin anchor. FB1 sits on the +3V3_D/+3V3_A partition, 13.6 mm from L1 (min 10). FL1 must straddle the shield ring wall.
- AN4938 7.4 p.32 and DS12110 6.1.6 p.97 allow STM32 decouplers on the underside below the pins, so U8 decouplers have vias_ok = true.
- BQ25798 8.4.1 item 2 p.139 explicitly allows the BTST caps (C310/C311) on the other side with vias.
- Relocation targets must respect the DRU keep-outs: v3_keepout_F_footprints (K4_TFT_LOOP, K11_*), v3_keepout_B_footprints (K6_B_RF_END, K10B_HSE_SHADOW, K12_*, K13_U402_VIAFIELD, K16_DISP_LANE) and v3_K9_batt_window_no_tp_jp.
- AD7380 Rev A: analog.com timed out for WebFetch, so the text was read from the PDF in the browser pane. STM32H743 DS12110 used the Rev 5 mirror; pin map and decoupling text match the PCB.
