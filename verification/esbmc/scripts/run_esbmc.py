#!/usr/bin/env python3
"""Build ESBMC harnesses and run them; append one row per run to results/results.csv.

A harness is verified on one concatenated file:
    model/traci_stub.py + model/env_core_<version>.py + harnesses/<harness>.py
(so ESBMC never has to resolve imports). Built files go to verification/esbmc/build/.

Usage (from the repo root, venv active):
    python verification/esbmc/scripts/run_esbmc.py --list            # show the suite
    python verification/esbmc/scripts/run_esbmc.py G2-v0 T1-v0-y0    # run suite entries
    python verification/esbmc/scripts/run_esbmc.py --all             # whole suite
    python verification/esbmc/scripts/run_esbmc.py --harness h_G2 --version v0 \
        --set K=20 --set MAX_GREEN=40 -- --unwind 22                 # ad-hoc run
Options: --esbmc PATH (default: esbmc on PATH), --timeout SECONDS (default 900).
"""
import argparse
import csv
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ESBMC_DIR = Path(__file__).resolve().parents[1]
MODEL = ESBMC_DIR / "model"
HARNESSES = ESBMC_DIR / "harnesses"
BUILD = ESBMC_DIR / "build"
RESULTS = ESBMC_DIR / "results"
RAW = RESULTS / "raw"
CSV_PATH = RESULTS / "results.csv"
CSV_HEADER = ["tool", "property", "version", "config", "bound", "result",
              "ce_length", "time_s", "memory_mb", "notes"]

AUTO = "@auto"  # in a suite entry's ESBMC args: compute per-loop bounds from --show-loops
# Python objects become structs; without flattening, Z3 needs minutes for a 4-step harness.
DEFAULT_ARGS = ["--tuple-node-flattener"]

VERSIONS = {
    "v0": "env_core_v0.py",
    "v1": "env_core_v1.py",
    "v1naive": "env_core_v1_naive.py",
}


# (id, property, harness, version, {NAME: value}, extra ESBMC args, expected result)
# "@auto" = per-loop unwind bounds computed by auto_unwind(). Entries whose id ends in
# "-str" run on the verbatim string model (no int abstraction).
SUITE = [
    # ---- lemma for the int abstraction (string-level, verbatim model) ----
    ("S0-strings-str", "S0", "h_S0_strings", "v0", {}, [AUTO], "PASS"),
    # ---- v0, default parameters, L0 stub ----
    ("S1-v0", "S1", "h_S1", "v0", {}, [AUTO], "PASS"),
    ("T1-v0", "T1", "h_T1", "v0", {}, [AUTO], "PASS"),
    ("T1-v0-y0", "T1", "h_T1", "v0", {"YELLOW_TIME": "0"}, [AUTO], "FAIL"),
    ("T2-v0", "T2", "h_T2", "v0", {}, [AUTO], "PASS"),
    ("T2-v0-any", "T2", "h_T2", "v0", {"ANY_ACTION": "True"}, [AUTO], "FAIL"),
    ("G1-v0", "G1", "h_G1", "v0", {}, [AUTO], "PASS"),
    ("G2-v0", "G2", "h_G2", "v0", {}, [AUTO], "FAIL"),
    ("L1-v0", "L1", "h_L1", "v0", {}, [AUTO], "FAIL"),
    ("C1-v0", "C1", "h_C1", "v0", {}, [AUTO], "PASS"),
    ("C1-v0-any", "C1", "h_C1", "v0", {"ANY_ACTION": "True"}, [AUTO], "FAIL"),
    ("R1-v0", "R1", "h_R1", "v0", {}, [AUTO], "FAIL"),
    ("P1-v0", "P1", "h_P1", "v0", {}, [AUTO], "FAIL"),
    ("V0-cover-v0", "V0", "h_V0_cover", "v0", {}, [AUTO] + ["--multi-property", "--no-pointer-check"], "COVERED"),
    # ---- v0, L1 stub (SUMO static program modelled): E7 ----
    ("T2-v0-L1", "T2", "h_T2", "v0", {"STATIC_PROGRAM": "True"}, [AUTO], "FAIL"),
    ("G1-v0-L1", "G1", "h_G1", "v0", {"STATIC_PROGRAM": "True"}, [AUTO], "FAIL"),
    ("C1-v0-L1", "C1", "h_C1", "v0", {"STATIC_PROGRAM": "True"}, [AUTO], "FAIL"),
    ("G2-v0-L1", "G2", "h_G2", "v0", {"STATIC_PROGRAM": "True", "K": "20"}, [AUTO], "FAIL"),
    # ---- v1 (all four fixes), L1 stub: everything should hold ----
    ("S1-v1", "S1", "h_S1", "v1", {"STATIC_PROGRAM": "True"}, [AUTO], "PASS"),
    ("T1-v1", "T1", "h_T1", "v1", {"STATIC_PROGRAM": "True"}, [AUTO], "PASS"),
    ("T2-v1", "T2", "h_T2", "v1", {"STATIC_PROGRAM": "True"}, [AUTO], "PASS"),
    ("G1-v1", "G1", "h_G1", "v1", {"STATIC_PROGRAM": "True"}, [AUTO], "PASS"),
    ("G2-v1", "G2", "h_G2", "v1", {"STATIC_PROGRAM": "True"}, [AUTO], "PASS"),
    ("L1-v1", "L1", "h_L1", "v1", {"STATIC_PROGRAM": "True"}, [AUTO], "PASS"),
    ("C1-v1", "C1", "h_C1", "v1", {"STATIC_PROGRAM": "True"}, [AUTO], "PASS"),
    ("R1-v1", "R1", "h_R1", "v1", {}, [AUTO], "PASS"),
    ("P1-v1", "P1", "h_P1", "v1", {}, [AUTO], "PASS"),
    # ---- F5: parametric max-green ----
    ("G2param-v1naive", "G2", "h_G2_param", "v1naive", {}, [AUTO], "FAIL"),
    ("G2param-v1", "G2", "h_G2_param", "v1", {}, [AUTO], "PASS"),
    # ---- unbounded proof (induction written out; see h_G2_ind.py) ----
    ("G2ind-v0", "G2", "h_G2_ind", "v0", {}, [AUTO], "FAIL"),
    ("G2ind-v1", "G2", "h_G2_ind", "v1", {}, [AUTO], "PASS"),
]


# String -> int-code abstraction of the model (proved equivalent by h_S0_strings).
# Each `old` must occur in the model file, otherwise the build stops: if you edit the model,
# keep these lines or update this table and re-run S0.
INT_REWRITES = [
    ("self.phase_states: dict[int, str] = {0: PHASE_NS, 1: PHASE_EW}",
     "self.phase_states: int = 0  # int abstraction: the dict is replaced by phase_code()"),
    ("if phase in self.phase_states:",
     "if phase == 0 or phase == 1:"),
    ("traci.trafficlight.setRedYellowGreenState(self.tls_id, self.phase_states[phase])",
     "traci.trafficlight.setCode(self.tls_id, phase_code(phase))"),
    ("traci.trafficlight.setRedYellowGreenState(self.tls_id, self.phase_states[0])",
     "traci.trafficlight.setCode(self.tls_id, C_NS)"),
    ("current_state: str = traci.trafficlight.getRedYellowGreenState(self.tls_id)",
     "current_state: int = traci.trafficlight.getCode(self.tls_id)"),
    ("yellow_state: str = current_state.replace('G', 'y').replace('g', 'y')",
     "yellow_state: int = yellow_of(current_state)"),
    ("traci.trafficlight.setRedYellowGreenState(self.tls_id, yellow_state)",
     "traci.trafficlight.setCode(self.tls_id, yellow_state)"),
]


def abstract_model(src: str) -> str:
    for old, new in INT_REWRITES:
        if old not in src:
            sys.exit(f"int abstraction: expected line not found in the model:\n    {old}")
        src = src.replace(old, new)
    return src


def build(harness: str, version: str, sets: dict, tag: str, abstraction: str = "int") -> Path:
    """Concatenate stub + model + harness, applying NAME=VALUE overrides to the harness.
    abstraction="int": string lines of the model are rewritten to int codes (INT_REWRITES);
    abstraction="str": the model is used verbatim."""
    h = (HARNESSES / f"{harness}.py").read_text()
    for name, value in sets.items():
        pattern = re.compile(rf"^{re.escape(name)}(\s*:\s*\w+)?\s*=\s*[^#\n]*", re.M)
        if not pattern.search(h):
            sys.exit(f"--set {name}: no such parameter at the top of {harness}.py")
        h = pattern.sub(lambda m: f"{name}{m.group(1) or ''} = {value}", h, count=1)
    parts = [
        f"# built from model/traci_stub.py + model/{VERSIONS.get(version, version)} + harnesses/{harness}.py\n",
        f"# overrides: {json.dumps(sets)}   abstraction: {abstraction}\n",
        (MODEL / "traci_stub.py").read_text(),
        "\n\n# ---------------- model ----------------\n",
        (abstract_model if abstraction == "int" else (lambda x: x))((MODEL / VERSIONS.get(version, version)).read_text()),
        "\n\n# ---------------- harness ----------------\n",
        h,
    ]
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / f"{tag}.py"
    out.write_text("".join(parts))
    return out


def harness_param(src: str, name: str, default: int) -> int:
    m = re.search(rf"^{name}\s*(?::\s*\w+)?\s*=\s*(-?\d+)", src, re.M)
    return int(m.group(1)) if m else default


def auto_unwind(esbmc: str, path: Path) -> list:
    """Exact loop bounds (unwinding assertions stay on, so a bound that is too small
    shows up as a failed 'unwinding assertion', never as a silent PASS)."""
    src = path.read_text()
    k = harness_param(src, "K", 16)
    delta = max(harness_param(src, "DELTA_TIME", 5), harness_param(src, "D_HI", 0))
    yellow = harness_param(src, "YELLOW_TIME", 3)
    p = subprocess.run([esbmc, str(path), "--python", sys.executable, "--show-loops"],
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    pairs = []
    for m in re.finditer(r"goto-loop Loop (\d+) \(([^)]*)\)", out):
        n, name = m.group(1), m.group(2)
        if "@F@_apply_action" in name:
            b = yellow + 1
        elif "@F@reset" in name:
            b = 10 + 1                      # warmup_steps
        elif "@F@step" in name:
            b = delta + 1
        elif "@F@main" in name:
            b = k + 1
        elif "@F@phase_features" in name:
            b = 4
        else:
            b = 16                          # library loops; the longest string has 14 chars
        pairs.append(f"{n}:{b}")
    return ["--unwind", "16"] + (["--unwindset", ",".join(pairs)] if pairs else [])


def run_esbmc(esbmc: str, path: Path, extra: list, timeout: int):
    """Run ESBMC in a small wrapper process so that peak memory is measured per run."""
    wrapper = (
        "import resource, subprocess, sys, json\n"
        "p = subprocess.run(sys.argv[1:], capture_output=True, text=True)\n"
        "rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss\n"
        "rss_mb = rss / (1024 * 1024) if sys.platform == 'darwin' else rss / 1024\n"
        "sys.stdout.write(p.stdout + p.stderr)\n"
        "sys.stdout.write('\\n@@RUN ' + json.dumps({'rc': p.returncode, 'rss_mb': rss_mb}) + '\\n')\n"
    )
    if AUTO in extra:
        extra = [x for x in extra if x != AUTO] + auto_unwind(esbmc, path)
    cmd = [sys.executable, "-c", wrapper, esbmc, str(path), "--python", sys.executable] + DEFAULT_ARGS + extra
    t0 = time.time()
    # The wrapper and the esbmc it starts share a new process group, so a timeout kills both
    # (killing only the wrapper would leave the solver running in the background).
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         start_new_session=True)
    try:
        so, se = p.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        so, se = p.communicate()
        timed_out = True
    out = (so or "") + (se or "")
    elapsed = time.time() - t0
    m = re.search(r"@@RUN (\{.*\})", out)
    meta = json.loads(m.group(1)) if m else {"rc": None, "rss_mb": None}
    return out, elapsed, meta, timed_out


ACTION_RE = re.compile(r"^\s*(?:[\w@!$.]*::)?a\s*=\s*(-?\d+)", re.M)


def classify_result(out: str, timed_out: bool) -> str:
    if timed_out:
        return "TIMEOUT"
    if "VERIFICATION SUCCESSFUL" in out:
        return "PASS"
    if "VERIFICATION FAILED" in out:
        return "FAIL"
    if "VERIFICATION UNKNOWN" in out:
        return "UNKNOWN"
    return "ERROR"


def violated_property(out: str) -> str:
    m = re.search(r"Violated property:\s*\n(.*\n){0,3}", out)
    return " ".join(m.group(0).split()) if m else ""


def esbmc_version(out: str) -> str:
    """Version from ESBMC's banner, e.g. 'ESBMC version 8.6.0 64-bit aarch64 macos' -> '8.6.0'."""
    m = re.search(r"^ESBMC version (\S+)", out, re.M)
    return m.group(1) if m else "n/a"


def solvers_used(out: str) -> str:
    """Solver(s) this run actually called, from 'Solving with solver Bitwuzla 0.9.1' lines.
    'n/a' when ESBMC never reached the solver (timeout, frontend error, no VCCs left)."""
    names = dict.fromkeys(re.findall(r"^Solving with solver (.+?)\s*$", out, re.M))
    return " + ".join(names) or "n/a"


def append_csv(row: list):
    RESULTS.mkdir(parents=True, exist_ok=True)
    new = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CSV_HEADER)
        w.writerow(row)


def config_string(sets: dict) -> str:
    base = {"DELTA_TIME": "5", "YELLOW_TIME": "3", "MIN_GREEN": "10", "MAX_GREEN": "60"}
    base.update({k: v for k, v in sets.items() if k in base})
    s = f"d{base['DELTA_TIME']}-y{base['YELLOW_TIME']}-min{base['MIN_GREEN']}-max{base['MAX_GREEN']}"
    flags = [f"{k}={v}" for k, v in sets.items() if k not in base]
    return s + ("" if not flags else ";" + ";".join(flags))


def run_entry(esbmc, entry, timeout):
    tag, prop, harness, version, sets, extra, expected = entry
    path = build(harness, version, sets, tag, "str" if tag.endswith("-str") else "int")
    out, elapsed, meta, timed_out = run_esbmc(esbmc, path, extra, timeout)
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{tag}.txt").write_text(out)
    result = classify_result(out, timed_out)
    if expected == "COVERED":
        # with --multi-property a reachable __ESBMC_cover is reported as a failed property
        m = re.search(r"\*\* (\d+) of (\d+) properties failed", out)
        n_covers = path.read_text().count("__ESBMC_cover(")
        result = "COVERED" if (m and int(m.group(1)) == n_covers) else "NOT-COVERED"
    ce_len = len(ACTION_RE.findall(out[out.find("[Counterexample]"):])) if result == "FAIL" else ""
    bound = "k-induction" if "--k-induction" in extra else (
        f"K={harness_param(path.read_text(), 'K', 16)}" if AUTO in extra else " ".join(extra))
    note = violated_property(out) if result == "FAIL" else ""
    ok = "adhoc" if expected == "?" else ("ok" if result == expected else f"EXPECTED {expected}")
    # notes = "<tag>; <ok>[; <violated property>]; esbmc <version>; solver <solver>".
    # results_table.py reads the first two fields. Only the property text is cut to stay
    # within 300 characters, so the version and solver are always kept.
    tool = f"esbmc {esbmc_version(out)}; solver {solvers_used(out)}"
    head = "; ".join(x for x in (tag, ok, note) if x)
    notes = head[:300 - len(tool) - 2] + "; " + tool
    append_csv(["esbmc", prop, version, config_string(sets), bound, result, ce_len,
                f"{elapsed:.2f}", "" if meta.get("rss_mb") is None else f"{meta['rss_mb']:.0f}",
                notes])
    print(f"{tag:18s} {result:8s} ({ok}) {elapsed:7.2f}s  ce_len={ce_len}  raw=results/raw/{tag}.txt")
    return result == expected


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="suite entry ids to run")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--harness")
    ap.add_argument("--version", default="v0",
                    help="v0 | v1 | v1naive, or a file name inside model/ (e.g. env_core_llm1.py)")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    ap.add_argument("--esbmc", default=shutil.which("esbmc") or "esbmc")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("extra", nargs=argparse.REMAINDER, help="after --: extra ESBMC arguments")
    args = ap.parse_args()

    if args.list:
        for e in SUITE:
            print(f"{e[0]:18s} {e[1]:3s} {e[2]:12s} {e[3]:8s} {json.dumps(e[4]):28s} {' '.join(e[5]):32s} expect {e[6]}")
        return
    entries = []
    if args.harness:
        sets = dict(s.split("=", 1) for s in args.set)
        extra = [x for x in args.extra if x != "--"]
        if not any(x.startswith("--unwind") or x == "--k-induction" for x in extra):
            extra = [AUTO] + extra          # e.g. `-- --z3` keeps the automatic loop bounds
        tag = f"{args.harness}-{Path(args.version).stem}-adhoc"
        entries.append((tag, args.harness.split("_")[1], args.harness, args.version, sets, extra, "?"))
    elif args.all:
        entries = SUITE
    else:
        by_id = {e[0]: e for e in SUITE}
        unknown = [i for i in args.ids if i not in by_id]
        if unknown or not args.ids:
            sys.exit(f"unknown or missing ids: {unknown}; use --list")
        entries = [by_id[i] for i in args.ids]
    ok = all([run_entry(args.esbmc, e, args.timeout) for e in entries])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
