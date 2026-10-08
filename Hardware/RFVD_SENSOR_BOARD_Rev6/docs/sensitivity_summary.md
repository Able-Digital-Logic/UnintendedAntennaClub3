# RFVD SENSOR-D placement sensitivity (datasheet-backed)

Read-only study. Positions from `goal/place/parts.json`; pad geometry from the Jev board export. `gap` = pad-edge gap from the part pad on the anchor net to the anchor pin (the jev_audit metric). `max` = largest acceptable gap. Numbers no datasheet prints are marked *EMC practice* in `sensitivity.json` (with the rulebook rule or reason).

**Scored: 374 parts** (332 Jev audit items + FL701, F1401, F801, Q802-Q1401, JP401/402, U1102, SW801-5, 25 test points).

| class | all | lower half (y >= 98) | meaning |
|---|---|---|---|
| critical | 21 | 6 | at the pin, same layer, datasheet-mandated loop/node |
| high | 99 | 46 | 1.5-3 mm, short direct trace |
| medium | 114 | 55 | 3-10 mm, vias acceptable |
| low | 140 | 107 | placement-insensitive, 8-60 mm |

## Per IC: datasheet rule, critical parts, high parts

Format: part (gap now / max, mm). The routing note and citation for each part are in `sensitivity.json`.

**U1101 BQ25798 charger.** SLUSDV2C 8.4.1 p.139: PMID/SYS 0.1 uF on the IC layer, on top of the IC, short traces (one 10 uF in parallel); SW801/SW802 may drop through vias under the IC; BTST caps may use vias on both sides; REGN cap close + 2 GND vias; VBUS 0.1 uF close, VBUS 10 uF may be farther; BAT caps close; BATP/TS away from SW.  
- critical: C1108 (1.69/1.50 OVER), C1113 (2.29/1.50 OVER)
- high: C1106 (1.13/2.00), C1109 (1.77/3.00), C1107 (1.81/3.00), C1112 (1.87/3.00), C1102 (1.88/2.00), C1114 (1.88/3.00), C1401 (0.94/3.00), C1404 (0.71/3.00), L1101 (1.21/3.00)

**U401 STM32H743.** AN4938 2.2 p.12, 7.4 p.32, 9.3 p.38-39; DS12110 6.1.6 p.97 + Table 24 p.101: 100 nF per VDD pin (same side, or underside below the pins), 4.7 uF per package, VDDA and VREF+ 100 nF + 1 uF, VCAP 2.2 uF <100 mOhm. LSE crystal and load caps as close as possible (AN4938 4.2.2 p.23, AN2867 5.1 p.26-27). SDMMC/QSPI routing limits: AN4938 9.4.1 p.40, 9.4.3 p.41-43. APS6404L 16.4 p.25: 1 uF is the primary U602 decoupler.  
- critical: C507 (0.42/1.50), C505 (0.42/1.50), C422 (0.93/2.00), C421 (0.71/2.00), Y402 (0.00/3.00)
- high: C404 (0.49/2.00), C415 (1.50/2.50), C419 (0.72/2.50), C408 (0.46/2.50), C420 (0.53/2.50), C409 (0.80/2.50), C403 (0.44/2.50), C410 (0.44/2.50), C417 (0.46/2.50), C411 (0.44/2.50), C603 (0.49/2.00), C604 (0.55/2.00), C402 (0.59/1.50), C1201 (0.00/2.00), C906 (0.07/2.00), C405 (0.00/2.00), R402 (0.55/1.50), R33 (1.39/3.00), R603 (1.45/3.00), R1004 (0.90/3.00), Y401 (2.56/6.00)
- U602 itself: QSPI allows <120 mm and +/-10 mm matching (AN4938 9.4.3 p.41-42); rulebook R814 proposes a <=30 mm bus. U602 can move away from U401 if that frees fan-out; C603/C604 and R61/R63/R65/R67 travel with it.

**U1502 TPS259631 eFuse.** SLVSET8A 11.1 p.36: IN bypass closest to IN/GND; RILM, CdVdT, EN/UVLO and OVLO networks close to their pins, shortest GND return, away from switching nets.  
- high: C1506 (0.00/2.00), R1509 (0.36/3.00), R1512 (0.36/3.00), R1513 (0.00/2.00)
- U1502 itself: eFuse: on the VSYS to J1201 EXP_VHP path with a thermal-via field; RILM/OVLO/dVdT/IN-cap travel with it.

**U1401 BQ29209 / U1402 TPS70933.** SLUSA52C 11.1 p.15: VC1/VC2 input filters and the VDD RC as close to the IC as possible. TPS709 SBVS186H 10.1 p.16: CIN/COUT close, COUT GND to the device GND pin.  
- high: C1405 (0.94/2.00), C1406 (1.42/2.00), C1407 (1.59/2.00), C1410 (0.73/2.00)
- U1401 itself: Cell monitor: placement free; its VC/VDD RC filters must sit at its pins (SLUSA52C 11.1 p.15), so long BATT_MID/VBAT_PACK runs to it are acceptable.
- U1402 itself: uA always-on LDO: anywhere on the VBAT_PACK to U401 VBAT path; C1409/C1410 travel with it.

**U1501 / U801 TPS2553D, U1201 TCA9517A.** SLVSDL7 12.1 p.26 and 10.2.1.2.4 p.20: >=0.1 uF IN bypass close, RILIM trace as short as possible. TCA9517A SCPS245E 10.1 p.16: no special layout, 100 nF close to VCCA/VCCB.  
- high: C805 (1.36/2.00), C1501 (0.42/2.00), R803 (0.00/2.00), R1503 (0.43/2.00)
- U1501 itself: Load switch for +3V3_EXP: anywhere between +3V3_D and J1201 pins 3/4/37/38; C1501/R1503 travel with it.
- U801 itself: Load switch for +3V3_UI: anywhere on the +3V3_D to J801/J802 supply path; C805/R803 travel with it (SLVSDL7 12.1 p.26).
- U1201 itself: I2C buffer (400 kHz): anywhere between the host I2C bus and J1201 pins 25/27; no special layout (SCPS245E 10.1 p.16).

**Connectors J1101 / J601 / J801 / J802 / J1201 / J1401 (ESD, series, shunts).** TPD4E05U06 7.4.1 p.16, TPD1E10B06 7.4.1 p.11, PESD5V0U1UL 7 p.6: TVS as close to the connector as possible, straight protected trace, nothing unprotected alongside, short GND return. Series R and RF shunts at connectors are EMC practice (rulebook R33/R35/R36/R44).  
- high: C810 (0.00/2.00), D4 (0.00/3.00), D5 (0.00/3.00), D6 (0.00/3.00), D7 (0.00/3.00), D8 (0.00/3.00), D9 (0.00/3.00), D10 (0.12/3.00), D1101 (3.05/3.00), D1201 (0.86/3.00), D1202 (1.05/3.00), D1203 (0.78/3.00), D1205 (0.78/3.00), D1206 (1.05/3.00), D1204 (0.78/3.00), U1102 (3.10/3.00 OVER)

**U1301 LMR43620 buck.** SNVSBY5B 9.2.2.5 p.31, 9.5.1 p.39-40, Fig. 9-23 p.41: small-case 100 nF at VIN/GND (EVM 0.38 mm) plus >=4.7 uF CIN; CVCC and CBOOT close with short wide traces; FB divider at FB (VOUT sense may be long, away from SW); minimal SW area.  
- critical: C1306 (0.44/1.00), C35 (0.44/1.50), C37 (0.68/1.50)
- high: C1305 (1.98/3.00), C201 (1.62/2.00), C41 (2.43/3.00), C1307 (1.53/2.00), L1301 (2.09/3.00), R1301 (0.44/3.00), R1302 (2.57/3.00)

**U201 LT3045.** LT3045 Rev B p.12-19: COUT >=10 uF (ESR <20 mOhm, ESL <2 nH) with OUTS Kelvin; SET bypassed and guarded (OUT-tied ring on both sides), RSET/CSET GND to COUT GND; ILIM Kelvin to the GND pin; CIN >=4.7 uF at IN; keep switching current away.  
- critical: C204 (1.18/1.50), C205 (0.68/1.50), R203 (0.57/1.50)
- high: C203 (0.72/2.00), C202 (0.74/3.00)

**U702 ADL5511 + RF input (U701).** ADL5511 Rev E p.19 + Table 5 p.24: 100 pF + 0.1 uF 0402 as close as possible to VPOS. Table 3 p.8: FLT2/FLT3/FLT4 VPOS-referenced, VENV load <=10 pF, EP to GND. TLV809E 11.1 p.24: 0.1 uF at VDD.  
- critical: C708 (1.24/1.50), C704 (0.64/1.00), FL701 (-/-), R706 (0.70/1.50), R702 (0.34/1.50)
- high: C701 (0.58/2.00), C703 (2.00/2.00), C705 (0.65/2.00), C706 (1.12/2.00), C709 (2.46/2.50), D701 (0.48/1.50), D702 (0.69/1.50), R701 (1.88/2.00), R705 (0.80/1.50)
- U701 itself: Supervisor: anywhere on +5V_RF inside the shield; ENBL to U702 pin 4 is a DC line; C701 travels with it.

**U1001 AD7380.** AD7380 Rev A Table 7 p.9, p.16-17: 1 uF REFIO (mandatory), 0.1 uF REFCAP, 1 uF REGCAP, separate 1 uF VCC and VLOGIC, RC filter on the inputs, 100 ohm close to SDOA.  
- critical: C1004 (0.44/1.00), C1005 (0.44/1.00), C1006 (0.54/1.50)
- high: C1007 (0.47/1.50), C1001 (0.80/2.00), C1002 (0.80/1.50), C1003 (1.03/2.00), R1006 (1.25/2.00), R1002 (1.23/2.00), R1007 (3.80/3.00 OVER)
- U1001 itself: Design intent: straddle the U502/U501 to U401 boundary with inputs facing the op-amps and SPI facing U401 (rulebook R23).

**U502/U501 OPA2320 Sallen-Key.** OPAx320 SBOS513F 9 and 10.1 p.28, Fig. 49: 0.1 uF at the supply pins with minimum inductance; filter parts close to the device and to each other; inputs away from supply lines (EMI 7.3.6 p.18).  
- high: C10 (1.47/2.00), C503 (1.48/2.00), C513 (0.44/1.50), C515 (0.43/1.50), C506 (0.82/2.00), C504 (0.83/2.00), R506 (3.75/2.00 OVER), R501 (0.62/2.00), R5 (0.65/2.00), R502 (0.68/2.00), R9 (0.92/2.00), R504 (0.92/2.00)

**U503 REF5030.** REF50 SBOS410O 9.3 p.29, 9.4.1.1 p.29-30: VIN bypass as close as possible, 1 uF on NR, 1-50 uF output (ESR 1-1.5 ohm, optional series R) plus an HF cap at VOUT.  
- high: C509 (0.42/2.00), C510 (0.09/1.50), C512 (0.32/2.00), C508 (2.10/2.00 OVER)
- U503 itself: Keep >=10 mm from L1301/SW copper (rulebook R73, proposed); currently 16.6 mm.

**Sensors U302 / U301 / U702@pre-ECO003.** TMP117 SNOSD82D 10.1 p.36: 0.1 uF close; pull-ups are heat sources, keep them away. SHT4x Fig. 1 p.3: 100 nF. OPT3004 11.1 p.34: bypass close; the opposite side is optically best.  
- medium: C302 (0.43/3.00), C301 (0.41/3.00), C702@pre-ECO003 (0.44/3.00)
- U302 itself: Thermal: away from U1301/L1301/U401/U201 heat and with its pull-ups >=5 mm away (SNOSD82D 10.1 p.36).
- U301 itself: Uncoated vent window; no copper under the sensor (SHT4x 5.3 p.16).
- U702@pre-ECO003 itself: Optical window face-up; nearby parts >=2x their height away or on the other side (SBOS929A 11.1 p.34).

## Parts currently beyond their max

| part | class | anchor | gap | max |
|---|---|---|---|---|
| C1108 | critical | U1101.29 | 1.69 | 1.50 |
| C1113 | critical | U1101.25 | 2.29 | 1.50 |
| C508 | high | U503.2 | 2.10 | 2.00 |
| R1007 | high | U1001.13 | 3.80 | 3.00 |
| R506 | high | R5.1 | 3.75 | 2.00 |
| U1102 | high | J1101.A6 | 3.10 | 3.00 |
| C1508 | medium | U1502.2 | 4.47 | 4.00 |

## 20 most useful LOW parts to relocate

Ranked by local crowding (pads + vias within 3 mm) x footprint size x slack. Moving these opens fan-out room around U401 (B side), J1201, J801 and U1502.

| # | part | value | where (x, y, side) | anchor | gap now | max | why low |
|---|---|---|---|---|---|---|---|
| 1 | R22 | 20.0k 0.1% | 135.88, 101.8, B | R23.1 | 3.05 | 15.00 | divider_resistor (VSYS 100k/20k) |
| 2 | R207 | 100k 1% | 141.37, 90.11, B | U401.23 | 0.28 | 10.00 | pull_down_resistor (TE) |
| 3 | R1107 | 10k | 139.56, 91.82, B | U1101.21 | 18.05 | 30.00 | pull_up_resistor (INT) |
| 4 | R1219 | 33R | 139.1, 90.35, B | U401.29 | 0.13 | 15.00 | series_termination_resistor (EXP_GATE 1 kHz) |
| 5 | R409 | 100k 0.1% | 140.25, 94.62, B | U401.16 | 0.00 | 12.00 | divider_resistor (+5V_A monitor 100k/100k) |
| 6 | R1217 | 100k | 144.14, 137.14, B | J1201.35 | 2.58 | 15.00 | pull resistor (100 k default level) |
| 7 | D803 | NSI45020A | 135.85, 117.59, B | J801.36 | 12.13 | 25.00 | constant_current_regulator (backlight 20 mA) |
| 8 | R304 | 100k | 140.97, 100.82, B | U401.7 | 1.03 | 15.00 | divider_resistor (VBUS_DET bottom) |
| 9 | R1221 | 100k | 142.14, 138.14, B | J1201.31 | 3.63 | 15.00 | pull resistor (100 k default level) |
| 10 | JP402 | SJ open | 155.3, 101.64, F | U1502.3 | 24.93 | 40.00 | solder_jumper (MR kill) |
| 11 | R203@pre-ECO003 | 10k 1% | 137.25, 122.01, B | J801.12 | 0.13 | 15.00 | pull_up_resistor (8080 strobe default) |
| 12 | R407 | 100k 0.1% | 139.3, 96.12, B | U401.16 | 2.69 | 12.00 | divider_resistor (+5V_A monitor 100k/100k) |
| 13 | R204 | 10k 1% | 139.75, 122.86, B | J801.13 | 1.09 | 15.00 | pull_up_resistor (8080 strobe default) |
| 14 | R1213 | 100k | 144.11, 126.14, B | J1201.32 | 2.58 | 15.00 | pull resistor (100 k default level) |
| 15 | R302 | 4.7k 1% | 138.6, 102.65, B | U302.1 | 42.98 | 60.00 | pull_up_resistor (I2C 4.7 k, heat source) |
| 16 | R1501 | 10k | 135.51, 103.99, B | U401.87 | 0.48 | 15.00 | pull_up_resistor (EXP_FAULT_N) |
| 17 | C1507 | 10uF | 144.62, 120.72, F | J1201.19 | 7.35 | 15.00 | bulk_cap (EXP_VHP 10 uF at J1201) |
| 18 | TP502 | VENV_BUF | 148.01, 77.98, F | net:VENV_BUF | 0.87 | 15.00 | test_point |
| 19 | R1212 | 2.2k | 126.38, 127.63, B | U1201.7 | 1.48 | 15.00 | pull_up_resistor (EXP I2C 2.2 k) |
| 20 | R1215 | 100k | 140.6, 138.65, B | J1201.15 | 3.66 | 15.00 | pull resistor (100 k default level) |

## All LOW parts (move freely within max; respect the DRU keep-outs)


**J1101:** C302@pre-ECO003 (1.44/10.00) R1109 (2.31/25.00) R304 (1.03/15.00) R1112 (0.00/10.00) R1113 (0.00/10.00) 

**J1201:** C1502 (13.30/15.00) R1504 (11.88/20.00) R1216 (3.63/15.00) R1215 (3.66/15.00) R1221 (3.63/15.00) R1213 (2.58/15.00) R1217 (2.58/15.00) 

**J1401:** F1401 (15.19/25.00) Q1401 (13.05/25.00) R1403 (0.67/10.00) 

**J601:** C602 (10.47/15.00) R27 (0.13/10.00) R28 (0.23/10.00) R29 (0.23/10.00) R36 (0.13/10.00) R37 (0.23/10.00) R38 (0.23/10.00) R601 (0.50/15.00) 

**J801:** D801 (4.73/25.00) D802 (5.87/25.00) D803 (12.13/25.00) D804 (17.19/25.00) F801 (4.04/15.00) FB801 (2.26/15.00) Q802 (12.54/20.00) Q801 (2.46/15.00) Q803 (12.13/20.00) R50 (4.56/15.00) R806 (6.77/15.00) R812 (0.72/10.00) R200 (0.00/15.00) R201@pre-ECO003 (0.01/15.00) R202@pre-ECO003 (0.13/15.00) R203@pre-ECO003 (0.13/15.00) R204 (1.09/15.00) R810 (0.00/10.00) R809 (0.08/10.00) R811 (0.00/10.00) 

**J802:** R814 (0.03/15.00) R813 (0.00/15.00) R815 (0.00/15.00) 

**TP:** TP701 (5.96/15.00) TP503 (0.82/15.00) TP505 (-/-) TP502 (0.87/15.00) TP504 (0.51/15.00) TP9 (8.60/15.00) TP201 (2.40/15.00) TP1301 (6.26/15.00) TP1303 (0.82/15.00) TP202 (-/-) TP901 (-/-) TP20 (2.16/15.00) TP1104 (5.28/15.00) TP1403 (1.54/15.00) TP1402 (2.92/15.00) TP1105 (0.00/15.00) TP1103 (-/-) TP1401 (3.53/15.00) TP1302 (0.66/15.00) TP803 (-/-) TP801 (-/-) TP802 (-/-) 

**U801:** C68 (0.93/10.00) R802 (0.00/10.00) R801 (0.61/15.00) R805 (25.28/30.00) 

**U302:** R302 (42.98/60.00) R301 (44.21/60.00) 

**U1001:** D1001 (5.74/15.00) R1001 (2.62/10.00) 

**U1101:** C1104 (3.25/10.00) C1105 (7.00/20.00) C1116 (17.14/25.00) C1117 (18.70/25.00) C1101 (0.00/10.00) D3 (24.77/40.00) Q1402 (13.11/25.00) R19 (26.34/40.00) R1103 (0.25/8.00) R1101 (1.83/8.00) R1102 (1.32/8.00) R1104 (0.44/10.00) R1105 (0.78/10.00) R1106 (1.03/10.00) R1107 (18.05/30.00) R1108 (0.00/15.00) R1402 (38.54/40.00) R1111 (4.43/10.00) R1110 (1.91/15.00) 

**U1401:** Q1403 (29.76/40.00) R1406 (0.54/8.00) R1408 (1.98/15.00) 

**U1501:** JP401 (0.00/40.00) R1502 (0.49/10.00) 

**U1502:** C1507 (7.35/15.00) JP402 (24.93/40.00) R405@pre-ECO003 (0.61/15.00) R406@pre-ECO003 (0.65/15.00) R1511 (0.13/10.00) R1510 (4.61/20.00) 

**U1201:** C411@pre-ECO003 (0.69/10.00) R416 (0.65/10.00) R1212 (1.48/15.00) R1211 (1.46/15.00) 

**U1301:** C1313 (1.50/8.00) C1315 (2.38/10.00) R1307 (0.56/10.00) R1303 (0.00/10.00) 

**U201:** C27 (2.94/10.00) R201 (2.81/10.00) 

**U702@pre-ECO003:** R701@pre-ECO003 (36.36/40.00) 

**U401:** C412 (1.74/15.00) R507 (8.70/15.00) R505 (5.96/15.00) R18 (0.00/10.00) R21 (1.02/15.00) R22 (3.05/15.00) R409 (0.00/12.00) R407 (2.69/12.00) R44 (2.67/10.00) R49 (2.14/10.00) R1005 (0.72/15.00) R207 (0.28/10.00) R1501 (0.48/15.00) R1505 (43.33/50.00) R1506 (41.53/50.00) R1219 (0.13/15.00) R801@pre-ECO003 (0.00/15.00) 

**U602:** R604 (0.00/15.00) 

**UI:** SW801 (38.82/-) SW802 (38.21/-) SW3 (43.46/-) SW4 (37.53/-) SW1101 (32.12/-) 


(format: part (gap now / max mm); max "-" = mechanical/GND, position set by enclosure or not anchored)

## Notes and deviations

- Anchors assigned or changed vs Jev (Jev had none, a rail-level anchor, or a different pin of the same part): C27, C35, C1301, C1302, C1313, C1314, C417, C418, C412, C604, C1103, C1105, C1409, C1303, C1403, D1001, FB1301, FB801, R506, R501, R507, R505, R21, R1002, R1307, R1109, Y401.
- Most "max" numbers are EMC practice because datasheets say "as close as possible" without a distance. Printed numbers: LMR43620 EVM CINHF ~0.38 mm (9.2.2.5 p.31), LT3045 "1 inch" (CIN omission condition, p.18), AN4938 SDMMC/QSPI <120 mm and +/-10 mm (p.40-43).
- R506/R501: the datasheet only limits VENV load to 10 pF (ADL5511 Table 3 p.8), so the long run may be on VENV/EREF_RAW; keep the R506/R5/C9 (R501/R502/C501) junction compact at U502/U501. R506 is 3.7 mm from that junction today. Rulebook R508 (2 mm at U702) is a proposal, not a datasheet rule.
- R507/R505 are scored low: rulebook R27 allows a long op-amp-to-R run; C507/C505 (critical) stay at the ADC pins.
- D4-D10 and U1102 sit on B.Cu under F.Cu connectors. The TVS datasheets ask for "as close as possible" and give no layer rule. Rulebook R35 prefers the TVS before any via; under-pin B.Cu placement is acceptable if each TVS pad lands on the first via (no stub).
- FB1301 and FL701 have no pin anchor. FB1301 sits on the +3V3_D/+3V3_A partition, 13.6 mm from L1301 (min 10). FL701 must straddle the shield ring wall.
- AN4938 7.4 p.32 and DS12110 6.1.6 p.97 allow STM32 decouplers on the underside below the pins, so U401 decouplers have vias_ok = true.
- BQ25798 8.4.1 item 2 p.139 explicitly allows the BTST caps (C1107/C1112) on the other side with vias.
- Relocation targets must respect the DRU keep-outs: v3_keepout_F_footprints (K4_TFT_LOOP, K11_*), v3_keepout_B_footprints (K6_B_RF_END, K10B_HSE_SHADOW, K12_*, K13_U402_VIAFIELD, K16_DISP_LANE) and v3_K9_batt_window_no_tp_jp.
- AD7380 Rev A: analog.com timed out for WebFetch, so the text was read from the PDF in the browser pane. STM32H743 DS12110 used the Rev 5 mirror; pin map and decoupling text match the PCB.
