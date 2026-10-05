#!/bin/bash
# run_post.sh IN TAG : post-route EMC + track economy pipeline on a scratch board
#   gndvip (in-pad, then ring) -> retvia (R17 return vias) -> restitch (stitching field) -> trackq --fix (dogleg)
#   -> unconn/openregion -> sign-off DRC summary
G="$(cd "$(dirname "$0")" && pwd)"
T="C:/Users/gabor/Documents/RFVDProject_SeniorDsgn/RFVD_Authoritative/tools/layout"
PY="C:/Program Files/KiCad/10.0/bin/python.exe"
cd "$G"
IN=$1; TAG=$2
F() { grep -v "memory leak\|image handler"; }
"$PY" "$T/gndvip.py" "$IN" r26/${TAG}_a.kicad_pcb 2>&1 | F | tail -1 | cut -c1-90
"$PY" "$T/gndvip.py" r26/${TAG}_a.kicad_pcb r26/${TAG}_b.kicad_pcb --ring 2>&1 | F | tail -1 | cut -c1-90
"$PY" retvia.py r26/${TAG}_b.kicad_pcb r26/${TAG}_c.kicad_pcb 2>&1 | F | tail -2
"$PY" restitch.py r26/${TAG}_c.kicad_pcb r26/${TAG}_d.kicad_pcb --dmin 2.5 --grid 0.25 2>&1 | F | tail -2
"$PY" trackq.py r26/${TAG}_d.kicad_pcb r26/${TAG}_e.kicad_pcb --fix --report r26/${TAG}_tq.json --top 5 2>&1 | F | tail -3
"$PY" unconn.py r26/${TAG}_e.kicad_pcb r26/${TAG}_e_open.json 2>&1 | F | tail -1
"$PY" place/openregion.py r26/${TAG}_e.kicad_pcb r26/${TAG}_e_open.json 2>&1 | F | head -1
python drcsum.py r26/${TAG}_e.kicad_pcb r26/drc_${TAG}_e 2>&1 | tail -25
