#!/usr/bin/env python3
"""E11: how ESBMC's run time grows with the bound K, the parameter ranges and the solver.

Each run is built and classified exactly like run_esbmc.py does it, but rows go to
results/scaling.csv instead of results.csv, so the main results table stays clean.

Usage (from the repo root, venv active):
    python verification/esbmc/scripts/scaling_sweep.py --exp K        # bound K = 4..24
    python verification/esbmc/scripts/scaling_sweep.py --exp param    # wider max_green range
    python verification/esbmc/scripts/scaling_sweep.py --exp solver   # every solver this esbmc has
    python verification/esbmc/scripts/scaling_sweep.py --exp K --ks 4 8 12   # quick check
    python verification/esbmc/scripts/scaling_sweep.py --plot         # figure from scaling.csv

--plot needs matplotlib (pip install matplotlib) and writes results/fig_scaling_K.png.
"""
import argparse
import csv
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_esbmc as R  # noqa: E402

OUT = R.RESULTS / "scaling.csv"
HEADER = ["experiment", "harness", "version", "sets", "K", "solver", "result",
          "time_s", "memory_mb", "vccs"]

# (label, harness, version, fixed overrides). PASS cases are the expensive ones:
# ESBMC has to show that no execution of length K violates the property.
K_CASES = [
    ("G2-v1", "h_G2", "v1", {"STATIC_PROGRAM": "True"}),
    ("L1-v1", "h_L1", "v1", {"STATIC_PROGRAM": "True"}),
    ("G2-v0-L1", "h_G2", "v0", {"STATIC_PROGRAM": "True"}),   # FAIL case for contrast
]
SOLVERS = ["z3", "bitwuzla", "boolector", "yices", "cvc5", "mathsat"]


def vcc_count(out: str) -> str:
    m = re.search(r"Generated \d+ VCC\(s\), (\d+) remaining", out)
    return m.group(1) if m else ""          # VCCs left after simplification


def solver_available(esbmc: str, solver: str) -> bool:
    probe = R.BUILD / "solver_probe.py"
    R.BUILD.mkdir(parents=True, exist_ok=True)
    probe.write_text("x: int = nondet_int()\n__ESBMC_assume(x > 0 and x < 10)\nassert x < 10\n")
    out, _, _, _ = R.run_esbmc(esbmc, probe, [f"--{solver}"], 60)
    return "has not been built" not in out and "VERIFICATION SUCCESSFUL" in out


def one_run(esbmc, exp, label, harness, version, sets, solver, timeout):
    tag = f"scal-{exp}-{label}-" + "-".join(f"{k}{v}" for k, v in sets.items() if k != "STATIC_PROGRAM")
    tag = re.sub(r"[^\w.-]", "_", tag) + (f"-{solver}" if solver else "")
    path = R.build(harness, version, sets, tag)
    extra = [R.AUTO] + ([f"--{solver}"] if solver else [])
    out, elapsed, meta, timed_out = R.run_esbmc(esbmc, path, extra, timeout)
    R.RAW.mkdir(parents=True, exist_ok=True)
    (R.RAW / f"{tag}.txt").write_text(out)
    result = R.classify_result(out, timed_out)
    k = R.harness_param(path.read_text(), "K", 16)
    row = [exp, harness, version, ";".join(f"{a}={b}" for a, b in sets.items()), k,
           solver or "default", result, f"{elapsed:.2f}",
           "" if meta.get("rss_mb") is None else f"{meta['rss_mb']:.0f}", vcc_count(out)]
    new = not OUT.exists()
    with OUT.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(HEADER)
        w.writerow(row)
    print(f"{exp:6s} {label:9s} K={k:<3d} {solver or 'default':9s} {result:8s} {elapsed:8.2f}s "
          f"{row[8]:>5s} MB  vccs={row[9]}")
    return result


def plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = [r for r in csv.DictReader(OUT.open()) if r["experiment"] == "K" and r["result"] != "TIMEOUT"]

    def key(r):  # one line per harness/version/stub, whatever K is
        return r["harness"], r["version"], re.sub(r"(^|;)K=\d+", "", r["sets"]).strip(";")

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for g in sorted({key(r) for r in rows}):
        pts = sorted((int(r["K"]), float(r["time_s"]), r["result"]) for r in rows if key(r) == g)
        name = f"{g[0][2:]}-{g[1]}" + (" (L1 stub)" if "STATIC_PROGRAM=True" in g[2] else "")
        line, = ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", label=name)
        fails = [p for p in pts if p[2] == "FAIL"]
        if fails:  # a counterexample was found at this bound
            ax.scatter([p[0] for p in fails], [p[1] for p in fails], marker="x", s=70,
                       color="black", zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(sorted({int(r["K"]) for r in rows}))
    ax.set_xlabel("bound K (decision steps)")
    ax.set_ylabel("ESBMC time (s, log scale)")
    ax.grid(alpha=0.3, which="both")
    ax.legend(title="x = counterexample found", frameon=False)
    fig.tight_layout()
    out = R.RESULTS / "fig_scaling_K.png"
    fig.savefig(out, dpi=200)
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exp", choices=["K", "param", "solver"])
    ap.add_argument("--ks", type=int, nargs="*", default=[4, 8, 12, 16, 20, 24])
    ap.add_argument("--max-his", type=int, nargs="*", default=[16, 20, 24])
    ap.add_argument("--esbmc", default=shutil.which("esbmc") or "esbmc")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()
    if args.plot:
        plot()
        return
    if args.exp == "K":
        for label, harness, version, fixed in K_CASES:
            for k in args.ks:
                r = one_run(args.esbmc, "K", label, harness, version, {**fixed, "K": str(k)}, "", args.timeout)
                if r == "TIMEOUT":
                    break                       # larger K will time out too
    elif args.exp == "param":
        # widen the max_green range of h_G2_param; K must exceed MAX_HI so that d=1 can run past max
        for hi in args.max_his:
            sets = {"MAX_HI": str(hi), "K": str(hi + 4)}
            for version in ["v1naive", "v1"]:
                one_run(args.esbmc, "param", f"G2param-{version}", "h_G2_param", version, sets, "", args.timeout)
    elif args.exp == "solver":
        avail = [s for s in SOLVERS if solver_available(args.esbmc, s)]
        print("solvers built into this esbmc:", ", ".join(avail))
        for label, harness, version, fixed in K_CASES[:2]:
            for s in avail:
                one_run(args.esbmc, "solver", label, harness, version, {**fixed, "K": "16"}, s, args.timeout)
    else:
        ap.error("give --exp K|param|solver or --plot")


if __name__ == "__main__":
    main()
