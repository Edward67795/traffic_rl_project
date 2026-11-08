#!/usr/bin/env python3
"""Conformance test: does the verification model behave like the real environment?

Feeds the same random action sequences to
  (1) the real SumoTrafficEnv of the same version on real SUMO (verification/common/sumo_env.py:
      v0 = src/environment.py as checked out, v1 = a temporary copy with v1_fix.patch applied), and
  (2) the model: model/env_core_<version>.py on top of model/traci_stub.py (level L0 or L1),
and compares, after every simulated second, the signal state SUMO shows with the stub's,
and after every decision step (current_phase, phase_duration, current_step).

Usage (repo root, venv active, SUMO_HOME set):
    python verification/esbmc/scripts/conformance_test.py --model v0 --level L0 --runs 100
    python verification/esbmc/scripts/conformance_test.py --model v0 --level L1 --runs 100
    python verification/esbmc/scripts/conformance_test.py --model v1 --level L1 --runs 30
Expected for v0: L0 diverges on runs that keep phase 0 past t=42 s; L1 never diverges.
Expected for v1: L1 never diverges.
"""
import argparse
import contextlib
import io
import os
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MODEL = REPO / "verification" / "esbmc" / "model"
VERSIONS = {"v0": "env_core_v0.py", "v1": "env_core_v1.py"}
sys.path.insert(0, str(REPO / "verification" / "common"))
from sumo_env import load_sumo_env  # noqa: E402


def run_real(SumoTrafficEnv, actions, params):
    import traci
    seconds, decisions = [], []
    real_step = traci.simulationStep

    def logged(*a, **k):
        r = real_step(*a, **k)
        seconds.append(traci.trafficlight.getRedYellowGreenState("center"))
        return r

    traci.simulationStep = logged
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            env = SumoTrafficEnv("networks/single_intersection.net.xml", "scenarios/off_peak.rou.xml", **params)
            env.reset(seed=0)
            for a in actions:
                env.step(a)
                decisions.append((env.current_phase, env.phase_duration, env.current_step))
            env.close()
    finally:
        traci.simulationStep = real_step
    return seconds, decisions


def run_model(actions, params, version, level):
    ns = {"nondet_int": lambda: 0, "__ESBMC_assume": lambda c: None}
    code = (MODEL / "traci_stub.py").read_text() + "\n" + (MODEL / VERSIONS[version]).read_text()
    exec(compile(code, "model", "exec"), ns)
    stub = ns["traci"]
    ns["STATIC_PROGRAM"] = (level == "L1")
    seconds, decisions = [], []
    model_step = stub.simulationStep

    def logged():
        model_step()
        seconds.append(stub.trafficlight.getRedYellowGreenState("center"))

    stub.simulationStep = logged
    env = ns["SumoTrafficEnvCore"](params["delta_time"], params["yellow_time"], params["min_green"],
                                   params["max_green"], 3600)
    with contextlib.redirect_stdout(io.StringIO()):
        env.reset()
        for a in actions:
            env.step(a)
            decisions.append((env.current_phase, env.phase_duration, env.current_step))
    return seconds, decisions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="v0", choices=sorted(VERSIONS))
    ap.add_argument("--level", default="L0", choices=["L0", "L1"])
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    os.chdir(REPO)
    real_env = load_sumo_env(args.model)        # SUMO side runs the same version as the model
    params = dict(delta_time=5, yellow_time=3, min_green=10, max_green=60)
    rng = random.Random(args.seed)
    diverged = 0
    for run in range(args.runs):
        p_keep = rng.choice([0.5, 0.8, 0.95])     # vary how "sticky" the agent is
        actions, cur = [], 0
        for _ in range(args.steps):
            cur = cur if rng.random() < p_keep else 1 - cur
            actions.append(cur)
        rs, rd = run_real(real_env, actions, params)
        ms, md = run_model(actions, params, args.model, args.level)
        mismatch = next((i for i, (x, y) in enumerate(zip(rs, ms)) if x != y), None)
        if mismatch is None and len(rs) != len(ms):
            mismatch = min(len(rs), len(ms))
        dmis = next((i for i, (x, y) in enumerate(zip(rd, md)) if x != y), None)
        if mismatch is not None or dmis is not None:
            diverged += 1
            if diverged <= 3:
                sec = "-" if mismatch is None else f"second {mismatch + 1}: SUMO {rs[mismatch] if mismatch < len(rs) else '<end>'} vs model {ms[mismatch] if mismatch < len(ms) else '<end>'}"
                print(f"run {run}: diverges at {sec}; first decision mismatch at step {dmis}")
    print(f"{args.model}/{args.level}: {diverged} of {args.runs} runs diverge from SUMO")
    return 0 if diverged == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
