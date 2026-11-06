#!/usr/bin/env python3
"""S1, part 2: the four signal states of the static program never give two conflicting links
priority green ('G') at the same time.

Part 1 of S1 (only these four states are ever shown) is checked by ESBMC in harnesses/h_S1.py.
This part is a fact about the network file, so it is checked once here, without ESBMC.

Conflicts come from the junction's <request foes="..."> bit strings (the rightmost character is
link 0). The script assumes that the traffic light's link index i is the junction's request
index i, which holds for this single-junction network (14 links, 14 requests). A 'G' facing a
'g' is reported but allowed: in SUMO, 'g' is a permissive green that must yield.

Usage (repo root):
    python verification/esbmc/scripts/check_phase_strings.py [networks/single_intersection.net.xml]
Exit code 0 = no G/G conflict.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
NET = REPO / "networks" / "single_intersection.net.xml"


def main():
    net = Path(sys.argv[1]) if len(sys.argv) > 1 else NET
    root = ET.parse(net).getroot()
    junction = root.find("junction[@id='center']")
    foes = {}
    for req in junction.findall("request"):
        i, bits = int(req.get("index")), req.get("foes")
        foes[i] = {j for j in range(len(bits)) if bits[len(bits) - 1 - j] == "1"}
    asym = [(i, j) for i in foes for j in foes[i] if i not in foes.get(j, set())]
    if asym:
        sys.exit(f"foes matrix is not symmetric, check the bit order: {asym[:5]}")
    n_tl = len(root.findall("connection[@tl='center']"))
    if n_tl != len(foes):
        sys.exit(f"{n_tl} traffic-light links but {len(foes)} requests: link index != request index")
    bad = 0
    for phase in root.find("tlLogic[@id='center']").findall("phase"):
        state = phase.get("state")
        gg = sorted((i, j) for i in foes for j in foes[i] if i < j and state[i] == "G" and state[j] == "G")
        gp = sorted((i, j) for i in foes for j in foes[i] if i < j and {state[i], state[j]} == {"G", "g"})
        bad += len(gg)
        print(f"{state}  G/G conflicts: {len(gg)} {gg}   G/g (permissive, allowed): {len(gp)} {gp}")
    print("S1 part 2:", "PASS" if bad == 0 else "FAIL")
    sys.exit(0 if bad == 0 else 1)


if __name__ == "__main__":
    main()
