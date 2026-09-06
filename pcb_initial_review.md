# PCB INITIAL REVIEW — RFVD_SENSOR_BOARD Rev 1

**Project:** RF-Induced Voltage Detector for AIMD MR Safety Analysis
**Board:** `RFVD_SENSOR_BOARD`, folder `Hardware/RFVD_SENSOR_BOARD_Rev1`
**Design tool:** KiCad 10.0 (file format 20260206)
**Review date:** 6 September 2026
**Review type:** Read only. This review does not change the design files.

---

## 1. ABOUT THIS DOCUMENT

### 1.1 Purpose

This document gives the results of an initial review of the printed circuit board (PCB).
The review examined the schematic files, the PCB file, and the manufacture data.
The review compared the design to the data sheet of each component.

### 1.2 Language

This document uses the ASD-STE100 Simplified Technical English writing rules.
Sentences are short. Each sentence gives one item of information.
The document uses the active voice. The document uses one term for one meaning.

### 1.3 Severity categories

| Category | Name | Meaning |
|---|---|---|
| **1** | STOP | The board does not operate. Or the board becomes unserviceable. Correct this before you order parts or boards. |
| **2** | CORRECT | The board operates. But the board does not obey a requirement or a data sheet limit. Correct this before manufacture. |
| **3** | ADVISORY | The board operates correctly. An improvement is possible. |
| **4** | QUESTION | The review cannot tell if the design is correct. The designer must answer. |

### 1.4 Source of the data

The review read the netlist from the PCB file. The PCB file holds the connection of each pad.
This data is the data that the manufacturer receives. Therefore this data is correct.
Section 8 gives the data sheet of each component.
Section 9 gives the checks that this review did not do.

---

## 2. SUMMARY OF THE FINDINGS

| No. | Category | Item | Subject |
|---|---|---|---|
| F-01 | **1 STOP** | U5 | The regulator has a fixed 5 V output. The circuit uses a feedback divider. |
| F-02 | **1 STOP** | U5 | The symbol name, the ordered part, and the circuit do not agree. |
| F-03 | **2** | R1, R2 | The measurement accuracy depends on an internal impedance of U1. |
| F-04 | **2** | U1, U2, U12 | The chain saturates at about 12 V. The requirement is 14 V. |
| F-05 | **2** | J2, F1, D2 | The battery tracks are 0.15 mm wide. The tracks carry all the board current. |
| F-06 | **2** | Y1 | The oscillator has no local bypass capacitor. |
| F-07 | **2** | U11 | The buffer has no local bypass capacitor. |
| F-08 | **2** | U1 | The exposed pad has no ground via. |
| F-09 | **2** | U5 | The ground pad has no thermal via. |
| F-10 | **2** | Project | The PCB file has no stackup definition. |
| F-11 | **3** | U4 | The input capacitor is 5.33 mm from the input pin. |
| F-12 | **3** | Board | The ground stitch vias are few. The RF area has 18 vias. |
| F-13 | **3** | U5 | The inductor L1 is too large for a 2.2 MHz regulator. |
| F-14 | **3** | J7 | The trigger input has no 50 Ω termination. |
| F-15 | **3** | L1 | The part is an XGL5030. The footprint is an XAL5030. |
| F-16 | **3** | U2, U12 | The analog supply comes from the switched rail through a ferrite bead. |
| Q-01 | **4** | Firmware | What is the ADC sample rate? |
| Q-02 | **4** | U5 | Is the forced PWM mode intentional? |
| Q-03 | **4** | R85 | Is the value 2.15 kΩ intentional? |
| Q-04 | **4** | U1 | Why does the design measure the envelope and not the RMS value? |
| Q-05 | **4** | U13 | Does the firmware obey the 8 µs refresh limit? |
| Q-06 | **4** | H1 to H4 | Must the mounting holes connect to ground? |
| Q-07 | **4** | C2 | Is the 100 pF capacitor on FLT1 necessary? |

Section 7 gives the parts of the design that are correct. The design has much good work.

---

## 3. DESCRIPTION OF THE BOARD

### 3.1 Function

The board measures the radio frequency (RF) voltage that an MRI scanner induces on the lead of an active implantable medical device.
The board detects the RF envelope. The board converts the envelope to a digital value.
The board shows the value on a display. The board records the value on a memory card.

### 3.2 Physical data

| Item | Value |
|---|---|
| Board size | 100.0 mm × 70.0 mm |
| Corner radius | 3.0 mm |
| Board thickness | 1.6 mm |
| Copper layers | 4 |
| Layer names | F.Cu, In1.Cu, In2.Cu, B.Cu |
| Ground planes | In1.Cu and In2.Cu are continuous ground planes |
| Components | 189 |
| Tracks | 1643 |
| Vias | 267 (one size: 0.65 mm pad, 0.30 mm drill) |
| Mounting holes | 4, diameter 3.2 mm |

The zone data shows one fill polygon on In1.Cu and one fill polygon on In2.Cu.
Therefore both internal planes are continuous. This is correct for an RF board.

### 3.3 Schematic sheets

The design has ten schematic sheets.

| Sheet | Function |
|---|---|
| `RFVD_SENSOR_BOARD` | The root sheet. The root sheet holds the other sheets. |
| `RF_Input` | The input connector, the attenuator, the protection diode, and the detector U1. |
| `Analog_Acquisition` | The reference U3 and the anti-alias filters U2 and U12. |
| `Power` | The battery input, the regulator U5, and the regulator U4. |
| `MCU` | The microcontroller U6, the oscillator Y1, and the reset circuit. |
| `Storage` | The memory card J4 and the memory U13. |
| `Display` | The display connector J6 and the power switch U10. |
| `Temperature` | The temperature sensor U7. |
| `Trigger` | The trigger connector J7 and the buffer U11. |
| `Service` | The debug connector J3, the serial connector J5, and the test points. |

### 3.4 Signal path

The signal moves through the board in this sequence:

1. The connector J1 receives the RF signal. J1 is a U.FL coaxial connector.
2. The resistors R1 and R2 attenuate the signal. The total series resistance is 3.00 kΩ.
3. The capacitor C1 gives DC isolation. The value is 470 pF.
4. The diode D1 protects the input. D1 is a 2.5 V transient voltage suppressor.
5. The detector U1 converts the RF signal to two DC voltages. The voltages are VENV and EREF.
6. The filters U2 and U12 remove the frequencies above 100 kHz.
7. The microcontroller U6 measures the two voltages. U6 uses two ADC channels.
8. The firmware subtracts EREF from VENV. This gives the true envelope.

### 3.5 Power tree

```
J2 (2S battery, 6.0 V to 8.4 V)
 └─ F1  PTC fuse, 1.1 A hold, 16 V
     └─ D2  Schottky diode, reverse polarity protection
         └─ BATT_PROT
             ├─ U5  LMR43620 buck regulator ──> +3V3_D (3.3 V digital)
             │                                   ├─ FB1 ferrite bead ──> +3V3_A (3.3 V analog)
             │                                   └─ U10 TPS2553 switch ──> +3V3_UI (3.3 V display)
             └─ U4  LT3045 LDO regulator ─────> +5V_A (5.0 V analog)
                                                 └─ U3 REF5030 ──> +3V0_REF (3.0 V ADC reference)
```

The board has one ground net. The board does not have separate analog and digital ground nets.
Section 7.4 explains why this is correct.

---

## 4. CATEGORY 1 FINDINGS — STOP

### F-01 — The regulator U5 has a fixed output. The circuit uses a feedback divider.

> **CAUTION: DO NOT APPLY POWER TO A BOARD THAT HAS THIS DEFECT. THE 3.3 V RAIL GOES TO THE BATTERY VOLTAGE. ALL THE 3.3 V COMPONENTS BECOME UNSERVICEABLE.**

**The condition.**
The bill of material gives the part `LMR43620MB5RPER` for U5.
This part has a **fixed 5 V output**. Mouser gives the output voltage as 5 V.
On a fixed output part, pin 8 is the VOUT sense pin.
The feedback divider is inside the component.
The data sheet says that you must connect pin 8 directly to the output rail.

The board connects pin 8 to an external divider:

| Component | Value | Connection |
|---|---|---|
| R64 | 33.2 kΩ | From +3V3_D to pin 8 |
| R65 | 14.3 kΩ | From pin 8 to ground |
| C64 | 22 pF | Parallel with R64 |

**The effect.**
The regulator controls pin 8 to 5.0 V.
The divider ratio is 14.3 / (33.2 + 14.3) = 0.3011.
The output rail must go to 5.0 / 0.3011 = 16.6 V to make pin 8 equal to 5.0 V.
The regulator cannot make more voltage than the input voltage.
Therefore the regulator goes to the maximum duty cycle.
The rail +3V3_D goes to the battery voltage. This is 5.6 V to 8.4 V.

**The damage.**
The table gives the maximum supply voltage from the recommended operating conditions.

| Component | Maximum supply voltage | Applied voltage |
|---|---|---|
| U6 STM32H743VIT6 | 3.6 V | up to 8.4 V |
| U13 APS6404L | 3.6 V | up to 8.4 V |
| J4 microSD card | 3.6 V | up to 8.4 V |
| Y1 oscillator | 3.6 V | up to 8.4 V |
| U7 TMP117 | 5.5 V | up to 8.4 V |
| U11 SN74LVC1G17 | 5.5 V | up to 8.4 V |
| U2, U12 OPA2320 | 5.5 V | up to 8.4 V |
| Display through U10 | — | up to 8.4 V |

**The correction. Use one of these two options.**

**Option A. Keep the divider. Change the component.**
Order the adjustable version of the LMR43620 in the RPE package.
The divider values are already correct.
The reference voltage is 1.0 V. The output is 1.0 × (1 + 33.2 / 14.3) = **3.322 V**.

**Option B. Keep the component family. Remove the divider.**
Order `LMR43620MB3RPER`. This part has a fixed 3.3 V output and a 2 A capability.
Remove R64, R65, and C64.
Connect pin 8 directly to +3V3_D.

**The recommendation.**
Option B is better. Option B has fewer components.
Option B removes the risk of an incorrect resistor value at assembly.
Option B agrees with the name of the symbol in the library.

---

### F-02 — The symbol name, the ordered part, and the circuit do not agree.

**The condition.**
Three different components are present in the design data:

| Source | Part | Meaning |
|---|---|---|
| Symbol name in `RFVD_MVP_Symbols` | `LMR43610MB3RPER` | 1 A, fixed 3.3 V |
| Bill of material and PCB value | `LMR43620MB5RPER` | 2 A, fixed 5 V |
| Circuit connection at pin 8 | — | An adjustable part |

**The effect.**
A symbol with an incorrect name hides the error in F-01.
The next person who reads the schematic sees the name `LMR43610MB3RPER`.
That person expects a fixed 3.3 V part. The board has a fixed 5 V part.

**The correction.**
1. Select the correct component. Refer to F-01.
2. Change the name of the symbol to the correct part number.
3. Put the manufacturer part number in a symbol field.
4. Make sure that the symbol name and the bill of material agree.

---

## 5. CATEGORY 2 FINDINGS — CORRECT BEFORE MANUFACTURE

### F-03 — The measurement accuracy depends on an internal impedance of U1.

**The condition.**
The attenuator has two series resistors. R1 and R2 are 1.50 kΩ, 0.1 %, 25 ppm/°C.
The attenuator has **no shunt resistor**.
Therefore the lower part of the divider is the RFIN input impedance of U1.
The ADL5511 data sheet gives this impedance as **250 Ω nominal**.
The data sheet does not give a tolerance for this impedance.

The ADL5511 data sheet says this:
> "To achieve 50 Ω matching, an external 75 Ω shunt resistor connects between the ac-coupling capacitor source and ground."

The board does not have this shunt resistor.

**The effect on accuracy.**
The division ratio is 250 / (3000 + 250) = 0.07692. This is −22.28 dB.
The table shows the error if the internal impedance changes:

| Internal impedance | Change | Gain error |
|---|---|---|
| 200 Ω | −20 % | −1.80 dB (−19 %) |
| 225 Ω | −10 % | −0.85 dB (−9 %) |
| 250 Ω | nominal | 0.00 dB |
| 275 Ω | +10 % | +0.76 dB (+9 %) |
| 300 Ω | +20 % | +1.45 dB (+18 %) |

The requirement gives a precision of ±0.1 V on a range of 0.5 V to 14 V.
At 14 V this is ±0.7 %. At 0.5 V this is ±20 %.
A gain error of ±18 % is much larger than the requirement.
The 0.1 % resistors give no advantage, because an untrimmed internal impedance sets the ratio.

**The effect on the RF match.**
The input impedance at J1 is about 3.25 kΩ. The cable impedance is 50 Ω.
The reflection coefficient is 0.97. The voltage standing wave ratio is about 65.
The measured value changes with the cable length at 64 MHz and at 128 MHz.

**The correction.**
1. Add the 75 Ω shunt resistor. Put the resistor between C1 and ground.
2. Or, make a resistive pad with discrete resistors. The pad sets the ratio.
3. Calculate the new level plan. Refer to F-04. One change can correct both findings.
4. Calibrate each board through the inject port.

---

### F-04 — The signal chain saturates at about 12 V. The requirement is 14 V.

**The condition.**
The ADL5511 gives a VENV output of 0 V to 3.5 V.
The EREF output is 1.1 V nominal.
The conversion gain is 1.46 V/V at 900 MHz.

The operational amplifiers U2 and U12 use the +3V3_A rail. The rail is 3.3 V.
The OPA2320 common mode input limit is (V+) + 0.1 V. This is 3.4 V.
The ADC reference is +3V0_REF. The value is 3.000 V.
Therefore the ADC full scale is 3.000 V.

**The calculation.**

| Input at J1 | Peak at RFIN | VENV | Result |
|---|---|---|---|
| 0.5 V rms | 54 mV | 1.179 V | Correct |
| 5.0 V rms | 544 mV | 1.894 V | Correct |
| 12.0 V rms | 1306 mV | 3.006 V | At the ADC limit |
| 14.0 V rms | 1523 mV | 3.324 V | Above the ADC limit |

The chain saturates at about **11.96 V rms**.
The requirement is 14 V. Therefore the board loses the top 15 % of the range.

**The safety of the components.**
The OPA2320 absolute maximum input is (V+) + 0.5 V. This is 3.8 V.
The maximum VENV is 3.5 V. Therefore the amplifier does not become unserviceable.
The resistor R80 limits the input current to about 44 µA. The limit is 10 mA.
The components are safe. But the measurement is not correct above 12 V.

**The correction. Use one of these options.**
1. **Increase the attenuation.** Make the full scale of 14 V equal to about 2.8 V at VENV. This option also corrects F-03.
2. **Change the amplifier supply to +5V_A.** Then add a divider before the ADC.
3. **Increase the ADC reference to 3.3 V.** This option decreases the accuracy of the reference.

Option 1 is the best option. One change corrects F-03 and F-04.

**A caution about the calculation.**
The conversion gain of 1.46 V/V is a value at 900 MHz.
The gain at 64 MHz and at 128 MHz can be different.
Measure the gain on the first board. Then set the attenuation.

---

### F-05 — The battery tracks are too narrow.

**The condition.**
The track widths on the battery input path are:

| Net | Path | Width |
|---|---|---|
| `Net-(J2-Pin_1)` | J2 to F1 | **0.15 mm** |
| `Net-(D2-A)` | F1 to D2 | **0.15 mm** |
| `BATT_PROT` | D2 to the regulators | 0.80 mm |

These two tracks carry all the current of the board.

**The effect.**
The IPC-2221 formula gives the current for a 10 °C temperature increase.
A 0.15 mm track on 35 µm copper gives about **0.6 A**.
The fuse F1 holds at 1.1 A. The fuse trips at about 2.2 A.
Therefore the track carries more current than its rating before the fuse operates.
The track becomes the fuse.

**The correction.**
Increase the width of both tracks to 0.80 mm. Use the same width as BATT_PROT.
This change is easy. The two tracks are short. The total length is 11.9 mm.

---

### F-06 — The oscillator Y1 has no local bypass capacitor.

**The condition.**
The oscillator Y1 is an Abracon ASE-8.000MHZ-L-C-T.
Pin 4 is the supply pin. The rail is +3V3_D.
The nearest capacitor on +3V3_D is C28. The distance is **7.53 mm**.
C28 is a decoupling capacitor for the microcontroller U6.
Therefore Y1 has no local bypass capacitor.

**The effect.**
The oscillator output has more jitter.
The oscillator puts switch noise on the +3V3_D rail.
The oscillator gives the clock to the ADC. Clock jitter increases the measurement noise.

**The correction.**
Add a 100 nF capacitor. Put the capacitor within 2 mm of pin 4.
Connect the capacitor to ground with a via.

---

### F-07 — The buffer U11 has no local bypass capacitor.

**The condition.**
U11 is an SN74LVC1G17 Schmitt trigger buffer. Pin 5 is the supply pin.
The nearest capacitor on +3V3_D is C44. The distance is **5.53 mm**.

**The effect.**
U11 buffers the trigger signal from J7.
The output edge causes a current pulse. The pulse has no local capacitor.
This causes ground bounce and output ringing.
The trigger sets the time reference for the record. Jitter here corrupts the time stamp.

**The correction.**
Add a 100 nF capacitor. Put the capacitor within 2 mm of pin 5.

---

### F-08 — The exposed pad of U1 has no ground via.

**The condition.**
U1 is the ADL5511 detector in an LFCSP-16 package.
Pad 17 is the exposed pad. The pad connects to the GND net.
The review counted the vias in the pad. **The count is zero.**
The review counted the ground vias within 2 mm of the pad. **The count is zero.**

**The effect.**
The exposed pad is the RF ground return of the detector.
The pad connects to the ground fill on the top layer only.
The return current must move along the top layer to the nearest via.
This adds inductance to the RF ground. This decreases the detector accuracy.
The pad is also the thermal path. U1 uses 21.5 mA at 5 V.

**The correction.**
Add four to nine vias in the exposed pad. Use a 0.3 mm drill.
This connects the pad to the internal ground planes.

---

### F-09 — The ground pad of U5 has no thermal via.

**The condition.**
U5 is the buck regulator. Pin 9 is the ground pad. The size is 0.35 mm × 1.30 mm.
The review counted the vias in the pad. **The count is zero.**
The review counted the ground vias within 2 mm. **The count is one.**

**The effect.**
The ground pad is the power ground return of a 2 A regulator.
The pad is also the thermal path.
The return current of the switch loop must move through the top layer.
This increases the loop area. This increases the radiated emission.
The board must operate in an MRI room. The board must not corrupt its own measurement.

**The correction.**
Add vias in the ground pad and beside the ground pad.
Refer to the layout section of the LMR43620 data sheet.

---

### F-10 — The PCB file has no stackup definition.

**The condition.**
The `setup` section of the PCB file has no `stackup` block.
Therefore the design does not define these items:
- The dielectric thickness of each layer
- The copper weight of each layer
- The dielectric constant
- The controlled impedance of any track

**The effect.**
The manufacturer uses a default stackup.
The distance from F.Cu to In1.Cu is not known.
The calculation in F-05 assumed 35 µm copper. This assumption is not confirmed.

**The correction.**
Define the stackup in the KiCad board setup.
Give the copper weight. Give the dielectric thickness.
Send the stackup to the manufacturer with the manufacture files.

---

## 6. CATEGORY 3 FINDINGS — ADVISORY

### F-11 — The input capacitor of U4 is far from the input pin.
The nearest capacitor on `BATT_PROT` to pin 1 of U4 is C17. The distance is 5.33 mm.
The LT3045 is an ultralow noise regulator. The rail `BATT_PROT` carries 2.2 MHz ripple from U5.
Move a 1 µF capacitor to within 2 mm of pin 1.

### F-12 — The ground stitch vias are few.
The board has 141 ground vias. The board area is 70 cm².
This gives about 2 vias per cm².
The RF area is the left part of the board. This area has 18 ground vias.
The RF area holds J1, R1, R2, C1, D1, U1, U4, and U7.
An RF board usually has 5 to 15 vias per cm² in the RF area.
Add more vias. Put a line of vias beside the RF track.

### F-13 — The inductor L1 is too large.
The switch frequency of the LMR43620MB5 is 2.2 MHz.
The inductor L1 is 4.7 µH.
The calculated ripple current is 0.18 A. This is 9 % of the 2 A rating.
The usual target is 30 % to 40 %.
Peak current mode control needs a minimum ripple for a stable current loop.
Calculate the inductor again after you select the regulator variant. Refer to F-01.
The result is near 1.0 µH to 2.2 µH.

### F-14 — The trigger input has no 50 Ω termination.
J7 is a BNC connector. The input goes through R60 (330 Ω) to R61 (100 kΩ).
The division is 0.33 %. Therefore the divider gives almost no attenuation.
The input impedance is about 100 kΩ. The cable impedance is 50 Ω.
A fast trigger edge causes reflection and ringing on the cable.
Add a footprint for a 50 Ω resistor to ground. Do not fit the resistor by default.
This lets the user select the termination.

### F-15 — The inductor part and the footprint are from different series.
The bill of material gives `XGL5030-472MEC`. This is a Coilcraft XGL5030 series part.
The footprint is `Inductor_SMD:L_Coilcraft_XAL5030-XXX`. This is the XAL5030 land pattern.
The footprint pads are 1.18 mm × 4.70 mm. The pad pitch is 3.31 mm.
Both series use the 5030 case size. The land patterns are probably the same.
This review could not confirm this from the Coilcraft data.
Compare the XGL5030 land pattern to the footprint before manufacture.

### F-16 — The analog supply comes from the switched rail.
The rail +3V3_A comes from +3V3_D through the ferrite bead FB1.
+3V3_D is the output of the switch regulator U5.
The board has an ultralow noise regulator U4. But U4 makes only the +5V_A rail.
The amplifiers U2 and U12 are the precision part of the chain. They use +3V3_A.
The PSRR of the OPA2320 decreases at high frequency.
Consider a second low noise regulator. Make +3V3_A from +5V_A.

---

## 7. WHAT IS CORRECT

This section records the parts of the design that this review confirmed as correct.
The design shows much careful work.

### 7.1 The microcontroller pin assignment is correct.
The review compared each pin to the STM32H743VI LQFP-100 pin list.

- The QuadSPI signals all use Bank 1. PB2 is CLK. PB6 is NCS. PD11, PD12, PE2, and PD13 are IO0 to IO3.
- The SDMMC1 signals are correct. PC8 to PC12 and PD2 are the correct pins.
- The ADC inputs are PA6 and PC4. Both pins connect to ADC1 and ADC2.
  Therefore the firmware can sample VENV and EREF at the same time. This is important for the subtraction.
- PA0 is the trigger input. PA0 has a timer input capture function.
- PC6 is the backlight output. PC6 has a timer PWM function.
- The oscillator uses PH0 only. PH1 is free. This is correct for an external oscillator in bypass mode.
- The two VCAP pins have 2.2 µF capacitors. This obeys the STM32H7 requirement.
- Each of the five VDD pins has a 100 nF capacitor within 1.84 mm to 2.20 mm.
- VREF+ has a 100 nF capacitor at 2.14 mm. VDDA has a 100 nF capacitor at 2.62 mm.

### 7.2 The detector filter pins are correct.
The ADL5511 has two types of filter pin. This is easy to get wrong. The design is correct.

| Pin | Type | Capacitor | Reference | Result |
|---|---|---|---|---|
| FLT1 (3) | Ground referenced | C2, 100 pF | GND | Correct |
| FLT2 (16) | Supply referenced | C3, 1 nF | +5V_A | Correct |
| FLT3 (1) | Supply referenced | C4, 1 nF | +5V_A | Correct |
| FLT4 (14) | Supply referenced | C5, 100 nF | +5V_A | Correct |

The FLT4 capacitor sets the RMS average filter. The data sheet gives 47 nF to 220 nF. C5 is 100 nF.

### 7.3 The temperature sensor thermal pad is correct.
The TMP117 data sheet says this:
> "the thermal pad is not connected to the device ground and should be left unsoldered for best measurement accuracy."

The footprint name is `TMP117_DRV_WSON6_NoPasteEP`.
The pad has copper and a mask opening. The pad has **no paste layer**.
The pad has no net. Therefore the pad is free.
This obeys the data sheet exactly.

### 7.4 The ground system is correct.
The board has one ground net. The report describes separate analog and digital grounds.
The board design is better than the report.
One continuous ground plane gives a lower impedance return than two split planes.
A split plane makes a slot. A signal that crosses a slot makes a large loop.
The board has a continuous plane on In1.Cu and on In2.Cu.
The test points TP11, TP12, and TP13 let you measure the ground shift at three positions.

### 7.5 The linear regulator U4 is correct.
The review compared each pin to the LT3045 MSOP-12 pin list.

| Pin | Function | Connection | Result |
|---|---|---|---|
| 1, 2, 3 | IN | BATT_PROT | Correct |
| 4 | EN/UV | BATT_PROT | Correct. The data sheet permits this. |
| 5 | PG | Free | Correct. The function is not used. |
| 6 | ILIM | R17, 1 kΩ to ground | Correct. The limit is 150 mA. |
| 7 | PGFB | BATT_PROT | Correct. The data sheet permits this. |
| 8 | SET | R16, 49.9 kΩ, and C19 | Correct. 100 µA × 49.9 kΩ = 4.99 V. |
| 9, 13 | GND | GND | Correct |
| 10 | OUTS | +5V_A | Correct |
| 11, 12 | OUT | +5V_A | Correct |

The LT3045 data sheet says this about pin 7:
> "Tie PGFB to IN if power good and fast start-up functionalities are not needed."

The output capacitance is more than 10 µF. This obeys the data sheet.

### 7.6 The detector enable circuit is correct.
U9 is a TLV809EA46DBZR. The threshold is 4.63 V. The delay is 200 ms.
The output is push-pull and active low. Therefore the output needs no pull-up resistor.
U9 monitors +5V_A. The output goes to the ENBL pin of U1.
The ADL5511 needs 3.6 V minimum to enable. The output high level is about 4.99 V.
Therefore the detector starts 200 ms after the analog rail is correct.
This prevents an incorrect measurement at power on.

### 7.7 The memory card circuit is correct.
- Each fast signal has a 33 Ω series resistor. R30, R34, and R43 to R46.
- Each data signal has a 47 kΩ pull-up resistor. R25 to R29.
- The pull-up resistors connect on the card side of the series resistors. This is the correct position.
- Each card signal has an ESD diode. D8 to D14.
- The card detect signal has a pull-up resistor R31 and an ESD diode D14.

### 7.8 The memory U13 pin assignment is correct.
The review compared each pin to the APS6404L SOP-8 pin list. All eight pins are correct.
The supply range is 2.7 V to 3.6 V. The rail is +3V3_D. This is correct.

### 7.9 The display power switch is correct.
U10 is a TPS2553DBVR. The enable input is active high.
R52 is a 100 kΩ pull-down resistor. Therefore the display rail is off at reset.
R51 is 66.5 kΩ. The formula gives 23950 / 66.5 = **360 mA** current limit.
The permitted resistor range is 15 kΩ to 232 kΩ. 66.5 kΩ is inside the range.
The fault output is open drain. R53 is the pull-up resistor.
The touch panel pull-up resistors R54 and R55 connect to +3V3_UI.
Therefore the touch panel does not receive power when the display rail is off.

### 7.10 The trigger protection is correct.
D7 is a TPD1E10B06. The working voltage is 5.5 V. The breakdown voltage is 6 V minimum.
U11 has an absolute maximum input of 6.5 V. The inputs accept 5.5 V with a 3.3 V supply.
Therefore the diode operates before the buffer input limit.
At 1 A the diode clamps at 10 V. R60 is 330 Ω.
The current into the buffer input clamp is (10 − 6.5) / 330 = 10.6 mA.
The buffer limit is 50 mA. Therefore the protection is correct.
A 5 V trigger signal operates correctly.

### 7.11 The voltage reference is correct.
U3 is a REF5030IDR. The pin assignment is correct.
The output capacitance is 1.2 µF. The data sheet permits 1 µF to 50 µF.
C12 is a 1 µF capacitor on the TRIM/NR pin. The data sheet says that this decreases the noise by half.
R15 (1 Ω) and C13 (4.7 µF) make a damping network to ground.
This network does not carry the load current. The network is a good addition.

### 7.12 The RF protection diode is correct.
D1 is a PESD2V5Y1BSF. The capacitance is 0.3 pF maximum.
This is a very low capacitance. Therefore the diode does not change the RF response.
The maximum peak signal at RFIN is 1.52 V. The diode working voltage is 2.5 V.
Therefore the diode does not clip the signal.

### 7.13 The anti-alias filter design is good.
The filter is two Sallen-Key sections and one RC section.

| Section | Components | f₀ | Q |
|---|---|---|---|
| VENV stage 1 | R80, R81, C80, C81 | 143.8 kHz | 0.521 |
| VENV stage 2 | R82, R83, C82, C83 | 159.3 kHz | 0.799 |
| ADC RC | R84, C84 | 10.3 MHz | — |

The composite −3 dB frequency is **99.3 kHz**.
The amplifiers use the unity gain buffer configuration. This is the correct topology.

### 7.14 Other correct items.
- The exposed pad of U1 has four paste openings. The paste coverage is 64 %. This is correct QFN practice.
- The reset circuit has a 10 kΩ pull-up resistor, a 100 nF capacitor, and a switch.
- BOOT0 has a 10 kΩ pull-down resistor and a header. This is correct.
- The status LED sinks current from the microcontroller. R22 sets 1.2 mA. This is a low power design.
- The battery sense divider gives 1.4 V at 8.4 V. This is inside the 3.0 V reference.
- The board has 15 test points. The test points cover every rail and every analog node.

---

## 8. PARTS LIST AND DATA SHEETS

### 8.1 Integrated circuits and active components

| Ref | Part | Manufacturer | Function | Key data | Data sheet |
|---|---|---|---|---|---|
| U1 | ADL5511ACPZ-R7 | Analog Devices | RF envelope and RMS detector | DC to 6 GHz. RFIN 250 Ω. Supply 4.75–5.25 V, 21.5 mA. VENV 0–3.5 V. EREF 1.1 V. Max input +17 dBm. ENBL high ≥3.6 V. | [PDF](https://www.analog.com/media/en/technical-documentation/data-sheets/ADL5511.pdf) |
| U2, U12 | OPA2320AQDGKRQ1 | Texas Instruments | Precision amplifier | Supply 1.8–5.5 V, max 6 V. Input limit (V−)−0.5 to (V+)+0.5 V. Common mode (V−)−0.1 to (V+)+0.1 V. 20 MHz. 7 nV/√Hz. | [PDF](https://www.ti.com/lit/ds/symlink/opa2320-q1.pdf) |
| U3 | REF5030IDR | Texas Instruments | 3.0 V voltage reference | VIN 3.2–18 V. Output ±10 mA. Load capacitor 1–50 µF, ESR ≤1.5 Ω. | [PDF](https://www.ti.com/lit/ds/symlink/ref50.pdf) |
| U4 | LT3045EMSE#PBF | Analog Devices | Ultralow noise LDO | 20 V, 500 mA. VOUT = 100 µA × RSET. ILIM = 150 mA·kΩ / RILIM. Dropout 260 mV at 500 mA. | [PDF](https://www.analog.com/media/en/technical-documentation/data-sheets/LT3045.pdf) |
| U5 | LMR43620MB5RPER | Texas Instruments | Buck regulator | **Fixed 5 V**, 2 A, 2.2 MHz. VIN 3–36 V. EN max 42 V. VCC cap 1 µF. BOOT cap 100 nF. See **F-01**. | [PDF](https://www.ti.com/lit/ds/symlink/lmr43620.pdf) |
| U6 | STM32H743VIT6 | STMicroelectronics | Microcontroller | Cortex-M7. LQFP-100. VDD 1.62–3.6 V. Two VCAP capacitors. | [PDF](https://www.st.com/resource/en/datasheet/stm32h743vi.pdf) |
| U7 | TMP117MAIDRVR | Texas Instruments | Temperature sensor | 1.7–5.5 V, max 6 V. ±0.2 °C. Address 0x48 with ADD0 to ground. Thermal pad free. | [PDF](https://www.ti.com/lit/ds/symlink/tmp117.pdf) |
| U9 | TLV809EA46DBZR | Texas Instruments | Voltage supervisor | Threshold 4.63 V. Push-pull, active low. Delay 200 ms. | [PDF](https://www.ti.com/lit/ds/symlink/tlv803e.pdf) |
| U10 | TPS2553DBVR | Texas Instruments | Current limit switch | 2.5–6.5 V. EN active high. IOS = 23950 / RILIM(kΩ). FAULT open drain. | [PDF](https://www.ti.com/lit/ds/symlink/tps2553.pdf) |
| U11 | SN74LVC1G17DBVR | Texas Instruments | Schmitt trigger buffer | VCC 1.65–5.5 V. Input max 6.5 V. Inputs accept 5.5 V. VT+ 1.48–1.92 V. | [PDF](https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf) |
| U13 | APS6404L-3SQR-SN | AP Memory | QSPI PSRAM, 64 Mbit | VDD 2.7–3.6 V, max 4.0 V. 109 MHz at 3.3 V. **tCEM 8 µs maximum.** | [PDF](https://www.mouser.com/datasheet/2/1127/APM_PSRAM_QSPI_APS6404L_3SQN_v2_3_PKG-1954905.pdf) |
| Y1 | ASE-8.000MHZ-L-C-T | Abracon | 8 MHz oscillator | 3.3 V CMOS. Pin 1 enable. Pin 4 supply. | [Digi-Key](https://www.digikey.com/en/products/detail/abracon-llc/ASE-8-000MHZ-L-C-T/1236874) |

### 8.2 Protection, magnetic, and discrete components

| Ref | Part | Manufacturer | Function | Key data | Data sheet |
|---|---|---|---|---|---|
| D1 | PESD2V5Y1BSFYL | Nexperia | RF ESD protection | ±2.5 V working. 0.3 pF max. ±15 kV IEC 61000-4-2. Bidirectional. | [PDF](https://assets.nexperia.com/documents/data-sheet/PESD2V5Y1BSF.pdf) |
| D2 | PMEG6030EP,115 | Nexperia | Reverse polarity diode | 60 V, 3 A Schottky. | [JLCPCB](https://jlcpcb.com/partdetail/C456127) |
| D7 | TPD1E10B06DYAR | Texas Instruments | Trigger ESD protection | ±5.5 V working. 6 V breakdown. 12 pF. Bidirectional. | [PDF](https://www.ti.com/lit/ds/symlink/tpd1e10b06.pdf) |
| D8–D14 | PESD5V0U1UL,315 | Nexperia | Card ESD protection | 5 V, 2 pF. | [JLCPCB](https://jlcpcb.com/partdetail/C85401) |
| D3 | LTST-C190KGKT | Lite-On | Green status LED | 0603. | [JLCPCB](https://jlcpcb.com/partdetail/C125094) |
| F1 | MF-MSMF110/16-2 | Bourns | PTC fuse | 1.1 A hold, 16 V. | [JLCPCB](https://jlcpcb.com/partdetail/C210834) |
| FB1 | BLM18AG601SN1D | Murata | Ferrite bead | 600 Ω at 100 MHz, 500 mA. | [JLCPCB](https://jlcpcb.com/partdetail/C19330) |
| L1 | XGL5030-472MEC | Coilcraft | Buck inductor | 4.7 µH ±20 %. DCR 24.5 mΩ max. Isat 3.1 A. Irms 8.5 A. See **F-13**, **F-15**. | [Coilcraft](https://www.coilcraft.com/getmedia/e64ac115-95f2-45c7-b798-1b3769b91583/xgl5030.pdf) |

### 8.3 Connectors and switches

| Ref | Part | Manufacturer | Function | Data sheet |
|---|---|---|---|---|
| J1 | U.FL-R-SMT-1(01) | Hirose | RF input connector | [Digi-Key](https://www.digikey.com/en/products/detail/hirose-electric-co-ltd/U-FL-R-SMT-1-01/3978494) |
| J2 | B2B-PH-K-S(LF)(SN) | JST | Battery connector, 2 way | [JLCPCB](https://jlcpcb.com/partdetail/C131337) |
| J3 | TC2030-NL | Tag-Connect | SWD debug, not fitted | — |
| J4 | DM3AT-SF-PEJM5 | Hirose | microSD card socket | [JLCPCB](https://jlcpcb.com/partdetail/C114218) |
| J5 | TSW-106-07-G-S | Samtec | Serial and recovery header | [Digi-Key](https://www.digikey.com/en/products/detail/samtec-inc/TSW-106-07-G-S/1101321) |
| J6 | TSW-108-07-G-D | Samtec | Display harness, 2×8 | [Mouser](https://www.mouser.com/en/ProductDetail/Samtec/TSW-108-07-G-D) |
| J7 | 031-5539 | Amphenol RF | BNC trigger connector | [Digi-Key](https://www.digikey.com/en/products/detail/amphenol-rf/031-5539/252798) |
| JP1 | TSW-102-07-G-S | Samtec | BOOT0 header | [JLCPCB](https://jlcpcb.com/partdetail/C7402729) |
| SW1–SW3 | B3U-1000P | Omron | Reset, record, mark switches | [JLCPCB](https://jlcpcb.com/partdetail/C231329) |

### 8.4 Precision passive components

| Ref | Value | Part | Function |
|---|---|---|---|
| R1, R2 | 1.50 kΩ 0.1 % 25 ppm | ERA-2AEB152X | RF attenuator. See **F-03**. |
| R16 | 49.9 kΩ 0.1 % 25 ppm | ERA3AEB4992V | LT3045 output set. Gives 4.99 V. |
| R35 | 100 kΩ 0.1 % | ERA-3AEB104V | Battery sense divider, upper |
| R36 | 20.0 kΩ 0.1 % | ERA3AEB203V | Battery sense divider, lower |
| R80, R81, R86 | 2.26 kΩ | RT0603BRD072K26L | Filter stage 1 |
| R85 | 2.15 kΩ | RT0603BRD072K15L | Filter stage 1, EREF. See **Q-03**. |
| R82, R83, R87, R88 | 1.33 kΩ | RT0603BRD071K33L | Filter stage 2 |
| R84, R89 | 47 Ω | RT0603BRD0747RL | ADC series resistor |
| C19 | 470 nF film | 35MU474KA13216 | LT3045 SET capacitor |

The complete bill of material has 76 lines and **75 unique part numbers**.
The file `manufacturing/SENSOR_C_REVIEW/SENSOR_C_ASSEMBLY_BOM.csv` gives the full list.

### 8.5 The bill of material agrees with the board.

The review compared the bill of material to the PCB file.

| Item | Count |
|---|---|
| Footprints on the board | 189 |
| Excluded from the bill of material | 21 (H1–H4, 16 test points, J3 not fitted) |
| Fitted components | 168 |
| Sum of the quantities in the bill of material | **168** |
| Reference designators on the board but not in the bill of material | **None** |
| Reference designators in the bill of material but not on the board | **None** |

Therefore the bill of material is complete and correct.
Each fitted component has a manufacturer part number and a supplier link.

---

## 9. QUESTIONS FOR THE DESIGNER

### Q-01 — What is the ADC sample rate?
The anti-alias filter has a −3 dB frequency of 99.3 kHz.
The report gives a sample rate requirement of 20 kS/s or more.
The table shows the filter attenuation at the Nyquist frequency:

| Sample rate | Nyquist | Attenuation |
|---|---|---|
| 20 kS/s | 10 kHz | **−0.03 dB** |
| 100 kS/s | 50 kHz | −0.71 dB |
| 500 kS/s | 250 kHz | −19.6 dB |
| 1 MS/s | 500 kHz | −42.0 dB |
| 2 MS/s | 1 MHz | −65.7 dB |

At 20 kS/s the filter gives no protection.
Every frequency between 10 kHz and 100 kHz folds into the measurement band.
The filter design needs a sample rate of 500 kS/s or more.
**The hardware and the written requirement do not agree.**
Give the sample rate in the firmware. Then correct the requirement document or the filter.

### Q-02 — Is the forced PWM mode intentional?
Pin 1 of U5 is the MODE/SYNC pin. The pin connects to VCC.
This selects the forced PWM mode. The regulator switches at a constant frequency at all loads.
This is good for an RF instrument, because the switch frequency stays at a known value.
This is bad for the 8 hour battery requirement, because the light load efficiency decreases.
Was this choice intentional?

### Q-03 — Is the value of R85 intentional?
R80 is 2.26 kΩ in the VENV channel. R85 is 2.15 kΩ in the EREF channel.
The other resistors in the two channels are equal.
This changes the corner frequency of the first stage:

| Channel | f₀ | Q |
|---|---|---|
| VENV stage 1 | 143.84 kHz | 0.521 |
| EREF stage 1 | 147.47 kHz | 0.521 |

**The effect in the measurement band is very small.**
At 20 kHz the difference between the two channels is 0.007 dB.
At 100 kHz the difference is 0.13 dB.
Therefore this is not a defect. But 2.15 kΩ and 2.26 kΩ are adjacent E96 values.
Did you select 2.15 kΩ for a reason? Or is this a selection error?

### Q-04 — Why does the design measure the envelope and not the RMS value?
The ADL5511 gives an RMS output on pin 11. The net is `VRMS_DIAG`.
This net connects to the test point TP3 only. The microcontroller does not measure it.
The microcontroller measures VENV and EREF. The firmware calculates the envelope.
The report describes an RMS detector.
The envelope gives more detail for a pulsed MRI RF signal. Therefore this choice can be correct.
But the board and the report do not agree. Please confirm the intent.

### Q-05 — Does the firmware obey the memory refresh limit?
The APS6404L has a maximum chip select low time. The value is 8 µs for the standard grade.
The memory needs this time for the internal refresh.
The board uses this memory as the capture buffer.
A long DMA transfer with a continuous chip select causes data loss.
Does the firmware divide the transfer into blocks?

### Q-06 — Must the mounting holes connect to ground?
The holes H1 to H4 have no net.
If the enclosure is plastic, the design is correct. A free hole prevents a ground loop.
If the enclosure is metal, connect the holes to ground. This bonds the board to the enclosure.
The MRI requirement says non-ferrous material. Therefore the enclosure is probably plastic.
Please confirm the enclosure material.

### Q-07 — Is the capacitor C2 necessary?
C2 is a 100 pF capacitor on the FLT1 pin of U1.
The ADL5511 data sheet says that this capacitor decreases the internal 3.2 MHz corner frequency.
The data sheet says to use this capacitor for a carrier frequency below 32 MHz.
The carrier frequencies of this project are 64 MHz and 128 MHz. Both are above 32 MHz.
Therefore the capacitor is probably not necessary.
The value is small. The effect is probably small.
Did you add C2 for a reason?

---

## 10. CHECKS THAT THIS REVIEW DID NOT DO

This review has limits. Do these checks before manufacture.

1. **The KiCad Design Rule Check did not run.** This review read the files only.
   Run the DRC in KiCad. Correct all errors.
2. **The manufacture files are not present.** The folder has no Gerber files and no drill files.
   The folder has the placement files and the bill of material only.
   Make the Gerber files. Then examine the Gerber files in a viewer.
3. **The review did not look at the board.** The review read the file data only.
   Look at the 2D view and the 3D view in KiCad.
4. **The review did not check the silkscreen.** Make sure that no text is on a pad.
   Make sure that each reference designator is legible.
5. **The review did not check the courtyard overlap.** An automatic check gave 15 results.
   All 15 results are near the long connectors J5 and J6. These results are probably false.
   Use the KiCad courtyard check.
6. **The review did not check the clearance between tracks.** Use the DRC.
7. **The review did not read the firmware.** The folder `Software` holds an STM32CubeIDE project.
   Q-01 and Q-05 need an examination of the firmware.
8. **The review did not calculate the power budget.** The report gives an 8 hour requirement.
   The STM32H743 uses much more power than the STM32L476 in the report.
   Calculate the current of each rail. Then calculate the battery life.

---

## 11. RECOMMENDED SEQUENCE OF WORK

1. Correct F-01 and F-02. Select the regulator variant. Change the symbol.
2. Answer Q-01. This tells you if the filter design is correct.
3. Correct F-03 and F-04 together. One change in the attenuator corrects both.
4. Correct F-05, F-06, and F-07. These are small layout changes.
5. Correct F-08 and F-09. Add the vias.
6. Define the stackup. This is F-10.
7. Run the KiCad DRC. Correct all errors.
8. Make the Gerber files. Examine the Gerber files.
9. Calculate the power budget.

---

## 12. DOCUMENT DATA

| Item | Value |
|---|---|
| Reviewed files | 10 schematic files, 1 PCB file, 3 manufacture files, 1 symbol library |
| PCB file size | 3 225 198 bytes |
| Netlist source | The PCB file. 158 nets. 189 components. |
| Components examined | 189 |
| Data sheets read | 14 |
| Findings | 2 Category 1, 8 Category 2, 6 Category 3, 7 Questions |

**End of document.**
