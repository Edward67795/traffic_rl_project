#!/usr/bin/env python3
"""Run an ESBMC harness under plain CPython with random choices (a random-testing baseline).

Builds the same concatenated file as run_esbmc.py, then replaces the ESBMC intrinsics:
    choose_int(lo, hi) -> random.randint(lo, hi)
    __ESBMC_assume(c) -> skip the trial when c is false
    __ESBMC_cover(c)  -> counted
and runs main() many times. Prints the first property violation with its choice sequence.

Usage:
    python verification/esbmc/scripts/py_sim.py h_G2 --version v0 --trials 20000 --seed 1
    python verification/esbmc/scripts/py_sim.py h_T1 --set YELLOW_TIME=0
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_esbmc import build, VERSIONS  # noqa: E402


class Reject(Exception):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("harness")
    ap.add_argument("--version", default="v0", help="v0 | v1 | v1naive, or a file name inside model/")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    ap.add_argument("--trials", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    sets = dict(s.split("=", 1) for s in args.set)
    path = build(args.harness, args.version, sets, f"{args.harness}-{Path(args.version).stem}-pysim")
    src = path.read_text()
    lines = src.rstrip().splitlines()
    assert lines[-1].strip() == "main()", "harness must end with a call to main()"
    code = compile("\n".join(lines[:-1]) + "\n", str(path), "exec")

    rng = random.Random(args.seed)
    choices = []

    def choose_int(lo, hi):
        v = rng.randint(lo, hi)
        choices.append(v)
        return v

    def assume(c):
        if not c:
            raise Reject()

    hits = {}
    for trial in range(1, args.trials + 1):
        ns = {"__name__": "__harness__", "nondet_int": lambda: rng.randint(-10**6, 10**6),
              "__ESBMC_assume": assume}
        cover_idx = [0]

        def esbmc_cover(c, _idx=cover_idx):
            _idx[0] += 1
            if c:
                hits[_idx[0]] = hits.get(_idx[0], 0) + 1
        ns["__ESBMC_cover"] = esbmc_cover
        exec(code, ns)
        ns["choose_int"] = choose_int          # override the ESBMC version from traci_stub.py
        choices.clear()
        try:
            ns["main"]()
        except Reject:
            continue
        except (AssertionError, ZeroDivisionError, ValueError, IndexError, KeyError) as e:
            print(f"VIOLATION after {trial} trials: {type(e).__name__}: {e}")
            print(f"choices (in call order): {choices}")
            return 1
    print(f"no violation in {args.trials} random trials")
    if hits:
        print("cover hits:", dict(sorted(hits.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
