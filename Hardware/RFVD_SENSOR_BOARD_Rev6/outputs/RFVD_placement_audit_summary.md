# Placement audit: RFVD_SENSOR_BOARD.kicad_pcb

- Ratsnest (MST, all nets but GND): **3522 mm** over 517 part-to-part connections; **83 longer than 12 mm** (42 of them still open).
- Parts: 0 MOVE candidates, 0 over their datasheet budget, 7 fixed (mechanical).
- Detours (routed copper > 1.6x ratsnest and > 8 mm extra): 5 nets.

## MOVE candidates (a legal free spot shortens their connections)

| Part | Side | Now | Nets | Partners | Demand now | Free spot | Saving |
|---|---|---|---|---|---|---|---|

## Kept on purpose (placeaudit_keep.json)

| Part | Reason | Demand now | Would save |
|---|---|---|---|
| R412 | EXP_VHP_SNS divider top (100 k) at the rail end, 5.2 mm from J11.21: the long run to U8.17 carries only the divided node, never the raw shield rail (sensitivity.json routing rule) | 49.1 mm | 21.7 mm |
| RN203 | LCD control series source termination: belongs at U8 (source end) | 102.3 mm | 18.2 mm |
| R414 | EXP_3V3_SNS divider top (100 k) at the rail end, 1.0 mm from C403: the long run to U8.18 carries only the divided node | 44.7 mm | 13.3 mm |
| R417 | EXP_I2C_SCL 2.2 k pull-up, left at its pre-cp4 spot when the U403 cluster moved (its twin R418 sits at U403). The spot at U403 is copper-blocked: the SCL / SDA F.Cu pair passes U403.7 at 0.22 mm pitch with R418 beside it, so no via fits. Electrically neutral: a 12 mm open-drain stub at <= 400 kHz (rise >= 300 ns). Optional hand clean-up: docs/LEAD_GUI_STEPS.md | 18.2 mm | 15.3 mm |
| D203 | NSI45020A backlight constant-current regulator: anywhere on the cathode line, and the four CCRs D201-D204 are spread for heat (about Vak x 20 mA each), per its sensitivity rule | 22.1 mm | 12.9 mm |
| R47 | MARK_N 1 k series resistor at the MCU end (7.4 mm from U8.3) to limit button ESD current into the pin; the 41 mm run to SW2 is the button-to-MCU distance, not the resistor's | 48.1 mm | 9.4 mm |
| U701 | SHT40 in-box humidity / temperature sensor: 3 mm from the south board edge, 28 mm from the charger U301 (heat), 1.0 mm from its decoupling cap C701 and 3.5-4.3 mm from U403 on the I2C bus; the audit's saving is towards far I2C partners | 8.8 mm | 7.2 mm |
| R213 | LCD_DC series source termination at the driver (5.3 mm from U8.5), like RN201-RN203; the 25 mm run to J4.11 is the MCU-to-display distance | 30.2 mm | 6.1 mm |
| R54 | I2C_SDA pull-up at the MCU bus end (3.8 mm from U8.96), 48 mm from U11 (self-heating rule >= 5 mm); the saving is 4.6 mm | 6.8 mm | 4.6 mm |
| R907 | +3V3_SD 1 ohm isolation resistor at the load end (1.1 mm from U901.17), so the filtered node with C62 stays local to the SD socket; the +3V3_D side is the feed | 11.6 mm | 4.2 mm |
| TP306 | pogo test pad on USB_DM: position set by the display frame / pogo dongle mechanics; it sits on the D- route 5.2 mm from J10.A7, no stub | 5.2 mm | 5.2 mm |
| R53 | I2C_SCL pull-up at the MCU bus end (3.2 mm from U8.95), 41 mm from U11 (self-heating rule >= 5 mm); the saving is 3.7 mm | 6.5 mm | 4.2 mm |
| R210 | Q201 gate resistor of the slow backlight high-side switch, 1.5 mm from R209 and 2.9 mm from Q201.1; the 3.7 mm saving would re-route a finished cluster | 6.3 mm | 3.0 mm |
| C301 | VBUS 1 uF hot-plug cap 3.8 mm from J10.A9 / B4, inside its 5 mm datasheet budget, with D301; the audit's spot is not copper-legal (query.py free --copper: nearest legal spot 7.8 mm from it) | 3.8 mm | 3.7 mm |
| U11 | TMP117: measures the board temperature at the RF / analog section (drift checks), so it sits there on purpose | 87.9 mm | 72.8 mm |
| RN201 | LCD bus series source termination: belongs at U8 (source end) | 69.3 mm | 4.3 mm |
| RN202 | LCD bus series source termination: belongs at U8 (source end) | 146.9 mm | 2.2 mm |
| C902 | REF5030 VIN 100 nF: the nearest part to U5 pin 2 (2.10 mm against 2.0 mm, 0.1 mm over); GND pad in the F.Cu GND fill plus a GND via 1.09 mm away (datasheet 9.3: as close as possible) | 2.0 mm | 2.0 mm |
| C309 | BQ25798 PMID 0.1 uF at the south end of U301's west pin column, courtyard touching U301's (closest legal pose), on F.Cu with a GND via in the pad and a 0.5 mm feed, as in TI Fig. 8-21. 1.69 mm pad gap against 1.5 mm EMC practice (datasheet: 'on top of the IC, short traces') | 1.6 mm | 1.5 mm |
| C318 | BQ25798 SYS 0.1 uF at the north end of U301's west pin column (pins 25-29 at x 143.10), on F.Cu with a GND via in the pad and a 0.5 mm feed, as in TI Fig. 8-21. SW1 / SW2 (pins 26 / 28) leave west between C318 and C309, so the cap cannot sit beside pin 25. 2.29 mm pad gap; the 0.6 mm courtyard slack left would give 1.69 mm, still over the 1.5 mm, which is EMC practice, not a datasheet number | 1.2 mm | 1.2 mm |

## Over the datasheet distance budget

| Part | Sensitivity | Anchor | Gap / max (mm) |
|---|---|---|---|

## Longest connections (> 12 mm)

| Net | From | To | Length | Routed | Cheapest end to move |
|---|---|---|---|---|---|
| EXP_MISO_MCU | U8.53 | R423.1 | 48.04 | **open** | R423 |
| EXP_CS0_N_MCU | U8.51 | R425.1 | 48.03 | **open** | R425 |
| EXP_CS1_N_MCU | U8.55 | R427.1 | 46.59 | **open** | R427 |
| EXP_3V3_EN | U8.45 | U401.3 | 45.65 | yes | U401 |
| NRST | J6.3 | U8.14 | 45.17 | **open** | U8 |
| I2C_SDA | U8.96 | U11.6 | 44.72 | yes | U11 |
| EXP_VHP_SNS | U8.17 | R412.2 | 43.84 | **open** | R412 |
| EXP_3V3_SNS | U8.18 | R414.2 | 43.72 | **open** | R414 |
| EXP_SPI_SCK | J11.5 | R419.2 | 43.64 | **open** | R419 |
| EXP_GATE | J11.33 | R433.2 | 42.93 | **open** | R433 |
| EXP_SPI_MOSI | J11.7 | R421.2 | 42.77 | **open** | R421 |
| I2C_SCL | R53.1 | U11.1 | 42.26 | yes | R53 |
| SWDIO | J6.2 | U8.72 | 41.37 | yes | U8 |
| MARK_N | SW2.1 | R47.2 | 40.66 | **open** | R47 |
| RECORD_N | SW1.1 | R46.2 | 39.94 | **open** | R46 |
| SWCLK | J6.4 | U8.76 | 38.25 | yes | U8 |
| LCD_D7 | J4.29 | RN202.5 | 36.94 | **open** | RN202 |
| LCD_D6 | J4.28 | RN202.6 | 36.32 | **open** | RN202 |
| TP_SDA | R42.2 | U8.47 | 35.84 | yes | R42 |
| LCD_D5 | J4.27 | RN202.7 | 35.7 | **open** | RN202 |
| TP_SCL | J8.3 | U8.46 | 35.7 | **open** | U8 |
| LCD_D4 | J4.26 | RN202.8 | 35.08 | **open** | RN202 |
| EXP_INT1_N_MCU | U8.57 | RN401.1 | 34.77 | **open** | RN401 |
| EXP_INT0_N_MCU | U8.56 | R426.1 | 33.95 | yes | R426 |
| EXP_RST_N_MCU | U8.91 | R431.1 | 33.61 | **open** | R431 |
| QON_N | U301.12 | SW5.2 | 33.33 | **open** | U301 |
| LCD_D1 | J4.23 | RN201.7 | 33.24 | **open** | RN201 |
| EXP_TMR1 | D404.9 | R424.2 | 32.92 | yes | R424 |
| EXP_SYNC | J11.35 | R434.2 | 32.61 | **open** | R434 |
| LCD_D0 | J4.22 | RN201.8 | 32.54 | **open** | RN201 |
| EXP_TMR0 | D404.6 | R420.2 | 30.79 | yes | R420 |
| TP_INT | J8.5 | R906.2 | 30.24 | **open** | R906 |
| TP_RST | J8.6 | R905.2 | 30.07 | yes | R905 |
| EXP_ANA_MON | D406.6 | R435.2 | 29.96 | **open** | R435 |
| I2C_SDA | U301.15 | U701.1 | 29.6 | yes | U701 |
| I2C_SCL | U301.14 | U701.2 | 29.13 | yes | U701 |
| LCD_RST | R51.1 | R904.2 | 27.48 | yes | R51 |
| LCD_BL | U8.63 | R211.1 | 27.38 | **open** | R211 |
| VSYS | C28.1 | U7.4 | 27.31 | yes | C28 |
| LCD_DC | J4.11 | R213.2 | 24.91 | **open** | R213 |
| EXP_VHP_EN | R407.1 | U8.13 | 24.22 | yes | R407 |
| LCD_D2 | J4.24 | RN203.5 | 24.18 | **open** | RN203 |
| +3V3_D | C65.1 | U11.5 | 23.95 | yes | U11 |
| +3V3_UI | C200.2 | R205.1 | 23.83 | yes | R205 |
| LCD_D3 | J4.25 | RN203.7 | 23.44 | **open** | RN203 |
| USB_DM | U301.7 | U8.70 | 23.36 | **open** | U301 |
| EXP_TMR_IN_MCU | U8.77 | R422.1 | 23.14 | yes | R422 |
| USB_DP | U301.6 | U8.71 | 22.74 | **open** | U301 |
| EXP_FAULT_N | U402.6 | U401.4 | 22.65 | yes | U401 |
| EXP_DETECT_N_MCU | U8.90 | RN401.4 | 22.23 | **open** | RN401 |
| LCD_CS_N | J4.10 | RN203.6 | 22.14 | **open** | RN203 |
| UI_EN | U8.33 | Q202.1 | 21.46 | yes | Q202 |
| EXP_IO1_MCU | U8.97 | RN401.3 | 21.37 | **open** | RN401 |
| EXP_IO0_MCU | U8.98 | RN401.2 | 21.27 | **open** | RN401 |
| LCD_WR_N | J4.12 | RN203.8 | 21.25 | **open** | RN203 |
| LCD_LED_K4 | J4.37 | D204.2 | 21.23 | **open** | D204 |
| PSRAM_IO2_RAM | U9.3 | R64.2 | 20.45 | **open** | U9 |
| +3V3_D | J6.1 | U401.1 | 20.23 | yes | U401 |
| BUCK_SYNC | TP900.1 | R901.2 | 20.22 | yes | TP900 |
| VBUS | R303.2 | Q302.1 | 20.09 | yes | R303 |

## Detours

| Net | Pads | Ratsnest | Routed | Ratio |
|---|---|---|---|---|
| EXP_TMR1 | 4 | 35.6 | 85.9 | 2.41 |
| EXP_INT0_N_MCU | 2 | 33.9 | 65.9 | 1.94 |
| TP_RST | 2 | 30.1 | 55.5 | 1.85 |
| SWCLK | 2 | 38.3 | 62.9 | 1.64 |
| EXP_I2C_SDA | 4 | 18.5 | 31.3 | 1.7 |
