#!/usr/bin/env python3
"""Replay an action sequence on the REAL SumoTrafficEnv and check every property on what
SUMO actually shows. --src v0 (default) runs src/environment.py as checked out; --src v1 runs
a temporary copy with verification/esbmc/model/v1_fix.patch applied (common/sumo_env.py;
src/ is never edited).

The per-second checks reuse the exact monitor code of verification/esbmc/model/traci_stub.py,
so "FAIL in ESBMC" and "FAIL in SUMO" mean the same thing.

Usage (repo root, venv active, SUMO_HOME set):
    python verification/common/replay_in_sumo.py --actions 1,0,0,0,0,0,0,0,0,0,0,0,0
    python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/G2-v0.txt
    python verification/common/replay_in_sumo.py --actions 1,0,1 --yellow-time 0
    python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/G2-v0.txt --src v1
Exit code 0 = the counterexample reproduces (at least one property fails), 1 = it does not.
A ValueError from v1 (a rejected parameter or action) is reported but is not a property failure.
"""
import argparse
import contextlib
import io
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STUB = REPO / "verification" / "esbmc" / "model" / "traci_stub.py"
sys.path.insert(0, str(REPO / "verification" / "common"))
sys.path.insert(0, str(REPO / "verification" / "esbmc" / "scripts"))
from sumo_env import load_sumo_env  # noqa: E402


MONITORED = ("S1", "T1", "T2", "G1", "G2", "L1")


def load_monitors(min_green, max_green, yellow_time):
    """One stub instance per property, each with only its own CHK_ flag on -- exactly like
    the ESBMC harnesses, so the first violation of one property cannot hide another."""
    monitors = {}
    for prop in MONITORED:
        ns = {"nondet_int": lambda: 0, "__ESBMC_assume": lambda c: None}
        exec(compile(STUB.read_text(), str(STUB), "exec"), ns)
        ns["CHK_" + prop] = True
        ns["MON_MIN_GREEN"], ns["MON_MAX_GREEN"], ns["MON_YELLOW"] = min_green, max_green, yellow_time
        monitors[prop] = (ns["TraciStub"](), ns["classify"])
    return monitors


def report(failures, target):
    """Print the first failure of each kind and the verdict; return the exit code."""
    seen = {}
    for t, msg in failures:
        seen.setdefault(msg.split(":")[0], (t, msg))
    for key, (t, msg) in seen.items():
        print(f"  t={t:.0f}s  {msg}")
    if target is None:
        ok = any(key != "ValueError" for key in seen)   # a rejected input is not a violation
        print("REPRODUCED in SUMO" if ok else "NOT reproduced: no property fails in SUMO")
    else:
        ok = target in seen
        print(f"{target} REPRODUCED in SUMO" if ok else
              f"{target} NOT reproduced in SUMO" + (f" (other violations: {', '.join(seen)})" if seen else ""))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--actions", help="comma-separated actions, e.g. 1,0,0")
    g.add_argument("--ce", help="ESBMC output file; actions are read from its counterexample")
    ap.add_argument("--delta-time", type=int, default=5)
    ap.add_argument("--yellow-time", type=int, default=3)
    ap.add_argument("--min-green", type=int, default=10)
    ap.add_argument("--max-green", type=int, default=60)
    ap.add_argument("--scenario", default="off_peak")
    ap.add_argument("--property", help="property id to look for (default: the one the CE violates)")
    ap.add_argument("--src", default="v0", choices=["v0", "v1"],
                    help="real environment: v0 = src/environment.py as checked out (default), "
                         "v1 = a temporary copy with v1_fix.patch applied")
    args = ap.parse_args()

    target = args.property
    if args.ce:
        from ce_to_actions import actions_from_file
        actions = actions_from_file(args.ce)
        if target is None:
            import re
            m = re.search(r"Violated property:(?:.*\n){1,4}?.*?\b([STGLCRP][0-9]):", open(args.ce).read())
            target = m.group(1) if m else None
    else:
        actions = [int(x) for x in args.actions.split(",") if x.strip()]
    print(f"replaying {len(actions)} actions: {actions}" + (f"   (looking for {target})" if target else "")
          + f"   [src {args.src}]")

    os.chdir(REPO)
    import traci
    SumoTrafficEnv = load_sumo_env(args.src)

    monitors = load_monitors(args.min_green, args.max_green, args.yellow_time)
    failed = set()
    failures = []
    real_step = traci.simulationStep

    def observed_step(*a, **k):
        # check the state shown during this second, exactly as the stub does
        state = traci.trafficlight.getRedYellowGreenState("center")
        for prop, (mon, classify) in monitors.items():
            if prop in failed:
                continue
            try:
                mon._monitor(classify(state))
            except AssertionError as e:
                failed.add(prop)
                failures.append((traci.simulation.getTime(), str(e)))
        return real_step(*a, **k)

    traci.simulationStep = observed_step
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            env = SumoTrafficEnv("networks/single_intersection.net.xml",
                                 f"scenarios/{args.scenario}.rou.xml",
                                 delta_time=args.delta_time, yellow_time=args.yellow_time,
                                 min_green=args.min_green, max_green=args.max_green)
    except ValueError as e:          # v1 rejects invalid parameters in __init__, before SUMO starts
        return report([(0.0, f"ValueError: {e}")], target)
    with contextlib.redirect_stdout(io.StringIO()):
        env.reset(seed=0)
    phase_ns, phase_ew = env.phase_states[0], env.phase_states[1]
    for i, a in enumerate(actions, 1):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                env.step(a)
        except ValueError as e:      # v1 rejects invalid actions
            failures.append((traci.simulation.getTime(), f"ValueError: {e}"))
            break
        shown = traci.trafficlight.getRedYellowGreenState("center")
        if env.phase_duration > env.max_green:
            failures.append((traci.simulation.getTime(), f"G2: phase_duration={env.phase_duration} after step {i}"))
        if env.current_phase not in (0, 1):
            failures.append((traci.simulation.getTime(), f"C1: current_phase={env.current_phase} after step {i}"))
        elif shown != (phase_ns if env.current_phase == 0 else phase_ew):
            failures.append((traci.simulation.getTime(), f"C1: controller phase {env.current_phase} but SUMO shows {shown} after step {i}"))
    env.close()
    return report(failures, target)


if __name__ == "__main__":
    sys.exit(main())
