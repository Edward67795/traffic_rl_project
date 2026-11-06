#!/usr/bin/env python3
"""Extract the agent's action sequence (and any nondet parameters) from an ESBMC counterexample.

ESBMC prints a counterexample as numbered "State" blocks; every assignment to the harness
variable `a` is one decision step. Parameters chosen by choose_int() in parametric harnesses
(d, y, mn, mx) are reported too.

Usage:
    python verification/esbmc/scripts/ce_to_actions.py verification/esbmc/results/raw/G2-v0.txt
"""
import json
import re
import sys

ASSIGN = re.compile(r"^\s*(?:[\w@!$.#]*::)?(?P<name>a|d|y|mn|mx)\s*=\s*(?P<val>-?\d+)\b", re.M)


def parse(text: str) -> dict:
    start = text.find("[Counterexample]")
    body = text[start:] if start >= 0 else text
    actions, params = [], {}
    for m in ASSIGN.finditer(body):
        name, val = m.group("name"), int(m.group("val"))
        if name == "a":
            actions.append(val)
        else:
            params.setdefault(name, val)
    return {"actions": actions, "params": params}


def actions_from_file(path: str) -> list:
    return parse(open(path).read())["actions"]


if __name__ == "__main__":
    result = parse(open(sys.argv[1]).read())
    print(json.dumps(result))
    print("replay with: python verification/common/replay_in_sumo.py --actions "
          + ",".join(str(a) for a in result["actions"]))
