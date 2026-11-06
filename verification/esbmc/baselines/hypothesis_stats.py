#!/usr/bin/env python3
"""How often does Hypothesis find each v0 bug? Runs the PBT suite under N seeds.

    python verification/esbmc/baselines/hypothesis_stats.py --seeds 10 --max-examples 200
Writes verification/esbmc/results/hypothesis_stats.csv (test, seeds, found, rate).
"""
import argparse
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = ["test_G2_max_green", "test_L1_no_starvation", "test_T2_static_program",
         "test_C1_any_action", "test_G2_parametric"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--max-examples", type=int, default=200)
    ap.add_argument("--model", default="v0")
    args = ap.parse_args()
    found = {t: 0 for t in TESTS}
    env = dict(os.environ, MODEL=args.model, MAX_EXAMPLES=str(args.max_examples))
    for seed in range(args.seeds):
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            f"--hypothesis-seed={seed}", str(HERE / "test_hypothesis.py")],
                           capture_output=True, text=True, env=env)
        for t in TESTS:
            if re.search(rf"FAILED .*::{t}\b", p.stdout):
                found[t] += 1
    out = HERE.parent / "results" / "hypothesis_stats.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["test", "model", "max_examples", "seeds", "bug_found", "rate"])
        for t in TESTS:
            w.writerow([t, args.model, args.max_examples, args.seeds, found[t], f"{found[t] / args.seeds:.2f}"])
            print(f"{t:26s} found in {found[t]:2d} of {args.seeds} seeds")
    print(f"written to {out}")


if __name__ == "__main__":
    main()
