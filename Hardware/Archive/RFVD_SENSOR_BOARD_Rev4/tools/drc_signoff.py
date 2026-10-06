"""Sign-off DRC for the RFVD SENSOR-D board: runs the full rule set, including the '#SIGNOFF' rules.

Why: RFVD_SENSOR_BOARD.kicad_dru keeps its large-clearance rules (BUCK_SYNC: 5 mm to RF, 5 mm to the board edge,
3 mm to the LSE crystal nets) commented out with a '#SIGNOFF ' prefix, because KiCad sizes the interactive router's
obstacle search by the largest clearance in any rule and those rules made hand routing crawl. This script strips the
prefix on a scratch copy (the rules sit at their original positions, so precedence is unchanged), appends a sentinel
rule that must fire (kicad-cli silently ignores a rules file it cannot parse), runs kicad-cli DRC and reports every
violation of a '#SIGNOFF' rule. The project folder is only read.

usage:  python drc_signoff.py [--board-dir DIR] [--out DIR] [--no-refill]
        (KiCad's own python works: "C:/Program Files/KiCad/10.0/bin/python.exe" drc_signoff.py)
exit:   0 = no sign-off errors (warnings are listed), 1 = sign-off errors found, 2 = could not check
env:    KICAD_CLI = path to kicad-cli if it is not in the default KiCad 10 folder or on PATH
"""
import argparse
import collections
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

PREFIX = "#SIGNOFF "
SENTINEL = "zz_signoff_sentinel_rules_loaded"
# The sentinel proves kicad-cli loaded the rules file. It is an assertion on footprint H1, which competes with no other
# constraint. (Until 2026-10-04 it was a hole_size rule on every via/pad; being last, it overrode all real drill rules
# and hid drill errors - critique RULES-05, shown with a planted 0.15 mm drill.)
SENTINEL_RULE = """
(rule "%s"
   (condition "A.Type == 'Footprint' && A.Reference == 'H1'")
   (constraint assertion "A.Reference == 'NOPE'")
   (severity warning))
""" % SENTINEL


def kicad_cli():
    for c in (os.environ.get("KICAD_CLI"), r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe", shutil.which("kicad-cli")):
        if c and os.path.isfile(c):
            return c
    sys.exit("ERROR: kicad-cli not found (set KICAD_CLI)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--board-dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--out", help="folder for the scratch copy and drc_signoff.json (default: a new temp folder)")
    ap.add_argument("--no-refill", action="store_true", help="skip zone refill (faster, but zone clearances go stale)")
    a = ap.parse_args()

    pros = glob.glob(os.path.join(a.board_dir, "*.kicad_pro"))
    if len(pros) != 1:
        print("ERROR: expected one .kicad_pro in", a.board_dir); return 2
    name = os.path.splitext(os.path.basename(pros[0]))[0]
    dru = os.path.join(a.board_dir, name + ".kicad_dru")
    if not os.path.isfile(dru):
        print("ERROR: no", dru); return 2

    out = a.out or tempfile.mkdtemp(prefix="drc_signoff_")
    os.makedirs(out, exist_ok=True)
    for ext in (".kicad_pcb", ".kicad_pro"):
        shutil.copy(os.path.join(a.board_dir, name + ext), out)
    # project footprint library + table, so KiCad does not report the project footprints as missing (2026-10-04)
    for t in ("fp-lib-table", "sym-lib-table"):
        if os.path.isfile(os.path.join(a.board_dir, t)):
            shutil.copy(os.path.join(a.board_dir, t), out)
    if os.path.isdir(os.path.join(a.board_dir, "libraries")) and not os.path.isdir(os.path.join(out, "libraries")):
        shutil.copytree(os.path.join(a.board_dir, "libraries"), os.path.join(out, "libraries"),
                        ignore=shutil.ignore_patterns("3dmodels"))
    lines, names = [], []
    for line in open(dru, encoding="utf-8").read().split("\n"):
        if line.startswith(PREFIX) or line == PREFIX.rstrip():
            line = line[len(PREFIX):]
            m = re.match(r'\(rule\s+"?([^"\s)]+)', line)
            if m:
                names.append(m.group(1))
        lines.append(line)
    open(os.path.join(out, name + ".kicad_dru"), "w", encoding="utf-8", newline="\n").write(
        "\n".join(lines).rstrip("\n") + "\n" + SENTINEL_RULE)
    print("sign-off rules enabled:", ", ".join(names) if names else "(none found - checking the live rules only)")

    # --all-track-errors: by default KiCad reports one error per track and which one varies between runs
    cmd = [kicad_cli(), "pcb", "drc", "--severity-all", "--all-track-errors", "--format", "json", "--units", "mm",
           "-o", os.path.join(out, "drc_signoff.json")]
    if not a.no_refill:
        cmd.append("--refill-zones")
    t0 = time.perf_counter()
    subprocess.run(cmd + [os.path.join(out, name + ".kicad_pcb")], cwd=out, capture_output=True)
    try:
        rep = json.load(open(os.path.join(out, "drc_signoff.json"), encoding="utf-8"))
    except (OSError, ValueError) as e:
        print("ERROR: kicad-cli produced no report:", e); return 2
    print("DRC %.1f s%s, report: %s" % (time.perf_counter() - t0, "" if a.no_refill else " (zones refilled)",
                                        os.path.join(out, "drc_signoff.json")))

    viol = rep["violations"]
    sent = [v for v in viol if SENTINEL in v["description"]]
    if len(sent) != 1 or sent[0]["type"] != "assertion_failure":
        print("ERROR: expected exactly 1 sentinel assertion_failure on H1, got %d (rules file not loaded, or H1 renamed)"
              % len(sent))
        return 2
    viol = [v for v in viol if SENTINEL not in v["description"]]
    hits = [v for v in viol if any("rule '%s'" % n in v["description"] for n in names)]
    sev = collections.Counter(v["severity"] for v in viol)
    print("full DRC: %d errors, %d warnings, %d unconnected (all rules, sentinel removed)"
          % (sev["error"], sev["warning"], len(rep.get("unconnected_items", []))))
    for v in hits:
        where = "; ".join("%s @ (%.2f, %.2f)" % (i["description"], i["pos"]["x"], i["pos"]["y"]) for i in v["items"])
        print("  %-7s %s | %s" % (v["severity"].upper(), v["description"], where))
    errs = sum(1 for v in hits if v["severity"] == "error")
    print("SIGN-OFF %s: %d errors, %d warnings from the #SIGNOFF rules"
          % ("FAIL" if errs else "PASS", errs, len(hits) - errs))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
